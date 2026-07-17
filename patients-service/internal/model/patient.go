package model

import "time"

// Patient — equivalente a la tabla `pacientes` en SQLite
type Patient struct {
	ID                 uint      `gorm:"primaryKey;column:pac_id"                  json:"pac_id"`
	NombreCorto        string    `gorm:"column:pac_nombre_corto"                   json:"pac_nombre_corto"`
	Nombres            string    `gorm:"column:pac_nombres"                        json:"pac_nombres"`
	Apellidos          string    `gorm:"column:pac_apellidos"                      json:"pac_apellidos"`
	Telefono           string    `gorm:"column:pac_telefono;uniqueIndex"           json:"pac_telefono"`
	Email              string    `gorm:"column:pac_email"                          json:"pac_email"`
	Direccion          string    `gorm:"column:pac_direccion"                      json:"pac_direccion"`
	Ciudad             string    `gorm:"column:pac_ciudad"                         json:"pac_ciudad"`
	Comuna             string    `gorm:"column:pac_comuna"                         json:"pac_comuna"`
	ContactoEmergencia string    `gorm:"column:pac_contacto_emergencia"            json:"pac_contacto_emergencia"`
	TelefonoEmergencia string    `gorm:"column:pac_telefono_emergencia"            json:"pac_telefono_emergencia"`
	Estado             string    `gorm:"column:pac_estado;default:ACTIVO"          json:"pac_estado"`
	CreatedAt          time.Time `gorm:"column:pac_fecha_creacion"                 json:"pac_fecha_creacion"`
}

func (Patient) TableName() string {
	return "pacientes"
}

// --- Request / Response structs ---

type CreatePatientRequest struct {
	Nombres            string `json:"nombres"              validate:"required"`
	Apellidos          string `json:"apellidos"            validate:"required"`
	Telefono           string `json:"telefono"`
	NombreCorto        string `json:"nombre_corto"`
	Email              string `json:"email"`
	Direccion          string `json:"direccion"`
	Ciudad             string `json:"ciudad"`
	Comuna             string `json:"comuna"`
	ContactoEmergencia string `json:"contacto_emergencia"`
	TelefonoEmergencia string `json:"telefono_emergencia"`
}

type UpdatePatientRequest struct {
	NombreCorto        string `json:"nombre_corto"`
	Nombres            string `json:"nombres"`
	Apellidos          string `json:"apellidos"`
	Telefono           string `json:"telefono"`
	Email              string `json:"email"`
	Direccion          string `json:"direccion"`
	Ciudad             string `json:"ciudad"`
	Comuna             string `json:"comuna"`
	ContactoEmergencia string `json:"contacto_emergencia"`
	TelefonoEmergencia string `json:"telefono_emergencia"`
}
