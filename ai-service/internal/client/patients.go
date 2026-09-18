package client

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
)

// PatientsClient llama al patients-service en :8083
type PatientsClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewPatientsClient() *PatientsClient {
	url := os.Getenv("PATIENTS_SERVICE_URL")
	if url == "" {
		url = "http://localhost:8083"
	}
	return &PatientsClient{baseURL: url, httpClient: &http.Client{}}
}

type Patient struct {
	ID          uint   `json:"pac_id"`
	NombreCorto string `json:"pac_nombre_corto"`
	Telefono    string `json:"pac_telefono"`
	Estado      string `json:"pac_estado"`
	Prevision   string `json:"pac_prevision"`
}

type Ficha struct {
	ID                 uint   `json:"fic_id"`
	PacID              uint   `json:"pac_id"`
	Diagnostico        string `json:"fic_diagnostico"`
	CantidadSesiones   int    `json:"fic_cantidad_sesiones"`
	SesionesRealizadas int    `json:"fic_sesiones_realizadas"`
	Estado             string `json:"fic_estado"`
}

func (c *PatientsClient) get(path string, out interface{}) error {
	resp, err := c.httpClient.Get(c.baseURL + path)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode == 404 {
		return fmt.Errorf("not found")
	}
	body, _ := io.ReadAll(resp.Body)
	return json.Unmarshal(body, out)
}

func (c *PatientsClient) post(path string, payload map[string]interface{}, out interface{}) error {
	b, _ := json.Marshal(payload)
	resp, err := c.httpClient.Post(c.baseURL+path, "application/json", strings.NewReader(string(b)))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return json.Unmarshal(body, out)
}

func (c *PatientsClient) put(path string) error {
	req, _ := http.NewRequest("PUT", c.baseURL+path, nil)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}

func (c *PatientsClient) putJSON(path string, payload map[string]interface{}) error {
	b, _ := json.Marshal(payload)
	req, err := http.NewRequest("PUT", c.baseURL+path, strings.NewReader(string(b)))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}

// GetByID — obtiene un paciente por su ID
func (c *PatientsClient) GetByID(pacID uint) (*Patient, error) {
	var p Patient
	if err := c.get(fmt.Sprintf("/patients/%d", pacID), &p); err != nil {
		return nil, err
	}
	return &p, nil
}

// GetByTelefono — equivale a obtener_paciente_por_telefono
func (c *PatientsClient) GetByTelefono(telefono string) (*Patient, error) {
	var p Patient
	if err := c.get("/patients/telefono/"+telefono, &p); err != nil {
		return nil, err
	}
	return &p, nil
}

// Create — equivale a crear_paciente
func (c *PatientsClient) Create(nombres, apellidos, telefono string) (*Patient, error) {
	var p Patient
	err := c.post("/patients", map[string]interface{}{
		"nombres":      nombres,
		"apellidos":    apellidos,
		"telefono":     telefono,
		"nombre_corto": nombres + " " + apellidos,
	}, &p)
	return &p, err
}

// GetFichaActiva — equivale a obtener_ficha_activa
func (c *PatientsClient) GetFichaActiva(pacID uint) (*Ficha, error) {
	var f Ficha
	if err := c.get(fmt.Sprintf("/patients/%d/fichas/activa", pacID), &f); err != nil {
		return nil, err
	}
	return &f, nil
}

// CreateFicha — equivale a crear_ficha
func (c *PatientsClient) CreateFicha(pacID uint, diagnostico string, sesiones int) (*Ficha, error) {
	var f Ficha
	err := c.post(fmt.Sprintf("/patients/%d/fichas", pacID), map[string]interface{}{
		"diagnostico":      diagnostico,
		"cantidad_sesiones": sesiones,
	}, &f)
	return &f, err
}

// SetPrevision — guarda la previsión del paciente (FONASA/ISAPRE/PARTICULAR)
// para poder diferenciar el mensaje de confirmación de cita más adelante.
func (c *PatientsClient) SetPrevision(pacID uint, prevision string) error {
	return c.putJSON(fmt.Sprintf("/patients/%d/prevision", pacID), map[string]interface{}{
		"prevision": prevision,
	})
}

// IncrementarSesion — equivale a incrementar_sesion_realizada
func (c *PatientsClient) IncrementarSesion(ficID uint) error {
	return c.put(fmt.Sprintf("/fichas/%d/incrementar", ficID))
}

// DisminuirSesion — equivale a disminuir_sesion_realizada
func (c *PatientsClient) DisminuirSesion(ficID uint) error {
	return c.put(fmt.Sprintf("/fichas/%d/disminuir", ficID))
}
