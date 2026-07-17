package handler

import (
	"ai-service/internal/intent"
	"ai-service/internal/model"
	"ai-service/internal/responder"
	"ai-service/internal/router"
	"ai-service/internal/session"
	"log"

	"github.com/gofiber/fiber/v2"
)

// ProcessHandler orquesta el flujo completo de un mensaje entrante.
// Equivale a procesar_mensaje_whatsapp en conversation_service.py
type ProcessHandler struct {
	classifier *intent.Classifier
	sessionStore *session.Store
	router     *router.Router
	responder  *responder.Natural
}

func NewProcessHandler(
	c *intent.Classifier,
	s *session.Store,
	ro *router.Router,
	re *responder.Natural,
) *ProcessHandler {
	return &ProcessHandler{classifier: c, sessionStore: s, router: ro, responder: re}
}

// POST /process
// Body: { "numero": "56911111111", "mensaje": "quiero una hora mañana" }
func (h *ProcessHandler) Process(c *fiber.Ctx) error {
	var req model.ProcessRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "body inválido"})
	}

	log.Printf("[Process] numero=%s mensaje=%s", req.Numero, req.Mensaje)

	// 1. Obtener sesión actual
	sesion := h.sessionStore.Obtener(req.Numero)

	// 2. Clasificar intención con OpenAI
	intencion, err := h.classifier.Clasificar(req.Mensaje, req.Numero, sesion)
	if err != nil {
		log.Printf("[Process] Error clasificando: %v", err)
		intencion = &model.Intent{
			Intencion: "desconocida",
			Datos:     map[string]interface{}{"texto_original": req.Mensaje},
		}
	}
	log.Printf("[Process] intención=%s", intencion.Intencion)

	// 3. Ejecutar acción
	resultado := h.router.Ejecutar(req.Numero, intencion, sesion)

	// 4. Guardar nueva sesión
	var pacID *uint
	if v, ok := resultado["pac_id"]; ok {
		switch val := v.(type) {
		case uint:
			pacID = &val
		case float64:
			u := uint(val)
			pacID = &u
		}
	}

	nuevaSesion := map[string]interface{}{}
	if ns, ok := resultado["nueva_sesion"].(map[string]interface{}); ok {
		nuevaSesion = ns
	}

	h.sessionStore.Guardar(req.Numero, nuevaSesion, pacID, intencion.Intencion)

	// 5. Generar respuesta natural
	respuesta := h.responder.Generar(req.Mensaje, resultado)

	return c.JSON(model.ProcessResponse{Respuesta: respuesta})
}
