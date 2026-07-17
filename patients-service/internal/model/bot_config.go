package model

import "time"

// BotConfig — fila única con la configuración del bot de WhatsApp
type BotConfig struct {
	ID          uint      `gorm:"primaryKey;column:cfg_id"           json:"cfg_id"`
	Persona     string    `gorm:"column:cfg_persona;type:text"       json:"persona"`      // system prompt / fine-tuning
	Activo      bool      `gorm:"column:cfg_activo;default:true"     json:"activo"`
	UpdatedAt   time.Time `gorm:"column:cfg_updated_at;autoUpdateTime" json:"updated_at"`
}

func (BotConfig) TableName() string { return "bot_config" }

type UpdateBotConfigRequest struct {
	Persona string `json:"persona"`
	Activo  *bool  `json:"activo"`
}
