package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/gorilla/websocket"
	"github.com/jackc/pgx/v5"         // Базовый PostgreSQL-драйвер
	"github.com/jackc/pgx/v5/pgxpool" // Расширение: пул подключений к PostgreSQL
)

// Строка подключения по умолчанию (используется, если не задана через переменную окружения)
const defaultDSN = "postgres://postgres:tychaaa@localhost:5432/messenger?sslmode=disable"

// Pool — глобальный пул соединений к базе данных.
// Используется во всех частях проекта для работы с PostgreSQL
var Pool *pgxpool.Pool

func InitDB() {
	/**
	InitDB инициализирует подключение к базе данных PostgreSQL.
	Подключается с использованием строки DSN, проверяет доступность БД,
	и сохраняет пул соединений в глобальную переменную Pool.
	*/

	// Получаем строку подключения из переменной окружения (если она задана)
	dsn := os.Getenv("POSTGRES_DSN")
	if dsn == "" {
		// Если переменная не задана — используем значение по умолчанию
		dsn = defaultDSN
	}

	var err error

	// Создаём пул соединений с базой данных
	Pool, err = pgxpool.New(context.Background(), dsn)
	if err != nil {
		// Ошибка создания пула → логируем и завершаем программу
		log.Fatalf("Failed to create PostgreSQL connection pool: %v", err)
	}

	// Проверяем, отвечает ли база данных (делаем ping)
	if err = Pool.Ping(context.Background()); err != nil {
		log.Fatalf("PostgreSQL is not responding to ping: %v", err)
	}

	// Всё хорошо — выводим сообщение
	log.Println("PostgreSQL connection pool is ready")
}

func CloseDB() {
	/**
	CloseDB закрывает пул соединений с базой данных PostgreSQL.
	Вызывается при завершении работы сервера для корректного освобождения ресурсов.
	*/
	Pool.Close()
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

func getUserID(ctx context.Context, username string) (int64, error) {
	/**
	Возвращает ID пользователя по его username.

	Если пользователь не найден — возвращает ошибку.
	*/

	var id int64
	err := Pool.QueryRow(ctx,
		`SELECT id FROM users WHERE username=$1`, username).
		Scan(&id)
	if err != nil {
		return 0, fmt.Errorf("unknown user %q: %w", username, err)
	}
	return id, nil
}

func ensureDirectChat(ctx context.Context, u1, u2 int64) (int64, error) {
	/**
	Гарантирует наличие личного чата между двумя пользователями.
	Если такой чат уже существует — возвращает его ID.
	Если нет — создаёт новый чат и добавляет в него обоих участников.
	*/

	// Упорядочиваем ID, чтобы избежать дубликатов в разных порядках
	if u1 > u2 {
		u1, u2 = u2, u1
	}

	var chatID int64

	// Ищем существующий чат между двумя пользователями (не групповой)
	err := Pool.QueryRow(ctx,
		`SELECT c.id
           FROM chats c
           JOIN chat_members m1 ON m1.chat_id = c.id AND m1.user_id = $1
           JOIN chat_members m2 ON m2.chat_id = c.id AND m2.user_id = $2
          WHERE c.is_group = false
          LIMIT 1`, u1, u2).Scan(&chatID)

	// Если не найдено — создаём новый личный чат
	if err == pgx.ErrNoRows {
		// Вставляем запись о новом чате
		if err = Pool.QueryRow(ctx,
			`INSERT INTO chats (is_group) VALUES (false) RETURNING id`,
		).Scan(&chatID); err != nil {
			return 0, err
		}

		// Добавляем обоих участников в таблицу chat_members
		if _, err = Pool.Exec(ctx,
			`INSERT INTO chat_members (chat_id, user_id)
             VALUES ($1, $2), ($1, $3)`,
			chatID, u1, u2); err != nil {
			return 0, err
		}
	}

	// Возвращаем ID чата (существующего или нового)
	return chatID, err
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

func GetUserChats(ctx context.Context, username string) ([]ChatSummary, error) {
	/**
	Возвращает список чатов пользователя с последними сообщениями.

	В выборку попадают как групповые, так и личные чаты, отсортированные по дате последнего сообщения.
	Каждый элемент — это ChatSummary, содержащий ID, тип, отображаемое имя, последнее сообщение и его время.
	*/

	// 1) Получаем ID пользователя по его username
	var uid int64
	if err := Pool.QueryRow(ctx,
		`SELECT id FROM users WHERE username = $1`, username,
	).Scan(&uid); err != nil {
		return nil, fmt.Errorf("getUserChats: %w", err)
	}

	// 2) Извлекаем чаты, в которых участвует пользователь, вместе с последним сообщением
	rows, err := Pool.Query(ctx, `
		SELECT
		    -- Извлекаем список чатов пользователя с их последним сообщением
		  c.id,                              -- ID чата
		  c.is_group,                        -- Признак группового чата
		  c.title,                           -- Название (только для групповых)
		  
		  -- Для личных чатов: имя собеседника, для групп — пустая строка
		  CASE WHEN c.is_group THEN '' ELSE u.username END AS username,
		  
		  -- Отображаемое имя: название группы или имя собеседника
		  CASE WHEN c.is_group THEN c.title ELSE u.display_name END AS display,
		  
		  m.text,                            -- Текст последнего сообщения
		  
		  -- Время последнего сообщения в миллисекундах Unix-времени
		  EXTRACT(EPOCH FROM m.send_at)*1000 AS last_at

		FROM chats c
		JOIN chat_members cm ON cm.chat_id = c.id          -- текущий пользователь состоит в чате

		-- Ищем второго участника (для личных чатов)
		LEFT JOIN chat_members cm2
		  ON cm2.chat_id = c.id AND cm2.user_id <> cm.user_id

		-- Получаем его имя
		LEFT JOIN users u ON u.id = cm2.user_id

		-- Последнее сообщение в чате (используем подзапрос через LATERAL)
		LEFT JOIN LATERAL (
			SELECT text, send_at
			  FROM messages
			 WHERE chat_id = c.id
			 ORDER BY send_at DESC
			 LIMIT 1
		) m ON true

		-- Оставляем только чаты, где состоит указанный пользователь
		WHERE cm.user_id = $1

		-- Сортировка по дате последнего сообщения (или дате создания, если сообщений не было)
		ORDER BY COALESCE(EXTRACT(EPOCH FROM m.send_at), EXTRACT(EPOCH FROM c.created_at)) * 1000 DESC
	`, uid)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	// Преобразуем результат в []ChatSummary
	var chats []ChatSummary
	for rows.Next() {
		var ch ChatSummary         // Один чат
		var title sql.NullString   // Название чата (может быть NULL)
		var lastMsg sql.NullString // Последнее сообщение (может быть NULL)
		var lastAt sql.NullFloat64 // Время последнего сообщения в ms (может быть NULL)

		// Считываем данные из строки результата
		if err := rows.Scan(
			&ch.ChatID,
			&ch.IsGroup,
			&title,
			&ch.Username,
			&ch.Display,
			&lastMsg,
			&lastAt,
		); err != nil {
			return nil, err
		}

		// Обработка NULL-значений, которые могли прийти из БД:

		// Если это групповой чат, title будет заполнен, иначе — NULL
		if title.Valid {
			ch.Title = title.String
		} else {
			ch.Title = ""
		}

		/// Последнее сообщение может отсутствовать (если чат пуст)
		if lastMsg.Valid {
			ch.LastMsg = lastMsg.String
		} else {
			ch.LastMsg = ""
		}

		// Метка времени может отсутствовать (если сообщений не было)
		if lastAt.Valid {
			ch.LastAt = int64(lastAt.Float64)
		} else {
			ch.LastAt = 0
		}

		// Добавляем чат в общий список
		chats = append(chats, ch)
	}

	// Возвращаем все собранные чаты
	return chats, nil
}

// UserSummary содержит минимальную информацию о пользователе
// для отображения в результатах поиска
type UserSummary struct {
	Username    string `json:"username"`     // Уникальное имя пользователя
	DisplayName string `json:"display_name"` // Имя, отображаемое в UI
}

func SearchUsers(ctx context.Context, self string, q string, limit int) ([]UserSummary, error) {
	/**
	Выполняет поиск пользователей по username или имени (display_name).
	Исключает самого себя из результатов.
	Результаты ограничены по количеству (limit) и отсортированы по алфавиту.
	*/

	// Выполняем SQL-запрос с фильтрацией по частичному совпадению
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

	// Сканируем результаты в срез структур UserSummary
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

func CreateGroupChat(ctx context.Context, ownerID int64, title string, memberIDs []int64) (int64, error) {
	/**
	Создаёт новый групповой чат в базе данных.

	Шаги:
	1. Начинает транзакцию.
	2. Создаёт запись в таблице chats.
	3. Добавляет всех участников, включая создателя, в chat_members.
	4. Завершает транзакцию.
	*/

	// Начинаем транзакцию
	tx, err := Pool.Begin(ctx)
	if err != nil {
		return 0, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx) // откат на случай ошибки

	// 1) Создаём сам чат (is_group = true)
	var chatID int64
	err = tx.QueryRow(ctx,
		`INSERT INTO chats (is_group, title, owner_id) 
         VALUES (true, $1, $2) RETURNING id`,
		title, ownerID,
	).Scan(&chatID)
	if err != nil {
		return 0, fmt.Errorf("insert chat: %w", err)
	}

	// 2) Собираем участников без дубликатов, включая создателя
	seen := map[int64]bool{ownerID: true}
	for _, uid := range memberIDs {
		if uid == ownerID {
			continue // не добавляем дважды
		}
		seen[uid] = true
	}

	// Вставляем всех участников в таблицу chat_members
	for uid := range seen {
		if _, err = tx.Exec(ctx,
			`INSERT INTO chat_members (chat_id, user_id) VALUES ($1, $2)`,
			chatID, uid,
		); err != nil {
			return 0, fmt.Errorf("insert member %d: %w", uid, err)
		}
	}

	// 3) Подтверждаем транзакцию
	if err := tx.Commit(ctx); err != nil {
		return 0, fmt.Errorf("commit tx: %w", err)
	}
	return chatID, nil
}

func GetChatMembers(ctx context.Context, chatID int64) ([]string, error) {
	/**
	Возвращает список username всех участников заданного чата.

	Запрашивает из базы пользователей, связанных с chat_id через таблицу chat_members.
	*/

	// Получаем список имён пользователей, входящих в чат
	rows, err := Pool.Query(ctx,
		`SELECT u.username
           FROM chat_members cm
           JOIN users u ON u.id = cm.user_id
          WHERE cm.chat_id = $1`, chatID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []string
	for rows.Next() {
		var uname string
		if err := rows.Scan(&uname); err != nil {
			return nil, err
		}
		// Добавляем имя участника в результат
		users = append(users, uname)
	}
	return users, nil
}
