#!/bin/bash
# Arranca el servidor Python y abre el ejecutable 3D de Campo3D.
#
# Uso: doble clic en este archivo (o en Terminal: ./iniciar_campo3d.command)
# Al cerrar el juego se detiene el servidor.

set -u

RAIZ="$(cd "$(dirname "$0")" && pwd)"
APP="$RAIZ/escenario/Builds/Campo3D.app"
PYTHON="$RAIZ/.venv/bin/python"
SERVIDOR_PY="$RAIZ/Agentes/agentesPrueba.py"
LOG="/tmp/campo3d_servidor.log"

if [ ! -x "$PYTHON" ]; then
    echo "No se encontro $PYTHON. Corre: uv sync"
    exit 1
fi

if [ ! -d "$APP" ]; then
    echo "No se encontro el ejecutable en $APP"
    echo "Compilalo desde Unity: Herramientas > Campo 3D > Construir macOS"
    exit 1
fi

echo "Iniciando servidor Python..."
"$PYTHON" "$SERVIDOR_PY" >"$LOG" 2>&1 &
SERVIDOR=$!

# Esperar a que el puerto responda (maximo 15 s)
for _ in $(seq 1 30); do
    if curl -s -m 1 http://127.0.0.1:5000/ >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

echo "Abriendo Campo3D..."
"$APP/Contents/MacOS/escenario"

kill "$SERVIDOR" 2>/dev/null
wait "$SERVIDOR" 2>/dev/null

echo "Listo."
