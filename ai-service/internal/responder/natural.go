package responder

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// PersonaProvider permite inyectar el system prompt sin importar ciclos.
type PersonaProvider interface {
	GetPersona() string
}

// Natural genera respuestas en lenguaje humano usando OpenAI.
// Equivale a generar_respuesta_natural en ai_service.py
type Natural struct {
	apiKey     string
	httpClient *http.Client
	persona    PersonaProvider
}

func NewNatural(persona PersonaProvider) *Natural {
	return &Natural{
		apiKey:     os.Getenv("OPENAI_API_KEY"),
		httpClient: &http.Client{Timeout: 30 * time.Second},
		persona:    persona,
	}
}

// Generar — si el resultado ya trae respuesta la usa directamente,
// si no llama a OpenAI para redactarla con la voz del bot.
func (n *Natural) Generar(mensajeUsuario string, resultado map[string]interface{}) string {
	// Si el action router ya definió una respuesta, úsala directamente
	if respuesta, ok := resultado["respuesta"].(string); ok && respuesta != "" {
		return respuesta
	}

	// System prompt: persona del bot desde la configuración dinámica
	systemPrompt := "Redactas respuestas breves para WhatsApp de una clínica kinésica."
	if n.persona != nil {
		p := n.persona.GetPersona()
		if p != "" {
			systemPrompt = p
		}
	}

	intencion, _ := resultado["intencion"].(string)
	contextoExtra := ""
	switch intencion {
	case "consulta_precio":
		contextoExtra = "El paciente está preguntando por el precio o costo de las sesiones."
	case "consulta_fonasa":
		contextoExtra = "El paciente está preguntando sobre atención con FONASA, bono o prevision."
	case "consulta_servicios":
		contextoExtra = "El paciente está preguntando qué servicios ofrece la clínica."
	case "ayuda":
		contextoExtra = "El paciente quiere saber en qué le puedes ayudar."
	}
	if contextoExtra != "" {
		contextoExtra = "\nContexto: " + contextoExtra
	}

	prompt := fmt.Sprintf(`Responde directamente la consulta del paciente usando la información de tu contexto.%s

Mensaje del paciente: %s

Reglas:
- Máximo 2-3 líneas.
- Usa el estilo y tono definido en tu personalidad.
- Si no tienes la información exacta, di que puedes consultar. NUNCA inventes ni confirmes una dirección, precio, horario o dato que el paciente proponga si no coincide EXACTAMENTE con la información de tu contexto. Si el paciente sugiere un dato incorrecto (ej. una dirección distinta), corrígelo con el dato real en vez de validarlo.
- NO termines la respuesta con "Oka", "Ok", "Listo" ni ninguna palabra de cierre. Esas palabras solo se usan para CONFIRMAR acciones del paciente, no para cerrar respuestas informativas.
- NO agregues frases como "¿Necesitas algo más?" ni menús de opciones al final.`, contextoExtra, mensajeUsuario)

	payload := map[string]interface{}{
		"model":       "gpt-4o-mini",
		"temperature": 0.3,
		"messages": []map[string]string{
			{"role": "system", "content": systemPrompt},
			{"role": "user", "content": prompt},
		},
	}

	body, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", "https://api.openai.com/v1/chat/completions",
		bytes.NewBuffer(body))
	req.Header.Set("Authorization", "Bearer "+n.apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := n.httpClient.Do(req)
	if err != nil {
		return "Ocurrió un problema. Intenta nuevamente."
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	var openAIResp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.Unmarshal(respBody, &openAIResp); err != nil || len(openAIResp.Choices) == 0 {
		return "Ocurrió un problema. Intenta nuevamente."
	}

	return openAIResp.Choices[0].Message.Content
}
