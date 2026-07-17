package repository

import (
	"agenda-service/internal/model"

	"gorm.io/gorm"
)

type AgendaRepository struct {
	db *gorm.DB
}

func NewAgendaRepository(db *gorm.DB) *AgendaRepository {
	return &AgendaRepository{db: db}
}

func (r *AgendaRepository) Create(a *model.Agenda) error {
	return r.db.Create(a).Error
}

func (r *AgendaRepository) GetByID(id uint) (*model.Agenda, error) {
	var a model.Agenda
	err := r.db.First(&a, id).Error
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// GetByPatient — todas las citas de un paciente, más reciente primero
func (r *AgendaRepository) GetByPatient(pacID uint) ([]model.Agenda, error) {
	var agenda []model.Agenda
	err := r.db.Where("pac_id = ?", pacID).
		Order("agen_fecha DESC, agen_hora DESC").
		Find(&agenda).Error
	return agenda, err
}

// GetByFecha — agenda de un día específico (para la vista diaria)
func (r *AgendaRepository) GetByFecha(fecha string) ([]model.Agenda, error) {
	var agenda []model.Agenda
	err := r.db.Where("agen_fecha = ?", fecha).
		Order("agen_hora ASC").
		Find(&agenda).Error
	return agenda, err
}

// HayDisponibilidad — verifica si el slot fecha+hora está libre
// equivalente a hay_disponibilidad en Python
func (r *AgendaRepository) HayDisponibilidad(fecha, hora string) (bool, error) {
	var count int64
	err := r.db.Model(&model.Agenda{}).
		Where("agen_fecha = ? AND agen_hora = ? AND UPPER(agen_estado) != 'CANCELADA'", fecha, hora).
		Count(&count).Error
	if err != nil {
		return false, err
	}
	return count == 0, nil
}

// Reagendar — mueve la cita a nueva fecha/hora
func (r *AgendaRepository) Reagendar(id uint, nuevaFecha, nuevaHora, observacion string) error {
	updates := map[string]interface{}{
		"agen_fecha":  nuevaFecha,
		"agen_hora":   nuevaHora,
		"agen_estado": "REAGENDADA",
	}
	if observacion != "" {
		updates["agen_observacion"] = observacion
	}
	return r.db.Model(&model.Agenda{}).Where("agen_id = ?", id).Updates(updates).Error
}

// Cancelar — marca la cita como cancelada
func (r *AgendaRepository) Cancelar(id uint, observacion string) error {
	updates := map[string]interface{}{
		"agen_estado":    "CANCELADA",
		"agen_realizada": "NO",
	}
	if observacion != "" {
		updates["agen_observacion"] = observacion
	}
	return r.db.Model(&model.Agenda{}).Where("agen_id = ?", id).Updates(updates).Error
}

// MarcarRealizada — marca la sesión como realizada
func (r *AgendaRepository) MarcarRealizada(id uint, observacion string) error {
	updates := map[string]interface{}{
		"agen_estado":    "REALIZADA",
		"agen_realizada": "SI",
	}
	if observacion != "" {
		updates["agen_observacion"] = observacion
	}
	return r.db.Model(&model.Agenda{}).Where("agen_id = ?", id).Updates(updates).Error
}

// DesmarcarRealizada — revierte a AGENDADA
func (r *AgendaRepository) DesmarcarRealizada(id uint) error {
	return r.db.Model(&model.Agenda{}).Where("agen_id = ?", id).Updates(map[string]interface{}{
		"agen_estado":    "AGENDADA",
		"agen_realizada": "NO",
	}).Error
}

// SetCalEventID — guarda el ID del evento de Google Calendar
func (r *AgendaRepository) SetCalEventID(id uint, calEventID string) error {
	return r.db.Model(&model.Agenda{}).Where("agen_id = ?", id).
		Update("agen_cal_event_id", calEventID).Error
}
