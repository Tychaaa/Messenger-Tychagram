package main

import (
	"context"
	"database/sql"
	"fmt"
	"github.com/gorilla/websocket"
	"github.com/jackc/pgx/v5"
	"log"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool" // Библиотека для работы с PostgreSQL через пул соединений
)

// Строка подключения по умолчанию
const defaultDSN = "postgres://postgres:tychaaa@localhost:5432/messenger?sslmode=disable"

// Pool — глобальный пул соединений к базе данных
// Используется во всех функциях, которые работают с PostgreSQL
var Pool *pgxpool.Pool

// InitDB подключается к PostgreSQL, создаёт пул соединений и проверяет соединение
func InitDB() {
	// Получаем строку подключения из переменной окружения, если она есть
	dsn := os.Getenv("POSTGRES_DSN")
	if dsn == "" {
		// Если переменная не задана — используем значение по умолчанию
		dsn = defaultDSN
	}

	var err error
	// Создаём новый пул соединений
	Pool, err = pgxpool.New(context.Background(), dsn)
	if err != nil {
		// Если не удалось подключиться — завершаем программу
		log.Fatalf("Failed to create PostgreSQL connection pool: %v", err)
	}

	// Проверяем, что соединение с БД работает
	if err = Pool.Ping(context.Background()); err != nil {
		log.Fatalf("PostgreSQL is not responding to ping: %v", err)
	}

	// Всё хорошо — выводим сообщение
	log.Println("PostgreSQL connection pool is ready")
}

// CloseDB закрывает пул соединений
func CloseDB() { Pool.Close() }

func persistMsg(p Packet) {
	ctx := context.Background()

	fromID, err := getUserID(ctx, p.From)
	if err != nil {
		log.Printf("unknown sender %q: %v", p.From, err)
		return
	}

	toID, err := getUserID(ctx, p.To)
	if err != nil {
		log.Printf("unknown recipient %q: %v", p.To, err)
		return
	}

	chatID, err := ensureDirectChat(ctx, fromID, toID)
	if err != nil {
		log.Printf("ensuring chat: %v", err)
		return
	}

	_, err = Pool.Exec(ctx,
		`INSERT INTO messages (chat_id, sender_id, text)
         VALUES ($1,$2,$3)`,
		chatID, fromID, p.Text)
	if err != nil {
		log.Printf("insert msg: %v", err)
	}
}

// getUserID возвращает ID существующего пользователя или ошибку
func getUserID(ctx context.Context, username string) (int64, error) {
	var id int64
	err := Pool.QueryRow(ctx,
		`SELECT id FROM users WHERE username=$1`, username).
		Scan(&id)
	if err != nil {
		return 0, fmt.Errorf("unknown user %q: %w", username, err)
	}
	return id, nil
}

// ensureDirectChat гарантирует, что личный чат между u1 и u2 существует.
// Если нет — создаёт записи в chats и chat_members.
func ensureDirectChat(ctx context.Context, u1, u2 int64) (int64, error) {
	if u1 > u2 {
		u1, u2 = u2, u1
	}

	var chatID int64
	err := Pool.QueryRow(ctx,
		`SELECT c.id
           FROM chats c
           JOIN chat_members m1 ON m1.chat_id = c.id AND m1.user_id = $1
           JOIN chat_members m2 ON m2.chat_id = c.id AND m2.user_id = $2
          WHERE c.is_group = false
          LIMIT 1`, u1, u2).Scan(&chatID)

	if err == pgx.ErrNoRows {
		// создаём новый чат
		if err = Pool.QueryRow(ctx,
			`INSERT INTO chats (is_group) VALUES (false) RETURNING id`,
		).Scan(&chatID); err != nil {
			return 0, err
		}
		// добавляем участников
		if _, err = Pool.Exec(ctx,
			`INSERT INTO chat_members (chat_id, user_id)
             VALUES ($1, $2), ($1, $3)`,
			chatID, u1, u2); err != nil {
			return 0, err
		}
	}
	return chatID, err
}

func sendHistory(username string, ws *websocket.Conn) {
	ctx := context.Background()

	var uid int64
	_ = Pool.QueryRow(ctx,
		`SELECT id FROM users WHERE username=$1`, username).Scan(&uid)

	rows, _ := Pool.Query(ctx,
		`SELECT c.id,
		        (SELECT u.username                       -- имя второго участника
		           FROM chat_members cm
		           JOIN users u ON u.id = cm.user_id
		          WHERE cm.chat_id = c.id AND cm.user_id <> $1) AS peer
		   FROM chats c
		   JOIN chat_members m ON m.chat_id = c.id
		  WHERE c.is_group = false AND m.user_id = $1`, uid)
	defer rows.Close()

	for rows.Next() {
		var chatID int64
		var peerName string
		_ = rows.Scan(&chatID, &peerName)

		msgRows, _ := Pool.Query(ctx,
			`SELECT u.username, m.text, m.send_at
			   FROM messages m
			   JOIN users u ON u.id = m.sender_id
			  WHERE m.chat_id = $1
			  ORDER BY m.send_at ASC              -- ↑ хронологически
			  LIMIT 50`, chatID)

		var msgs []map[string]interface{}
		for msgRows.Next() {
			var from, text string
			var ts time.Time
			_ = msgRows.Scan(&from, &text, &ts)

			to := peerName
			if from != username { // входящее
				to = username
			}

			msgs = append(msgs, map[string]interface{}{
				"from": from,
				"to":   to,
				"text": text,
				"ts":   ts.UnixMilli(),
			})
		}
		msgRows.Close()

		_ = ws.WriteJSON(map[string]interface{}{
			"type":     "history",
			"chat_id":  chatID,
			"messages": msgs,
		})
	}
}

// ChatSummary описывает одну запись в списке чатов
type ChatSummary struct {
	ChatID   int64  `json:"chat_id"`
	Username string `json:"username"`
	Display  string `json:"display"`
	LastMsg  string `json:"last_msg"`
	LastAt   int64  `json:"last_at"` // Unix ms
}

// GetUserChats возвращает список личных чатов пользователя с последним сообщением
func GetUserChats(ctx context.Context, username string) ([]ChatSummary, error) {
	// находим ID пользователя
	var uid int64
	if err := Pool.QueryRow(ctx,
		`SELECT id FROM users WHERE username=$1`, username,
	).Scan(&uid); err != nil {
		return nil, fmt.Errorf("getUserID: %w", err)
	}

	// собираем все диалоги, берём peer и последнее сообщение
	rows, err := Pool.Query(ctx, `
SELECT c.id,
       u.username,
       u.display_name,
       m.text,
       EXTRACT(EPOCH FROM m.send_at)*1000 AS last_at
  FROM chats c
  JOIN chat_members cm ON cm.chat_id = c.id
  JOIN chat_members cm2 ON cm2.chat_id = c.id AND cm2.user_id <> cm.user_id
  JOIN users u ON u.id = cm2.user_id
  LEFT JOIN LATERAL (
      SELECT text, send_at
        FROM messages
       WHERE chat_id = c.id
       ORDER BY send_at DESC
       LIMIT 1
  ) m ON true
 WHERE c.is_group = false
   AND cm.user_id = $1
`, uid)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var chats []ChatSummary
	for rows.Next() {
		var ch ChatSummary
		var lastMsg sql.NullString
		var lastAt sql.NullFloat64
		if err := rows.Scan(
			&ch.ChatID,
			&ch.Username,
			&ch.Display,
			&lastMsg,
			&lastAt,
		); err != nil {
			return nil, err
		}
		// Если в чате ещё нет сообщений — отдаём пустую строку
		if lastMsg.Valid {
			ch.LastMsg = lastMsg.String
		} else {
			ch.LastMsg = ""
		}
		if lastAt.Valid {
			ch.LastAt = int64(lastAt.Float64)
		} else {
			ch.LastAt = 0
		}
		chats = append(chats, ch)
	}
	return chats, nil
}

type UserSummary struct {
	Username    string `json:"username"`
	DisplayName string `json:"display_name"`
}

// SearchUsers ищет пользователей по username или display_name, исключая самого себя.
func SearchUsers(ctx context.Context, self string, q string, limit int) ([]UserSummary, error) {
	rows, err := Pool.Query(ctx, `
SELECT username, display_name
  FROM users
 WHERE (username ILIKE '%'||$1||'%' OR display_name ILIKE '%'||$1||'%')
   AND username <> $2
 ORDER BY username
 LIMIT $3
`, q, self, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var res []UserSummary
	for rows.Next() {
		var u UserSummary
		if err := rows.Scan(&u.Username, &u.DisplayName); err != nil {
			return nil, err
		}
		res = append(res, u)
	}
	return res, nil
}
