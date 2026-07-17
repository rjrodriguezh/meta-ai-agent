package repository

import (
	"patients-service/internal/model"

	"gorm.io/gorm"
)

// FichaRepository — equivalente a ficha_service.py (solo acceso a datos)
type FichaRepository struct {
	db *gorm.DB
}

func NewFichaRepository(db *gorm.DB) *FichaRepository {
	return &FichaRepository{db: db}
}

// Create cierra la ficha activa existente (si hay) antes de crear la nueva.
func (r *FichaRepository) Create(f *model.Ficha) error {
	// Desactivar fichas activas previas del mismo paciente
	r.db.Model(&model.Ficha{}).
		Where("pac_id = ? AND LOWER(fic_estado) = 'activa'", f.PacID).
		Updates(map[string]interface{}{"fic_estado": "FINALIZADA"})

	return r.db.Create(f).Error
}

func (r *FichaRepository) GetByID(id uint) (*model.Ficha, error) {
	var f model.Ficha
	err := r.db.First(&f, id).Error
	if err != nil {
		return nil, err
	}
	return &f, nil
}

func (r *FichaRepository) GetByPatient(pacID uint) ([]model.Ficha, error) {
	var fichas []model.Ficha
	err := r.db.Where("pac_id = ?", pacID).
		Order("fic_id DESC").
		Find(&fichas).Error
	return fichas, err
}

// GetActiva — equivalente a obtener_ficha_activa
func (r *FichaRepository) GetActiva(pacID uint) (*model.Ficha, error) {
	var f model.Ficha
	err := r.db.Where("pac_id = ? AND LOWER(fic_estado) = 'activa'", pacID).
		Order("fic_id DESC").
		First(&f).Error
	if err != nil {
		return nil, err
	}
	return &f, nil
}

// IncrementarSesion — equivalente a incrementar_sesion_realizada
func (r *FichaRepository) IncrementarSesion(ficID uint) error {
	return r.db.Model(&model.Ficha{}).
		Where("fic_id = ?", ficID).
		UpdateColumn("fic_sesiones_realizadas", gorm.Expr("fic_sesiones_realizadas + 1")).
		Error
}

// DisminuirSesion — equivalente a disminuir_sesion_realizada
func (r *FichaRepository) DisminuirSesion(ficID uint) error {
	return r.db.Model(&model.Ficha{}).
		Where("fic_id = ? AND fic_sesiones_realizadas > 0", ficID).
		UpdateColumn("fic_sesiones_realizadas", gorm.Expr("fic_sesiones_realizadas - 1")).
		Error
}

func (r *FichaRepository) Cerrar(ficID uint) error {
	return r.db.Model(&model.Ficha{}).
		Where("fic_id = ?", ficID).
		Updates(map[string]interface{}{
			"fic_estado": "FINALIZADA",
		}).Error
}

func (r *FichaRepository) UpdateObservacion(ficID uint, observacion string) error {
	return r.db.Model(&model.Ficha{}).
		Where("fic_id = ?", ficID).
		Update("fic_observacion", observacion).Error
}

func (r *FichaRepository) Update(ficID uint, req model.UpdateFichaRequest) error {
	updates := map[string]interface{}{}
	if req.Diagnostico != "" {
		updates["fic_diagnostico"] = req.Diagnostico
	}
	if req.CantidadSesiones > 0 {
		updates["fic_cantidad_sesiones"] = req.CantidadSesiones
	}
	updates["fic_observacion"] = req.Observacion
	if req.DocumentoPath != "" {
		updates["fic_documento_path"]   = req.DocumentoPath
		updates["fic_documento_nombre"] = req.DocumentoNombre
	}
	return r.db.Model(&model.Ficha{}).Where("fic_id = ?", ficID).Updates(updates).Error
}

func (r *FichaRepository) Delete(ficID uint) error {
	return r.db.Delete(&model.Ficha{}, ficID).Error
}
