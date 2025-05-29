package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
)

func searchUsersHandler(w http.ResponseWriter, r *http.Request) {
	/**
	Обработчик поиска пользователей (GET /users/search?q=...).

	Доступен только авторизованным пользователям.
	Ищет пользователей по username или имени/фамилии.
	Возвращает JSON-массив UserSummary.
	*/

	// Разрешён только метод GET
	if r.Method != http.MethodGet {
		http.Error(w, "GET only", http.StatusMethodNotAllowed)
		return
	}

	// Проверяем авторизацию — извлекаем имя пользователя по токену
	user, err := authUsername(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	// Извлекаем строку поиска из параметров запроса (?q=...)
	q := r.URL.Query().Get("q")
	if q == "" {
		// Если запрос пустой — возвращаем пустой список
		json.NewEncoder(w).Encode([]UserSummary{})
		return
	}

	// Выполняем поиск пользователей в базе данных
	users, err := SearchUsers(context.Background(), user, q, 20)
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}

	// Отправляем найденных пользователей в формате JSON
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(users)
}

func createDirectChatHandler(w http.ResponseWriter, r *http.Request) {
	/**
	Обработчик создания личного чата (POST /chats/direct).
	Принимает JSON с именем собеседника, проверяет пользователей,
	создаёт чат при необходимости и рассылает обновления через WebSocket.
	*/

	// Разрешён только POST-запрос
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	// Авторизация по токену — получаем username
	user, err := authUsername(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	// Парсим тело запроса: ожидаем поле "username" (второй участник чата)
	var req struct {
		Username string `json:"username"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}

	ctx := context.Background()

	// Получаем ID текущего пользователя (отправителя)
	fromID, err := getUserID(ctx, user)
	if err != nil {
		http.Error(w, "unknown user", http.StatusBadRequest)
		return
	}

	// Получаем ID второго участника чата
	toID, err := getUserID(ctx, req.Username)
	if err != nil {
		http.Error(w, "peer not found", http.StatusNotFound)
		return
	}

	// Убеждаемся, что такой чат существует или создаём его
	chatID, err := ensureDirectChat(ctx, fromID, toID)
	if err != nil {
		http.Error(w, "cannot ensure chat", http.StatusInternalServerError)
		return
	}

	// Отправляем клиенту ID чата
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]int64{"chat_id": chatID})

	// Пушим обновлённые списки чатов обоим участникам по WebSocket
	mu.Lock()
	if c, ok := clients[user]; ok {
		sendChats(user, c) // отправителю
	}
	if c, ok := clients[req.Username]; ok {
		sendChats(req.Username, c) // получателю
	}
	mu.Unlock()
}

func createGroupChatHandler(w http.ResponseWriter, r *http.Request) {
	/**
	Обработчик создания группового чата (POST /chats/group).
	Принимает JSON с названием и списком участников,
	создаёт новый чат в базе данных и уведомляет всех участников через WebSocket.
	*/

	// Разрешён только POST-запрос
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	// Аутентифицируем пользователя по токену (извлекаем имя создателя)
	creator, err := authUsername(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	// Парсим тело запроса в структуру createGroupReq
	var req createGroupReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}

	// Проверка: название группы и хотя бы один участник обязательны
	if req.Title == "" || len(req.Usernames) == 0 {
		http.Error(w, "title and at least one user required", http.StatusBadRequest)
		return
	}

	ctx := context.Background() // Контекст выполнения запроса

	// Получаем ID создателя по username
	ownerID, err := getUserID(ctx, creator)
	if err != nil {
		http.Error(w, "unknown creator", http.StatusBadRequest)
		return
	}

	// Преобразуем username'ы участников в их ID
	var memberIDs []int64
	for _, uname := range req.Usernames {
		uid, err := getUserID(ctx, uname)
		if err != nil {
			http.Error(w, fmt.Sprintf("user %s not found", uname), http.StatusNotFound)
			return
		}
		memberIDs = append(memberIDs, uid)
	}

	// Создаём новый групповой чат в БД
	chatID, err := CreateGroupChat(ctx, ownerID, req.Title, memberIDs)
	if err != nil {
		http.Error(w, "cannot create group chat", http.StatusInternalServerError)
		return
	}

	// Отправляем клиенту ID созданного чата
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]int64{"chat_id": chatID})

	// Уведомляем всех участников (включая создателя), отправив им обновлённый список чатов
	participants := append(req.Usernames, creator)
	mu.Lock()
	for _, uname := range participants {
		if conn, ok := clients[uname]; ok {
			sendChats(uname, conn)
		}
	}
	mu.Unlock()
}
