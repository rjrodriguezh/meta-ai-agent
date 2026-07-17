package session

import (
	"ai-service/internal/model"
	"encoding/json"
	"log"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// Store maneja la sesión de conversación de cada usuario.
// Equivale a session_service.py
type Store struct {
	db *gorm.DB
}

func NewStore(db *gorm.DB) *Store {
	return &Store{db: db}
}

// Obtener — lee el contexto de sesión del usuario.
// Equivale a obtener_sesion en Python.
func (s *Store) Obtener(telefono string) map[string]interface{} {
	var conv model.Conversacion
	err := s.db.Where("con_telefono = ?", telefono).First(&conv).Error
	if err != nil {
		return map[string]interface{}{}
	}

	if conv.ContextoJSON == "" {
		return map[string]interface{}{}
	}

	var ctx map[string]interface{}
	if err := json.Unmarshal([]byte(conv.ContextoJSON), &ctx); err != nil {
		log.Printf("[Session] Error parseando contexto: %v", err)
		return map[string]interface{}{}
	}
	return ctx
}

// Guardar — persiste el contexto de sesión.
// Equivale a guardar_sesion en Python (con UPSERT).
func (s *Store) Guardar(telefono string, ctx map[string]interface{}, pacID *uint, ultimaIntencion string) {
	ctxJSON, err := json.Marshal(ctx)
	if err != nil {
		log.Printf("[Session] Error serializando contexto: %v", err)
		return
	}

	conv := model.Conversacion{
		Telefono:        telefono,
		PacID:           pacID,
		ContextoJSON:    string(ctxJSON),
		UltimaIntencion: ultimaIntencion,
	}

	// UPSERT — equivale al INSERT OR UPDATE de Python
	s.db.Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "con_telefono"}},
		DoUpdates: clause.AssignmentColumns([]string{
			"con_contexto_json",
			"con_ultima_intencion",
			"con_fecha_actualizacion",
		}),
	}).Create(&conv)
}

// Limpiar — borra el contexto de sesión (equivale a limpiar_sesion)
func (s *Store) Limpiar(telefono string) {
	s.db.Model(&model.Conversacion{}).
		Where("con_telefono = ?", telefono).
		Updates(map[string]interface{}{
			"con_contexto_json":   "",
			"con_ultima_intencion": "",
		})
}
