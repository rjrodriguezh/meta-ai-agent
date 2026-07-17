package main

import (
	"log"
	"os"
	"whatsapp-service/internal/client"
	"whatsapp-service/internal/handler"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/joho/godotenv"
)

func main() {
	_ = godotenv.Load("../.env")

	// Clientes externos
	metaClient := client.NewMetaClient()
	aiClient := client.NewAIClient()

	// Handler
	webhookH := handler.NewWebhookHandler(metaClient, aiClient)

	app := fiber.New(fiber.Config{
		AppName: "whatsapp-service v1.0",
	})

	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} ${method} ${path} (${latency})\n",
	}))

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "whatsapp-service"})
	})

	// Webhook Meta
	app.Get("/webhook", webhookH.Verificar)
	app.Post("/webhook", webhookH.Recibir)

	port := os.Getenv("WHATSAPP_PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("whatsapp-service escuchando en :%s", port)
	log.Fatal(app.Listen(":" + port))
}
