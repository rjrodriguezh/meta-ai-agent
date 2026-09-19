package repository

import (
	"activities-service/internal/model"
	"strings"

	"gorm.io/gorm"
)

type DiagnosticoRepository struct {
	db *gorm.DB
}

func NewDiagnosticoRepository(db *gorm.DB) *DiagnosticoRepository {
	return &DiagnosticoRepository{db: db}
}

func (r *DiagnosticoRepository) Create(d *model.Diagnostico) error {
	return r.db.Create(d).Error
}

func (r *DiagnosticoRepository) GetAll() ([]model.Diagnostico, error) {
	var list []model.Diagnostico
	err := r.db.Preload("Ejercicios").Order("diag_nombre ASC").Find(&list).Error
	return list, err
}

func (r *DiagnosticoRepository) GetByID(id uint) (*model.Diagnostico, error) {
	var d model.Diagnostico
	err := r.db.Preload("Ejercicios").First(&d, id).Error
	if err != nil {
		return nil, err
	}
	return &d, nil
}

func (r *DiagnosticoRepository) Update(id uint, req model.UpdateDiagnosticoRequest) error {
	updates := map[string]interface{}{}
	if req.Nombre != "" {
		updates["diag_nombre"] = req.Nombre
	}
	if req.Zona != "" {
		updates["diag_zona"] = req.Zona
	}
	if req.Keywords != "" {
		updates["diag_keywords"] = req.Keywords
	}
	if len(updates) > 0 {
		if err := r.db.Model(&model.Diagnostico{}).Where("diag_id = ?", id).Updates(updates).Error; err != nil {
			return err
		}
	}
	if req.EjercicioIDs != nil {
		var d model.Diagnostico
		if err := r.db.First(&d, id).Error; err != nil {
			return err
		}
		var ejercicios []model.Ejercicio
		if len(*req.EjercicioIDs) > 0 {
			if err := r.db.Where("eje_id IN ?", *req.EjercicioIDs).Find(&ejercicios).Error; err != nil {
				return err
			}
		}
		if err := r.db.Model(&d).Association("Ejercicios").Replace(ejercicios); err != nil {
			return err
		}
	}
	return nil
}

func (r *DiagnosticoRepository) Delete(id uint) error {
	return r.db.Delete(&model.Diagnostico{}, id).Error
}

// BuscarPorTexto encuentra el diagnóstico cuyo nombre o palabras clave mejor
// coinciden con un texto libre (ej. el fic_diagnostico de una ficha clínica).
// Estrategia: normaliza tildes/mayúsculas y puntúa cada diagnóstico por
// cuántas de sus keywords (+ su propio nombre) aparecen en el texto; gana el
// de mayor puntaje. No requiere coincidencia exacta de texto.
func (r *DiagnosticoRepository) BuscarPorTexto(texto string) (*model.Diagnostico, error) {
	var todos []model.Diagnostico
	if err := r.db.Preload("Ejercicios").Find(&todos).Error; err != nil {
		return nil, err
	}
	t := sinTildesActivities(strings.ToLower(texto))

	var mejor *model.Diagnostico
	mejorScore := 0
	for i := range todos {
		d := todos[i]
		score := 0
		if strings.Contains(t, sinTildesActivities(strings.ToLower(d.Nombre))) {
			score += 10
		}
		for _, kw := range strings.Split(d.Keywords, ",") {
			kw = strings.TrimSpace(sinTildesActivities(strings.ToLower(kw)))
			if kw != "" && strings.Contains(t, kw) {
				score++
			}
		}
		if score > mejorScore {
			mejorScore = score
			mejor = &todos[i]
		}
	}
	if mejor == nil {
		return nil, gorm.ErrRecordNotFound
	}
	return mejor, nil
}

func sinTildesActivities(s string) string {
	r := strings.NewReplacer("á", "a", "é", "e", "í", "i", "ó", "o", "ú", "u")
	return r.Replace(s)
}
