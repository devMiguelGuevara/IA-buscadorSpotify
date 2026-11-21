"""Formatos que el motor web de la ventana no reproduce (APE, WMA, WavPack, AIFF, Musepack,
TTA, AC3): se convierten una vez a FLAC, sin pérdida, solo para escucharlos.

La copia vive en cache/reproduccion/ y se reutiliza mientras el original no cambie. El
original nunca se toca. La caché se recorta sola a TOPE_BYTES, borrando lo más viejo.
"""

from __future__ import annotations

import hashlib
import subprocess
import threading
from pathlib import Path

from . import RAIZ_APP
from .descargador import buscar_ffmpeg

A_CONVERTIR = {".ape", ".wma", ".wv", ".aiff", ".aif", ".mpc", ".tta", ".ac3"}
CACHE = RAIZ_APP / "cache" / "reproduccion"
TOPE_BYTES = 3 * 1024 ** 3
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_candados: dict[str, threading.Lock] = {}
_lock = threading.Lock()


def necesita(archivo: Path) -> bool:
    return archivo.suffix.lower() in A_CONVERTIR


def para_reproducir(archivo: Path) -> Path:
    """La copia FLAC del archivo (la crea si falta). Lanza RuntimeError si no se puede."""
    estado = archivo.stat()
    firma = hashlib.sha1(f"{archivo.resolve()}|{estado.st_size}|{int(estado.st_mtime)}".encode()).hexdigest()[:20]
    destino = CACHE / f"{firma}.flac"
    if destino.is_file():
        destino.touch()  # recién usado: lo último en borrarse
        return destino
    with _lock:
        candado = _candados.setdefault(firma, threading.Lock())
    with candado:  # dos pedidos del mismo archivo convierten una sola vez
        if destino.is_file():
            return destino
        ffmpeg = buscar_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("Falta ffmpeg para reproducir este formato")
        CACHE.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(".tmp.flac")
        r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(archivo),
                            "-map", "0:a:0", "-map_metadata", "0", "-c:a", "flac", str(temporal)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=600, creationflags=SIN_VENTANA)
        if r.returncode != 0 or not temporal.is_file():
            temporal.unlink(missing_ok=True)
            raise RuntimeError((r.stderr.strip().splitlines() or ["ffmpeg no pudo convertirlo"])[-1])
        temporal.replace(destino)
        with _lock:
            _candados.pop(firma, None)
    _recortar()
    return destino


def _recortar() -> None:
    archivos = sorted(CACHE.glob("*.flac"), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in archivos)
    for p in archivos:
        if total <= TOPE_BYTES:
            break
        total -= p.stat().st_size
        p.unlink(missing_ok=True)
