#!/usr/bin/env bash
# tests/run_tests.sh — Runner de pruebas con BD aislada (Linux/Mac)
#
# Uso:
#   cd /ruta/a/meta-ai-agent
#   bash tests/run_tests.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$PROJECT_ROOT/tests/results"
COLLECTION="$PROJECT_ROOT/tests/postman/KineApp.postman_collection.json"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_JSON="$RESULTS_DIR/run_$TIMESTAMP.json"

KEEP_UP=false
NO_BUILD=false

for arg in "$@"; do
  case $arg in
    --keep-up)   KEEP_UP=true ;;
    --no-build)  NO_BUILD=true ;;
  esac
done

step()  { echo -e "\n\033[36m▶ $*\033[0m"; }
ok()    { echo -e "  \033[32m✅ $*\033[0m"; }
warn()  { echo -e "  \033[33m⚠️  $*\033[0m"; }
fail()  { echo -e "  \033[31m❌ $*\033[0m"; }

wait_service() {
  local url=$1 name=$2
  for i in $(seq 1 30); do
    if curl -sf "$url" >/dev/null 2>&1; then
      ok "$name responde"
      return 0
    fi
    printf "  ⏳ Esperando %s... (%d/30)\r" "$name" "$i"
    sleep 2
  done
  fail "$name no respondió"
  return 1
}

# ─── Verificar dependencias ────────────────────────────────────────────────────
step "Verificando dependencias"
command -v docker   >/dev/null || { fail "Docker no encontrado"; exit 1; }
command -v newman   >/dev/null || { fail "Newman no encontrado. Instalar: npm install -g newman"; exit 1; }
[[ -f "$COLLECTION" ]]        || { fail "Colección no encontrada: $COLLECTION"; exit 1; }
mkdir -p "$RESULTS_DIR"
ok "Todo disponible"

# ─── 1. Limpiar volumen ────────────────────────────────────────────────────────
step "Eliminando volumen de BD de test (BD limpia)"
cd "$PROJECT_ROOT"
docker volume rm meta-ai-agent_test_db 2>/dev/null || true
ok "Volumen eliminado (o no existía)"

# ─── 2. Levantar servicios ────────────────────────────────────────────────────
step "Levantando servicios con BD de test"
BUILD_FLAG="--build"
[[ "$NO_BUILD" == "true" ]] && BUILD_FLAG=""
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d $BUILD_FLAG
ok "Servicios iniciados"

# ─── 3. Health checks ─────────────────────────────────────────────────────────
step "Esperando servicios"
sleep 5
ALL_UP=true
wait_service "http://localhost:8083/health" "patients-service  (:8083)" || ALL_UP=false
wait_service "http://localhost:8082/health" "agenda-service    (:8082)" || ALL_UP=false
wait_service "http://localhost:8081/health" "ai-service        (:8081)" || ALL_UP=false
wait_service "http://localhost:8080/health" "whatsapp-service  (:8080)" || ALL_UP=false
wait_service "http://localhost:8085/health" "calendar-service  (:8085)" || ALL_UP=false
wait_service "http://localhost:5000/health" "dashboard-service (:5000)" || ALL_UP=false

[[ "$ALL_UP" == "false" ]] && warn "Algunos servicios no respondieron"

# ─── 4. Newman ────────────────────────────────────────────────────────────────
step "Corriendo Newman"
newman run "$COLLECTION" \
  --timeout-request 15000 \
  --delay-request 500 \
  --reporters cli,json \
  --reporter-json-export "$REPORT_JSON"
NEWMAN_EXIT=$?

# ─── 5. Resultado ─────────────────────────────────────────────────────────────
step "Resultado"
if [[ $NEWMAN_EXIT -eq 0 ]]; then
  ok "Todas las pruebas pasaron ✔"
else
  warn "Hubo fallos. Reporte: $REPORT_JSON"
fi

# ─── 6. Bajar servicios ───────────────────────────────────────────────────────
if [[ "$KEEP_UP" != "true" ]]; then
  step "Bajando servicios de test"
  docker compose -f docker-compose.yml -f docker-compose.test.yml down
  ok "Servicios detenidos"
else
  warn "Servicios siguen corriendo (--keep-up activo)"
fi

echo ""
exit $NEWMAN_EXIT
