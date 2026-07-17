package router

import (
	"ai-service/internal/client"
	"ai-service/internal/model"
	"regexp"
	"strconv"
	"strings"
)

// Router despacha cada intención al handler correcto.
type Router struct {
	patients  *client.PatientsClient
	agenda    *client.AgendaClient
	calendar  *client.CalendarClient
	dashboard *client.DashboardClient
}

func NewRouter(patients *client.PatientsClient, agenda *client.AgendaClient, calendar *client.CalendarClient) *Router {
	return &Router{
		patients:  patients,
		agenda:    agenda,
		calendar:  calendar,
		dashboard: client.NewDashboardClient(),
	}
}

// palabrasEscape resetean la sesión desde cualquier estado
var palabrasEscape = []string{
	"menu", "menú", "inicio", "salir", "volver", "reset",
	"cancelar todo", "empezar de nuevo", "ayuda",
}

func esEscape(texto string) bool {
	t := strings.ToLower(strings.TrimSpace(texto))
	for _, kw := range palabrasEscape {
		if t == kw || strings.Contains(t, kw) {
			return true
		}
	}
	return false
}

func (r *Router) Ejecutar(numero string, intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	textoOriginal := getString(intent.Datos, "texto_original")
	seleccion := obtenerSeleccion(textoOriginal)
	accionPendiente := getString(sesion, "accion_pendiente")

	// --- Escape: resetea sesión desde cualquier estado ---
	if accionPendiente != "" && esEscape(textoOriginal) {
		return map[string]interface{}{
			"respuesta":    "Diga 😊",
			"nueva_sesion": map[string]interface{}{},
		}
	}

	// --- Máquina de estados ---
	if accionPendiente == "registrar_paciente" {
		return r.completarRegistroPaciente(numero, intent, sesion)
	}
	if accionPendiente == "confirmar_cancelacion_final" {
		return r.confirmarCancelacionFinal(intent, sesion)
	}
	if accionPendiente == "confirmar_cita_reagendar" {
		return r.confirmarCitaReagendar(intent, sesion)
	}
	if accionPendiente == "esperando_fecha_hora_reagendar" {
		return r.recibirFechaHoraReagendar(intent, sesion)
	}
	if accionPendiente == "confirmar_cancelacion" && seleccion != nil {
		return r.confirmarCancelacion(intent, sesion)
	}
	if accionPendiente == "confirmar_reagendar" && seleccion != nil {
		return r.confirmarReagendar(intent, sesion)
	}

	// --- Verificar paciente registrado ---
	paciente, err := r.patients.GetByTelefono(numero)
	if err != nil || paciente == nil {
		return map[string]interface{}{
			"respuesta": "Hola 👋 No tengo tu registro todavía.\n\nEscríbeme tu nombre y apellido para registrarte.",
			"nueva_sesion": map[string]interface{}{
				"accion_pendiente":   "registrar_paciente",
				"intencion_original": intent.Intencion,
			},
		}
	}

	// --- FAQ temporal (fine-tuning Felipe) — ver faq_felipe.go ---
	if respuesta, ok := buscarFAQFelipe(textoOriginal); ok {
		return map[string]interface{}{
			"respuesta":    respuesta,
			"nueva_sesion": map[string]interface{}{},
		}
	}

	// --- Diagnóstico con dos zonas/lados distintos → escalar a Felipe ---
	if esBilateral(textoOriginal) {
		return map[string]interface{}{
			"respuesta":    "Gracias por la información, en un momento Felipe te contacta personalmente para coordinar su tratamiento.",
			"nueva_sesion": map[string]interface{}{},
		}
	}

	// --- Despachar por intención ---
	switch intent.Intencion {
	case "agendar_hora":
		return r.manejarAgendar(intent.Datos, sesion, paciente)
	case "reagendar_hora":
		return r.manejarReagendar(intent.Datos, sesion, paciente)
	case "cancelar_hora":
		return r.manejarCancelar(sesion, paciente)
	case "consultar_horas", "consultar_sesiones":
		return r.manejarConsultar(paciente)
	case "crear_ficha":
		return r.manejarCrearFicha(intent.Datos, paciente)
	case "marcar_sesion_realizada":
		return r.manejarMarcarRealizada(paciente)
	case "saludo":
		return map[string]interface{}{
			"respuesta":    "¡Hola! 👋 ¿En qué puedo ayudarte?\n\nPuedo agendar, reagendar, cancelar o consultar tus horas.",
			"nueva_sesion": map[string]interface{}{},
		}
	case "consulta_precio", "consulta_fonasa", "consulta_servicios", "ayuda":
		// Sin respuesta hardcodeada → Natural llama a OpenAI con la persona completa
		return map[string]interface{}{
			"intencion":    intent.Intencion,
			"nueva_sesion": sesion,
		}
	default:
		// Tampoco hardcodeamos "no entendí": dejamos que OpenAI intente responder
		return map[string]interface{}{
			"intencion":    "desconocida",
			"nueva_sesion": sesion,
		}
	}
}

// --- Helpers ---

func getString(m map[string]interface{}, key string) string {
	if v, ok := m[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}

func getUintFromMap(m map[string]interface{}, key string) *uint {
	v, ok := m[key]
	if !ok {
		return nil
	}
	switch val := v.(type) {
	case float64:
		u := uint(val)
		return &u
	case int:
		u := uint(val)
		return &u
	}
	return nil
}

func getIntFromMap(m map[string]interface{}, key string, def int) int {
	v, ok := m[key]
	if !ok {
		return def
	}
	switch val := v.(type) {
	case float64:
		return int(val)
	case int:
		return val
	}
	return def
}

func obtenerSeleccion(texto string) *int {
	texto = strings.ToLower(strings.TrimSpace(texto))
	re := regexp.MustCompile(`\b(\d+)\b`)
	if match := re.FindStringSubmatch(texto); len(match) > 1 {
		n, _ := strconv.Atoi(match[1])
		return &n
	}
	palabras := map[string]int{
		"primera": 1, "segunda": 2, "tercera": 3, "cuarta": 4, "quinta": 5,
	}
	for p, n := range palabras {
		if strings.Contains(texto, p) {
			cp := n
			return &cp
		}
	}
	return nil
}

func mensajeCierre(msg string) string {
	return msg + "\n\n¿Necesitas algo más?\n\n" +
		"- Agendar una hora\n" +
		"- Consultar mis horas\n" +
		"- Reagendar una hora\n" +
		"- Cancelar una hora"
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
