package database

import (
	"activities-service/internal/model"
	"log"
	"os"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

func Connect() *gorm.DB {
	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "activities.db"
	}

	log.Println("[DB] Usando SQLite:", dbPath)
	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		log.Fatalf("[DB] Error al conectar: %v", err)
	}

	if err := db.AutoMigrate(&model.Ejercicio{}, &model.Diagnostico{}); err != nil {
		log.Fatalf("[DB] Error en AutoMigrate: %v", err)
	}

	log.Println("[DB] Conexión establecida y tablas verificadas.")
	return db
}
