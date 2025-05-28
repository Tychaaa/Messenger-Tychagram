package main

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
)

type signReq struct {
	Username  string `json:"username"`
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name,omitempty"`
	Password  string `json:"password"`
}

type signResp struct {
	Token    string `json:"token"`
	Username string `json:"username"`
}

func signupHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	var req signReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", 400)
		return
	}

	// проверка уникальности
	var exists bool
	_ = Pool.QueryRow(context.Background(),
		`SELECT EXISTS(SELECT 1 FROM users WHERE username=$1)`, req.Username).Scan(&exists)
	if exists {
		http.Error(w, "username taken", 409)
		return
	}

	hash, _ := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)

	var userID int64
	err := Pool.QueryRow(context.Background(),
		`INSERT INTO users (username,first_name,last_name,password_hash)
		 VALUES ($1,$2,$3,$4) RETURNING id`,
		req.Username, req.FirstName, req.LastName, string(hash)).Scan(&userID)
	if err != nil {
		http.Error(w, "db err", 500)
		return
	}

	// создаём сессию
	token := uuid.NewString()
	_, _ = Pool.Exec(context.Background(),
		`INSERT INTO sessions(token,user_id,expires_at)
		 VALUES ($1,$2,$3)`,
		token, userID, time.Now().AddDate(0, 0, 7)) // 7-дней

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(signResp{Token: token, Username: req.Username})
}
