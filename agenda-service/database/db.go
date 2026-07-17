package database

import (
	"agenda-service/internal/model"
	"log"
	"os"

	"github.com/glebarez/sqlite"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

func Connect() *gorm.DB {
	dsn := os.Getenv("DB_DSN")

	var db *gorm.DB
	var err error

	if dsn != "" {
		log.Println("[DB] Conectando a PostgreSQL...")
		db, err = gorm.Open(postgres.Open(dsn), &gorm.Config{
			Logger: logger.Default.LogMode(logger.Info),
		})
	} else {
		log.Println("[DB] Usando SQLite (desarrollo)...")
		dbPath := os.Getenv("DB_PATH")
		if dbPath == "" {
			dbPath = "../agenda.db"
		}
		db, err = gorm.Open(sqlite.Open(dbPath), &gorm.Config{
			Logger: logger.Default.LogMode(logger.Info),
		})
	}

	if err != nil {
		log.Fatalf("[DB] Error al conectar: %v", err)
	}

	if err := db.AutoMigrate(&model.Agenda{}); err != nil {
		log.Fatalf("[DB] Error en AutoMigrate: %v", err)
	}

	log.Println("[DB] Conexión establecida.")
	DB = db
	return db
}
