"""Leer y guardar listas de canciones en Excel, CSV o TXT."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook, load_workbook

from .cancion import Cancion, duracion_a_segundos, normalizar, segundos_a_duracion

COLUMNAS = ["#", "Título", "Artista", "Álbum", "Duración", "Spotify ID"]

# Nombres de columna reconocidos (normalizados) -> campo de Cancion.
# Incluye los de Exportify ("Track Name", "Artist Name(s)", "Duration (ms)"...).
_ALIAS = {
    "titulo": "titulo", "track name": "titulo", "title": "titulo", "name": "titulo",
    "artista": "artista", "artist name s": "artista", "artist": "artista", "artists": "artista",
    "album": "album", "album name": "album",
    "duracion": "duracion", "duration": "duracion", "duration ms": "duracion_ms",
    "spotify id": "spotify_id", "track uri": "spotify_id", "track id": "spotify_id",
}


def leer_lista(ruta: Path) -> list[Cancion]:
    sufijo = ruta.suffix.lower()
    if sufijo in (".xlsx", ".xlsm"):
        libro = load_workbook(ruta, read_only=True, data_only=True)
        filas = [list(f) for f in libro.worksheets[0].iter_rows(values_only=True)]
        libro.close()
    elif sufijo == ".csv":
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.reader(f))
    elif sufijo == ".txt":
        filas = [[linea] for linea in ruta.read_text(encoding="utf-8").splitlines()]
    else:
        raise ValueError(f"Formato no soportado: {ruta.suffix} (usa .xlsx, .csv o .txt)")
    return _interpretar_filas(filas)


def _interpretar_filas(filas: list[list]) -> list[Cancion]:
    filas = [f for f in filas if any(c not in (None, "") for c in f)]
    if not filas:
        return []

    columnas = {i: _ALIAS.get(normalizar(str(c or ""))) for i, c in enumerate(filas[0])}
    if {"titulo", "artista"} <= set(columnas.values()):
        return [c for f in filas[1:] if (c := _desde_columnas(f, columnas))]

    # Formato libre: una celda por fila con "Título - Artista - Álbum - m:ss".
    canciones = []
    for fila in filas:
        texto = max((str(c) for c in fila if isinstance(c, str)), key=len, default="")
        if " - " in texto and (cancion := Cancion.desde_texto(texto)):
            canciones.append(cancion)
    return canciones


def _desde_columnas(fila: list, columnas: dict[int, str | None]) -> Cancion | None:
    datos = {campo: fila[i] for i, campo in columnas.items() if campo and i < len(fila)}
    titulo = str(datos.get("titulo") or "").strip()
    if not titulo:
        return None
    if datos.get("duracion_ms"):
        duracion = int(float(datos["duracion_ms"]) // 1000)
    else:
        duracion = duracion_a_segundos(str(datos.get("duracion") or ""))
    spotify_id = str(datos.get("spotify_id") or "").removeprefix("spotify:track:")
    return Cancion(
        titulo=titulo,
        artista=str(datos.get("artista") or "").strip(),
        album=str(datos.get("album") or "").strip(),
        duracion=duracion,
        spotify_id=spotify_id,
    )


def guardar_lista(canciones: list[Cancion], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas = [
        [i, c.titulo, c.artista, c.album, segundos_a_duracion(c.duracion), c.spotify_id]
        for i, c in enumerate(canciones, 1)
    ]
    if ruta.suffix.lower() == ".csv":
        with ruta.open("w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.writer(f)
            escritor.writerow(COLUMNAS)
            escritor.writerows(filas)
        return

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Canciones"
    hoja.append(COLUMNAS)
    for fila in filas:
        hoja.append(fila)
    for letra, ancho in zip("ABCDEF", (5, 45, 35, 40, 10, 24)):
        hoja.column_dimensions[letra].width = ancho
    hoja.freeze_panes = "A2"
    libro.save(ruta)
