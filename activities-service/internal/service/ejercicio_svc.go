package service

import (
	"activities-service/internal/model"
	"activities-service/internal/repository"
	"errors"
)

type EjercicioService struct {
	repo *repository.EjercicioRepository
}

func NewEjercicioService(repo *repository.EjercicioRepository) *EjercicioService {
	return &EjercicioService{repo: repo}
}

func (s *EjercicioService) Create(req model.CreateEjercicioRequest) (*model.Ejercicio, error) {
	if req.Nombre == "" {
		return nil, errors.New("nombre es requerido")
	}
	series := req.Series
	if series == 0 {
		series = 3
	}
	reps := req.Repeticiones
	if reps == 0 {
		reps = 10
	}
	e := &model.Ejercicio{
		Nombre:       req.Nombre,
		Detalle:      req.Detalle,
		LinkYoutube:  req.LinkYoutube,
		Series:       series,
		Repeticiones: reps,
		Categoria:    req.Categoria,
		Activo:       true,
	}
	if err := s.repo.Create(e); err != nil {
		return nil, err
	}
	return e, nil
}

func (s *EjercicioService) GetByID(id uint) (*model.Ejercicio, error) {
	return s.repo.GetByID(id)
}

func (s *EjercicioService) GetAll(categoria string) ([]model.Ejercicio, error) {
	return s.repo.GetAll(categoria)
}

func (s *EjercicioService) Search(texto string) ([]model.Ejercicio, error) {
	return s.repo.Search(texto)
}

func (s *EjercicioService) Update(id uint, req model.UpdateEjercicioRequest) (*model.Ejercicio, error) {
	if err := s.repo.Update(id, req); err != nil {
		return nil, err
	}
	return s.repo.GetByID(id)
}

func (s *EjercicioService) Delete(id uint) error {
	return s.repo.Delete(id)
}
