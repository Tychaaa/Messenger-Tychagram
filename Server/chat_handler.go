package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
)

// helper: извлечь username из заголовка Authorization: Bearer <token>
func authUsername(r *http.Request) (string, error) {
	h := r.Header.Get("Authorization")
	parts := strings.Fields(h)
	if len(parts) != 2 || parts[0] != "Bearer" {
		return "", fmt.Errorf("invalid auth header")
	}
	var user string
	err := Pool.QueryRow(context.Background(),
		`SELECT u.username
           FROM sessions s
           JOIN users u ON u.id = s.user_id
          WHERE s.token=$1 AND s.expires_at > NOW()`,
		parts[1],
	).Scan(&user)
	if err != nil {
		return "", err
	}
	return user, nil
}

// GET /users/search?q=…
func searchUsersHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "GET only", http.StatusMethodNotAllowed)
		return
	}
	user, err := authUsername(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	q := r.URL.Query().Get("q")
	if q == "" {
		json.NewEncoder(w).Encode([]UserSummary{})
		return
	}

	users, err := SearchUsers(context.Background(), user, q, 20)
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(users)
}

// POST /chats/direct  { "username": "<peer>" }
func createDirectChatHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	user, err := authUsername(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	var req struct {
		Username string `json:"username"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}

	ctx := context.Background()
	fromID, err := getUserID(ctx, user)
	if err != nil {
		http.Error(w, "unknown user", http.StatusBadRequest)
		return
	}
	toID, err := getUserID(ctx, req.Username)
	if err != nil {
		http.Error(w, "peer not found", http.StatusNotFound)
		return
	}

	chatID, err := ensureDirectChat(ctx, fromID, toID)
	if err != nil {
		http.Error(w, "cannot ensure chat", http.StatusInternalServerError)
		return
	}

	// Ответим сразу с chat_id (необязательно)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]int64{"chat_id": chatID})

	// Пушим обновлённые списки чатов по WS обоим участникам
	mu.Lock()
	if c, ok := clients[user]; ok {
		sendChats(user, c)
	}
	if c, ok := clients[req.Username]; ok {
		sendChats(req.Username, c)
	}
	mu.Unlock()
}
