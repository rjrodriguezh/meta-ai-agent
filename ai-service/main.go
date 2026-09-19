package main

import (
	"ai-service/database"
	"ai-service/internal/client"
	"ai-service/internal/handler"
	"ai-service/internal/intent"
	"ai-service/internal/responder"
	"ai-service/internal/router"
	"ai-service/internal/session"
	"log"
	"os"

	"github.com/gofiber/fiber/v2"
	fiberlogger "github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/joho/godotenv"
)

func main() {
	_ = godotenv.Load("../.env")

	// Base de datos (para sesiones)
	db := database.Connect()

	// Clientes HTTP hacia otros servicios
	patientsClient   := client.NewPatientsClient()
	agendaClient     := client.NewAgendaClient()
	configClient     := client.NewConfigClient()
	calendarClient   := client.NewCalendarClient()
	activitiesClient := client.NewActivitiesClient()

	// Componentes internos
	sessionStore    := session.NewStore(db)
	classifier      := intent.NewClassifier(configClient)
	actionRouter    := router.NewRouter(patientsClient, agendaClient, calendarClient, activitiesClient)
	naturalResponder := responder.NewNatural(configClient)

	// Handler principal
	processH := handler.NewProcessHandler(classifier, sessionStore, actionRouter, naturalResponder)

	app := fiber.New(fiber.Config{AppName: "ai-service v1.0"})
	app.Use(fiberlogger.New(fiberlogger.Config{
		Format: "[${time}] ${status} ${method} ${path} (${latency})\n",
	}))

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "ai-service"})
	})

	// Refresca la caché del bot config (llamado desde dashboard tras guardar)
	app.Post("/config/reload", func(c *fiber.Ctx) error {
		configClient.Invalidate()
		return c.JSON(fiber.Map{"status": "ok", "message": "bot config recargado"})
	})

	// Endpoint principal — recibe mensajes desde whatsapp-service
	app.Post("/process", processH.Process)

	port := os.Getenv("AI_PORT")
	if port == "" {
		port = "8081"
	}

	log.Printf("ai-service escuchando en :%s", port)
	log.Fatal(app.Listen(":" + port))
}
