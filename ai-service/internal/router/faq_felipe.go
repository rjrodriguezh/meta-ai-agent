package router

import "strings"

// ---------------------------------------------------------------------
// PARCHE TEMPORAL — FAQ Felipe
//
// El folder de Postman "Preguntas Frecuentes (Fine-Tuning Felipe)" detectó
// 8 preguntas donde OpenAI improvisaba mal la respuesta (decía que la
// atención es individual, que sí hacen piso pélvico, no escalaba casos
// bilaterales, etc.) a pesar de tener la persona/contexto correcto.
//
// Mientras se ajusta el prompt/fine-tuning real, estas reglas responden
// directo por texto plano ANTES de llamar a OpenAI, garantizando que estas
// preguntas puntuales siempre den la respuesta correcta.
//
// TODO: eliminar este archivo cuando el classifier/responder maneje estos
// casos de forma confiable por sí solo.
// ---------------------------------------------------------------------

type reglaFAQ struct {
	incluye   []string // todas las palabras deben estar presentes (AND)
	respuesta string
}

var reglasFAQFelipe = []reglaFAQ{
	{
		incluye:   []string{"5 sesion"},
		respuesta: "No hay promociones con 5 sesiones. Solo con 10. ¿Por fonasa?",
	},
	{
		incluye:   []string{"individual"},
		respuesta: "No, la atención es grupal (máximo 3 pacientes por sesión), no es individual.",
	},
	{
		incluye:   []string{"masaje", "lipo"},
		respuesta: "No realizamos masajes post operatorios (post lipo o post cirugía estética). Te recomiendo consultar directamente con Felipe.",
	},
	{
		incluye:   []string{"masaje", "post operator"},
		respuesta: "No realizamos masajes post operatorios (post lipo o post cirugía estética). Te recomiendo consultar directamente con Felipe.",
	},
	{
		incluye:   []string{"piso pelvico"},
		respuesta: "No realizamos ejercicios de piso pélvico en nuestra clínica.",
	},
	{
		incluye:   []string{"kine", "antes"},
		respuesta: "No es necesario que vengas antes; todo se coordina directamente por WhatsApp.",
	},
	{
		incluye:   []string{"fonasa", "tarde"},
		respuesta: "Los bonos FONASA se deben comprar antes de las 14:00 hrs, de lunes a viernes.",
	},
	{
		incluye:   []string{"fonasa", "2pm"},
		respuesta: "Los bonos FONASA se deben comprar antes de las 14:00 hrs, de lunes a viernes.",
	},
}

// sinTildes normaliza acentos para que el matching sea más robusto
// (piso pélvico / piso pelvico, atención / atencion, etc.)
func sinTildes(s string) string {
	r := strings.NewReplacer(
		"á", "a", "é", "e", "í", "i", "ó", "o", "ú", "u",
	)
	return r.Replace(s)
}

// buscarFAQFelipe devuelve una respuesta fija si el texto matchea alguna regla.
func buscarFAQFelipe(texto string) (string, bool) {
	t := sinTildes(strings.ToLower(texto))
	for _, regla := range reglasFAQFelipe {
		match := true
		for _, palabra := range regla.incluye {
			if !strings.Contains(t, palabra) {
				match = false
				break
			}
		}
		if match {
			return regla.respuesta, true
		}
	}
	return "", false
}
