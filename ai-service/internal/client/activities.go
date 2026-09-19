package client

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"
)

// ActivitiesClient llama al activities-service en :8084 (catálogo de
// ejercicios y diagnósticos) para poder mandarle al paciente los ejercicios
// que le corresponden según su diagnóstico.
type ActivitiesClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewActivitiesClient() *ActivitiesClient {
	u := os.Getenv("ACTIVITIES_SERVICE_URL")
	if u == "" {
		u = "http://localhost:8084"
	}
	return &ActivitiesClient{baseURL: u, httpClient: &http.Client{Timeout: 5 * time.Second}}
}

type Ejercicio struct {
	ID           uint   `json:"eje_id"`
	Nombre       string `json:"eje_nombre"`
	Detalle      string `json:"eje_detalle"`
	LinkYoutube  string `json:"eje_link_youtube"`
	Series       int    `json:"eje_series"`
	Repeticiones int    `json:"eje_repeticiones"`
}

type Diagnostico struct {
	ID         uint        `json:"diag_id"`
	Nombre     string      `json:"diag_nombre"`
	Zona       string      `json:"diag_zona"`
	Ejercicios []Ejercicio `json:"ejercicios"`
}

// Disponible indica si hay un cliente configurado (siempre true, no depende
// de credenciales externas como el de Calendar).
func (c *ActivitiesClient) Disponible() bool {
	return c != nil
}

// ObtenerTodos devuelve el catálogo completo de diagnósticos (con sus
// ejercicios) — usado para armar el menú "elige tu diagnóstico" cuando el
// paciente indica una zona del cuerpo en vez de un diagnóstico exacto.
func (c *ActivitiesClient) ObtenerTodos() ([]Diagnostico, error) {
	resp, err := c.httpClient.Get(c.baseURL + "/diagnosticos")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var list []Diagnostico
	if err := json.Unmarshal(body, &list); err != nil {
		return nil, err
	}
	return list, nil
}

// BuscarPorDiagnostico busca el tipo de diagnóstico (y sus ejercicios) que
// mejor coincide con un texto libre — normalmente el fic_diagnostico de la
// ficha activa del paciente. Devuelve ErrNotFound si no hay coincidencias.
func (c *ActivitiesClient) BuscarPorDiagnostico(texto string) (*Diagnostico, error) {
	u := c.baseURL + "/diagnosticos/buscar?" + url.Values{"texto": {texto}}.Encode()
	resp, err := c.httpClient.Get(u)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode == 404 {
		return nil, ErrNotFound
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("activities-service error %d", resp.StatusCode)
	}
	body, _ := io.ReadAll(resp.Body)
	var d Diagnostico
	if err := json.Unmarshal(body, &d); err != nil {
		return nil, err
	}
	return &d, nil
}
