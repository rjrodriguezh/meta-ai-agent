package handler

import (
	"log"
	"os"
	"whatsapp-service/internal/client"
	"whatsapp-service/internal/model"

	"github.com/gofiber/fiber/v2"
)

type WebhookHandler struct {
	meta *client.MetaClient
	ai   *client.AIClient
}

func NewWebhookHandler(meta *client.MetaClient, ai *client.AIClient) *WebhookHandler {
	return &WebhookHandler{meta: meta, ai: ai}
}

// GET /webhook — verificación de Meta (sirve para WhatsApp e Instagram)
func (h *WebhookHandler) Verificar(c *fiber.Ctx) error {
	mode      := c.Query("hub.mode")
	token     := c.Query("hub.verify_token")
	challenge := c.Query("hub.challenge")

	verifyToken := os.Getenv("META_VERIFY_TOKEN")

	if mode == "subscribe" && token == verifyToken {
		log.Println("[Webhook] Verificación exitosa")
		return c.SendString(challenge)
	}
	return c.Status(403).SendString("Token inválido")
}

// POST /webhook — recibe mensajes de WhatsApp e Instagram
func (h *WebhookHandler) Recibir(c *fiber.Ctx) error {
	var payload model.WebhookPayload
	if err := c.BodyParser(&payload); err != nil {
		log.Printf("[Webhook] Error parseando body: %v", err)
		return c.Status(400).JSON(fiber.Map{"error": "payload inválido"})
	}

	// Normalizar mensajes de ambas plataformas
	var mensajes []model.IncomingMessage

	for _, entry := range payload.Entry {
		// --- WhatsApp ---
		for _, change := range entry.Changes {
			for _, msg := range change.Value.Messages {
				if msg.From == "" {
					continue
				}
				// Bug #4: antes las imágenes/documentos/audio se descartaban
				// en silencio (Text.Body vacío). Aún no tenemos OCR de
				// órdenes médicas (esa función existía en el Python viejo
				// vía Azure Document Intelligence y no se migró a Go), pero
				// al menos avisamos al paciente en vez de no responder nada.
				if msg.Text.Body == "" {
					if msg.Type != "" && msg.Type != "text" {
						log.Printf("[Webhook] Mensaje tipo '%s' de %s — no se puede leer aún, se avisa al paciente", msg.Type, msg.From)
						mensajes = append(mensajes, model.IncomingMessage{
							Numero:     msg.From,
							Texto:      "__no_procesable__",
							Plataforma: "whatsapp",
						})
					}
					continue
				}
				mensajes = append(mensajes, model.IncomingMessage{
					Numero:     msg.From,
					Texto:      msg.Text.Body,
					Plataforma: "whatsapp",
				})
			}
		}

		// --- Instagram ---
		for _, ig := range entry.Messaging {
			if ig.Sender.ID == "" || ig.Message.Text == "" {
				continue
			}
			// Prefijo "ig_" para distinguir IDs de Instagram de teléfonos WhatsApp
			mensajes = append(mensajes, model.IncomingMessage{
				Numero:     "ig_" + ig.Sender.ID,
				Texto:      ig.Message.Text,
				Plataforma: "instagram",
			})
		}
	}

	// Procesar cada mensaje
	for _, msg := range mensajes {
		log.Printf("[Webhook/%s] De %s: %s", msg.Plataforma, msg.Numero, msg.Texto)

		var respuesta string
		var err error
		if msg.Texto == "__no_procesable__" {
			// Aún no leemos fotos/documentos/audio (Bug #4) — avisar en vez
			// de fallar silenciosamente o mandarlo a clasificar como texto.
			respuesta = "Por ahora no puedo leer fotos ni documentos 🙏 Cuéntame en texto tu diagnóstico o el motivo de tu consulta."
		} else {
			respuesta, err = h.ai.ProcesarMensaje(msg.Numero, msg.Texto)
			if err != nil {
				log.Printf("[Webhook] Error en ai-service: %v", err)
				respuesta = "Ocurrió un problema. Intenta nuevamente."
			}
		}

		// Enviar respuesta por la plataforma correcta
		switch msg.Plataforma {
		case "instagram":
			igsid := msg.Numero[3:] // quitar prefijo "ig_"
			if err := h.meta.EnviarInstagram(igsid, respuesta); err != nil {
				log.Printf("[Webhook/IG] Error enviando: %v", err)
			}
		default:
			if err := h.meta.EnviarWhatsApp(msg.Numero, respuesta); err != nil {
				log.Printf("[Webhook/WA] Error enviando: %v", err)
			}
		}
	}

	// Meta siempre espera 200 OK
	return c.JSON(fiber.Map{"status": "ok"})
}
