package router

import (
	"ai-service/internal/client"
	"ai-service/internal/model"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"
)

// --- AGENDAR ---

func (r *Router) manejarAgendar(datos map[string]interface{}, sesion map[string]interface{}, paciente *client.Patient) map[string]interface{} {
	fecha := getString(datos, "fecha")
	hora  := normalizarHora(getString(datos, "hora"))

	// Sin fecha → consultar Google Calendar para sugerir próximos días disponibles
	if fecha == "" {
		if r.calendar != nil && r.calendar.Disponible() {
			dias, err := r.calendar.ProximosDisponibles(3)
			if err == nil && len(dias) > 0 {
				sugerencia := fmt.Sprintf("¿Para qué día? Tengo disponible:\n")
				for _, d := range dias {
					slots := d.SlotsLibres
					if len(slots) > 3 {
						slots = slots[:3]
					}
					sugerencia += fmt.Sprintf("- %s (%s): %s\n", d.Fecha, d.DiaSemana, joinSlots(slots))
				}
				return map[string]interface{}{
					"respuesta":    sugerencia,
					"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID},
				}
			}
		}
		return map[string]interface{}{
			"respuesta":    "¿Para qué día quieres agendar la hora?",
			"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID},
		}
	}

	// Sin hora → consultar slots disponibles para esa fecha en Google Calendar
	if hora == "" {
		if r.calendar != nil && r.calendar.Disponible() {
			slots, err := r.calendar.DisponibilidadDia(fecha)
			if err == nil && len(slots) > 0 {
				mostrar := slots
				if len(mostrar) > 5 {
					mostrar = mostrar[:5]
				}
				return map[string]interface{}{
					"respuesta":    fmt.Sprintf("Para el %s tengo: %s\n\n(Solo horarios en punto, ej: 10:00)\n¿A qué hora?", fecha, joinSlots(mostrar)),
					"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID, "fecha": fecha},
				}
			} else if err == nil && len(slots) == 0 {
				return map[string]interface{}{
					"respuesta":    mensajeSinDisponibilidad(fecha),
					"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID},
				}
			}
		}
		return map[string]interface{}{
			"respuesta":    "¿A qué hora quieres agendar?",
			"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID, "fecha": fecha},
		}
	}

	// Reglas de negocio propias: día hábil (L-V) y hora en punto.
	// Se validan en Go, sin depender de que Google Calendar responda bien,
	// para que nunca se agende un fin de semana o una hora y media.
	if esFinDeSemana(fecha) || !esHoraEnPunto(hora) {
		return map[string]interface{}{
			"respuesta":    mensajeHorarioInvalido(fecha),
			"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID, "fecha": fecha},
		}
	}

	// Verificar disponibilidad en Google Calendar primero, luego en agenda local
	if r.calendar != nil && r.calendar.Disponible() {
		slots, err := r.calendar.DisponibilidadDia(fecha)
		if err != nil {
			// Google Calendar falló (ej: credenciales inválidas) — no agendar a
			// ciegas, usar la agenda local como respaldo en vez de omitir la
			// validación por completo.
			log.Printf("[Calendar] DisponibilidadDia error, usando fallback local: %v", err)
			disponible, _ := r.agenda.HayDisponibilidad(fecha, hora)
			if !disponible {
				return map[string]interface{}{
					"respuesta":    fmt.Sprintf("La hora %s del %s no está disponible. Indica otro horario.", hora, fecha),
					"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID},
				}
			}
		} else {
			libre := false
			for _, s := range slots {
				if s == hora || s == hora+":00" {
					libre = true
					break
				}
			}
			if !libre {
				msg := "Solo agendamos en horarios en punto (ej: 10:00, 11:00), no en horas y media."
				if len(slots) > 0 {
					mostrar := slots
					if len(mostrar) > 6 {
						mostrar = mostrar[:6]
					}
					msg += fmt.Sprintf("\n\nPara el %s tengo disponible: %s\n¿A qué hora?", fecha, joinSlots(mostrar))
				} else {
					msg = mensajeSinDisponibilidad(fecha)
				}
				return map[string]interface{}{
					"respuesta":    msg,
					"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID, "fecha": fecha},
				}
			}
		}
	} else {
		// Fallback: verificar solo en agenda local
		disponible, _ := r.agenda.HayDisponibilidad(fecha, hora)
		if !disponible {
			return map[string]interface{}{
				"respuesta":    fmt.Sprintf("La hora %s del %s no está disponible. Indica otro horario.", hora, fecha),
				"nueva_sesion": map[string]interface{}{"accion_pendiente": "agendar_hora", "pac_id": paciente.ID},
			}
		}
	}

	ficha, _ := r.patients.GetFichaActiva(paciente.ID)
	var ficID *uint
	if ficha != nil {
		ficID = &ficha.ID
	}

	cita, err := r.agenda.Crear(paciente.ID, ficID, fecha, hora)
	if err != nil {
		return map[string]interface{}{"respuesta": "No pude agendar la hora. Intenta nuevamente.", "nueva_sesion": map[string]interface{}{}}
	}

	// Crear evento en Google Calendar con descripción enriquecida
	if r.calendar != nil && r.calendar.Disponible() {
		diagnostico := ""
		if ficha != nil {
			diagnostico = ficha.Diagnostico
		}
		titulo := fmt.Sprintf("%s — Cita #%d — %s", diagnostico, cita.ID, paciente.NombreCorto)
		if diagnostico == "" {
			titulo = fmt.Sprintf("Cita #%d — %s", cita.ID, paciente.NombreCorto)
		}
		ubicacion := client.ClinicaUbicacion()
		mapsURL   := "https://maps.google.com/?q=San+Antonio+418,+Santiago,+Chile"
		desc := fmt.Sprintf("👤 Paciente: %s\n📞 Teléfono: %s", paciente.NombreCorto, paciente.Telefono)
		if ficha != nil {
			pendientes := ficha.CantidadSesiones - ficha.SesionesRealizadas
			desc += fmt.Sprintf("\n\n📋 Ficha #%d: %s\n✅ Sesiones: %d realizadas de %d totales — %d pendientes",
				ficha.ID, ficha.Diagnostico, ficha.SesionesRealizadas, ficha.CantidadSesiones, pendientes)
		}
		desc += fmt.Sprintf("\n\n📌 Instrucciones:\n• Llevar ropa cómoda y zapatillas\n• No aplicar cremas en la zona afectada\n• FONASA: traer bonos y orden médica\n\n🩺 Felipe Castillo y Tomas Sepúlveda\n📍 %s\n🗺 %s", ubicacion, mapsURL)
		eventID, calErr := r.calendar.CrearEvento(titulo, fecha, hora, desc, ubicacion)
		if calErr != nil {
			log.Printf("[Calendar] ERROR al crear evento: %v", calErr)
		} else {
			log.Printf("[Calendar] Evento creado OK: %s", eventID)
			r.agenda.SetCalEventID(cita.ID, eventID)
		}
	} else {
		log.Printf("[Calendar] Skipping GCal — calendar=%v disponible=%v", r.calendar != nil, r.calendar != nil && r.calendar.Disponible())
	}

	notif := ""
	if r.dashboard != nil {
		notif = r.dashboard.NotifyEmail(paciente.ID, "agendada", fecha, hora, cita.ID, "", "")
	}
	respuesta := fmt.Sprintf("Listo %s. Quedas agendado/a el %s a las %s.\nLleva ropa cómoda y zapatillas.", paciente.NombreCorto, fecha, hora)
	if notif != "" {
		respuesta += "\n\n📩 " + notif
	}
	return map[string]interface{}{
		"respuesta":    respuesta,
		"nueva_sesion": map[string]interface{}{},
		"pac_id":       paciente.ID,
		"agen_id":      cita.ID,
	}
}

func joinSlots(slots []string) string {
	return strings.Join(slots, " | ")
}

// esFinDeSemana indica si la fecha (YYYY-MM-DD) cae sábado o domingo.
func esFinDeSemana(fecha string) bool {
	t, err := time.Parse("2006-01-02", fecha)
	if err != nil {
		return false
	}
	wd := t.Weekday()
	return wd == time.Saturday || wd == time.Sunday
}

// normalizarHora convierte formatos como "10:00am", "4:00 PM", "16:00" a "HH:MM"
// en 24 horas. Si no puede interpretarla, devuelve el string original tal cual.
func normalizarHora(hora string) string {
	h := strings.ToLower(strings.TrimSpace(hora))
	if h == "" {
		return hora
	}
	esPM := strings.Contains(h, "pm")
	esAM := strings.Contains(h, "am")
	h = strings.ReplaceAll(h, "pm", "")
	h = strings.ReplaceAll(h, "am", "")
	h = strings.TrimSpace(h)

	partes := strings.Split(h, ":")
	if len(partes) < 2 {
		return hora
	}
	hh, err1 := strconv.Atoi(strings.TrimSpace(partes[0]))
	mm, err2 := strconv.Atoi(strings.TrimSpace(strings.Split(partes[1], " ")[0]))
	if err1 != nil || err2 != nil {
		return hora
	}
	if esPM && hh < 12 {
		hh += 12
	}
	if esAM && hh == 12 {
		hh = 0
	}
	return fmt.Sprintf("%02d:%02d", hh, mm)
}

// esHoraEnPunto exige horarios en punto (HH:00) — no se agenda en horas y media.
func esHoraEnPunto(hora string) bool {
	partes := strings.Split(hora, ":")
	if len(partes) != 2 {
		return false
	}
	return partes[1] == "00"
}

// mensajeHorarioInvalido explica por qué la fecha/hora pedida no es válida.
func mensajeHorarioInvalido(fecha string) string {
	if esFinDeSemana(fecha) {
		return "Atendemos de lunes a viernes. Indica un día entre esos y un horario en punto (ej: 10:00, 11:00), no en horas y media."
	}
	return "Solo agendamos en horarios en punto (ej: 10:00, 11:00), no en horas y media. ¿A qué hora te acomoda?"
}

// mensajeSinDisponibilidad arma el mensaje cuando no hay horas para una fecha.
// Si cae fin de semana, aclara que solo se atiende de lunes a viernes y pide
// un día y horario en punto; si es un día hábil sin cupos, pide otro día.
func mensajeSinDisponibilidad(fecha string) string {
	if esFinDeSemana(fecha) {
		return "Atendemos de lunes a viernes. Indica un día entre esos y un horario en punto (ej: 10:00, 11:00), no en horas y media."
	}
	return fmt.Sprintf("No tengo horas disponibles para el %s. Indica otro día entre semana.", fecha)
}

// --- REAGENDAR ---

func (r *Router) manejarReagendar(datos map[string]interface{}, sesion map[string]interface{}, paciente *client.Patient) map[string]interface{} {
	fecha := getString(datos, "fecha")
	hora := getString(datos, "hora")

	pendientes, _ := r.agenda.GetPendientes(paciente.ID)
	if len(pendientes) == 0 {
		return map[string]interface{}{"respuesta": "No encontré citas pendientes para reagendar.", "nueva_sesion": map[string]interface{}{}}
	}

	if len(pendientes) > 1 {
		texto := "Tienes varias horas pendientes:\n\n"
		opciones := []map[string]interface{}{}
		for i, c := range pendientes[:minInt(len(pendientes), 10)] {
			texto += fmt.Sprintf("%d. %s a las %s\n", i+1, c.Fecha, c.Hora)
			opciones = append(opciones, map[string]interface{}{"numero": i + 1, "agen_id": c.ID, "fecha": c.Fecha, "hora": c.Hora})
		}
		return map[string]interface{}{
			"respuesta": texto + "\n¿Cuál quieres reagendar?",
			"nueva_sesion": map[string]interface{}{
				"accion_pendiente": "confirmar_reagendar", "opciones_reagendar": opciones,
				"nueva_fecha": fecha, "nueva_hora": hora,
			},
		}
	}

	cita := pendientes[0]
	if fecha == "" || hora == "" {
		return map[string]interface{}{
			"respuesta": "¿Para qué fecha y hora quieres mover la cita?",
			"nueva_sesion": map[string]interface{}{
				"accion_pendiente": "esperando_fecha_hora_reagendar",
				"agen_id_reagendar": cita.ID, "fecha_original": cita.Fecha, "hora_original": cita.Hora,
			},
		}
	}

	disponible, _ := r.agenda.HayDisponibilidad(fecha, hora)
	if !disponible {
		return map[string]interface{}{"respuesta": fmt.Sprintf("La hora %s del %s no está disponible.", hora, fecha), "nueva_sesion": map[string]interface{}{}}
	}
	r.agenda.Reagendar(cita.ID, fecha, hora)
	return map[string]interface{}{
		"respuesta":    mensajeCierre(fmt.Sprintf("Listo. Moví tu cita para %s a las %s.", fecha, hora)),
		"nueva_sesion": map[string]interface{}{},
	}
}

func (r *Router) confirmarReagendar(intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	texto := getString(intent.Datos, "texto_original")
	seleccion := obtenerSeleccion(texto)
	opcionesRaw, _ := sesion["opciones_reagendar"].([]interface{})

	var opcion map[string]interface{}
	for _, o := range opcionesRaw {
		if om, ok := o.(map[string]interface{}); ok {
			if n := getUintFromMap(om, "numero"); n != nil && seleccion != nil && int(*n) == *seleccion {
				opcion = om
				break
			}
		}
	}
	if opcion == nil {
		return map[string]interface{}{"respuesta": "No entendí cuál quieres reagendar. Indica 1, 2 o 3.", "nueva_sesion": sesion}
	}
	agenID := getUintFromMap(opcion, "agen_id")
	return map[string]interface{}{
		"respuesta": fmt.Sprintf("Elegiste la cita del %s a las %s.\n\n¿Confirmas que quieres moverla?", getString(opcion, "fecha"), getString(opcion, "hora")),
		"nueva_sesion": map[string]interface{}{
			"accion_pendiente": "confirmar_cita_reagendar",
			"agen_id_reagendar": *agenID, "fecha_original": getString(opcion, "fecha"), "hora_original": getString(opcion, "hora"),
		},
	}
}

func (r *Router) confirmarCitaReagendar(intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	texto := strings.ToLower(strings.TrimSpace(getString(intent.Datos, "texto_original")))
	for _, p := range []string{"si", "sí", "confirmo", "ok", "dale", "ya"} {
		if texto == p {
			return map[string]interface{}{
				"respuesta": "Perfecto. ¿Para qué fecha y hora quieres moverla?",
				"nueva_sesion": map[string]interface{}{
					"accion_pendiente": "esperando_fecha_hora_reagendar",
					"agen_id_reagendar": sesion["agen_id_reagendar"],
					"fecha_original": sesion["fecha_original"], "hora_original": sesion["hora_original"],
				},
			}
		}
	}
	if texto == "no" || texto == "nop" {
		return map[string]interface{}{"respuesta": "Ok, no hice cambios.", "nueva_sesion": map[string]interface{}{}}
	}
	return map[string]interface{}{"respuesta": "¿Confirmas? Respóndeme sí o no.", "nueva_sesion": sesion}
}

func (r *Router) recibirFechaHoraReagendar(intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	nuevaFecha := getString(intent.Datos, "fecha")
	nuevaHora := getString(intent.Datos, "hora")
	if nuevaFecha == "" || nuevaHora == "" {
		return map[string]interface{}{"respuesta": "Necesito fecha y hora. Ej: mañana a las 18:00.", "nueva_sesion": sesion}
	}
	disponible, _ := r.agenda.HayDisponibilidad(nuevaFecha, nuevaHora)
	if !disponible {
		return map[string]interface{}{"respuesta": fmt.Sprintf("La hora %s del %s no está disponible.", nuevaHora, nuevaFecha), "nueva_sesion": sesion}
	}
	agenID := getUintFromMap(sesion, "agen_id_reagendar")
	if agenID == nil {
		return map[string]interface{}{"respuesta": "Error en sesión. Intenta nuevamente.", "nueva_sesion": map[string]interface{}{}}
	}
	// Sincronizar Google Calendar: eliminar evento viejo y crear nuevo
	if r.calendar != nil && r.calendar.Disponible() {
		if cita, err := r.agenda.GetByID(*agenID); err == nil {
			if cita.CalEventID != "" {
				if delErr := r.calendar.EliminarEvento(cita.CalEventID); delErr != nil {
					log.Printf("[Calendar] ERROR al eliminar evento viejo %s: %v", cita.CalEventID, delErr)
				}
			}
			// Construir descripción completa igual que al agendar
			paciente, _ := r.patients.GetByID(cita.PacID)
			ficha, _     := r.patients.GetFichaActiva(cita.PacID)
			nombrePac := ""
			if paciente != nil {
				nombrePac = paciente.NombreCorto
			}
			titulo := fmt.Sprintf("Cita #%d — %s (reagendada)", *agenID, nombrePac)
			desc   := fmt.Sprintf("👤 Paciente: %s\n📞 Teléfono: %s", nombrePac, func() string {
				if paciente != nil { return paciente.Telefono }; return ""
			}())
			if ficha != nil {
				pendientes := ficha.CantidadSesiones - ficha.SesionesRealizadas
				desc += fmt.Sprintf("\n\n📋 Ficha #%d: %s\n✅ Sesiones: %d realizadas de %d totales — %d pendientes",
					ficha.ID, ficha.Diagnostico, ficha.SesionesRealizadas, ficha.CantidadSesiones, pendientes)
			}
			desc += "\n\n📌 Instrucciones:\n• Llevar ropa cómoda y zapatillas\n• No aplicar cremas en la zona afectada\n• FONASA: traer bonos y orden médica"
			desc += fmt.Sprintf("\n\n🩺 Felipe Castillo y Tomas Sepúlveda\n📍 %s\n🗺 https://maps.google.com/?q=San+Antonio+418,+Santiago,+Chile", client.ClinicaUbicacion())
			desc += fmt.Sprintf("\n\n📅 Reagendado desde %s %s", getString(sesion, "fecha_original"), getString(sesion, "hora_original"))
			newEventID, calErr := r.calendar.CrearEvento(titulo, nuevaFecha, nuevaHora, desc, client.ClinicaUbicacion())
			if calErr != nil {
				log.Printf("[Calendar] ERROR al crear evento reagendado: %v", calErr)
			} else {
				r.agenda.SetCalEventID(*agenID, newEventID)
				log.Printf("[Calendar] Evento reagendado OK: %s", newEventID)
			}
		}
	}
	r.agenda.Reagendar(*agenID, nuevaFecha, nuevaHora)
	notif := ""
	if r.dashboard != nil {
		fechaOrig := getString(sesion, "fecha_original")
		horaOrig  := getString(sesion, "hora_original")
		// paciente viene del bloque if de calendar arriba; si no, lo buscamos
		pacID := uint(0)
		if cita, err := r.agenda.GetByID(*agenID); err == nil {
			pacID = cita.PacID
		}
		if pacID > 0 {
			notif = r.dashboard.NotifyEmail(pacID, "reagendada", nuevaFecha, nuevaHora, *agenID, fechaOrig, horaOrig)
		}
	}
	resp := mensajeCierre(fmt.Sprintf("Listo. Moví tu cita del %s a las %s para %s a las %s.",
		getString(sesion, "fecha_original"), getString(sesion, "hora_original"), nuevaFecha, nuevaHora))
	if notif != "" {
		resp += "\n\n📩 " + notif
	}
	return map[string]interface{}{
		"respuesta":    resp,
		"nueva_sesion": map[string]interface{}{},
	}
}

// --- CANCELAR ---

func (r *Router) manejarCancelar(sesion map[string]interface{}, paciente *client.Patient) map[string]interface{} {
	pendientes, _ := r.agenda.GetPendientes(paciente.ID)
	if len(pendientes) == 0 {
		return map[string]interface{}{"respuesta": "No encontré horas pendientes para cancelar.", "nueva_sesion": map[string]interface{}{}}
	}
	if len(pendientes) > 1 {
		texto := "Tienes varias horas pendientes:\n\n"
		opciones := []map[string]interface{}{}
		for i, c := range pendientes[:minInt(len(pendientes), 10)] {
			texto += fmt.Sprintf("%d. %s a las %s\n", i+1, c.Fecha, c.Hora)
			opciones = append(opciones, map[string]interface{}{"numero": i + 1, "agen_id": c.ID, "fecha": c.Fecha, "hora": c.Hora})
		}
		return map[string]interface{}{
			"respuesta":    texto + "\n¿Cuál quieres cancelar?",
			"nueva_sesion": map[string]interface{}{"accion_pendiente": "confirmar_cancelacion", "opciones_cancelacion": opciones},
		}
	}
	cita := pendientes[0]
	return map[string]interface{}{
		"respuesta": fmt.Sprintf("Elegiste cancelar la cita del %s a las %s.\n\nEscribe CANCELAR para confirmar.", cita.Fecha, cita.Hora),
		"nueva_sesion": map[string]interface{}{
			"accion_pendiente": "confirmar_cancelacion_final",
			"agen_id_cancelar": cita.ID, "fecha_original": cita.Fecha, "hora_original": cita.Hora,
		},
	}
}

func (r *Router) confirmarCancelacion(intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	seleccion := obtenerSeleccion(getString(intent.Datos, "texto_original"))
	opcionesRaw, _ := sesion["opciones_cancelacion"].([]interface{})
	var opcion map[string]interface{}
	for _, o := range opcionesRaw {
		if om, ok := o.(map[string]interface{}); ok {
			if n := getUintFromMap(om, "numero"); n != nil && seleccion != nil && int(*n) == *seleccion {
				opcion = om
				break
			}
		}
	}
	if opcion == nil {
		return map[string]interface{}{"respuesta": "No entendí cuál quieres cancelar. Indica 1, 2 o 3.", "nueva_sesion": sesion}
	}
	agenID := getUintFromMap(opcion, "agen_id")
	return map[string]interface{}{
		"respuesta": fmt.Sprintf("Elegiste cancelar la cita del %s a las %s.\n\nEscribe CANCELAR para confirmar.", getString(opcion, "fecha"), getString(opcion, "hora")),
		"nueva_sesion": map[string]interface{}{
			"accion_pendiente": "confirmar_cancelacion_final",
			"agen_id_cancelar": *agenID, "fecha_original": getString(opcion, "fecha"), "hora_original": getString(opcion, "hora"),
		},
	}
}

func (r *Router) confirmarCancelacionFinal(intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	texto := strings.TrimSpace(strings.ToLower(getString(intent.Datos, "texto_original")))
	if texto != "cancelar" {
		return map[string]interface{}{"respuesta": "Para confirmar, escribe CANCELAR.", "nueva_sesion": sesion}
	}
	agenID := getUintFromMap(sesion, "agen_id_cancelar")
	if agenID == nil {
		return map[string]interface{}{"respuesta": "Error en sesión.", "nueva_sesion": map[string]interface{}{}}
	}
	// Eliminar evento de Google Calendar si existe
	if r.calendar != nil && r.calendar.Disponible() {
		if cita, err := r.agenda.GetByID(*agenID); err == nil && cita.CalEventID != "" {
			if delErr := r.calendar.EliminarEvento(cita.CalEventID); delErr != nil {
				log.Printf("[Calendar] ERROR al eliminar evento %s: %v", cita.CalEventID, delErr)
			} else {
				log.Printf("[Calendar] Evento eliminado OK: %s", cita.CalEventID)
			}
		}
	}
	fechaOrig := getString(sesion, "fecha_original")
	horaOrig  := getString(sesion, "hora_original")
	// Obtener pac_id antes de cancelar
	pacID := uint(0)
	if cita, err := r.agenda.GetByID(*agenID); err == nil {
		pacID = cita.PacID
	}
	r.agenda.Cancelar(*agenID)
	notif := ""
	if r.dashboard != nil && pacID > 0 {
		notif = r.dashboard.NotifyEmail(pacID, "cancelada", fechaOrig, horaOrig, *agenID, "", "")
	}
	resp := mensajeCierre(fmt.Sprintf("Listo. Cancelé la cita del %s a las %s.", fechaOrig, horaOrig))
	if notif != "" {
		resp += "\n\n📩 " + notif
	}
	return map[string]interface{}{
		"respuesta":    resp,
		"nueva_sesion": map[string]interface{}{},
	}
}

// --- CONSULTAR HORAS (unifica consultar citas + sesiones) ---

func (r *Router) manejarConsultar(paciente *client.Patient) map[string]interface{} {
	var texto string

	// 1. Obtener todas las citas para contar y detallar
	todas, _ := r.agenda.GetByPatient(paciente.ID)
	var realizadas []client.Cita
	for _, c := range todas {
		if strings.ToLower(c.Realizada) == "si" || strings.ToLower(c.Estado) == "realizada" {
			realizadas = append(realizadas, c)
		}
	}

	// 2. Ficha activa
	ficha, _ := r.patients.GetFichaActiva(paciente.ID)
	if ficha != nil {
		// Usar el máximo entre el contador de la ficha y las citas reales (por si están desincronizados)
		nRealizadas := ficha.SesionesRealizadas
		if len(realizadas) > nRealizadas {
			nRealizadas = len(realizadas)
		}
		pendientes := ficha.CantidadSesiones - nRealizadas
		if pendientes < 0 {
			pendientes = 0
		}
		texto += fmt.Sprintf("📋 Ficha activa por *%s*.\n", ficha.Diagnostico)
		texto += fmt.Sprintf("Sesiones totales: %d\n", ficha.CantidadSesiones)
		texto += fmt.Sprintf("Realizadas: %d\n", nRealizadas)

		// 3. Detalle de sesiones realizadas (máx 5 más recientes)
		if len(realizadas) > 0 {
			inicio := len(realizadas) - minInt(len(realizadas), 5)
			for _, c := range realizadas[inicio:] {
				linea := fmt.Sprintf("  · %s", c.Fecha)
				if resumen := resumirObservacion(c.Observacion); resumen != "" {
					linea += ": " + resumen
				}
				texto += linea + "\n"
			}
		}

		texto += fmt.Sprintf("Pendientes: %d\n\n", pendientes)
	}

	// 4. Próximas citas agendadas
	var futuras []client.Cita
	for _, c := range todas {
		estado := strings.ToLower(c.Estado)
		if (estado == "agendada" || estado == "reagendada") && strings.ToLower(c.Realizada) != "si" {
			futuras = append(futuras, c)
		}
	}

	if len(futuras) == 0 {
		if ficha == nil {
			return map[string]interface{}{"respuesta": "No encontré citas ni ficha activa.", "nueva_sesion": map[string]interface{}{}}
		}
		texto += "No tienes horas agendadas próximas."
	} else {
		texto += "Estas son tus próximas horas:\n"
		for _, c := range futuras[:minInt(len(futuras), 5)] {
			texto += fmt.Sprintf("- %s a las %s (%s)\n", c.Fecha, c.Hora[:5], strings.ToUpper(c.Estado))
		}
	}

	return map[string]interface{}{"respuesta": strings.TrimSpace(texto), "nueva_sesion": map[string]interface{}{}}
}

// esBilateral detecta si el diagnóstico menciona zonas corporales distintas o lados distintos.
// resumirObservacion extrae un resumen compacto de la observación guardada.
// Formato esperado:
//
//	Ejercicios realizados:
//	  • Curl de bíceps con banda — 3 series × 12 reps
//	  • Sentadilla a silla — 3 series × 10 reps
//
//	Texto libre de observación
func resumirObservacion(obs string) string {
	obs = strings.TrimSpace(obs)
	if obs == "" {
		return ""
	}
	lineas := strings.Split(obs, "\n")

	var ejercicios []string
	var textoLibre []string
	enEjercicios := false

	for _, l := range lineas {
		l = strings.TrimSpace(l)
		if l == "" {
			enEjercicios = false
			continue
		}
		if strings.HasPrefix(l, "Ejercicios realizados") {
			enEjercicios = true
			continue
		}
		if enEjercicios && strings.HasPrefix(l, "•") {
			// "• Curl de bíceps con banda — 3 series × 12 reps"
			// Solo queremos el nombre (antes del " — ")
			nombre := strings.TrimPrefix(l, "•")
			nombre = strings.TrimSpace(nombre)
			if idx := strings.Index(nombre, " — "); idx > 0 {
				nombre = nombre[:idx]
			}
			ejercicios = append(ejercicios, nombre)
		} else if !enEjercicios {
			textoLibre = append(textoLibre, l)
		}
	}

	partes := []string{}
	if len(ejercicios) > 0 {
		partes = append(partes, strings.Join(ejercicios, ", "))
	}
	if len(textoLibre) > 0 {
		nota := strings.Join(textoLibre, " ")
		if len(nota) > 50 {
			nota = nota[:50] + "…"
		}
		partes = append(partes, nota)
	}
	return strings.Join(partes, " · ")
}

func esBilateral(diagnostico string) bool {
	d := strings.ToLower(diagnostico)

	// Palabras que indican dos zonas distintas
	indicadoresBilateral := []string{
		" y ", " e ", "ambos", "ambas", "bilateral", "dos rodillas",
		"dos hombros", "dos pies", "dos tobillos",
	}
	for _, ind := range indicadoresBilateral {
		if strings.Contains(d, ind) {
			// Verificar que no sea el mismo lado (ej: "rodilla y pierna derecha" = una parte)
			mismoLado := (strings.Contains(d, "derech") && !strings.Contains(d, "izquierd")) ||
				(strings.Contains(d, "izquierd") && !strings.Contains(d, "derech"))
			if !mismoLado {
				return true
			}
		}
	}
	return false
}

func (r *Router) manejarCrearFicha(datos map[string]interface{}, paciente *client.Patient) map[string]interface{} {
	diagnostico := getString(datos, "diagnostico")
	if diagnostico == "" {
		diagnostico = getString(datos, "lesion")
	}
	if diagnostico == "" {
		return map[string]interface{}{"respuesta": "¿Cuál es el diagnóstico o lesión?", "nueva_sesion": map[string]interface{}{}}
	}

	// Detectar bilateral antes de crear ficha
	if esBilateral(diagnostico) {
		return map[string]interface{}{
			"respuesta":    "Gracias por la información, en un momento Felipe te contacta personalmente para coordinar su tratamiento.",
			"nueva_sesion": map[string]interface{}{},
		}
	}

	sesiones := getIntFromMap(datos, "cantidad_sesiones", 10)
	ficha, err := r.patients.CreateFicha(paciente.ID, diagnostico, sesiones)
	if err != nil {
		return map[string]interface{}{"respuesta": "No pude crear la ficha.", "nueva_sesion": map[string]interface{}{}}
	}
	return map[string]interface{}{
		"respuesta":    fmt.Sprintf("Listo, ficha creada por %s con %d sesiones.", ficha.Diagnostico, ficha.CantidadSesiones),
		"nueva_sesion": map[string]interface{}{},
	}
}

func (r *Router) manejarMarcarRealizada(paciente *client.Patient) map[string]interface{} {
	pendientes, _ := r.agenda.GetPendientes(paciente.ID)
	if len(pendientes) == 0 {
		return map[string]interface{}{"respuesta": "No encontré sesiones pendientes.", "nueva_sesion": map[string]interface{}{}}
	}
	cita := pendientes[0]
	r.agenda.MarcarRealizada(cita.ID)
	ficha, _ := r.patients.GetFichaActiva(paciente.ID)
	if ficha != nil {
		r.patients.IncrementarSesion(ficha.ID)
	}
	return map[string]interface{}{
		"respuesta":    mensajeCierre(fmt.Sprintf("Listo, marqué como realizada la sesión del %s a las %s.", cita.Fecha, cita.Hora)),
		"nueva_sesion": map[string]interface{}{},
	}
}

func (r *Router) completarRegistroPaciente(numero string, intent *model.Intent, sesion map[string]interface{}) map[string]interface{} {
	texto := strings.TrimSpace(getString(intent.Datos, "texto_original"))
	partes := strings.Fields(texto)
	if len(partes) < 2 {
		return map[string]interface{}{"respuesta": "Necesito tu nombre y apellido. Ej: Juan Pérez.", "nueva_sesion": sesion}
	}
	paciente, err := r.patients.Create(partes[0], strings.Join(partes[1:], " "), numero)
	if err != nil {
		return map[string]interface{}{"respuesta": "No pude registrarte. Intenta nuevamente.", "nueva_sesion": sesion}
	}
	return map[string]interface{}{
		"respuesta": fmt.Sprintf("Listo, %s. Ya te registré.\n\nDime tu lesión o diagnóstico.", partes[0]),
		"nueva_sesion": map[string]interface{}{"accion_pendiente": "crear_ficha", "pac_id": paciente.ID},
		"pac_id": paciente.ID,
	}
}
