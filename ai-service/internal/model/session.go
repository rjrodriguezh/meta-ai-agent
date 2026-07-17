package model

import "time"

// Conversacion — tabla `conversaciones` en SQLite
// Equivale al esquema que usa session_service.py
type Conversacion struct {
	ID               uint      `gorm:"primaryKey;column:con_id"`
	Telefono         string    `gorm:"column:con_telefono;uniqueIndex;not null"`
	PacID            *uint     `gorm:"column:pac_id"`
	ContextoJSON     string    `gorm:"column:con_contexto_json"`
	UltimaIntencion  string    `gorm:"column:con_ultima_intencion"`
	FechaActualizacion time.Time `gorm:"column:con_fecha_actualizacion;autoUpdateTime"`
}

func (Conversacion) TableName() string {
	return "conversaciones"
}
