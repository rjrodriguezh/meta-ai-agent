package repository

import (
	"patients-service/internal/model"

	"gorm.io/gorm"
)

// PatientRepository maneja todas las queries a la tabla pacientes.
// Equivalente a paciente_service.py pero solo la parte de acceso a datos.
type PatientRepository struct {
	db *gorm.DB
}

func NewPatientRepository(db *gorm.DB) *PatientRepository {
	return &PatientRepository{db: db}
}

func (r *PatientRepository) Create(p *model.Patient) error {
	return r.db.Create(p).Error
}

func (r *PatientRepository) GetByID(id uint) (*model.Patient, error) {
	var p model.Patient
	err := r.db.First(&p, id).Error
	if err != nil {
		return nil, err
	}
	return &p, nil
}

// GetByTelefono — usado por la IA para identificar al paciente por su número de WhatsApp
func (r *PatientRepository) GetByTelefono(telefono string) (*model.Patient, error) {
	var p model.Patient
	err := r.db.Where("pac_telefono = ?", telefono).First(&p).Error
	if err != nil {
		return nil, err
	}
	return &p, nil
}

// Search — busca por nombre, apellido o teléfono (equivalente a buscar_paciente)
func (r *PatientRepository) Search(texto string) ([]model.Patient, error) {
	var patients []model.Patient
	like := "%" + texto + "%"
	err := r.db.Where(
		"pac_nombres LIKE ? OR pac_apellidos LIKE ? OR pac_telefono LIKE ?",
		like, like, like,
	).Order("pac_apellidos, pac_nombres").Find(&patients).Error
	return patients, err
}

func (r *PatientRepository) Update(p *model.Patient) error {
	return r.db.Save(p).Error
}

// Deactivate — equivalente a desactivar_paciente
func (r *PatientRepository) Deactivate(id uint) error {
	return r.db.Model(&model.Patient{}).
		Where("pac_id = ?", id).
		Update("pac_estado", "INACTIVO").Error
}

func (r *PatientRepository) GetAll() ([]model.Patient, error) {
	var patients []model.Patient
	err := r.db.Order("pac_apellidos, pac_nombres").Find(&patients).Error
	return patients, err
}
