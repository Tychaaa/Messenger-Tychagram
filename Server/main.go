package main

import (
	"log"
	"net/http"
	"sync"

	"github.com/gorilla/websocket"
)

type Message struct {
	From string `json:"from"`
	Text string `json:"text"`
}

var (
	upgrader  = websocket.Upgrader{CheckOrigin: func(*http.Request) bool { return true }}
	clients   = make(map[*websocket.Conn]string) // сокет → имя
	broadcast = make(chan Message, 128)
	mu        sync.Mutex
)

func main() {
	http.HandleFunc("/ws", handleWS)
	go fanOut()

	log.Println("Server listening on :8080 …")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}

func handleWS(w http.ResponseWriter, r *http.Request) {
	user := r.URL.Query().Get("user")
	if user == "" {
		http.Error(w, "missing ?user=…", http.StatusBadRequest)
		return
	}
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	mu.Lock()
	clients[conn] = user
	mu.Unlock()

	for {
		var msg Message
		if err := conn.ReadJSON(&msg); err != nil {
			break // клиент закрыл соединение
		}
		broadcast <- msg
	}

	mu.Lock()
	delete(clients, conn)
	mu.Unlock()
}

func fanOut() {
	for msg := range broadcast {
		mu.Lock()
		for c := range clients {
			_ = c.WriteJSON(msg) // игнорируем ошибки записи
		}
		mu.Unlock()
	}
}
