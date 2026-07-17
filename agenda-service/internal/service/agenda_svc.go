package service

import (
	"agenda-service/internal/model"
	"agenda-service/internal/repository"
	"errors"
)

type AgendaService struct {
	repo *repository.AgendaRepository
}

func NewAgendaService(repo *repository.AgendaRepository) *AgendaService {
	return &AgendaService{repo: repo}
}

func (s *AgendaService) Create(req model.CreateAgendaRequest) (*model.Agenda, error) {
	// Validar que fecha y hora no estén ocupadas
	disponible, err := s.repo.HayDisponibilidad(req.Fecha, req.Hora)
	if err != nil {
		return nil, err
	}
	if !disponible {
		return nil, errors.New("horario no disponible: " + req.Fecha + " " + req.Hora)
	}

	a := &model.Agenda{
		PacID:       req.PacID,
		FicID:       req.FicID,
		Fecha:       req.Fecha,
		Hora:        req.Hora,
		Observacion: req.Observacion,
		CalEventID:  req.CalEventID,
		Estado:      "AGENDADA",
		Realizada:   "NO",
	}

	if err := s.repo.Create(a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *AgendaService) GetByID(id uint) (*model.Agenda, error) {
	return s.repo.GetByID(id)
}

func (s *AgendaService) GetByPatient(pacID uint) ([]model.Agenda, error) {
	return s.repo.GetByPatient(pacID)
}

func (s *AgendaService) GetByFecha(fecha string) ([]model.Agenda, error) {
	return s.repo.GetByFecha(fecha)
}

func (s *AgendaService) HayDisponibilidad(fecha, hora string) (bool, error) {
	return s.repo.HayDisponibilidad(fecha, hora)
}

func (s *AgendaService) Reagendar(id uint, req model.ReagendarRequest) error {
	// Verificar que el nuevo horario esté disponible
	disponible, err := s.repo.HayDisponibilidad(req.NuevaFecha, req.NuevaHora)
	if err != nil {
		return err
	}
	if !disponible {
		return errors.New("horario no disponible: " + req.NuevaFecha + " " + req.NuevaHora)
	}
	return s.repo.Reagendar(id, req.NuevaFecha, req.NuevaHora, req.Observacion)
}

func (s *AgendaService) Cancelar(id uint, req model.CancelarRequest) error {
	return s.repo.Cancelar(id, req.Observacion)
}

func (s *AgendaService) MarcarRealizada(id uint, observacion string) error {
	return s.repo.MarcarRealizada(id, observacion)
}

func (s *AgendaService) DesmarcarRealizada(id uint) error {
	return s.repo.DesmarcarRealizada(id)
}

func (s *AgendaService) SetCalEventID(id uint, calEventID string) error {
	return s.repo.SetCalEventID(id, calEventID)
}
