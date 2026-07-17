package client

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
)

// AgendaClient llama al agenda-service en :8082
type AgendaClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewAgendaClient() *AgendaClient {
	url := os.Getenv("AGENDA_SERVICE_URL")
	if url == "" {
		url = "http://localhost:8082"
	}
	return &AgendaClient{baseURL: url, httpClient: &http.Client{}}
}

type Cita struct {
	ID          uint   `json:"agen_id"`
	PacID       uint   `json:"pac_id"`
	FicID       *uint  `json:"fic_id"`
	Fecha       string `json:"agen_fecha"`
	Hora        string `json:"agen_hora"`
	Estado      string `json:"agen_estado"`
	Realizada   string `json:"agen_realizada"`
	Observacion string `json:"agen_observacion"`
	CalEventID  string `json:"agen_cal_event_id"`
}

func (c *AgendaClient) doRequest(method, path string, payload map[string]interface{}) ([]byte, error) {
	var body io.Reader
	if payload != nil {
		b, _ := json.Marshal(payload)
		body = strings.NewReader(string(b))
	}
	req, err := http.NewRequest(method, c.baseURL+path, body)
	if err != nil {
		return nil, err
	}
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}

// GetByPatient — equivale a obtener_agenda_paciente
func (c *AgendaClient) GetByPatient(pacID uint) ([]Cita, error) {
	data, err := c.doRequest("GET", fmt.Sprintf("/agenda/paciente/%d", pacID), nil)
	if err != nil {
		return nil, err
	}
	var citas []Cita
	return citas, json.Unmarshal(data, &citas)
}

// HayDisponibilidad — equivale a hay_disponibilidad
func (c *AgendaClient) HayDisponibilidad(fecha, hora string) (bool, error) {
	data, err := c.doRequest("GET",
		fmt.Sprintf("/agenda/disponibilidad?fecha=%s&hora=%s", fecha, hora), nil)
	if err != nil {
		return false, err
	}
	var result struct {
		Disponible bool `json:"disponible"`
	}
	return result.Disponible, json.Unmarshal(data, &result)
}

// Crear — equivale a crear_agenda
func (c *AgendaClient) Crear(pacID uint, ficID *uint, fecha, hora string) (*Cita, error) {
	payload := map[string]interface{}{
		"pac_id": pacID,
		"fecha":  fecha,
		"hora":   hora,
	}
	if ficID != nil {
		payload["fic_id"] = *ficID
	}
	data, err := c.doRequest("POST", "/agenda", payload)
	if err != nil {
		return nil, err
	}
	var cita Cita
	return &cita, json.Unmarshal(data, &cita)
}

// Reagendar — equivale a reagendar
func (c *AgendaClient) Reagendar(agenID uint, nuevaFecha, nuevaHora string) error {
	_, err := c.doRequest("PUT",
		fmt.Sprintf("/agenda/%d/reagendar", agenID),
		map[string]interface{}{"nueva_fecha": nuevaFecha, "nueva_hora": nuevaHora})
	return err
}

// Cancelar — equivale a cancelar_agenda
func (c *AgendaClient) Cancelar(agenID uint) error {
	_, err := c.doRequest("PUT",
		fmt.Sprintf("/agenda/%d/cancelar", agenID), map[string]interface{}{})
	return err
}

// MarcarRealizada — equivale a marcar_agenda_realizada
func (c *AgendaClient) MarcarRealizada(agenID uint) error {
	_, err := c.doRequest("PUT",
		fmt.Sprintf("/agenda/%d/realizada", agenID), map[string]interface{}{})
	return err
}

// GetByID — retorna una cita por su ID
func (c *AgendaClient) GetByID(agenID uint) (*Cita, error) {
	data, err := c.doRequest("GET", fmt.Sprintf("/agenda/%d", agenID), nil)
	if err != nil {
		return nil, err
	}
	var cita Cita
	return &cita, json.Unmarshal(data, &cita)
}

// SetCalEventID — guarda el event_id de Google Calendar en la cita
func (c *AgendaClient) SetCalEventID(agenID uint, calEventID string) error {
	_, err := c.doRequest("PATCH", fmt.Sprintf("/agenda/%d/cal_event", agenID),
		map[string]interface{}{"cal_event_id": calEventID})
	return err
}

// GetPendientes — filtra solo citas activas (no canceladas ni realizadas)
// Equivale a obtener_pendientes en action_router.py
func (c *AgendaClient) GetPendientes(pacID uint) ([]Cita, error) {
	todas, err := c.GetByPatient(pacID)
	if err != nil {
		return nil, err
	}

	var pendientes []Cita
	for _, cita := range todas {
		estado := strings.ToLower(cita.Estado)
		realizada := strings.ToLower(cita.Realizada)
		if (estado == "agendada" || estado == "reagendada") && realizada != "si" {
			pendientes = append(pendientes, cita)
		}
	}
	return pendientes, nil
}
