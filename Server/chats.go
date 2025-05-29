package main

import (
	"context"
	"database/sql"
	"fmt"
	"github.com/gorilla/websocket"
	"github.com/jackc/pgx/v5"
	"log"
)

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
