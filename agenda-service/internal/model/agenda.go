package model

import "time"

// Agenda — equivalente a la tabla `agenda` en SQLite
type Agenda struct {
	ID          uint       `gorm:"primaryKey;column:agen_id"                    json:"agen_id"`
	PacID       uint       `gorm:"column:pac_id;not null"                       json:"pac_id"`
	FicID       *uint      `gorm:"column:fic_id"                                json:"fic_id"`
	Fecha       string     `gorm:"column:agen_fecha;not null"                   json:"agen_fecha"`
	Hora        string     `gorm:"column:agen_hora;not null"                    json:"agen_hora"`
	Estado       string     `gorm:"column:agen_estado;default:AGENDADA"          json:"agen_estado"`
	Realizada    string     `gorm:"column:agen_realizada;default:NO"             json:"agen_realizada"`
	Observacion  string     `gorm:"column:agen_observacion"                      json:"agen_observacion"`
	CalEventID   string     `gorm:"column:agen_cal_event_id"                     json:"agen_cal_event_id"`
	CreatedAt   time.Time  `gorm:"column:agen_fecha_creacion"                   json:"agen_fecha_creacion"`
	UpdatedAt   time.Time  `gorm:"column:agen_fecha_actualizacion"              json:"agen_fecha_actualizacion"`
}

func (Agenda) TableName() string {
	return "agenda"
}

// --- Request structs ---

type CreateAgendaRequest struct {
	PacID       uint   `json:"pac_id"      validate:"required"`
	FicID       *uint  `json:"fic_id"`
	Fecha       string `json:"fecha"       validate:"required"`
	Hora        string `json:"hora"        validate:"required"`
	Observacion string `json:"observacion"`
	CalEventID  string `json:"cal_event_id"`
}

type ReagendarRequest struct {
	NuevaFecha  string `json:"nueva_fecha"  validate:"required"`
	NuevaHora   string `json:"nueva_hora"   validate:"required"`
	Observacion string `json:"observacion"`
}

type CancelarRequest struct {
	Observacion string `json:"observacion"`
}
