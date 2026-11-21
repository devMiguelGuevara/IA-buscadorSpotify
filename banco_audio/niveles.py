"""Volumen nivelado al reproducir (estilo ReplayGain), sin tocar los archivos.

Mide la sonoridad integrada (LUFS) y el true peak con ffmpeg (ebur128) y calcula la
ganancia para llevar cada canción a -14 LUFS, sin subirla tanto que pase de -1 dBTP.
Las medidas se recuerdan en cache/niveles.json por ruta, tamaño y fecha del archivo.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
from pathlib import Path

from . import RAIZ_APP
from .descargador import buscar_ffmpeg

OBJETIVO_LUFS = -14.0
TECHO_DBTP = -1.0
GANANCIA_MIN, GANANCIA_MAX = -12.0, 9.0
CACHE = RAIZ_APP / "cache" / "niveles.json"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_lock = threading.Lock()
_datos: dict[str, dict] | None = None
_midiendo: dict[str, threading.Lock] = {}


def _cargar() -> dict[str, dict]:
    global _datos
    if _datos is None:
        try:
            _datos = json.loads(CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _datos = {}
    return _datos


def _guardar() -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporal = CACHE.with_suffix(".tmp")
        temporal.write_text(json.dumps(_datos, ensure_ascii=False), encoding="utf-8")
        temporal.replace(CACHE)
    except OSError:
        pass


def medir(archivo: Path) -> dict:
    """LUFS integrado y true peak de todo el archivo (una pasada de ffmpeg)."""
    ffmpeg = buscar_ffmpeg()
    if not ffmpeg:
        return {}
    r = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(archivo), "-vn",
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300, creationflags=SIN_VENTANA)
    resumen = r.stderr[r.stderr.rfind("Summary:"):]

    def num(patron):
        m = re.search(patron, resumen)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None
    lufs, pico = num(r"I:\s+(-?[\d.]+) LUFS"), num(r"Peak:\s+(-?[\d.]+) dBFS")
    return {"lufs": lufs, "pico": pico} if lufs is not None and lufs > -70 else {}


def ganancia(medida: dict) -> float:
    """dB a aplicar: hacia el objetivo, sin pasar del techo de true peak."""
    if not medida.get("lufs"):
        return 0.0
    g = OBJETIVO_LUFS - medida["lufs"]
    if medida.get("pico") is not None:
        g = min(g, TECHO_DBTP - medida["pico"])
    return round(max(GANANCIA_MIN, min(GANANCIA_MAX, g)), 2)


def nivel(archivo: Path) -> dict:
    estado = archivo.stat()
    firma = f"{estado.st_size}:{int(estado.st_mtime)}"
    clave = str(archivo)
    with _lock:
        entrada = _cargar().get(clave)
        if entrada and entrada.get("firma") == firma:
            return entrada
        candado = _midiendo.setdefault(clave, threading.Lock())
    with candado:  # dos pedidos de la misma canción miden una sola vez
        with _lock:
            entrada = _cargar().get(clave)
            if entrada and entrada.get("firma") == firma:
                return entrada
        medida = medir(archivo)
        entrada = {"firma": firma, **medida, "ganancia_db": ganancia(medida)}
        with _lock:
            _cargar()[clave] = entrada
            _guardar()
            _midiendo.pop(clave, None)
    return entrada
