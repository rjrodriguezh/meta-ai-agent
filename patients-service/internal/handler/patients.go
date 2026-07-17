package handler

import (
	"patients-service/internal/model"
	"patients-service/internal/service"
	"strconv"

	"github.com/gofiber/fiber/v2"
)

type PatientHandler struct {
	svc *service.PatientService
}

func NewPatientHandler(svc *service.PatientService) *PatientHandler {
	return &PatientHandler{svc: svc}
}

// GET /patients
func (h *PatientHandler) GetAll(c *fiber.Ctx) error {
	patients, err := h.svc.GetAll()
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(patients)
}

// GET /patients/:id
func (h *PatientHandler) GetByID(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	p, err := h.svc.GetByID(uint(id))
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": "paciente no encontrado"})
	}
	return c.JSON(p)
}

// GET /patients/telefono/:telefono
// Usado por ai-service para identificar al paciente por su número de WhatsApp
func (h *PatientHandler) GetByTelefono(c *fiber.Ctx) error {
	telefono := c.Params("telefono")

	p, err := h.svc.GetByTelefono(telefono)
	if err != nil {
		// 404 es esperado cuando el paciente no está registrado
		return c.Status(404).JSON(fiber.Map{"error": "paciente no encontrado"})
	}
	return c.JSON(p)
}

// GET /patients/search?q=juan
func (h *PatientHandler) Search(c *fiber.Ctx) error {
	q := c.Query("q")
	if q == "" {
		return c.Status(400).JSON(fiber.Map{"error": "parámetro q requerido"})
	}

	patients, err := h.svc.Search(q)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(patients)
}

// POST /patients
func (h *PatientHandler) Create(c *fiber.Ctx) error {
	var req model.CreatePatientRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}

	p, err := h.svc.Create(req)
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}
	return c.Status(201).JSON(p)
}

// PUT /patients/:id
func (h *PatientHandler) Update(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	var req model.UpdatePatientRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}

	p, err := h.svc.Update(uint(id), req)
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(p)
}

// DELETE /patients/:id  (soft delete → estado INACTIVO)
func (h *PatientHandler) Deactivate(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	if err := h.svc.Deactivate(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}
