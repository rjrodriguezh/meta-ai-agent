package service

import (
	"patients-service/internal/model"
	"patients-service/internal/repository"
)

type FichaService struct {
	repo *repository.FichaRepository
}

func NewFichaService(repo *repository.FichaRepository) *FichaService {
	return &FichaService{repo: repo}
}

func (s *FichaService) Create(pacID uint, req model.CreateFichaRequest) (*model.Ficha, error) {
	f := &model.Ficha{
		PacID:              pacID,
		Diagnostico:        req.Diagnostico,
		CantidadSesiones:   req.CantidadSesiones,
		SesionesRealizadas: 0,
		Estado:             "ACTIVA",
		Observacion:        req.Observacion,
		DocumentoPath:      req.DocumentoPath,
		DocumentoNombre:    req.DocumentoNombre,
	}

	if err := s.repo.Create(f); err != nil {
		return nil, err
	}
	return f, nil
}

func (s *FichaService) GetByPatient(pacID uint) ([]model.Ficha, error) {
	return s.repo.GetByPatient(pacID)
}

func (s *FichaService) GetActiva(pacID uint) (*model.Ficha, error) {
	return s.repo.GetActiva(pacID)
}

func (s *FichaService) IncrementarSesion(ficID uint) error {
	return s.repo.IncrementarSesion(ficID)
}

func (s *FichaService) DisminuirSesion(ficID uint) error {
	return s.repo.DisminuirSesion(ficID)
}

func (s *FichaService) Cerrar(ficID uint) error {
	return s.repo.Cerrar(ficID)
}

func (s *FichaService) Update(ficID uint, req model.UpdateFichaRequest) error {
	return s.repo.Update(ficID, req)
}

func (s *FichaService) Delete(ficID uint) error {
	return s.repo.Delete(ficID)
}
