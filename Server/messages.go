package main

import (
	"context"
	"github.com/gorilla/websocket"
	"log"
	"time"
)

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

func persistMsg(p Packet) error {
	/**
	Сохраняет сообщение из WebSocket-пакета в базу данных.

	Если сообщение отправлено в групповой чат — использует p.ChatID.
	Если сообщение личное — определяет чат по участникам и создаёт его при необходимости.
	*/

	ctx := context.Background()

	// Получаем ID отправителя по имени
	fromID, err := getUserID(ctx, p.From)
	if err != nil {
		log.Printf("unknown sender %q: %v", p.From, err)
		return err
	}

	// === Групповой чат ===
	if p.ChatID != 0 {
		_, err := Pool.Exec(ctx,
			`INSERT INTO messages (chat_id, sender_id, text) VALUES ($1, $2, $3)`,
			p.ChatID, fromID, p.Text,
		)
		if err != nil {
			log.Printf("insert group msg: %v", err)
			return err
		}
		return nil
	}

	// === Личное сообщение ===

	// Получаем ID получателя
	toID, err := getUserID(ctx, p.To)
	if err != nil {
		log.Printf("unknown recipient %q: %v", p.To, err)
		return err
	}

	// Убеждаемся, что чат существует (или создаём новый)
	chatID, err := ensureDirectChat(ctx, fromID, toID)
	if err != nil {
		log.Printf("ensuring chat: %v", err)
		return err
	}

	// Сохраняем сообщение в БД
	_, err = Pool.Exec(ctx,
		`INSERT INTO messages (chat_id, sender_id, text) VALUES ($1, $2, $3)`,
		chatID, fromID, p.Text,
	)
	if err != nil {
		log.Printf("insert msg: %v", err)
		return err
	}

	return nil
}

func sendHistory(username string, ws *websocket.Conn) {
	/**
	Отправляет пользователю историю сообщений для всех его чатов (до 50 сообщений на чат).
	Вызывается при подключении клиента по WebSocket.
	*/

	ctx := context.Background()

	// Получаем ID пользователя по username
	var uid int64
	_ = Pool.QueryRow(ctx,
		`SELECT id FROM users WHERE username=$1`, username,
	).Scan(&uid)

	// Получаем ID всех чатов, в которых состоит пользователь
	rows, _ := Pool.Query(ctx,
		`SELECT c.id
           FROM chats c
           JOIN chat_members m ON m.chat_id = c.id
          WHERE m.user_id = $1`, uid,
	)
	// Закрываем результат после завершения чтения всех chat_id
	defer rows.Close()

	for rows.Next() {
		var chatID int64
		// Получаем chat_id из строки результата
		_ = rows.Scan(&chatID)

		// Извлекаем до 50 сообщений из чата в хронологическом порядке
		msgRows, _ := Pool.Query(ctx,
			`SELECT u.username, m.text, m.send_at
               FROM messages m
               JOIN users u ON u.id = m.sender_id
              WHERE m.chat_id = $1
              ORDER BY m.send_at ASC
              LIMIT 50`, chatID,
		)

		// Список сообщений в текущем чате (для отправки клиенту)
		var msgs []map[string]interface{}
		for msgRows.Next() {
			var from, text string
			var ts time.Time
			// Считываем отправителя, текст и временную метку из строки результата
			_ = msgRows.Scan(&from, &text, &ts)

			// Добавляем сообщение в список
			msgs = append(msgs, map[string]interface{}{
				"from": from,
				"text": text,
				"ts":   ts.UnixMilli(),
			})
		}
		msgRows.Close()

		// Отправляем клиенту историю сообщений по текущему чату
		_ = ws.WriteJSON(map[string]interface{}{
			"type":     "history",
			"chat_id":  chatID,
			"messages": msgs,
		})
	}
}
