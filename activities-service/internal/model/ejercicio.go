package model

import "time"

// Ejercicio — tabla de ejercicios terapéuticos
type Ejercicio struct {
	ID           uint      `gorm:"primaryKey;column:eje_id"                       json:"eje_id"`
	Nombre       string    `gorm:"column:eje_nombre;not null"                     json:"eje_nombre"`
	Detalle      string    `gorm:"column:eje_detalle;type:text"                   json:"eje_detalle"`
	LinkYoutube  string    `gorm:"column:eje_link_youtube"                        json:"eje_link_youtube"`
	Series       int       `gorm:"column:eje_series;default:3"                    json:"eje_series"`
	Repeticiones int       `gorm:"column:eje_repeticiones;default:10"             json:"eje_repeticiones"`
	Categoria    string    `gorm:"column:eje_categoria"                           json:"eje_categoria"`
	Activo       bool      `gorm:"column:eje_activo;default:true"                 json:"eje_activo"`
	CreatedAt    time.Time `gorm:"column:eje_fecha_creacion"                      json:"eje_fecha_creacion"`
	UpdatedAt    time.Time `gorm:"column:eje_fecha_actualizacion"                 json:"eje_fecha_actualizacion"`
}

func (Ejercicio) TableName() string { return "ejercicios" }

// --- Request structs ---

type CreateEjercicioRequest struct {
	Nombre       string `json:"nombre"        validate:"required"`
	Detalle      string `json:"detalle"`
	LinkYoutube  string `json:"link_youtube"`
	Series       int    `json:"series"`
	Repeticiones int    `json:"repeticiones"`
	Categoria    string `json:"categoria"`
}

type UpdateEjercicioRequest struct {
	Nombre       string `json:"nombre"`
	Detalle      string `json:"detalle"`
	LinkYoutube  string `json:"link_youtube"`
	Series       int    `json:"series"`
	Repeticiones int    `json:"repeticiones"`
	Categoria    string `json:"categoria"`
	Activo       *bool  `json:"activo"`
}
