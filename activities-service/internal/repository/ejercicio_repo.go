package repository

import (
	"activities-service/internal/model"

	"gorm.io/gorm"
)

type EjercicioRepository struct {
	db *gorm.DB
}

func NewEjercicioRepository(db *gorm.DB) *EjercicioRepository {
	return &EjercicioRepository{db: db}
}

func (r *EjercicioRepository) Create(e *model.Ejercicio) error {
	return r.db.Create(e).Error
}

func (r *EjercicioRepository) GetByID(id uint) (*model.Ejercicio, error) {
	var e model.Ejercicio
	err := r.db.First(&e, id).Error
	return &e, err
}

func (r *EjercicioRepository) GetAll(categoria string) ([]model.Ejercicio, error) {
	var list []model.Ejercicio
	q := r.db.Order("eje_nombre ASC")
	if categoria != "" {
		q = q.Where("eje_categoria = ?", categoria)
	}
	err := q.Find(&list).Error
	return list, err
}

func (r *EjercicioRepository) Search(texto string) ([]model.Ejercicio, error) {
	var list []model.Ejercicio
	like := "%" + texto + "%"
	err := r.db.Where("eje_nombre LIKE ? OR eje_detalle LIKE ? OR eje_categoria LIKE ?", like, like, like).
		Order("eje_nombre ASC").Find(&list).Error
	return list, err
}

func (r *EjercicioRepository) Update(id uint, req model.UpdateEjercicioRequest) error {
	updates := map[string]interface{}{}
	if req.Nombre != "" {
		updates["eje_nombre"] = req.Nombre
	}
	updates["eje_detalle"] = req.Detalle
	updates["eje_link_youtube"] = req.LinkYoutube
	updates["eje_categoria"] = req.Categoria
	if req.Series > 0 {
		updates["eje_series"] = req.Series
	}
	if req.Repeticiones > 0 {
		updates["eje_repeticiones"] = req.Repeticiones
	}
	if req.Activo != nil {
		updates["eje_activo"] = *req.Activo
	}
	return r.db.Model(&model.Ejercicio{}).Where("eje_id = ?", id).Updates(updates).Error
}

func (r *EjercicioRepository) Delete(id uint) error {
	return r.db.Delete(&model.Ejercicio{}, id).Error
}
