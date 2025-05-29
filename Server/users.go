package main

import (
	"context"
	"fmt"
)

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
