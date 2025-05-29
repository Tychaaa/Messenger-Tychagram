package main

import (
	"github.com/gorilla/websocket"
	"net/http"
	"sync"
)

// Глобальные переменные:
var (
	// clients — список всех подключённых по WebSocket пользователей:
	// Ключ — имя пользователя (username), значение — WebSocket-соединение.
	clients = map[string]*websocket.Conn{}

	// mu — мьютекс (mutex) для защиты clients от одновременного доступа из нескольких горутин
	mu sync.Mutex

	// broadcast — канал для входящих сообщений.
	// Клиенты отправляют пакеты в этот канал, а функция router()
	// забирает их и рассылает нужным адресатам.
	broadcast = make(chan Packet, 1024)

	// upg — конфигурация апгрейда HTTP-соединения до WebSocket.
	upg = websocket.Upgrader{
		CheckOrigin: func(*http.Request) bool {
			return true
		},
	}
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

// loginReq — структура, описывающая тело запроса при попытке входа.
// Используется при JSON-декодировании входящих данных от клиента.
type loginReq struct {
	Username string `json:"username"` // Имя пользователя (логин)
	Password string `json:"password"` // Пароль (в открытом виде)
}

// loginResp — структура ответа, отправляемого клиенту при успешной авторизации.
type loginResp struct {
	Token    string `json:"token"`    // Уникальный токен сессии
	Username string `json:"username"` // Имя пользователя
}

// signReq — структура, описывающая JSON-запрос для регистрации пользователя
type signReq struct {
	Username  string `json:"username"`            // Уникальное имя пользователя (логин)
	FirstName string `json:"first_name"`          // Имя (обязательное)
	LastName  string `json:"last_name,omitempty"` // Фамилия (необязательная)
	Password  string `json:"password"`            // Пароль (в открытом виде)
}

// signResp — структура JSON-ответа, который сервер отправляет при успешной регистрации
type signResp struct {
	Token    string `json:"token"`    // Сгенерированный токен сессии
	Username string `json:"username"` // Имя пользователя, под которым зарегистрировались
}

// createGroupReq — структура запроса для создания группового чата.
// Используется при JSON-декодировании тела POST-запроса на /chats/group.
type createGroupReq struct {
	Title     string   `json:"title"`     // Название группы (обязательное поле)
	Usernames []string `json:"usernames"` // Список участников (username'ы), которых нужно добавить в чат
}

// ChatSummary описывает одну запись в списке чатов
type ChatSummary struct {
	ChatID   int64  `json:"chat_id"`            // Уникальный ID чата
	IsGroup  bool   `json:"is_group"`           // Является ли чат групповым
	Title    string `json:"title,omitempty"`    // Название (для групповых чатов)
	Username string `json:"username,omitempty"` // Имя собеседника (для личных чатов)
	Display  string `json:"display"`            // Имя или название для отображения
	LastMsg  string `json:"last_msg"`           // Последнее сообщение
	LastAt   int64  `json:"last_at"`            // Время последнего сообщения
}

// UserSummary содержит минимальную информацию о пользователе
// для отображения в результатах поиска
type UserSummary struct {
	Username    string `json:"username"`     // Уникальное имя пользователя
	DisplayName string `json:"display_name"` // Имя, отображаемое в UI
}
