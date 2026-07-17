package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
)

// MetaClient maneja el envío de mensajes vía WhatsApp e Instagram.
type MetaClient struct {
	accessToken string
	phoneID     string   // WhatsApp phone number ID
	igUserID    string   // Instagram User ID (cuenta de la clínica)
	httpClient  *http.Client
}

func NewMetaClient() *MetaClient {
	return &MetaClient{
		accessToken: os.Getenv("META_ACCESS_TOKEN"),
		phoneID:     os.Getenv("PHONE_NUMBER_ID"),
		igUserID:    os.Getenv("IG_USER_ID"),
		httpClient:  &http.Client{},
	}
}

// EnviarWhatsApp envía un mensaje de texto por WhatsApp Business API.
func (c *MetaClient) EnviarWhatsApp(numeroDestino, mensaje string) error {
	url := fmt.Sprintf("https://graph.facebook.com/v20.0/%s/messages", c.phoneID)

	payload := map[string]interface{}{
		"messaging_product": "whatsapp",
		"to":                numeroDestino,
		"type":              "text",
		"text":              map[string]string{"body": mensaje},
	}
	return c.post(url, payload, "WA")
}

// EnviarInstagram envía un mensaje de texto por Instagram Direct.
// recipientID es el IGSID del usuario (sender.id del webhook).
func (c *MetaClient) EnviarInstagram(recipientID, mensaje string) error {
	igID := c.igUserID
	if igID == "" {
		igID = "me"
	}
	url := fmt.Sprintf("https://graph.facebook.com/v20.0/%s/messages", igID)

	payload := map[string]interface{}{
		"recipient": map[string]string{"id": recipientID},
		"message":   map[string]string{"text": mensaje},
	}
	return c.post(url, payload, "IG")
}

// EnviarMensaje — compatibilidad hacia atrás (WhatsApp por defecto)
func (c *MetaClient) EnviarMensaje(numeroDestino, mensaje string) error {
	return c.EnviarWhatsApp(numeroDestino, mensaje)
}

func (c *MetaClient) post(url string, payload interface{}, tag string) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("error serializando payload: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return fmt.Errorf("error creando request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("error enviando a Meta [%s]: %w", tag, err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	log.Printf("[META/%s] status=%d body=%s", tag, resp.StatusCode, string(respBody))

	if resp.StatusCode >= 400 {
		return fmt.Errorf("meta API error [%s] %d: %s", tag, resp.StatusCode, string(respBody))
	}
	return nil
}
