package main

import (
	"agenda-service/database"
	"agenda-service/internal/handler"
	"agenda-service/internal/repository"
	"agenda-service/internal/service"
	"log"
	"os"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/joho/godotenv"
)

func main() {
	_ = godotenv.Load("../.env")

	db := database.Connect()

	agendaRepo := repository.NewAgendaRepository(db)
	agendaSvc := service.NewAgendaService(agendaRepo)
	agendaH := handler.NewAgendaHandler(agendaSvc)

	app := fiber.New(fiber.Config{
		AppName: "agenda-service v1.0",
	})

	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} ${method} ${path} (${latency})\n",
	}))

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "agenda-service"})
	})

	// Consultas
	app.Get("/agenda/disponibilidad", agendaH.CheckDisponibilidad) // antes de /:id
	app.Get("/agenda/paciente/:pacId", agendaH.GetByPatient)
	app.Get("/agenda/fecha/:fecha", agendaH.GetByFecha)
	app.Get("/agenda/:id", agendaH.GetByID)

	// CRUD
	app.Post("/agenda", agendaH.Create)
	app.Put("/agenda/:id/reagendar", agendaH.Reagendar)
	app.Put("/agenda/:id/cancelar", agendaH.Cancelar)
	app.Put("/agenda/:id/realizada", agendaH.MarcarRealizada)
	app.Put("/agenda/:id/desmarcar", agendaH.DesmarcarRealizada)
	app.Patch("/agenda/:id/cal_event", agendaH.SetCalEvent)

	// --- Admin: reset total (borra TODAS las citas) ---
	// Usado por el botón de "resetear datos" del dashboard para poder probar
	// el bot como usuario nuevo sin tocar la base de datos a mano.
	app.Post("/admin/reset", func(c *fiber.Ctx) error {
		if err := db.Exec("DELETE FROM agenda").Error; err != nil {
			return c.Status(500).JSON(fiber.Map{"error": "no se pudo borrar agenda: " + err.Error()})
		}
		return c.JSON(fiber.Map{"status": "ok", "mensaje": "agenda eliminada"})
	})

	port := os.Getenv("AGENDA_PORT")
	if port == "" {
		port = "8082"
	}

	log.Printf("agenda-service escuchando en :%s", port)
	log.Fatal(app.Listen(":" + port))
}
