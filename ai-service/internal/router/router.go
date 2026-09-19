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
	patients   *client.PatientsClient
	agenda     *client.AgendaClient
	calendar   *client.CalendarClient
	activities *client.ActivitiesClient
	dashboard  *client.DashboardClient
}

func NewRouter(patients *client.PatientsClient, agenda *client.AgendaClient, calendar *client.CalendarClient, activities *client.ActivitiesClient) *Router {
	return &Router{
		patients:   patients,
		agenda:     agenda,
		calendar:   calendar,
		activities: activities,
		dashboard:  client.NewDashboardClient(),
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

// esLeadInformacion detecta el mensaje típico de un lead nuevo desde
// anuncios de Meta/Google ("quiero más información") — Flujo 1 del
// documento, distinto de un saludo genérico (Bug #5).
func esLeadInformacion(texto string) bool {
	t := strings.ToLower(texto)
	return strings.Contains(t, "mas informacion") || strings.Contains(t, "más información") ||
		strings.Contains(t, "más info") || strings.Contains(t, "mas info")
}

// esConsultaDisponibilidad detecta preguntas por horas LIBRES reales
// ("¿qué horarios tienes disponibles?"), distinto de preguntar el horario
// general de atención ("¿a qué hora atienden?") — Bug #9.
func esConsultaDisponibilidad(texto string) bool {
	t := strings.ToLower(texto)
	return strings.Contains(t, "disponible") || strings.Contains(t, "disponibilidad") ||
		strings.Contains(t, "horas libres") || strings.Contains(t, "hay hora")
}

// esConsultaEjercicios detecta si el paciente está pidiendo los ejercicios
// asignados a su tratamiento (ej. "¿qué ejercicios me tocan?", "mándame mi
// rutina"). Se revisa como una regla determinística (no depende de que el
// clasificador de OpenAI la reconozca como una intención propia).
func esConsultaEjercicios(texto string) bool {
	t := strings.ToLower(texto)
	disparadores := []string{
		"ejercicio", "ejercicios", "mi rutina", "la rutina",
		"que hago en casa", "qué hago en casa",
	}
	for _, d := range disparadores {
		if strings.Contains(t, d) {
			return true
		}
	}
	return false
}

// esComandoMenu detecta si el mensaje ES (no solo contiene) una palabra de menú.
// Coincidencia exacta a propósito: evita que frases como "necesito ayuda con
// mi hombro" disparen el menú en vez de seguir el flujo normal.
func esComandoMenu(texto string) bool {
	t := strings.ToLower(strings.TrimSpace(texto))
	switch t {
	case "menu", "menú", "inicio", "ayuda", "opciones":
		return true
	}
	return false
}

func (r *Router) Ejecutar(numero string, intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	textoOriginal := getString(intent.Datos, "texto_original")
	seleccion := obtenerSeleccion(textoOriginal)
	accionPendiente := getString(sesion, "accion_pendiente")

	// --- Escape: resetea sesión desde cualquier estado a medias (mid-flujo) ---
	if accionPendiente != "" && esEscape(textoOriginal) {
		return map[string]interface{}{
			"respuesta":    "Diga 😊",
			"nueva_sesion": map[string]interface{}{},
		}
	}

	// --- Comando de menú explícito fuera de un flujo: siempre muestra opciones.
	// Usa coincidencia EXACTA (no "contains") para no capturar frases normales
	// como "necesito ayuda con mi hombro".
	if accionPendiente == "" && esComandoMenu(textoOriginal) {
		return map[string]interface{}{
			"respuesta":    "¿Qué necesitas?\n\n- Agendar una hora\n- Reagendar una hora\n- Cancelar una hora\n- Consultar tus horas",
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

	// --- Continuar agendar_hora si estaba pendiente (evita que la fecha de
	// seguimiento se malinterprete como reagendar_hora u otra intención) ---
	if accionPendiente == "agendar_hora" {
		return r.manejarAgendar(intent.Datos, sesion, paciente)
	}

	// --- Continuar flujo de previsión si estaba pendiente ---
	if accionPendiente == "esperando_fonasa" {
		return r.manejarRespuestaFonasa(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_tramo" {
		return r.manejarRespuestaTramo(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_isapre_particular" {
		return r.manejarRespuestaIsapreParticular(intent, sesion, paciente)
	}
	if accionPendiente == "ofreciendo_agendar_primera_cita" {
		return r.manejarOfrecerAgendar(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_lado_diagnostico" {
		return r.manejarLadoDiagnostico(intent, sesion, paciente)
	}
	if accionPendiente == "confirmar_ficha_nueva" {
		return r.confirmarFichaNueva(intent, sesion, paciente)
	}
	// --- Registro extendido (RUT/peso/altura) + diagnóstico guiado por zona ---
	if accionPendiente == "esperando_rut" {
		return r.manejarEsperandoRut(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_peso" {
		return r.manejarEsperandoPeso(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_altura" {
		return r.manejarEsperandoAltura(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_diagnostico" {
		return r.manejarEsperandoDiagnostico(intent, sesion, paciente)
	}
	if accionPendiente == "confirmar_diagnostico_sugerido" {
		return r.confirmarDiagnosticoSugerido(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_relato_diagnostico" {
		return r.manejarEsperandoRelatoDiagnostico(intent, sesion, paciente)
	}
	if accionPendiente == "esperando_eleccion_diagnostico" {
		return r.manejarEleccionDiagnostico(intent, sesion, paciente)
	}

	// --- FAQ temporal (fine-tuning Felipe) — ver faq_felipe.go ---
	if respuesta, ok := buscarFAQFelipe(textoOriginal); ok {
		return map[string]interface{}{
			"respuesta":    respuesta,
			"nueva_sesion": map[string]interface{}{},
		}
	}

	// --- Consulta de ejercicios asignados a la ficha activa ---
	if esConsultaEjercicios(textoOriginal) {
		return r.manejarConsultaEjercicios(paciente)
	}

	// NOTA: la detección de bilateral (esBilateral) se hace SOLO dentro de
	// manejarCrearFicha, sobre el diagnóstico real — no acá sobre cualquier
	// mensaje, porque " y "/" e " aparecen en frases normales sin relación
	// a diagnósticos (ej. "dirección, horarios y códigos") y disparaban
	// escaladas falsas que cortaban la conversación.

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
		// NOTA: esta rama es para un paciente YA registrado que en cualquier
		// momento de la conversación menciona una lesión/diagnóstico nuevo
		// (ej. "tengo dolor de rodilla" semanas después de su registro). Ahí
		// se mantiene el flujo histórico: primero se verifica si ya tiene una
		// ficha activa (Bug #6) antes de preguntar nada de diagnóstico — no
		// tiene sentido mostrarle el menú de zonas si ya tiene tratamiento
		// en curso y lo primero es resolver ese conflicto.
		// El flujo guiado por zona / "¿quisiste decir X?" (iniciarFlujoDiagnostico)
		// se usa en el registro de pacientes NUEVOS, ver completarRegistroPaciente
		// -> esperando_rut -> esperando_peso -> esperando_altura.
		return r.manejarCrearFicha(intent.Datos, paciente)
	case "marcar_sesion_realizada":
		return r.manejarMarcarRealizada(paciente)
	case "saludo":
		// Flujo 1 (lead desde Meta/Google): "quiero más información" no es un
		// saludo genérico, es un lead nuevo — el documento pide bienvenida +
		// preguntar por orden médica, no el menú de opciones (Bug #5).
		if esLeadInformacion(textoOriginal) {
			return map[string]interface{}{
				"respuesta":    "¡Hola! 👋 Gracias por escribirnos.\n\n¿Tiene orden médica de derivación de Kinesiología?",
				"nueva_sesion": map[string]interface{}{},
			}
		}
		return map[string]interface{}{
			"respuesta":    "¡Hola! 👋 ¿En qué puedo ayudarte?\n\nPuedo agendar, reagendar, cancelar o consultar tus horas.",
			"nueva_sesion": map[string]interface{}{},
		}
	case "consulta_precio", "consulta_fonasa":
		// La respuesta ("¿Por fonasa?" + saludo) la sigue generando OpenAI con
		// la persona completa (ya lo hace bien), pero ahora quedamos en un
		// estado real (esperando_fonasa) para que la SIGUIENTE respuesta del
		// paciente se procese de forma determinística en vez de perderse
		// (Bug #1).
		return map[string]interface{}{
			"intencion":    intent.Intencion,
			"nueva_sesion": map[string]interface{}{"accion_pendiente": "esperando_fonasa"},
		}
	case "consulta_servicios", "ayuda":
		// "¿Qué horarios tienes disponibles?" pide disponibilidad REAL, no el
		// horario general de atención — consultar el Calendar (Bug #9).
		if intent.Intencion == "consulta_servicios" && esConsultaDisponibilidad(textoOriginal) {
			return r.manejarConsultaDisponibilidad()
		}
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
