package main

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/google/uuid"     // Для генерации уникальных идентификаторов (токенов)
	"golang.org/x/crypto/bcrypt" // Для безопасного хэширования и проверки паролей
)

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
