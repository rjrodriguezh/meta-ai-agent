package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"
)

// CalendarClient llama al google-calendar-service.
type CalendarClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewCalendarClient() *CalendarClient {
	base := os.Getenv("CALENDAR_SERVICE_URL")
	if base == "" {
		base = "http://localhost:8085"
	}
	return &CalendarClient{
		baseURL:    base,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

// ClinicaUbicacion retorna la dirección configurada para la clínica.
func ClinicaUbicacion() string {
	loc := os.Getenv("CLINIC_LOCATION")
	if loc == "" {
		loc = "Clínica de Kinesiología Felipe Castillo"
	}
	return loc
}

// DisponibilidadDia retorna los slots libres para una fecha (YYYY-MM-DD).
func (c *CalendarClient) DisponibilidadDia(fecha string) ([]string, error) {
	url := fmt.Sprintf("%s/disponibilidad?fecha=%s", c.baseURL, fecha)
	resp, err := c.httpClient.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("calendar-service error %d: %s", resp.StatusCode, string(body))
	}
	var result struct {
		SlotsLibres []string `json:"slots_libres"`
		Disponible  bool     `json:"disponible"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result.SlotsLibres, nil
}

// ProximosDisponibles retorna días con slots libres para los próximos N días.
func (c *CalendarClient) ProximosDisponibles(dias int) ([]DiaDisponible, error) {
	url := fmt.Sprintf("%s/disponibilidad/proximos?dias=%d", c.baseURL, dias)
	resp, err := c.httpClient.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result struct {
		Dias []DiaDisponible `json:"dias"`
	}
	body, _ := io.ReadAll(resp.Body)
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result.Dias, nil
}

type DiaDisponible struct {
	Fecha       string   `json:"fecha"`
	DiaSemana   string   `json:"dia_semana"`
	SlotsLibres []string `json:"slots_libres"`
}

// CrearEvento crea un evento en Google Calendar. Retorna el event_id.
func (c *CalendarClient) CrearEvento(titulo, fecha, hora, descripcion, ubicacion string) (string, error) {
	payload := map[string]interface{}{
		"titulo":      titulo,
		"fecha":       fecha,
		"hora":        hora,
		"descripcion": descripcion,
		"ubicacion":   ubicacion,
	}
	body, _ := json.Marshal(payload)
	resp, err := c.httpClient.Post(
		c.baseURL+"/eventos",
		"application/json",
		bytes.NewBuffer(body),
	)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		EventID string `json:"event_id"`
	}
	respBody, _ := io.ReadAll(resp.Body)
	if err := json.Unmarshal(respBody, &result); err != nil {
		return "", err
	}
	log.Printf("[Calendar] Evento creado: %s", result.EventID)
	return result.EventID, nil
}

// EliminarEvento elimina un evento de Google Calendar por su ID.
func (c *CalendarClient) EliminarEvento(eventID string) error {
	url := fmt.Sprintf("%s/eventos/%s", c.baseURL, eventID)
	req, _ := http.NewRequest("DELETE", url, nil)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("calendar error %d: %s", resp.StatusCode, string(body))
	}
	log.Printf("[Calendar] Evento eliminado: %s", eventID)
	return nil
}

// Disponible indica si el calendar-service está activo.
func (c *CalendarClient) Disponible() bool {
	resp, err := c.httpClient.Get(c.baseURL + "/health")
	return err == nil && resp.StatusCode == 200
}
