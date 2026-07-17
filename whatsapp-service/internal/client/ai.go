package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
)

// AIClient llama al ai-service para procesar el mensaje del paciente.
// Por ahora puede apuntar al Python en :8000, luego al Go en :8081.
type AIClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewAIClient() *AIClient {
	url := os.Getenv("AI_SERVICE_URL")
	if url == "" {
		url = "http://localhost:8000" // por defecto apunta al Python actual
	}
	return &AIClient{
		baseURL:    url,
		httpClient: &http.Client{},
	}
}

type ProcessRequest struct {
	Numero  string `json:"numero"`
	Mensaje string `json:"mensaje"`
}

type ProcessResponse struct {
	Respuesta string `json:"respuesta"`
}

// ProcesarMensaje — envía el mensaje al ai-service y obtiene la respuesta
func (c *AIClient) ProcesarMensaje(numero, mensaje string) (string, error) {
	payload := ProcessRequest{
		Numero:  numero,
		Mensaje: mensaje,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("error al serializar: %w", err)
	}

	resp, err := c.httpClient.Post(
		c.baseURL+"/process",
		"application/json",
		bytes.NewBuffer(body),
	)
	if err != nil {
		return "", fmt.Errorf("error al llamar ai-service: %w", err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	var result ProcessResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return "", fmt.Errorf("error al parsear respuesta: %w", err)
	}

	return result.Respuesta, nil
}
