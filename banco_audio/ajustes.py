"""Ajustes de la app (ajustes.json, junto al proyecto o al .exe) y carpetas de la biblioteca.

La biblioteca tiene una carpeta de descargas (siempre la primera, índice 0) y
cualquier número de carpetas extra que el usuario agregue, como las "carpetas
vigiladas" de Winamp.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .spotify import RAIZ

ARCHIVO = RAIZ / "ajustes.json"
_lock = threading.Lock()


def leer() -> dict:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar(cambios: dict) -> dict:
    with _lock:
        datos = leer() | dict(cambios or {})
        try:
            ARCHIVO.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return datos


_defecto: Path | None = None


def fijar_defecto(ruta: Path) -> None:
    """Carpeta de descargas si el usuario no eligió otra (la de --destino o BANCO_AUDIO_DIR)."""
    global _defecto
    _defecto = Path(ruta).expanduser()


def descargas_por_defecto() -> Path:
    return _defecto or Path(os.getenv("BANCO_AUDIO_DIR") or RAIZ / "musica").expanduser()


def carpetas() -> list[Path]:
    """Carpetas de la biblioteca: la de descargas primero y luego las extra."""
    c = leer().get("carpetas") or {}
    descargas = Path(c.get("descargas") or descargas_por_defecto()).expanduser()
    lista = [descargas]
    for extra in c.get("extra") or []:
        p = Path(extra).expanduser()
        if p not in lista:
            lista.append(p)
    return lista


def _guardar_carpetas(descargas: Path, extra: list[Path]) -> None:
    guardar({"carpetas": {"descargas": str(descargas), "extra": [str(p) for p in extra]}})


def agregar_carpeta(ruta: str) -> None:
    p = Path(ruta.strip().strip('"')).expanduser()
    if not p.is_dir():
        raise ValueError(f"No existe la carpeta: {ruta}")
    actuales = carpetas()
    if p not in actuales:
        _guardar_carpetas(actuales[0], actuales[1:] + [p])


def quitar_carpeta(ruta: str) -> None:
    actuales = carpetas()
    p = Path(ruta).expanduser()
    _guardar_carpetas(actuales[0], [c for c in actuales[1:] if c != p])


def cambiar_descargas(ruta: str) -> None:
    p = Path(ruta.strip().strip('"')).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    actuales = carpetas()
    anterior = actuales[0]
    extra = [c for c in actuales[1:] if c != p]
    if anterior != p and anterior.exists() and anterior not in extra:
        extra.insert(0, anterior)  # la carpeta anterior sigue en la biblioteca
    _guardar_carpetas(p, extra)
