package main

import (
	"log"      // Для вывода логов в консоль
	"net/http" // Для запуска HTTP-сервера и обработки запросов
	"sync"     // Для использования мьютекса
	"time"

	"github.com/gorilla/websocket" // Библиотека для работы с WebSocket-соединениями
)

// Packet — это структура, описывающая сообщение между клиентом и сервером
type Packet struct {
	Type  string   `json:"type"`           // Тип пакета: "msg" — сообщение, "users" — список пользователей
	From  string   `json:"from,omitempty"` // Отправитель (сервер подставляет сам при получении сообщения)
	To    string   `json:"to"`             // Получатель (обязательное поле для отправки сообщения)
	Text  string   `json:"text,omitempty"` // Текст сообщения (используется только при Type == "msg")
	Ts    int64    `json:"ts,omitempty"`
	Users []string `json:"users,omitempty"` // Список всех онлайн-пользователей (используется только при Type == "users")
}

// Глобальные переменные:
var (
	// clients — список всех подключённых пользователей:
	// ключ — имя пользователя, значение — WebSocket-соединение
	clients = map[string]*websocket.Conn{}

	// mu — мьютекс для безопасного доступа к clients из разных горутин
	mu sync.Mutex

	// broadcast — канал, в который попадают входящие сообщения от клиентов
	// router() слушает этот канал и рассылает сообщения адресатам
	broadcast = make(chan Packet, 1024)

	// upg — конфигурация WebSocket-апгрейда (разрешаем все входящие соединения)
	upg = websocket.Upgrader{
		CheckOrigin: func(*http.Request) bool {
			return true
		},
	}
)

func main() {
	// Инициализируем БД
	InitDB()
	defer CloseDB()

	// Устанавливаем обработчик для WebSocket-подключений по адресу /ws
	http.HandleFunc("/ws", handleWS)

	// Запускаем отдельную горутину для обработки всех входящих сообщений
	go router()

	// Печатаем в консоль, что сервер запущен
	log.Println("Tychagram server listening on :8080")

	// Запускаем HTTP-сервер на порту 8080 (будет обрабатывать входящие подключения)
	// log.Fatal завершит программу, если сервер не запустится или произойдёт ошибка
	log.Fatal(http.ListenAndServe(":8080", nil))
}

// handleWS обрабатывает новое подключение клиента по WebSocket
func handleWS(w http.ResponseWriter, r *http.Request) {
	// Получаем имя пользователя из URL-параметра ?user=
	user := r.URL.Query().Get("user")
	if user == "" {
		// Если имя не указано — возвращаем ошибку и выходим
		http.Error(w, "`user` param required", http.StatusBadRequest)
		return
	}

	// Обновляем соединение до WebSocket
	conn, err := upg.Upgrade(w, r, nil)
	if err != nil {
		log.Println("upgrade:", err)
		return
	}

	// Добавляем клиента в список и рассылаем обновлённый онлайн-лист
	mu.Lock()
	clients[user] = conn
	pushUsersLocked()
	mu.Unlock()

	// Когда клиент отключится — удалим его и снова обновим онлайн-лист
	defer func() {
		mu.Lock()
		delete(clients, user)
		pushUsersLocked()
		mu.Unlock()
		conn.Close()
	}()

	// Основной цикл чтения входящих сообщений от клиента
	for {
		var p Packet
		// Пытаемся прочитать JSON-пакет от клиента
		if err := conn.ReadJSON(&p); err != nil {
			break // соединение закрылось или произошла ошибка — выходим из цикла
		}

		// Обрабатываем только личные сообщения
		if p.Type == "msg" && p.To != "" && p.To != user {
			p.From = user // выставляем имя отправителя
			p.Ts = time.Now().UnixMilli()
			broadcast <- p // передаём сообщение в канал для пересылки
		}
	}
}

// router — постоянно слушает канал broadcast и рассылает сообщения:
// 1. получателю (To)
// 2. отправителю (From), чтобы он тоже увидел своё сообщение
func router() {
	for p := range broadcast {
		mu.Lock() // блокируем доступ к clients

		// Отправляем сообщение получателю, если он онлайн
		if dst, ok := clients[p.To]; ok {
			_ = dst.WriteJSON(p) // отправляем JSON-пакет
		}

		// Отправляем сообщение обратно отправителю (эхо),
		// если он не отправил его самому себе
		if src, ok := clients[p.From]; ok && p.From != p.To {
			_ = src.WriteJSON(p)
		}

		mu.Unlock() // разблокируем clients
	}
}

// pushUsersLocked отправляет всем пользователям обновлённый список онлайна
func pushUsersLocked() {
	// Собираем имена всех пользователей в отдельный список
	lst := make([]string, 0, len(clients))
	for u := range clients {
		lst = append(lst, u)
	}

	// Формируем пакет с типом "users" и этим списком
	p := Packet{Type: "users", Users: lst}

	// Отправляем этот пакет всем подключённым клиентам
	for _, c := range clients {
		_ = c.WriteJSON(p) // игнорируем ошибку при отправке
	}
}
