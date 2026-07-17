package main

import (
	"activities-service/database"
	"activities-service/internal/handler"
	"activities-service/internal/repository"
	"activities-service/internal/service"
	"log"
	"os"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/joho/godotenv"
)

func main() {
	_ = godotenv.Load("../.env")

	db := database.Connect()

	repo := repository.NewEjercicioRepository(db)
	svc := service.NewEjercicioService(repo)
	h := handler.NewEjercicioHandler(svc)

	app := fiber.New(fiber.Config{
		AppName: "activities-service v1.0",
	})

	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} ${method} ${path} (${latency})\n",
	}))

	app.Use(cors.New())

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "activities-service"})
	})

	// CRUD ejercicios
	app.Get("/ejercicios/search", h.Search)   // antes de /:id
	app.Get("/ejercicios", h.GetAll)
	app.Get("/ejercicios/:id", h.GetByID)
	app.Post("/ejercicios", h.Create)
	app.Put("/ejercicios/:id", h.Update)
	app.Delete("/ejercicios/:id", h.Delete)

	port := os.Getenv("ACTIVITIES_PORT")
	if port == "" {
		port = "8084"
	}

	log.Printf("activities-service escuchando en :%s", port)
	log.Fatal(app.Listen(":" + port))
}
