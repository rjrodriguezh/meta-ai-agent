package database

import (
	"log"
	"os"
	"patients-service/internal/model"

	"github.com/glebarez/sqlite"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

// Connect se llama al arrancar el servicio.
// Si DB_DSN está definida usa PostgreSQL, si no usa SQLite (desarrollo local).
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
			dbPath = "agenda.db"
		}
		db, err = gorm.Open(sqlite.Open(dbPath), &gorm.Config{
			Logger: logger.Default.LogMode(logger.Info),
		})
	}

	if err != nil {
		log.Fatalf("[DB] Error al conectar: %v", err)
	}

	// AutoMigrate crea las tablas si no existen (equivalente a inicializar_bd en Python)
	if err := db.AutoMigrate(&model.Patient{}, &model.Ficha{}, &model.BotConfig{}); err != nil {
		log.Fatalf("[DB] Error en AutoMigrate: %v", err)
	}

	log.Println("[DB] Conexión establecida y tablas verificadas.")
	DB = db
	return db
}
