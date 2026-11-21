#!/usr/bin/env bash
# Lanzador del banco de audio para macOS y Linux.
# Sin argumentos abre el menú. Con una lista como argumento, la descarga.
# La primera vez crea el entorno de Python e instala lo necesario.
cd "$(dirname "$0")" || exit 1
PY=".venv/bin/python"

preparar() {
    echo
    echo "  Primera vez: preparando el entorno de Python..."
    local base=""
    for cand in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$cand" >/dev/null 2>&1; then base="$cand"; break; fi
    done
    if [ -z "$base" ] || ! "$base" -m venv .venv; then
        echo "  No se encontró Python 3.10 o superior. Guía: docs/INSTALACION.md"
        return 1
    fi
    if ! "$PY" -m pip install -r requirements.txt; then
        echo "  Falló la instalación de dependencias. Revisa tu conexión y vuelve a intentar."
        rm -rf .venv
        return 1
    fi
    [ -f .env ] || cp .env.example .env
    echo "  Listo. Para usar Spotify, completa tus credenciales en el archivo .env"
}

limpiar_ruta() {
    # Quita las comillas y los escapes que agrega la terminal al arrastrar un archivo.
    local f="$1"
    f="${f%\"}"; f="${f#\"}"; f="${f%\'}"; f="${f#\'}"
    printf '%s' "${f//\\ / }"
}

pedir_fuente() {
    echo
    echo "  Pega la ruta de un Excel, CSV o TXT, un enlace de playlist de Spotify"
    echo "  o escribe guardadas. También puedes arrastrar el archivo a esta ventana."
    read -r -p "  > " FUENTE
    FUENTE="$(limpiar_ruta "$FUENTE")"
}

pausa() { read -r -p "  Presiona Enter para continuar..." _; }

[ -x "$PY" ] || preparar || exit 1

if [ -n "$1" ]; then
    "$PY" -m banco_audio descargar "$1"
    exit $?
fi

while true; do
    clear
    cat <<'MENU'

  ==========================================
    BANCO DE AUDIO  -  IA-buscadorSpotify
  ==========================================

    1. Abrir el reproductor
    2. Descargar una lista, playlist o "guardadas"
    3. Probar sin descargar (simulación)
    4. Ver mis playlists de Spotify
    5. Exportar una playlist de Spotify a Excel
    6. Actualizar yt-dlp
    7. Lector rápido
    0. Salir

MENU
    read -r -p "  Elige una opción: " op
    case "$op" in
        1) "$PY" -m banco_audio app & ;;
        2) pedir_fuente; [ -n "$FUENTE" ] && "$PY" -m banco_audio descargar "$FUENTE"; pausa ;;
        3) pedir_fuente
           if [ -n "$FUENTE" ]; then
               read -r -p "  ¿Cuántas canciones probar? [5]: " lim
               "$PY" -m banco_audio descargar "$FUENTE" --simular --limite "${lim:-5}"
           fi
           pausa ;;
        4) "$PY" -m banco_audio playlists; pausa ;;
        5) read -r -p "  Enlace de la playlist o guardadas: " FUENTE
           [ -n "$FUENTE" ] && "$PY" -m banco_audio exportar "$FUENTE"; pausa ;;
        6) "$PY" -m pip install -U "yt-dlp[default]"; pausa ;;
        7) "$PY" lector/lector_rapido.py & ;;
        0) exit 0 ;;
    esac
done
