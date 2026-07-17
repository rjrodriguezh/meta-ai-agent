package model

import "time"

// Ficha — equivalente a la tabla `fichas` en SQLite
type Ficha struct {
	ID                 uint      `gorm:"primaryKey;column:fic_id"                    json:"fic_id"`
	PacID              uint      `gorm:"column:pac_id;not null"                      json:"pac_id"`
	Diagnostico        string    `gorm:"column:fic_diagnostico;not null"             json:"fic_diagnostico"`
	CantidadSesiones   int       `gorm:"column:fic_cantidad_sesiones;default:10"     json:"fic_cantidad_sesiones"`
	SesionesRealizadas int       `gorm:"column:fic_sesiones_realizadas;default:0"    json:"fic_sesiones_realizadas"`
	Estado             string    `gorm:"column:fic_estado;default:ACTIVA"            json:"fic_estado"`
	Observacion        string    `gorm:"column:fic_observacion"                      json:"fic_observacion"`
	DocumentoPath      string    `gorm:"column:fic_documento_path"                   json:"fic_documento_path"`
	DocumentoNombre    string    `gorm:"column:fic_documento_nombre"                 json:"fic_documento_nombre"`
	CreatedAt          time.Time `gorm:"column:fic_fecha_creacion;autoCreateTime"    json:"fic_fecha_creacion"`
	UpdatedAt          time.Time `gorm:"column:fic_fecha_actualizacion;autoUpdateTime" json:"fic_fecha_actualizacion"`
}

func (Ficha) TableName() string {
	return "fichas"
}

// --- Request structs ---

type CreateFichaRequest struct {
	Diagnostico      string `json:"diagnostico"       validate:"required"`
	CantidadSesiones int    `json:"cantidad_sesiones"`
	Observacion      string `json:"observacion"`
	DocumentoPath    string `json:"documento_path"`
	DocumentoNombre  string `json:"documento_nombre"`
}

type UpdateFichaRequest struct {
	Diagnostico      string `json:"diagnostico"`
	CantidadSesiones int    `json:"cantidad_sesiones"`
	Observacion      string `json:"observacion"`
	DocumentoPath    string `json:"documento_path"`
	DocumentoNombre  string `json:"documento_nombre"`
}
