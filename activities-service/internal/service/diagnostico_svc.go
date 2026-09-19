package service

import (
	"activities-service/internal/model"
	"activities-service/internal/repository"
	"errors"
)

type DiagnosticoService struct {
	repo *repository.DiagnosticoRepository
}

func NewDiagnosticoService(repo *repository.DiagnosticoRepository) *DiagnosticoService {
	return &DiagnosticoService{repo: repo}
}

func (s *DiagnosticoService) Create(req model.CreateDiagnosticoRequest) (*model.Diagnostico, error) {
	if req.Nombre == "" {
		return nil, errors.New("nombre es requerido")
	}
	d := &model.Diagnostico{Nombre: req.Nombre, Zona: req.Zona, Keywords: req.Keywords}
	if err := s.repo.Create(d); err != nil {
		return nil, err
	}
	if len(req.EjercicioIDs) > 0 {
		ids := req.EjercicioIDs
		if err := s.repo.Update(d.ID, model.UpdateDiagnosticoRequest{EjercicioIDs: &ids}); err != nil {
			return nil, err
		}
	}
	return s.repo.GetByID(d.ID)
}

func (s *DiagnosticoService) GetAll() ([]model.Diagnostico, error) { return s.repo.GetAll() }

func (s *DiagnosticoService) GetByID(id uint) (*model.Diagnostico, error) { return s.repo.GetByID(id) }

func (s *DiagnosticoService) Update(id uint, req model.UpdateDiagnosticoRequest) (*model.Diagnostico, error) {
	if err := s.repo.Update(id, req); err != nil {
		return nil, err
	}
	return s.repo.GetByID(id)
}

func (s *DiagnosticoService) Delete(id uint) error { return s.repo.Delete(id) }

func (s *DiagnosticoService) BuscarPorTexto(texto string) (*model.Diagnostico, error) {
	if texto == "" {
		return nil, errors.New("texto requerido")
	}
	return s.repo.BuscarPorTexto(texto)
}
