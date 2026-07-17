package main

import (
	"log"
	"os"
	"patients-service/database"
	"patients-service/internal/handler"
	"patients-service/internal/repository"
	"patients-service/internal/service"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/joho/godotenv"
)

func main() {
	// Cargar .env si existe (equivalente a dotenv en Python)
	_ = godotenv.Load("../.env")

	// Conexión a la base de datos
	db := database.Connect()

	// Dependencias (inyección manual, sin framework)
	// Repository → Service → Handler
	patientRepo    := repository.NewPatientRepository(db)
	fichaRepo      := repository.NewFichaRepository(db)
	botConfigRepo  := repository.NewBotConfigRepository(db)

	patientSvc := service.NewPatientService(patientRepo)
	fichaSvc   := service.NewFichaService(fichaRepo)

	patientH   := handler.NewPatientHandler(patientSvc)
	fichaH     := handler.NewFichaHandler(fichaSvc)
	botCfgH    := handler.NewBotConfigHandler(botConfigRepo)

	// App Fiber
	app := fiber.New(fiber.Config{
		AppName: "patients-service v1.0",
	})

	// Middleware de logging (equivalente al logging de uvicorn)
	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} ${method} ${path} (${latency})\n",
	}))

	// Health check
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "patients-service"})
	})

	// --- Rutas de pacientes ---
	app.Get("/patients", patientH.GetAll)
	app.Get("/patients/search", patientH.Search)                    // antes de /:id
	app.Get("/patients/telefono/:telefono", patientH.GetByTelefono) // antes de /:id
	app.Get("/patients/:id", patientH.GetByID)
	app.Post("/patients", patientH.Create)
	app.Put("/patients/:id", patientH.Update)
	app.Delete("/patients/:id", patientH.Deactivate)

	// --- Rutas de fichas ---
	app.Get("/patients/:id/fichas", fichaH.GetByPatient)
	app.Get("/patients/:id/fichas/activa", fichaH.GetActiva)
	app.Post("/patients/:id/fichas", fichaH.Create)

	// CRUD fichas
	app.Put("/fichas/:id", fichaH.Update)
	app.Delete("/fichas/:id", fichaH.Delete)

	// Endpoints que llama agenda-service internamente
	app.Put("/fichas/:id/incrementar", fichaH.Incrementar)
	app.Put("/fichas/:id/disminuir", fichaH.Disminuir)
	app.Put("/fichas/:id/cerrar", fichaH.Cerrar)

	// --- Configuración bot ---
	app.Get("/config/bot", botCfgH.Get)
	app.Put("/config/bot", botCfgH.Update)

	// Puerto
	port := os.Getenv("PATIENTS_PORT")
	if port == "" {
		port = "8083"
	}

	log.Printf("patients-service escuchando en :%s", port)
	log.Fatal(app.Listen(":" + port))
}
