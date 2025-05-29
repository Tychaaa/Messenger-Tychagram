package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"     // Для генерации уникальных идентификаторов (токенов)
	"golang.org/x/crypto/bcrypt" // Для безопасного хэширования и проверки паролей
)

func loginHandler(w http.ResponseWriter, r *http.Request) {
	/**
	Обработчик входа пользователя.
	Принимает POST-запрос с JSON: { "username": "...", "password": "..." }.
	Проверяет логин и пароль, и если они верны — создаёт сессию и возвращает токен.
	*/

	// Разрешён только метод POST
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	// Разбираем JSON-запрос в структуру loginReq
	var req loginReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", 400)
		return
	}

	var uid int64
	var hash string

	// Проверяем наличие пользователя в БД и получаем его ID и хэш пароля
	err := Pool.QueryRow(context.Background(),
		`SELECT id,password_hash FROM users WHERE username=$1`, req.Username).
		Scan(&uid, &hash)
	if err != nil {
		// Пользователь не найден
		http.Error(w, "user not found", 404)
		return
	}

	// Сравниваем хэш пароля с введённым паролем
	if bcrypt.CompareHashAndPassword([]byte(hash), []byte(req.Password)) != nil {
		// Пароль неверный
		http.Error(w, "wrong password", 401)
		return
	}

	// Генерируем новый токен сессии
	token := uuid.NewString()

	// Сохраняем сессию в таблицу sessions (на 7 дней)
	_, _ = Pool.Exec(context.Background(),
		`INSERT INTO sessions(token,user_id,expires_at)
		 VALUES ($1,$2,$3)`,
		token, uid, time.Now().AddDate(0, 0, 7))

	// Возвращаем токен и имя пользователя клиенту в формате JSON
	_ = json.NewEncoder(w).Encode(loginResp{
		Token:    token,
		Username: req.Username,
	})
}

func authUsername(r *http.Request) (string, error) {
	/**
	Проверяет заголовок авторизации и возвращает username, если токен валиден.

	Формат заголовка: Authorization: Bearer <token>
	Возвращает: имя пользователя или ошибку.
	*/

	// Извлекаем заголовок Authorization из HTTP-запроса
	h := r.Header.Get("Authorization")

	// Разделяем заголовок по пробелам: ожидаем два слова → "Bearer" и сам токен
	parts := strings.Fields(h)
	if len(parts) != 2 || parts[0] != "Bearer" {
		// Формат неверный
		return "", fmt.Errorf("invalid auth header")
	}

	// parts[1] — это сам токен
	var user string

	// Получаем имя пользователя (u.username)
	// по токену, если он существует и ещё не истёк.
	err := Pool.QueryRow(context.Background(),
		`SELECT u.username
           FROM sessions s
           JOIN users u ON u.id = s.user_id
          WHERE s.token=$1 AND s.expires_at > NOW()`,
		parts[1],
	).Scan(&user)

	if err != nil {
		// Токен не найден или просрочен
		return "", err
	}

	// Возвращаем имя пользователя, соответствующее токену
	return user, nil
}
