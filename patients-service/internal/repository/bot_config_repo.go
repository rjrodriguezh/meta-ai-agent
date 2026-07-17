package repository

import (
	"patients-service/internal/model"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type BotConfigRepository struct {
	db *gorm.DB
}

func NewBotConfigRepository(db *gorm.DB) *BotConfigRepository {
	return &BotConfigRepository{db: db}
}

// Get devuelve la config (siempre existe: crea una fila vacía si no hay)
func (r *BotConfigRepository) Get() (*model.BotConfig, error) {
	var cfg model.BotConfig
	err := r.db.First(&cfg).Error
	if err == gorm.ErrRecordNotFound {
		cfg = model.BotConfig{ID: 1, Activo: true}
		r.db.Create(&cfg)
		return &cfg, nil
	}
	return &cfg, err
}

// Update guarda los cambios (upsert por ID=1)
func (r *BotConfigRepository) Update(req model.UpdateBotConfigRequest) (*model.BotConfig, error) {
	updates := map[string]interface{}{"cfg_persona": req.Persona}
	if req.Activo != nil {
		updates["cfg_activo"] = *req.Activo
	}

	cfg := model.BotConfig{ID: 1}
	err := r.db.Model(&cfg).Clauses(clause.OnConflict{UpdateAll: true}).
		Updates(updates).Error
	if err != nil {
		return nil, err
	}
	return r.Get()
}
