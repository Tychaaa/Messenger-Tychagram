package main

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
)

type loginReq struct {
	Username string `json:"username"`
	Password string `json:"password"`
}
type loginResp struct {
	Token    string `json:"token"`
	Username string `json:"username"`
}

func loginHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var req loginReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", 400)
		return
	}

	var uid int64
	var hash string
	err := Pool.QueryRow(context.Background(),
		`SELECT id,password_hash FROM users WHERE username=$1`, req.Username).
		Scan(&uid, &hash)
	if err != nil {
		http.Error(w, "user not found", 404)
		return
	}
	if bcrypt.CompareHashAndPassword([]byte(hash), []byte(req.Password)) != nil {
		http.Error(w, "wrong password", 401)
		return
	}

	token := uuid.NewString()
	_, _ = Pool.Exec(context.Background(),
		`INSERT INTO sessions(token,user_id,expires_at)
		 VALUES ($1,$2,$3)`,
		token, uid, time.Now().AddDate(0, 0, 7))

	_ = json.NewEncoder(w).Encode(loginResp{Token: token, Username: req.Username})
}
