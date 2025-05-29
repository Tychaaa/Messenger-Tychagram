package main

import (
	"context"
	"github.com/jackc/pgx/v5/pgxpool" // Расширение: пул подключений к PostgreSQL
	"log"
	"os"
)

// Строка подключения по умолчанию (используется, если не задана через переменную окружения)
const defaultDSN = "postgres://postgres:tychaaa@localhost:5432/messenger?sslmode=disable"

// Pool — глобальный пул соединений к базе данных.
// Используется во всех частях проекта для работы с PostgreSQL
var Pool *pgxpool.Pool

func InitDB() {
	/**
	InitDB инициализирует подключение к базе данных PostgreSQL.
	Подключается с использованием строки DSN, проверяет доступность БД,
	и сохраняет пул соединений в глобальную переменную Pool.
	*/

	// Получаем строку подключения из переменной окружения (если она задана)
	dsn := os.Getenv("POSTGRES_DSN")
	if dsn == "" {
		// Если переменная не задана — используем значение по умолчанию
		dsn = defaultDSN
	}

	var err error

	// Создаём пул соединений с базой данных
	Pool, err = pgxpool.New(context.Background(), dsn)
	if err != nil {
		// Ошибка создания пула → логируем и завершаем программу
		log.Fatalf("Failed to create PostgreSQL connection pool: %v", err)
	}

	// Проверяем, отвечает ли база данных (делаем ping)
	if err = Pool.Ping(context.Background()); err != nil {
		log.Fatalf("PostgreSQL is not responding to ping: %v", err)
	}

	// Всё хорошо — выводим сообщение
	log.Println("PostgreSQL connection pool is ready")
}

func CloseDB() {
	/**
	CloseDB закрывает пул соединений с базой данных PostgreSQL.
	Вызывается при завершении работы сервера для корректного освобождения ресурсов.
	*/
	Pool.Close()
}
