package main

import (
	"log"      // Для логирования — вывода сообщений в консоль
	"net/http" // Для создания HTTP-сервера и обработки HTTP-запросов
)

func main() {
	// Инициализируем подключение к базе данных и пул соединений
	InitDB()
	// Закрываем пул соединений при завершении работы сервера
	defer CloseDB()

	// Регистрируем HTTP-обработчики для различных маршрутов:
	http.HandleFunc("/signup", signupHandler)                 // регистрация пользователя
	http.HandleFunc("/login", loginHandler)                   // вход пользователя
	http.HandleFunc("/users/search", searchUsersHandler)      // поиск пользователей
	http.HandleFunc("/chats/direct", createDirectChatHandler) // создание личного чата
	http.HandleFunc("/chats/group", createGroupChatHandler)   // создание группового чата
	http.HandleFunc("/ws", handleWS)                          // WebSocket-соединение

	// Запускаем отдельную горутину, которая будет слушать канал broadcast
	// и рассылать сообщения клиентам
	go router()

	// Выводим сообщение о запуске сервера в консоль
	log.Println("Tychagram server listening on :8080")

	// Запускаем HTTP-сервер на порту 8080.
	// log.Fatal завершит выполнение программы, если произойдёт ошибка запуска
	log.Fatal(http.ListenAndServe(":8080", nil))
}
