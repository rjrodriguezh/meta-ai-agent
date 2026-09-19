package handler

import (
	"activities-service/internal/model"
	"activities-service/internal/service"
	"strconv"

	"github.com/gofiber/fiber/v2"
)

type DiagnosticoHandler struct {
	svc *service.DiagnosticoService
}

func NewDiagnosticoHandler(svc *service.DiagnosticoService) *DiagnosticoHandler {
	return &DiagnosticoHandler{svc: svc}
}

// GET /diagnosticos
func (h *DiagnosticoHandler) GetAll(c *fiber.Ctx) error {
	list, err := h.svc.GetAll()
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(list)
}

// GET /diagnosticos/buscar?texto=...
// Usado por ai-service (bot de WhatsApp) y dashboard-service para encontrar
// los ejercicios recomendados a partir del texto libre de una ficha clínica.
func (h *DiagnosticoHandler) Buscar(c *fiber.Ctx) error {
	texto := c.Query("texto")
	d, err := h.svc.BuscarPorTexto(texto)
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": "sin coincidencias"})
	}
	return c.JSON(d)
}

// GET /diagnosticos/:id
func (h *DiagnosticoHandler) GetByID(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	d, err := h.svc.GetByID(uint(id))
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": "no encontrado"})
	}
	return c.JSON(d)
}

// POST /diagnosticos
func (h *DiagnosticoHandler) Create(c *fiber.Ctx) error {
	var req model.CreateDiagnosticoRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}
	d, err := h.svc.Create(req)
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}
	return c.Status(201).JSON(d)
}

// PUT /diagnosticos/:id
func (h *DiagnosticoHandler) Update(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	var req model.UpdateDiagnosticoRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}
	d, err := h.svc.Update(uint(id), req)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(d)
}

// DELETE /diagnosticos/:id
func (h *DiagnosticoHandler) Delete(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	if err := h.svc.Delete(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}
