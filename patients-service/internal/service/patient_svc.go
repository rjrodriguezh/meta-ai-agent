package service

import (
	"errors"
	"patients-service/internal/model"
	"patients-service/internal/repository"
)

// PatientService contiene la lógica de negocio.
// El handler llama al service, el service llama al repository.
type PatientService struct {
	repo *repository.PatientRepository
}

func NewPatientService(repo *repository.PatientRepository) *PatientService {
	return &PatientService{repo: repo}
}

func (s *PatientService) Create(req model.CreatePatientRequest) (*model.Patient, error) {
	if req.Nombres == "" || req.Apellidos == "" {
		return nil, errors.New("nombres y apellidos son requeridos")
	}

	nombreCorto := req.NombreCorto
	if nombreCorto == "" {
		nombreCorto = req.Nombres + " " + req.Apellidos
	}

	p := &model.Patient{
		Nombres:            req.Nombres,
		Apellidos:          req.Apellidos,
		Telefono:           req.Telefono,
		NombreCorto:        nombreCorto,
		Email:              req.Email,
		Direccion:          req.Direccion,
		Ciudad:             req.Ciudad,
		Comuna:             req.Comuna,
		ContactoEmergencia: req.ContactoEmergencia,
		TelefonoEmergencia: req.TelefonoEmergencia,
		Rut:                req.Rut,
		Peso:               req.Peso,
		Altura:             req.Altura,
		Estado:             "ACTIVO",
	}

	if err := s.repo.Create(p); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *PatientService) GetByID(id uint) (*model.Patient, error) {
	return s.repo.GetByID(id)
}

func (s *PatientService) GetByTelefono(telefono string) (*model.Patient, error) {
	return s.repo.GetByTelefono(telefono)
}

func (s *PatientService) Search(texto string) ([]model.Patient, error) {
	return s.repo.Search(texto)
}

func (s *PatientService) GetAll() ([]model.Patient, error) {
	return s.repo.GetAll()
}

func (s *PatientService) Update(id uint, req model.UpdatePatientRequest) (*model.Patient, error) {
	p, err := s.repo.GetByID(id)
	if err != nil {
		return nil, errors.New("paciente no encontrado")
	}

	if req.Nombres != "" {
		p.Nombres = req.Nombres
	}
	if req.Apellidos != "" {
		p.Apellidos = req.Apellidos
	}
	if req.Telefono != "" {
		p.Telefono = req.Telefono
	}
	if req.NombreCorto != "" {
		p.NombreCorto = req.NombreCorto
	}
	p.Email              = req.Email
	p.Direccion          = req.Direccion
	p.Ciudad             = req.Ciudad
	p.Comuna             = req.Comuna
	p.ContactoEmergencia = req.ContactoEmergencia
	p.TelefonoEmergencia = req.TelefonoEmergencia

	// Rut/Peso/Altura se actualizan de forma CONDICIONAL (a diferencia de los
	// campos de arriba) porque ai-service los guarda en llamadas separadas,
	// una por turno de la conversación (primero rut, después peso, después
	// altura) — si fueran incondicionales, cada llamada borraría el valor
	// que la llamada anterior acababa de guardar.
	if req.Rut != "" {
		p.Rut = req.Rut
	}
	if req.Peso != "" {
		p.Peso = req.Peso
	}
	if req.Altura != "" {
		p.Altura = req.Altura
	}

	if err := s.repo.Update(p); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *PatientService) Deactivate(id uint) error {
	return s.repo.Deactivate(id)
}

func (s *PatientService) SetPrevision(id uint, prevision string) error {
	if prevision == "" {
		return errors.New("previsión requerida")
	}
	return s.repo.SetPrevision(id, prevision)
}
