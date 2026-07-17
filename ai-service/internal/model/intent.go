package model

// Intent — lo que devuelve OpenAI al clasificar el mensaje del usuario
// Equivale al JSON que retorna interpretar_intencion_ia en intent_service.py
type Intent struct {
	Intencion            string                 `json:"intencion"`
	Datos                map[string]interface{} `json:"datos"`
	FaltanDatos          []string               `json:"faltan_datos"`
	Confianza            string                 `json:"confianza"`
	RequiereConfirmacion bool                   `json:"requiere_confirmacion"`
}

// OpcionCita — una cita del menú de selección (reagendar/cancelar múltiples)
type OpcionCita struct {
	Numero  int    `json:"numero"`
	AgenID  uint   `json:"agen_id"`
	Fecha   string `json:"fecha"`
	Hora    string `json:"hora"`
}

// ActionResult — lo que devuelve cada handler del router
type ActionResult struct {
	Respuesta   string                 `json:"respuesta"`
	NuevaSesion map[string]interface{} `json:"nueva_sesion"`
	PacID       *uint                  `json:"pac_id,omitempty"`
	FicID       *uint                  `json:"fic_id,omitempty"`
	AgenID      *uint                  `json:"agen_id,omitempty"`
}

// ProcessRequest — lo que recibe el ai-service desde whatsapp-service
type ProcessRequest struct {
	Numero  string `json:"numero"`
	Mensaje string `json:"mensaje"`
}

// ProcessResponse — lo que devuelve al whatsapp-service
type ProcessResponse struct {
	Respuesta string `json:"respuesta"`
}
