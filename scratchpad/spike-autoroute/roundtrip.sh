#!/usr/bin/env bash
# Spike autorouting — round-trip headless completo, reproducible.
# Uso: roundtrip.sh <src.kicad_pcb> <workdir> [run_label]
#
# Requisitos de SISTEMA (no de pyproject): java>=21, pcbnew (python del sistema
# que trae KiCad), freerouting.jar. Todo detectado abajo.
set -euo pipefail

SRC="${1:?falta src.kicad_pcb}"
WORK="${2:?falta workdir}"
LABEL="${3:-run}"
HERE="$(cd "$(dirname "$0")" && pwd)"

SYS_PY="${SYS_PY:-/usr/bin/python3}"
JAR="${FREEROUTING_JAR:-/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar}"
FR_ARGS="${FR_ARGS:-}"   # p.ej. "-mp 100" para más pasadas de optimización

mkdir -p "$WORK"
DSN="$WORK/${LABEL}.dsn"
SES="$WORK/${LABEL}.ses"
ROUTED="$WORK/${LABEL}.routed.kicad_pcb"
FRLOG="$WORK/${LABEL}.freerouting.log"

echo "=== [$LABEL] round-trip: $SRC ==="

# Paso 1: export DSN (dibuja contorno si falta, persiste en SRC)
"$SYS_PY" "$HERE/01_export_dsn.py" "$SRC" "$DSN" 2>&1 | grep -v "m_choices.GetCount" || true

# Paso 2: Freerouting headless. Medimos SOLO el router.
echo "=== [$LABEL] freerouting (router) ==="
T0=$(date +%s.%N)
timeout 600 java -jar "$JAR" -de "$DSN" -do "$SES" -host KiCad $FR_ARGS >"$FRLOG" 2>&1 || true
T1=$(date +%s.%N)
ROUTER_SECS=$(echo "$T1 - $T0" | bc)
echo "[$LABEL] router wall-clock: ${ROUTER_SECS}s"
if [ ! -s "$SES" ]; then
  echo "[$LABEL] ERROR: no se generó SES. Cola del log:"
  tail -20 "$FRLOG"
  exit 2
fi

# Paso 3: import SES + save
"$SYS_PY" "$HERE/02_import_ses.py" "$SRC" "$SES" "$ROUTED" 2>&1 | grep -v "m_choices.GetCount" || true

echo "[$LABEL] router_secs=${ROUTER_SECS}  routed=$ROUTED  log=$FRLOG"
