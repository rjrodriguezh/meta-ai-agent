package intent

import (
	"ai-service/internal/model"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// PersonaProvider permite inyectar el system prompt del bot sin importar ciclos.
type PersonaProvider interface {
	GetPersona() string
}

// Classifier llama a OpenAI para clasificar la intención del usuario.
// Equivale a interpretar_intencion_ia en intent_service.py
type Classifier struct {
	apiKey     string
	httpClient *http.Client
	persona    PersonaProvider
}

func NewClassifier(persona PersonaProvider) *Classifier {
	return &Classifier{
		apiKey:     os.Getenv("OPENAI_API_KEY"),
		httpClient: &http.Client{Timeout: 30 * time.Second},
		persona:    persona,
	}
}

func (c *Classifier) Clasificar(texto, numero string, sesion map[string]interface{}) (*model.Intent, error) {
	// Atajo rápido para reagendar (igual que Python)
	// Incluye "no puedo ir" / "no voy a poder" (Bug #3): el documento espera
	// que se ofrezca reagendar primero, no cancelar directo, cuando el
	// paciente avisa que no puede asistir sin pedir cancelación explícita.
	textoLower := strings.ToLower(strings.TrimSpace(texto))
	for _, kw := range []string{
		"reagendar", "cambiar cita", "cambiar hora", "mover cita", "mover hora",
		"no puedo ir", "no podre ir", "no podré ir", "no voy a poder", "no puedo asistir",
	} {
		if strings.Contains(textoLower, kw) {
			return &model.Intent{
				Intencion: "reagendar_hora",
				Datos:     map[string]interface{}{"texto_original": texto},
			}, nil
		}
	}

	hoy := time.Now().Format("2006-01-02")

	// Contexto de la clínica desde la persona dinámica
	personaCtx := ""
	if c.persona != nil {
		personaCtx = "\n\n--- CONTEXTO DE LA CLÍNICA Y ESTILO DEL BOT ---\n" + c.persona.GetPersona() + "\n---"
	}

	prompt := fmt.Sprintf(`Eres un clasificador de intenciones para una agenda kinésica por WhatsApp.%s
Fecha actual: %s

Tu tarea: analizar el mensaje y devolver SIEMPRE un JSON válido sin texto adicional.

Intenciones permitidas:
1. agendar_hora
2. reagendar_hora
3. cancelar_hora
4. consultar_horas
5. registrar_paciente
6. crear_ficha
7. marcar_sesion_realizada
8. consulta_precio
9. consulta_fonasa
10. consulta_servicios
11. saludo
12. ayuda
13. desconocida

Formato esperado:
{
  "intencion": "agendar_hora",
  "datos": {
    "nombre_paciente": null,
    "fecha": null,
    "hora": null,
    "horario_referencia": null,
    "diagnostico": null,
    "lesion": null,
    "cantidad_sesiones": null,
    "observacion": null,
    "tipo_prevision": null,
    "texto_original": ""
  },
  "faltan_datos": [],
  "confianza": "alta",
  "requiere_confirmacion": true
}

Reglas:
- Si dice "mañana", convierte a fecha YYYY-MM-DD.
- El campo "hora" SIEMPRE debe ir en formato 24 horas "HH:MM" (ej: "10:00", "16:00"). Nunca uses "am"/"pm" ni "10:00am"/"4:00 PM" — conviértelo tú antes de responder.
- Si menciona lesión/diagnóstico/sesiones sin agendar hora → "crear_ficha".
- Si dice cambiar/mover/reagendar → "reagendar_hora".
- Si pregunta por SUS citas, MIS horas, mis sesiones, historial personal, cuántas ME quedan, cuándo TENGO hora → "consultar_horas".
- Si pregunta por los horarios de atención del lugar, días que atienden, a qué hora abren/cierran, "¿qué horarios tienen?", "¿atienden los sábados?" → "consulta_servicios".
- Si pregunta precio/valor/cuánto cuesta → "consulta_precio".
- Si pregunta por FONASA/bono → "consulta_fonasa".
- Si pregunta qué servicios ofrecen → "consulta_servicios".
- Si ambiguo → "desconocida".`, personaCtx, hoy)

	contexto := map[string]interface{}{
		"numero":  numero,
		"sesion":  sesion,
		"mensaje": texto,
	}
	contextoJSON, _ := json.Marshal(contexto)

	payload := map[string]interface{}{
		"model":       "gpt-4o-mini",
		"temperature": 0,
		"messages": []map[string]string{
			{"role": "system", "content": prompt},
			{"role": "user", "content": string(contextoJSON)},
		},
	}

	body, _ := json.Marshal(payload)
	req, err := http.NewRequest("POST", "https://api.openai.com/v1/chat/completions",
		bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
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
		return intentDesconocida(texto), nil
	}

	contenido := strings.TrimSpace(openAIResp.Choices[0].Message.Content)
	// Limpiar markdown si OpenAI lo envuelve en ```json
	contenido = strings.TrimPrefix(contenido, "```json")
	contenido = strings.TrimPrefix(contenido, "```")
	contenido = strings.TrimSuffix(contenido, "```")

	var intent model.Intent
	if err := json.Unmarshal([]byte(contenido), &intent); err != nil {
		return intentDesconocida(texto), nil
	}

	if intent.Datos == nil {
		intent.Datos = map[string]interface{}{}
	}
	intent.Datos["texto_original"] = texto

	// Corrección determinística: si el mensaje menciona un día de la semana
	// explícito ("lunes", "martes", etc.) y la fecha que devolvió el modelo
	// no cae en ese día, la recalculamos en Go (GPT no siempre calcula bien
	// aritmética de fechas relativas).
	for nombre, wd := range diasSemana {
		if !strings.Contains(textoLower, nombre) {
			continue
		}
		fechaGPT, _ := intent.Datos["fecha"].(string)
		correcta := true
		if fechaGPT != "" {
			if t, err := time.Parse("2006-01-02", fechaGPT); err == nil && t.Weekday() == wd {
				correcta = false
			}
		}
		if fechaGPT == "" || correcta {
			intent.Datos["fecha"] = proximaFechaParaDia(wd)
		}
		break
	}

	return &intent, nil
}

// diasSemana mapea nombres de días en español a time.Weekday.
var diasSemana = map[string]time.Weekday{
	"domingo":   time.Sunday,
	"lunes":     time.Monday,
	"martes":    time.Tuesday,
	"miercoles": time.Wednesday,
	"miércoles": time.Wednesday,
	"jueves":    time.Thursday,
	"viernes":   time.Friday,
	"sabado":    time.Saturday,
	"sábado":    time.Saturday,
}

// proximaFechaParaDia calcula la fecha (YYYY-MM-DD) de la próxima ocurrencia
// de ese día de semana, estrictamente después de hoy.
func proximaFechaParaDia(wd time.Weekday) string {
	hoy := time.Now()
	dias := (int(wd) - int(hoy.Weekday()) + 7) % 7
	if dias == 0 {
		dias = 7
	}
	return hoy.AddDate(0, 0, dias).Format("2006-01-02")
}

func intentDesconocida(texto string) *model.Intent {
	return &model.Intent{
		Intencion: "desconocida",
		Datos:     map[string]interface{}{"texto_original": texto},
		Confianza: "baja",
	}
}
