package client

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

// ConfigClient obtiene la configuración del bot desde patients-service
// y la cachea para no llamar en cada mensaje.
type ConfigClient struct {
	baseURL    string
	httpClient *http.Client
	mu         sync.RWMutex
	cached     string
	cachedAt   time.Time
	cacheTTL   time.Duration
}

func NewConfigClient() *ConfigClient {
	base := os.Getenv("PATIENTS_SERVICE_URL")
	if base == "" {
		base = "http://localhost:8083"
	}
	return &ConfigClient{
		baseURL:    base,
		httpClient: &http.Client{Timeout: 5 * time.Second},
		cacheTTL:   5 * time.Minute,
	}
}

// GetPersona devuelve el system prompt / persona del bot.
// Si la caché es válida la usa directamente.
func (c *ConfigClient) GetPersona() string {
	c.mu.RLock()
	if c.cached != "" && time.Since(c.cachedAt) < c.cacheTTL {
		p := c.cached
		c.mu.RUnlock()
		return p
	}
	c.mu.RUnlock()

	persona := c.fetchPersona()

	c.mu.Lock()
	c.cached = persona
	c.cachedAt = time.Now()
	c.mu.Unlock()

	return persona
}

// Invalidate fuerza refresco en la próxima llamada (útil tras PUT /config/bot)
func (c *ConfigClient) Invalidate() {
	c.mu.Lock()
	c.cached = ""
	c.mu.Unlock()
}

func (c *ConfigClient) fetchPersona() string {
	resp, err := c.httpClient.Get(c.baseURL + "/config/bot")
	if err != nil {
		log.Printf("[ConfigClient] error fetching bot config: %v", err)
		return defaultPersona()
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var result struct {
		Persona string `json:"persona"`
		Activo  bool   `json:"activo"`
	}
	if err := json.Unmarshal(body, &result); err != nil || !result.Activo || result.Persona == "" {
		return defaultPersona()
	}
	return result.Persona
}

func defaultPersona() string {
	return `Eres un asistente de agenda kinésica por WhatsApp.
Responde de forma breve, clara y amable.
Ayudas a agendar, reagendar y cancelar citas.`
}
