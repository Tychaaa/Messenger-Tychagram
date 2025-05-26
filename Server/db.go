package main

import (
	"context"
	"log"
	"os"

	"github.com/jackc/pgx/v5/pgxpool" // Библиотека для работы с PostgreSQL через пул соединений
)

// Строка подключения по умолчанию
const defaultDSN = "postgres://postgres:tychaaa@localhost:5432/messenger?sslmode=disable"

// Pool — глобальный пул соединений к базе данных
// Используется во всех функциях, которые работают с PostgreSQL
var Pool *pgxpool.Pool

// InitDB подключается к PostgreSQL, создаёт пул соединений и проверяет соединение
func InitDB() {
	// Получаем строку подключения из переменной окружения, если она есть
	dsn := os.Getenv("POSTGRES_DSN")
	if dsn == "" {
		// Если переменная не задана — используем значение по умолчанию
		dsn = defaultDSN
	}

	var err error
	// Создаём новый пул соединений
	Pool, err = pgxpool.New(context.Background(), dsn)
	if err != nil {
		// Если не удалось подключиться — завершаем программу
		log.Fatalf("Failed to create PostgreSQL connection pool: %v", err)
	}

	// Проверяем, что соединение с БД работает
	if err = Pool.Ping(context.Background()); err != nil {
		log.Fatalf("PostgreSQL is not responding to ping: %v", err)
	}

	// Всё хорошо — выводим сообщение
	log.Println("PostgreSQL connection pool is ready")
}

// CloseDB закрывает пул соединений
func CloseDB() { Pool.Close() }
