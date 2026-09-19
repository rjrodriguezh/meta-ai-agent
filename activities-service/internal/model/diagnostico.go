package model

import "time"

// Diagnostico — tipo de diagnóstico kinésico (ej. "Esguince de tobillo"),
// con su lista de ejercicios recomendados asociada (many-to-many).
type Diagnostico struct {
	ID         uint        `gorm:"primaryKey;column:diag_id"                  json:"diag_id"`
	Nombre     string      `gorm:"column:diag_nombre;not null;uniqueIndex"    json:"diag_nombre"`
	Zona       string      `gorm:"column:diag_zona"                           json:"diag_zona"`
	Keywords   string      `gorm:"column:diag_keywords"                       json:"diag_keywords"`
	Ejercicios []Ejercicio `gorm:"many2many:diagnostico_ejercicios;"          json:"ejercicios,omitempty"`
	CreatedAt  time.Time   `gorm:"column:diag_fecha_creacion;autoCreateTime"  json:"diag_fecha_creacion"`
}

func (Diagnostico) TableName() string { return "diagnosticos" }

// --- Request structs ---

type CreateDiagnosticoRequest struct {
	Nombre       string `json:"nombre"        validate:"required"`
	Zona         string `json:"zona"`
	Keywords     string `json:"keywords"`
	EjercicioIDs []uint `json:"ejercicio_ids"`
}

type UpdateDiagnosticoRequest struct {
	Nombre       string  `json:"nombre"`
	Zona         string  `json:"zona"`
	Keywords     string  `json:"keywords"`
	EjercicioIDs *[]uint `json:"ejercicio_ids"` // puntero: nil = no tocar la lista, [] = vaciarla
}
