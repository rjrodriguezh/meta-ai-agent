package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
)

// DashboardClient llama al dashboard-service en :5000
type DashboardClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewDashboardClient() *DashboardClient {
	url := os.Getenv("DASHBOARD_SERVICE_URL")
	if url == "" {
		url = "http://localhost:5000"
	}
	return &DashboardClient{baseURL: url, httpClient: &http.Client{}}
}

type notifyEmailRequest struct {
	PacID     uint   `json:"pac_id"`
	Evento    string `json:"evento"`
	Fecha     string `json:"fecha"`
	Hora      string `json:"hora"`
	AgenID    uint   `json:"agen_id"`
	FechaOrig string `json:"fecha_orig"`
	HoraOrig  string `json:"hora_orig"`
}

// NotifyEmail llama a /internal/notify-email en dashboard-service.
// Retorna el mensaje de notificación (ej. "[Email deshabilitado] Se notificaría a...")
// o string vacío si hay error.
func (c *DashboardClient) NotifyEmail(pacID uint, evento, fecha, hora string, agenID uint, fechaOrig, horaOrig string) string {
	body, _ := json.Marshal(notifyEmailRequest{
		PacID:     pacID,
		Evento:    evento,
		Fecha:     fecha,
		Hora:      hora,
		AgenID:    agenID,
		FechaOrig: fechaOrig,
		HoraOrig:  horaOrig,
	})
	resp, err := c.httpClient.Post(
		c.baseURL+"/internal/notify-email",
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		return fmt.Sprintf("(no se pudo notificar al paciente: %v)", err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	var out struct {
		Notif string `json:"notif"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return ""
	}
	return out.Notif
}
