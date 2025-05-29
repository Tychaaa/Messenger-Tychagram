package main

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/google/uuid"     // Для генерации уникальных идентификаторов (токенов)
	"golang.org/x/crypto/bcrypt" // Для безопасного хэширования и проверки паролей
)

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

func signupHandler(w http.ResponseWriter, r *http.Request) {
	/**
	Обработчик регистрации нового пользователя.
	Принимает POST-запрос с JSON-данными: имя, фамилия, username и пароль.
	Если username уникален, создаёт пользователя и возвращает токен сессии.
	*/

	// Разрешён только метод POST
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	// Парсим тело запроса в структуру signReq
	var req signReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", 400)
		return
	}

	// Проверяем, занят ли уже такой username
	var exists bool
	_ = Pool.QueryRow(context.Background(),
		`SELECT EXISTS(SELECT 1 FROM users WHERE username=$1)`, req.Username).Scan(&exists)
	if exists {
		http.Error(w, "username taken", 409)
		return
	}

	// Хэшируем пароль для безопасного хранения
	hash, _ := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)

	// Вставляем нового пользователя в базу и получаем его ID
	var userID int64
	err := Pool.QueryRow(context.Background(),
		`INSERT INTO users (username,first_name,last_name,password_hash)
		 VALUES ($1,$2,$3,$4) RETURNING id`,
		req.Username, req.FirstName, req.LastName, string(hash)).Scan(&userID)
	if err != nil {
		http.Error(w, "db err", 500)
		return
	}

	// Создаём сессию для нового пользователя (токен на 7 дней)
	token := uuid.NewString()
	_, _ = Pool.Exec(context.Background(),
		`INSERT INTO sessions(token,user_id,expires_at)
		 VALUES ($1,$2,$3)`,
		token, userID, time.Now().AddDate(0, 0, 7)) // 7-дней

	// Отправляем клиенту токен и username в ответ
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(signResp{
		Token:    token,
		Username: req.Username,
	})
}
