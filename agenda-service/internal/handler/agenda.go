package handler

import (
	"agenda-service/internal/model"
	"agenda-service/internal/service"
	"strconv"

	"github.com/gofiber/fiber/v2"
)

type AgendaHandler struct {
	svc *service.AgendaService
}

func NewAgendaHandler(svc *service.AgendaService) *AgendaHandler {
	return &AgendaHandler{svc: svc}
}

// GET /agenda/:id
func (h *AgendaHandler) GetByID(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	a, err := h.svc.GetByID(uint(id))
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": "no encontrado"})
	}
	return c.JSON(a)
}

// PATCH /agenda/:id/cal_event
func (h *AgendaHandler) SetCalEvent(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}
	type Req struct {
		CalEventID string `json:"cal_event_id"`
	}
	var req Req
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}
	if err := h.svc.SetCalEventID(uint(id), req.CalEventID); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// GET /agenda/paciente/:pacId
func (h *AgendaHandler) GetByPatient(c *fiber.Ctx) error {
	pacID, err := strconv.Atoi(c.Params("pacId"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "pacId inválido"})
	}

	agenda, err := h.svc.GetByPatient(uint(pacID))
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(agenda)
}

// GET /agenda/fecha/:fecha  — ej: /agenda/fecha/2026-07-01
func (h *AgendaHandler) GetByFecha(c *fiber.Ctx) error {
	fecha := c.Params("fecha")

	agenda, err := h.svc.GetByFecha(fecha)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(agenda)
}

// GET /agenda/disponibilidad?fecha=2026-07-01&hora=17:00
func (h *AgendaHandler) CheckDisponibilidad(c *fiber.Ctx) error {
	fecha := c.Query("fecha")
	hora := c.Query("hora")

	if fecha == "" || hora == "" {
		return c.Status(400).JSON(fiber.Map{"error": "fecha y hora requeridas"})
	}

	disponible, err := h.svc.HayDisponibilidad(fecha, hora)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"disponible": disponible})
}

// POST /agenda
func (h *AgendaHandler) Create(c *fiber.Ctx) error {
	var req model.CreateAgendaRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}

	a, err := h.svc.Create(req)
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}
	return c.Status(201).JSON(a)
}

// PUT /agenda/:id/reagendar
func (h *AgendaHandler) Reagendar(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	var req model.ReagendarRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}

	if err := h.svc.Reagendar(uint(id), req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// PUT /agenda/:id/cancelar
func (h *AgendaHandler) Cancelar(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	var req model.CancelarRequest
	if err := c.BodyParser(&req); err != nil {
		req = model.CancelarRequest{} // body opcional
	}

	if err := h.svc.Cancelar(uint(id), req); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// PUT /agenda/:id/realizada
func (h *AgendaHandler) MarcarRealizada(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	type Request struct {
		Observacion string `json:"observacion"`
	}
	var req Request
	_ = c.BodyParser(&req) // body opcional

	if err := h.svc.MarcarRealizada(uint(id), req.Observacion); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}

// PUT /agenda/:id/desmarcar
func (h *AgendaHandler) DesmarcarRealizada(c *fiber.Ctx) error {
	id, err := strconv.Atoi(c.Params("id"))
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "id inválido"})
	}

	if err := h.svc.DesmarcarRealizada(uint(id)); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"ok": true})
}
