# tests/run_tests.ps1 — Runner de pruebas con BD aislada
#
# Uso:
#   cd C:\proyectos\github\meta-ai-agent
#   .\tests\run_tests.ps1
#
# Qué hace:
#   1. Elimina el volumen test_db (BD siempre limpia)
#   2. Levanta servicios con BD de test (docker-compose.test.yml)
#   3. Espera que todos los health checks pasen
#   4. Corre Newman con la colección Postman
#   5. Guarda resultados JSON en tests/results/
#   6. Baja los servicios de test

param(
    [switch]$KeepUp,           # No bajar servicios al terminar (para depurar)
    [switch]$NoBuild,          # No rebuildar imágenes (más rápido si el código no cambió)
    [int]$WaitSeconds = 20     # Segundos a esperar por los servicios
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$resultsDir  = Join-Path $projectRoot "tests\results"
$collection  = Join-Path $projectRoot "tests\postman\KineApp.postman_collection.json"
$timestamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$reportJson  = Join-Path $resultsDir "run_$timestamp.json"

# ─── Colores ──────────────────────────────────────────────────────────────────
function Write-Step($msg)  { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "  ✅ $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  ⚠️  $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "  ❌ $msg" -ForegroundColor Red }

# ─── Función: esperar health check ────────────────────────────────────────────
function Wait-Service($url, $name) {
    $max = 30
    for ($i = 1; $i -le $max; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -eq 200) {
                Write-OK "$name responde ($url)"
                return $true
            }
        } catch { }
        Write-Host "  ⏳ Esperando $name... ($i/$max)" -NoNewline
        Write-Host "`r" -NoNewline
        Start-Sleep -Seconds 2
    }
    Write-Fail "$name no respondió después de $($max * 2) segundos"
    return $false
}

# ─── Verificar dependencias ────────────────────────────────────────────────────
Write-Step "Verificando dependencias"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fail "Docker no encontrado"
    exit 1
}
Write-OK "Docker disponible"

if (-not (Get-Command newman -ErrorAction SilentlyContinue)) {
    Write-Fail "Newman no encontrado. Instalar con: npm install -g newman"
    exit 1
}
Write-OK "Newman disponible"

if (-not (Test-Path $collection)) {
    Write-Fail "Colección Postman no encontrada: $collection"
    exit 1
}
Write-OK "Colección encontrada"

if (-not (Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir | Out-Null
}

# ─── 1. Limpiar volumen de test ────────────────────────────────────────────────
Write-Step "Eliminando volumen de BD de test (BD limpia)"
Set-Location $projectRoot
try { docker volume rm meta-ai-agent_test_db 2>$null } catch {}
Write-OK "Volumen eliminado (o no existía)"

# ─── 2. Levantar servicios con BD de test ─────────────────────────────────────
Write-Step "Levantando servicios con BD de test"

$buildFlag = if ($NoBuild) { "" } else { "--build" }
$composeCmd = "docker compose -f docker-compose.yml -f docker-compose.test.yml up -d $buildFlag"

Write-Host "  Ejecutando: $composeCmd"
Invoke-Expression $composeCmd

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Error al levantar servicios"
    exit 1
}
Write-OK "Servicios iniciados"

# ─── 3. Esperar health checks ─────────────────────────────────────────────────
Write-Step "Esperando que los servicios estén listos (~$WaitSeconds s)"
Start-Sleep -Seconds 5   # Pequeña pausa inicial

$services = @(
    @{ url = "http://localhost:8083/health"; name = "patients-service  (:8083)" },
    @{ url = "http://localhost:8082/health"; name = "agenda-service    (:8082)" },
    @{ url = "http://localhost:8081/health"; name = "ai-service        (:8081)" },
    @{ url = "http://localhost:8080/health"; name = "whatsapp-service  (:8080)" },
    @{ url = "http://localhost:8085/health"; name = "calendar-service  (:8085)" },
    @{ url = "http://localhost:5000/health"; name = "dashboard-service (:5000)" }
)

$allUp = $true
foreach ($svc in $services) {
    $ok = Wait-Service $svc.url $svc.name
    if (-not $ok) { $allUp = $false }
}

if (-not $allUp) {
    Write-Warn "Algunos servicios no respondieron. Los tests podrían fallar."
    Write-Host "  Puedes inspeccionar los logs con: docker compose logs"
}

# ─── 4. Correr Newman ─────────────────────────────────────────────────────────
Write-Step "Corriendo Newman"
Write-Host "  Colección : $collection"
Write-Host "  Reporte   : $reportJson"

newman run $collection `
    --timeout-request 15000 `
    --delay-request 500 `
    --reporters 'cli,json' `
    --reporter-json-export $reportJson

$newmanExit = $LASTEXITCODE

# ─── 5. Resultados ────────────────────────────────────────────────────────────
Write-Step "Resultado"
if ($newmanExit -eq 0) {
    Write-OK "Todas las pruebas pasaron ✔"
} else {
    Write-Warn "Hubo fallos (exit code $newmanExit). Revisa el reporte:"
    Write-Host "  $reportJson"
}

# ─── 6. Bajar servicios ───────────────────────────────────────────────────────
if (-not $KeepUp) {
    Write-Step "Bajando servicios de test"
    docker compose -f docker-compose.yml -f docker-compose.test.yml down
    Write-OK "Servicios detenidos"
} else {
    Write-Warn "KeepUp activo — servicios siguen corriendo con BD de test"
    Write-Host "  Para bajarlos: docker compose -f docker-compose.yml -f docker-compose.test.yml down"
}

Write-Host ""
exit $newmanExit
