# Contexto del Proyecto: KineApp — meta-ai-agent

Proyecto de automatización de agenda kinesiológica con WhatsApp, construido como arquitectura de microservicios en Go + Python.  
**Cliente**: Felipe Castillo — Kinesiólogo, clínica en Santiago, Chile.

---

## 1. OBJETIVO DEL SISTEMA

Un bot de WhatsApp que permite a los pacientes de Felipe agendar, reagendar y cancelar horas de kinesiología directamente por chat, sin intervención humana. El kinesiólogo tiene un dashboard web para ver y gestionar su agenda, fichas clínicas y configurar el comportamiento del bot.

---

## 2. ARQUITECTURA — 7 microservicios

```
WhatsApp (Meta API)
    ↓
whatsapp-service :8080   ← recibe webhooks, reenvía a ai-service
    ↓
ai-service :8081         ← cerebro: clasifica intención → enruta → responde
    ↙          ↘
patients-service :8083   agenda-service :8082
(pacientes, fichas,       (citas: crear, reagendar,
 bot_config)              cancelar, marcar realizada)
    ↓
calendar-service :8085   ← Python/FastAPI, integra Google Calendar
    ↓
activities-service :8084 ← Go, catálogo de ejercicios de kinesiología
    ↓
dashboard-service :5000  ← Python/Flask, UI web para Felipe
```

**Stack**: Go 1.22 + Fiber v2 + GORM + SQLite (servicios Go), Python 3.11 + FastAPI/Flask (servicios Python), Docker Compose.

---

## 3. SERVICIOS — DETALLE

### patients-service (:8083)
**Base de datos**: SQLite compartida `agenda.db`  
**Entidades**: Patient, Ficha (ficha clínica), BotConfig  
**Endpoints principales**:
- `GET /health`
- `GET /pacientes` — lista todos
- `GET /pacientes/:telefono` — busca por teléfono (formato: `56912345678`)
- `POST /pacientes` — crea paciente `{nombre, telefono, email?, prevision?}`
- `PUT /pacientes/:telefono` — actualiza
- `DELETE /pacientes/:telefono`
- `GET /fichas/:telefono` — ficha clínica del paciente
- `POST /fichas` — crea ficha `{telefono, diagnostico, sesiones_prescritas, ...}`
- `PUT /fichas/:id` — actualiza ficha
- `GET /config/bot` — obtiene persona del bot
- `PUT /config/bot` — actualiza persona `{persona: "...", activo: true}`

---

### agenda-service (:8082)
**Base de datos**: SQLite compartida `agenda.db`  
**Entidad**: Cita (agen_id, agen_telefono, agen_fecha, agen_hora, agen_estado, agen_observacion, cal_event_id)  
**Estados de cita**: `PENDIENTE`, `REALIZADA`, `CANCELADA`  
**Endpoints principales**:
- `GET /health`
- `GET /agenda` — lista todas las citas
- `GET /agenda/:id` — cita por ID
- `GET /agenda/telefono/:telefono` — citas de un paciente
- `POST /agenda` — crea cita `{agen_telefono, agen_fecha, agen_hora, agen_diagnostico?, agen_estado?}`
- `PUT /reagendar/:id` — cambia fecha/hora → responde `{"ok": true}`
- `PUT /cancelar/:id` — cancela cita → responde `{"ok": true}`
- `PUT /realizada/:id` — marca como realizada → responde `{"ok": true}`
- `PUT /desmarcar/:id` — desmarca realizada → responde `{"ok": true}`
- `PATCH /agenda/:id/cal_event` — guarda ID de evento de Google Calendar
- `DELETE /agenda/:id`

⚠️ **IMPORTANTE**: Los PUT (reagendar/cancelar/realizada/desmarcar) retornan `{"ok": true}`, NO el objeto cita completo.

---

### ai-service (:8081)
**Cerebro del sistema**. Recibe mensajes de WhatsApp, clasifica intención con GPT-4o-mini, enruta a los servicios correctos y genera respuesta natural.

**Endpoint principal**: `POST /process` → `{numero: "56912345678", mensaje: "quiero agendar"}`

**Pipeline**:
1. Clasificador (`intent/classifier.go`) — llama a OpenAI con el mensaje
2. Router (`router/router.go`) — máquina de estados por conversación
3. Responder (`responder/natural.go`) — genera respuesta en lenguaje natural con OpenAI

**Intenciones soportadas**:
- `agendar_hora` → crea cita en agenda-service
- `reagendar_hora` → busca citas pendientes, pide nueva fecha/hora
- `cancelar_hora` → lista citas, pide confirmación, cancela
- `consultar_horas` / `consultar_sesiones` → muestra citas del paciente
- `crear_ficha` → guarda diagnóstico/lesión en patients-service
- `marcar_sesion_realizada`
- `saludo`
- `consulta_precio`, `consulta_fonasa`, `consulta_servicios`, `ayuda` → OpenAI responde usando la persona del bot

**Sesión**: en memoria (map por número de teléfono). Se resetea con "menu", "inicio", "salir", "volver", "reset".

**Persona del bot**: se carga desde `patients-service/config/bot` con caché de 5 minutos (`client/config_client.go`). Si falla, usa `defaultPersona()`.

**FAQ estática** (`router/faq_felipe.go`): respuestas hardcodeadas para preguntas comunes de Felipe antes de pasar a OpenAI.

**Detección bilateral** (`router/router.go`): si el mensaje menciona dos zonas/lados distintos del cuerpo → escala a Felipe sin crear ficha.

---

### whatsapp-service (:8080)
**Integración con Meta WhatsApp Business API**.
- `GET /webhook` — verificación de Meta (token en `META_VERIFY_TOKEN`)
- `POST /webhook` — recibe mensajes, reenvía a ai-service, responde al usuario
- Env vars: `META_VERIFY_TOKEN`, `META_ACCESS_TOKEN`, `PHONE_NUMBER_ID`

⚠️ El `META_ACCESS_TOKEN` expira (token temporal de 24h en pruebas, token permanente en producción).

---

### calendar-service (:8085)
**Python/FastAPI**. Integra con Google Calendar via Service Account.
- `GET /health`
- `GET /disponibilidad?fecha=YYYY-MM-DD` — retorna slots disponibles para una fecha
- `POST /crear_evento` — crea evento en Google Calendar
- `DELETE /eliminar_evento/{event_id}` — elimina evento

**Env vars**: `GOOGLE_CALENDAR_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`

⚠️ **URL correcta**: query param `?fecha=`, NO path param `/disponibilidad/YYYY-MM-DD`.

---

### activities-service (:8084)
**Go/Fiber**. Catálogo de ejercicios de kinesiología.
- `GET /health`
- CRUD de ejercicios (nombre, descripción, categoría, video_url)
- Base de datos propia: volumen Docker `activities_data:/app/data/activities.db`

---

### dashboard-service (:5000)
**Python/Flask**. UI web para Felipe.
**Páginas**:
- `/` — agenda del día (tabla de citas con acciones)
- `/agenda` — agenda completa con filtros
- `/pacientes` — lista de pacientes
- `/paciente/<telefono>` — detalle de paciente con fichas
- `/configuracion/bot` — editar persona/FAQ del bot
- `/estadisticas` — métricas de la clínica

---

## 4. BASE DE DATOS

**SQLite compartida** (`agenda.db`) entre patients-service y agenda-service.

### Tablas principales:
```sql
-- patients
patients (id, nombre, telefono UNIQUE, email, prevision, created_at)

-- agenda
citas (agen_id, agen_telefono, agen_fecha, agen_hora, agen_estado,
       agen_diagnostico, agen_observacion, cal_event_id, created_at)

-- fichas clínicas
fichas (id, telefono, diagnostico, sesiones_prescritas,
        sesiones_realizadas, observaciones, updated_at)

-- configuración del bot
bot_configs (id, persona TEXT, activo BOOLEAN, updated_at)
```

---

## 5. VARIABLES DE ENTORNO (.env en raíz)

```env
OPENAI_API_KEY=sk-...
META_VERIFY_TOKEN=mi_token_secreto
META_ACCESS_TOKEN=EAAxxxx...  # expira, renovar en Meta for Developers
PHONE_NUMBER_ID=123456789
GOOGLE_CALENDAR_ID=primary
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
CLINIC_LOCATION=Clínica de Kinesiología Felipe Castillo
```

---

## 6. PERSONA DEL BOT (Felipe)

Se carga en BD vía `PUT /config/bot`. Incluye:
- Precio fijo: **$10.000** por sesión
- Promo: **10 sesiones = $90.000**
- FONASA nivel 1: solo antes de las 14:00
- NO acepta bonos online
- NO hace masajes post-liposucción ni piso pélvico
- Atención grupal (max 3 personas, mismo diagnóstico)
- Coordinación únicamente por WhatsApp
- Derivación bilateral: si el paciente tiene dolor en dos zonas/lados distintos → escala a Felipe

---

## 7. TESTING

### Suite Postman/Newman (`tests/`)
- **Colección**: `tests/postman/KineApp.postman_collection.json`
- **Runner PowerShell**: `tests/run_tests.ps1`
- **Runner Bash**: `tests/run_tests.sh`
- **Override Docker test**: `docker-compose.test.yml`

**Resultado último run**: 83 requests, 137 assertions, **10 fallos** (todos lógica de bot/código, no infraestructura)

**BD aislada para tests**: volumen Docker `test_db` con `DB_PATH=/app/testdata/test.db` — se elimina antes de cada run para empezar limpio.

**Folders de la colección**:
1. `⚙ Setup` — carga persona de Felipe via `PUT /config/bot`
2. `Patients Service` — CRUD pacientes, fichas, bot_config
3. `Agenda Service` — CRUD citas, reagendar, cancelar, marcar realizada
4. `Calendar Service` — disponibilidad, crear/eliminar eventos
5. `AI Service` — proceso de mensajes, reset sesión
6. `E2E Bot` — flujos completos de conversación (saludo → agendar → reagendar → cancelar)

**Variables de colección**: `pac_telefono` y `e2e_phone` con timestamp dinámico para evitar duplicados.

### Suite pytest (`tests/test_bot_*.py`)
- `test_bot_agenda.py` — flujos de agenda
- `test_bot_fonasa.py` — respuestas FONASA
- `test_bot_precios.py` — respuestas de precios
- `test_bot_servicios.py` — servicios disponibles

---

## 8. PROBLEMAS CONOCIDOS / PENDIENTES

### Código (requieren fix):
1. **Router bilateral**: el clasificador detecta `crear_ficha` antes de que el router verifique bilateral. Solución: verificar bilateral ANTES de entrar al switch de intenciones.
2. **Alias "mis citas"**: el classifier no mapea "mis citas" → `consultar_horas`. Agregar al prompt.
3. **Servicios NO ofrecidos**: el bot a veces no rechaza masajes post-lipo / piso pélvico correctamente. Reformular reglas en persona como imperativas.
4. **Calendar assertions**: el test de disponibilidad falla porque el campo de respuesta del calendar-service no se llama `slots` — verificar nombre exacto del campo.
5. **Meta token expirado**: el `META_ACCESS_TOKEN` del entorno de pruebas venció. Renovar en Meta for Developers Console.

### Infraestructura:
6. **Google Calendar**: aún no está conectado con credenciales reales de Felipe. El service account está configurado pero sin calendario real asignado.

---

## 9. CÓMO CORRER EL SISTEMA

```bash
# Producción
cd C:\proyectos\github\meta-ai-agent
docker compose up --build -d

# Tests con BD aislada (PowerShell)
.\tests\run_tests.ps1

# Tests con BD aislada (Bash/Linux)
bash tests/run_tests.sh

# Ver logs
docker compose logs -f ai-service
docker compose logs -f whatsapp-service

# Dashboard web
http://localhost:5000

# Editar persona del bot
http://localhost:5000/configuracion/bot
```

---

## 10. ESTRUCTURA DE DIRECTORIOS

```
meta-ai-agent/
├── patients-service/          # Go: pacientes, fichas, bot_config
├── agenda-service/            # Go: citas (CRUD + estados)
├── ai-service/                # Go: clasificador + router + responder
│   └── internal/
│       ├── intent/classifier.go   # GPT-4o-mini clasifica intención
│       ├── router/router.go       # máquina de estados por conversación
│       ├── router/actions.go      # handlers de cada intención
│       ├── router/faq_felipe.go   # FAQ estática de la clínica
│       ├── responder/natural.go   # genera respuesta con OpenAI
│       ├── client/config_client.go # carga persona del bot (caché 5 min)
│       └── session/store.go       # sesiones en memoria por teléfono
├── whatsapp-service/          # Go: webhook Meta WhatsApp
├── calendar-service/          # Python/FastAPI: Google Calendar
├── activities-service/        # Go: catálogo de ejercicios
├── dashboard-service/         # Python/Flask: UI web
├── tests/
│   ├── postman/KineApp.postman_collection.json
│   ├── run_tests.ps1
│   ├── run_tests.sh
│   ├── results/               # JSON reports de Newman
│   └── Reporte_Pruebas_KineApp_v3.docx
├── docker-compose.yml
├── docker-compose.test.yml    # override: BD aislada para tests
└── agenda.db                  # SQLite producción
```

---

## 11. DECISIONES TÉCNICAS CLAVE

- **SQLite compartida** entre patients y agenda via volumen Docker montado como archivo — simple y funciona bien para escala de 1 clínica.
- **Sesiones en memoria** en ai-service — no persisten entre reinicios. Aceptable para flujos cortos de WhatsApp.
- **Persona del bot en BD** (no hardcodeada) — Felipe puede editarla desde el dashboard sin tocar código.
- **GPT-4o-mini** para clasificación (barato, rápido) + GPT-4o para respuestas naturales si la intención lo requiere.
- **FAQ estática** antes de OpenAI — ahorra tokens para preguntas frecuentes simples.
- **Docker named volume** para BD de test — se destruye antes de cada run garantizando BD limpia.
- **Newman con `--reporters 'cli,json'`** (comillas necesarias en PowerShell para evitar NativeCommandError).
