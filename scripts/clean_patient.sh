#!/bin/bash
# Borra a un paciente (y sus fichas/citas) de agenda.db por número de teléfono.
# Uso: ./clean_patient.sh 56996724919
set -e

TEL="${1:?Uso: ./clean_patient.sh <telefono>}"
DB="${DB_PATH:-/root/meta-ai-agent/agenda.db}"

if ! command -v sqlite3 >/dev/null; then
  echo "sqlite3 no está instalado. Corre: apt-get install -y sqlite3"
  exit 1
fi

echo "Paciente encontrado (si existe):"
sqlite3 "$DB" "SELECT pac_id, pac_nombres, pac_apellidos, pac_telefono FROM pacientes WHERE pac_telefono='$TEL';"

sqlite3 "$DB" "
DELETE FROM agenda   WHERE pac_id IN (SELECT pac_id FROM pacientes WHERE pac_telefono='$TEL');
DELETE FROM fichas   WHERE pac_id IN (SELECT pac_id FROM pacientes WHERE pac_telefono='$TEL');
DELETE FROM pacientes WHERE pac_telefono='$TEL';
"

RESTANTE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pacientes WHERE pac_telefono='$TEL';")
if [ "$RESTANTE" = "0" ]; then
  echo "Listo: $TEL quedó limpio (pacientes, fichas y agenda)."
else
  echo "Algo no se borró, revisa manualmente."
fi
