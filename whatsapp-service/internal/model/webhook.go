package model

// WebhookPayload — payload unificado de Meta (WhatsApp e Instagram)
type WebhookPayload struct {
	Object string  `json:"object"`
	Entry  []Entry `json:"entry"`
}

// --- WhatsApp ---

type Entry struct {
	ID        string          `json:"id"`
	Changes   []Change        `json:"changes"`  // WhatsApp
	Messaging []IGMessaging   `json:"messaging"` // Instagram
}

type Change struct {
	Value Value  `json:"value"`
	Field string `json:"field"`
}

type Value struct {
	MessagingProduct string    `json:"messaging_product"`
	Messages         []Message `json:"messages"`
	Contacts         []Contact `json:"contacts"`
}

type Message struct {
	From string      `json:"from"`
	ID   string      `json:"id"`
	Type string      `json:"type"`
	Text MessageText `json:"text"`
}

type MessageText struct {
	Body string `json:"body"`
}

type Contact struct {
	Profile ContactProfile `json:"profile"`
	WaID    string         `json:"wa_id"`
}

type ContactProfile struct {
	Name string `json:"name"`
}

// --- Instagram ---

type IGMessaging struct {
	Sender    IGSender    `json:"sender"`
	Recipient IGRecipient `json:"recipient"`
	Timestamp int64       `json:"timestamp"`
	Message   IGMessage   `json:"message"`
}

type IGSender struct {
	ID string `json:"id"` // IGSID del usuario
}

type IGRecipient struct {
	ID string `json:"id"` // ID de la cuenta de Instagram de la clínica
}

type IGMessage struct {
	MID  string `json:"mid"`
	Text string `json:"text"`
}

// --- Plataforma normalizada (para ai-service) ---

type IncomingMessage struct {
	Numero    string // teléfono (WA) o IGSID (IG)
	Texto     string
	Plataforma string // "whatsapp" | "instagram"
}
