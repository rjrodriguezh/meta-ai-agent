package handler

import (
	"activities-service/internal/model"
	"activities-service/internal/service"
	"strconv"

	"github.com/gofiber/fiber/v2"
)

type EjercicioHandler struct {
	svc *service.EjercicioService
}

func NewEjercicioHandler(svc *service.EjercicioService) *EjercicioHandler {
	return &EjercicioHandler{svc: svc}
}

// GET /ejercicios?categoria=
func (h *EjercicioHandler) GetAll(c *fiber.Ctx) error {
	categoria := c.Query("categoria")
	list, err := h.svc.GetAll(categoria)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(list)
}

// GET /ejercicios/search?q=
func (h *EjercicioHandler) Search(c *fiber.Ctx) error {
	q := c.Query("q")
	if q == "" {
		return c.JSON([]model.Ejercicio{})
	}
	list, err := h.svc.Search(q)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(list)
}

// GET /ejercicios/:id
func (h *EjercicioHandler) GetByID(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	e, err := h.svc.GetByID(uint(id))
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": "ejercicio no encontrado"})
	}
	return c.JSON(e)
}

// POST /ejercicios
func (h *EjercicioHandler) Create(c *fiber.Ctx) error {
	var req model.CreateEjercicioRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}
	e, err := h.svc.Create(req)
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}
	return c.Status(201).JSON(e)
}

// PUT /ejercicios/:id
func (h *EjercicioHandler) Update(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	var req model.UpdateEjercicioRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}
	e, err := h.svc.Update(uint(id), req)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(e)
}

// DELETE /ejercicios/:id
func (h *EjercicioHandler) Delete(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	if err := h.svc.Delete(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}
