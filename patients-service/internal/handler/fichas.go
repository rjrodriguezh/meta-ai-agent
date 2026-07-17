package handler

import (
	"patients-service/internal/model"
	"patients-service/internal/service"
	"strconv"

	"github.com/gofiber/fiber/v2"
)

type FichaHandler struct {
	svc *service.FichaService
}

func NewFichaHandler(svc *service.FichaService) *FichaHandler {
	return &FichaHandler{svc: svc}
}

// GET /patients/:id/fichas
func (h *FichaHandler) GetByPatient(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	fichas, err := h.svc.GetByPatient(uint(id))
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fichas)
}

// GET /patients/:id/fichas/activa
// Usado por ai-service para consultar sesiones pendientes
func (h *FichaHandler) GetActiva(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	ficha, err := h.svc.GetActiva(uint(id))
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": "sin ficha activa"})
	}
	return c.JSON(ficha)
}

// POST /patients/:id/fichas
func (h *FichaHandler) Create(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	var req model.CreateFichaRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}

	ficha, err := h.svc.Create(uint(id), req)
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}
	return c.Status(201).JSON(ficha)
}

// PUT /fichas/:id/incrementar  — agenda-service lo llama al marcar sesión realizada
func (h *FichaHandler) Incrementar(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	if err := h.svc.IncrementarSesion(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// PUT /fichas/:id/disminuir  — agenda-service lo llama al desmarcar sesión
func (h *FichaHandler) Disminuir(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	if err := h.svc.DisminuirSesion(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// PUT /fichas/:id/cerrar
func (h *FichaHandler) Cerrar(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	if err := h.svc.Cerrar(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// PUT /fichas/:id
func (h *FichaHandler) Update(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	var req model.UpdateFichaRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}

	if err := h.svc.Update(uint(id), req); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// DELETE /fichas/:id
func (h *FichaHandler) Delete(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	if err := h.svc.Delete(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}
