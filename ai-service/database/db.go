package database

import (
	"ai-service/internal/model"
	"log"
	"os"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

func Connect() *gorm.DB {
	log.Println("[DB] Conectando a SQLite (agenda.db)...")

	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "../agenda.db" // desarrollo local
	}
	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{
		Logger:                                   logger.Default.LogMode(logger.Silent),
		DisableForeignKeyConstraintWhenMigrating: true,
	})
	if err != nil {
		log.Fatalf("[DB] Error al conectar: %v", err)
	}

	// La tabla conversaciones puede ya existir (creada por Python).
	// Usamos AutoMigrate solo para crearla si no existe, sin tocar FKs.
	if !db.Migrator().HasTable(&model.Conversacion{}) {
		if err := db.AutoMigrate(&model.Conversacion{}); err != nil {
			log.Fatalf("[DB] Error en AutoMigrate: %v", err)
		}
		log.Println("[DB] Tabla conversaciones creada.")
	}

	log.Println("[DB] Conexión establecida.")
	DB = db
	return db
}
