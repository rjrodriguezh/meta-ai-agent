package handler

import (
	"patients-service/internal/model"
	"patients-service/internal/repository"

	"github.com/gofiber/fiber/v2"
)

type BotConfigHandler struct {
	repo *repository.BotConfigRepository
}

func NewBotConfigHandler(repo *repository.BotConfigRepository) *BotConfigHandler {
	return &BotConfigHandler{repo: repo}
}

// GET /config/bot
func (h *BotConfigHandler) Get(c *fiber.Ctx) error {
	cfg, err := h.repo.Get()
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(cfg)
}

// PUT /config/bot
func (h *BotConfigHandler) Update(c *fiber.Ctx) error {
	var req model.UpdateBotConfigRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}
	cfg, err := h.repo.Update(req)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(cfg)
}
