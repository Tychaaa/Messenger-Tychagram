package main

import (
	"context"  // Пакет для управления контекстом выполнения
	"log"      // Для логирования — вывода сообщений в консоль
	"net/http" // Для создания HTTP-сервера и обработки HTTP-запросов
	"sync"     // Для работы с синхронизацией (mutex)
	"time"     // Для работы со временем — временные метки, таймауты

	"github.com/gorilla/websocket" // Библиотека для работы с WebSocket-соединениями
)

// Packet — структура, описывающая формат сообщения,
// которое пересылается между сервером и клиентами через WebSocket.
type Packet struct {
	Type   string        `json:"type"`              // Тип пакета
	ChatID int64         `json:"chat_id,omitempty"` // ID чата (группового или личного)
	From   string        `json:"from,omitempty"`    // Имя отправителя (устанавливается сервером)
	To     string        `json:"to"`                // Имя получателя (обязательно для личных сообщений)
	Text   string        `json:"text,omitempty"`    // Текст сообщения (если Type == "msg")
	Ts     int64         `json:"ts,omitempty"`      // Временная метка в миллисекундах
	Chats  []ChatSummary `json:"chats,omitempty"`   // Используется при отправке списка чатов
}

// Глобальные переменные:
var (
	// clients — список всех подключённых по WebSocket пользователей:
	// Ключ — имя пользователя (username), значение — WebSocket-соединение.
	// Используется для отправки сообщений конкретным пользователям.
	clients = map[string]*websocket.Conn{}

	// mu — мьютекс (mutex) для защиты clients от одновременного доступа
	// из нескольких горутин. Без него возможны гонки данных
	mu sync.Mutex

	// broadcast — канал для входящих сообщений.
	// Клиенты отправляют пакеты в этот канал, а функция router()
	// забирает их и рассылает нужным адресатам.
	broadcast = make(chan Packet, 1024)

	// upg — конфигурация апгрейда HTTP-соединения до WebSocket.
	// CheckOrigin всегда возвращает true → разрешаем подключение с любого источника.
	// В реальных условиях стоит делать проверку (например, по токену).
	upg = websocket.Upgrader{
		CheckOrigin: func(*http.Request) bool {
			return true
		},
	}
)

func main() {
	// Инициализируем подключение к базе данных и пул соединений
	InitDB()
	// Закрываем пул соединений при завершении работы сервера
	defer CloseDB()

	// Регистрируем HTTP-обработчики для различных маршрутов:
	http.HandleFunc("/signup", signupHandler)                 // регистрация пользователя
	http.HandleFunc("/login", loginHandler)                   // вход пользователя
	http.HandleFunc("/users/search", searchUsersHandler)      // поиск пользователей
	http.HandleFunc("/chats/direct", createDirectChatHandler) // создание личного чата
	http.HandleFunc("/chats/group", createGroupChatHandler)   // создание группового чата
	http.HandleFunc("/ws", handleWS)                          // WebSocket-соединение

	// Запускаем отдельную горутину, которая будет слушать канал broadcast
	// и рассылать сообщения клиентам
	go router()

	// Выводим сообщение о запуске сервера в консоль
	log.Println("Tychagram server listening on :8080")

	// Запускаем HTTP-сервер на порту 8080.
	// log.Fatal завершит выполнение программы, если произойдёт ошибка запуска
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func sendChats(username string, ws *websocket.Conn) {
	/**
	Отправляет пользователю обновлённый список его чатов через WebSocket.

	Параметры:
	- username: имя пользователя, которому нужно отправить список;
	- ws: его WebSocket-соединение.

	Используется:
	- после входа в систему;
	- при создании нового чата;
	- при получении/отправке сообщения.
	*/

	ctx := context.Background()

	// Получаем список чатов пользователя из базы данных
	chats, err := GetUserChats(ctx, username)
	if err != nil {
		log.Printf("sendChats: cannot fetch chats for %s: %v", username, err)
		return // Если не удалось — просто выходим
	}

	// Формируем пакет с типом "chats" и прикреплённым списком чатов
	p := Packet{
		Type:  "chats",
		Chats: chats,
	}

	// Отправляем JSON-пакет через WebSocket
	_ = ws.WriteJSON(p)
}

func handleWS(w http.ResponseWriter, r *http.Request) {
	/**
	Обрабатывает подключение клиента по WebSocket:
	- проверяет токен авторизации;
	- апгрейдит соединение;
	- добавляет клиента в список;
	- слушает входящие сообщения и отправляет их в канал broadcast.
	*/

	// Получаем токен из строки запроса
	token := r.URL.Query().Get("token")
	if token == "" {
		http.Error(w, "token required", 400)
		return
	}

	// Проверяем токен: ищем соответствующего пользователя в сессиях
	var user string

	// Ищем имя пользователя (u.username), связанное с переданным токеном.
	// Условие: токен должен быть действующим.
	err := Pool.QueryRow(context.Background(),
		`SELECT u.username
           FROM sessions s JOIN users u ON u.id = s.user_id
          WHERE s.token=$1 AND s.expires_at > NOW()`, token).Scan(&user)
	if err != nil {
		http.Error(w, "invalid token", 401)
		return
	}

	// Преобразуем HTTP-соединение в WebSocket
	conn, err := upg.Upgrade(w, r, nil)
	if err != nil {
		log.Println("upgrade:", err)
		return
	}

	// Добавляем клиента в список подключённых пользователей
	mu.Lock()
	clients[user] = conn
	mu.Unlock()

	// Отправляем клиенту список всех его чатов
	sendChats(user, conn)

	// Параллельно отправляем клиенту историю сообщений
	go sendHistory(user, conn)

	// Когда соединение завершится — удалим клиента из списка и закроем соединение
	defer func() {
		mu.Lock()
		delete(clients, user)
		mu.Unlock()
		conn.Close()
	}()

	// === Цикл получения сообщений от клиента ===
	for {
		var p Packet

		// Ждём новое сообщение от клиента в формате JSON
		if err := conn.ReadJSON(&p); err != nil {
			break // соединение закрыто или произошла ошибка
		}

		// Обрабатываем только сообщения типа "msg"
		if p.Type == "msg" {
			p.From = user                 // Устанавливаем имя отправителя
			p.Ts = time.Now().UnixMilli() // Временная метка отправки
			broadcast <- p                // Отправляем сообщение в канал
		}
	}
}

func router() {
	/**
	Фоновая горутина, которая постоянно слушает канал broadcast и
	рассылает входящие сообщения нужным пользователям через WebSocket.

	Также сохраняет каждое сообщение в базу данных и обновляет списки чатов у участников.
	*/

	for p := range broadcast {
		// Сохраняем сообщение в базу данных (в зависимости от типа чата)
		if err := persistMsg(p); err != nil {
			log.Printf("router: persistMsg failed: %v", err)
		}

		mu.Lock() // Блокируем доступ к clients на время рассылки

		// === Групповое сообщение ===
		if p.ChatID != 0 {
			// Получаем список всех участников этого чата
			members, err := GetChatMembers(context.Background(), p.ChatID)
			if err != nil {
				log.Printf("router: GetChatMembers failed: %v", err)
			}

			// Рассылаем сообщение каждому участнику
			for _, uname := range members {
				if conn, ok := clients[uname]; ok {
					conn.WriteJSON(p)      // Отправляем сообщение
					sendChats(uname, conn) // Обновляем список чатов
				}
			}

			// === Личное сообщение ===
		} else {
			// Отправляем получателю
			if dst, ok := clients[p.To]; ok {
				dst.WriteJSON(p)
				sendChats(p.To, dst)
			}

			// Отправляем копию отправителю (чтобы он тоже увидел своё сообщение)
			if src, ok := clients[p.From]; ok {
				src.WriteJSON(p)
				sendChats(p.From, src)
			}
		}
		mu.Unlock() // Освобождаем мьютекс
	}
}
