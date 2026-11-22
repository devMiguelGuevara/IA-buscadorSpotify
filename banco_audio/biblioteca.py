"""Indexar la biblioteca: recorre las carpetas de música y lee las etiquetas."""

from __future__ import annotations

import threading
from pathlib import Path

# Las últimas se reproducen a través de una copia FLAC en caché (ver conversion.py).
EXTENSIONES = {".mp3", ".m4a", ".opus", ".ogg", ".webm", ".flac", ".wav", ".aac",
               ".ape", ".wma", ".wv", ".aiff", ".aif", ".mpc", ".tta", ".ac3"}


def _leer(archivo: Path) -> dict:
    datos = {"titulo": "", "artista": "", "album": "", "artista_album": "", "numero": None, "anio": "",
             "duracion": None, "kbps": None, "khz": None}
    try:
        import mutagen
        audio = mutagen.File(archivo, easy=True)
        if audio is not None:
            etiquetas = audio.tags or {}

            def leer(*claves) -> str:
                # Las claves "fáciles" sirven para casi todo; WMA (ASF) y APEv2 (WavPack, APE, Musepack) usan las suyas.
                for k in claves:
                    try:
                        v = etiquetas.get(k)
                    except (KeyError, ValueError, TypeError):
                        v = None
                    if v:
                        v = v[0] if isinstance(v, list) else v
                        return str(getattr(v, "value", v)).strip()
                return ""
            datos["titulo"] = leer("title", "Title")
            datos["artista"] = leer("artist", "Author")
            datos["album"] = leer("album", "WM/AlbumTitle")
            datos["artista_album"] = leer("albumartist", "WM/AlbumArtist", "Album Artist", "AlbumArtist", "album_artist")
            numero = leer("tracknumber", "WM/TrackNumber", "Track").split("/")[0].strip()
            datos["numero"] = int(numero) if numero.isdigit() else None
            datos["anio"] = leer("date", "WM/Year", "Year")[:4]
            info = audio.info
            datos["duracion"] = round(info.length) if getattr(info, "length", None) else None
            if getattr(info, "bitrate", None):
                datos["kbps"] = round(info.bitrate / 1000)
            if getattr(info, "sample_rate", None):
                datos["khz"] = round(info.sample_rate / 1000, 1)
    except Exception:
        pass
    if not datos["titulo"]:
        # Sin etiquetas: el nombre del archivo es "Artista - Título".
        partes = archivo.stem.split(" - ", 1)
        datos["artista"], datos["titulo"] = (partes if len(partes) == 2 else ("", archivo.stem))
    return datos


_memoria: dict[str, tuple[str, dict]] = {}   # ruta -> (tamaño:fecha, etiquetas)
_memoria_lock = threading.Lock()


def _leer_recordando(archivo: Path) -> dict:
    estado = archivo.stat()
    firma = f"{estado.st_size}:{estado.st_mtime_ns}"
    clave = str(archivo)
    with _memoria_lock:
        guardado = _memoria.get(clave)
    if guardado and guardado[0] == firma:
        return dict(guardado[1])
    datos = _leer(archivo)
    with _memoria_lock:
        _memoria[clave] = (firma, datos)
    return dict(datos)


def escanear(raiz: Path) -> list[dict]:
    """Canciones de la biblioteca. La lista es la primera subcarpeta."""
    if not raiz.exists():
        return []
    canciones = []
    for archivo in sorted(raiz.rglob("*")):
        relativa = archivo.relative_to(raiz)
        if archivo.suffix.lower() not in EXTENSIONES or any(p.startswith(("_", ".")) for p in relativa.parts):
            continue
        canciones.append(pista(archivo, raiz))
    return canciones


def pista(archivo: Path, raiz: Path) -> dict:
    """Datos de un archivo de la biblioteca (relativo a su carpeta raíz)."""
    relativa = archivo.relative_to(raiz)
    return {
        "ruta": relativa.as_posix(),
        "lista": relativa.parts[0] if len(relativa.parts) > 1 else "",
        "formato": archivo.suffix.lower().lstrip("."),
        **_leer_recordando(archivo),
    }
