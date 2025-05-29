package main

import (
	"context"
	"log"
	"net/http"
	"time"
)

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
