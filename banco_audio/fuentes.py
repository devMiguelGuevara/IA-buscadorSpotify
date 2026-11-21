"""Resolver de dónde vienen las canciones: lo que el usuario pega o indica.

Acepta, una por línea:
- Enlaces de Spotify: playlist, álbum, canción, o la palabra "guardadas".
- Enlaces de YouTube, YouTube Music, SoundCloud y cualquier sitio que yt-dlp
  soporte: un video o una playlist entera.
- Rutas a listas en Excel, CSV o TXT.
- Texto suelto, una canción por línea: "Artista - Título".

Devuelve excepciones en vez de cerrar el programa, para que la CLI y la app
puedan mostrar el error a su manera.
"""

from __future__ import annotations

from pathlib import Path

from .cancion import Cancion
from .listas import leer_lista

NOMBRE_SUELTAS = "Canciones pegadas"


class FuenteInvalida(ValueError):
    """Lo indicado no se pudo leer como lista, enlace ni canción."""


class _Silencio:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def es_enlace(texto: str) -> bool:
    return texto.startswith(("http://", "https://", "spotify:"))


def _limpiar(texto: str) -> str:
    return texto.strip().strip('"').strip("'").strip()


def es_fuente(texto: str) -> bool:
    """True si la línea es un enlace, un archivo de lista o "guardadas" (y no una canción suelta)."""
    from .spotify import es_fuente_spotify
    texto = _limpiar(texto)
    if es_enlace(texto) or es_fuente_spotify(texto):
        return True
    try:
        return Path(texto).expanduser().is_file()
    except OSError:
        return False


def cargar_fuente(fuente: str) -> tuple[str, list[Cancion]]:
    """Devuelve (nombre de la lista, canciones) para una fuente."""
    from .spotify import cliente, es_fuente_spotify, obtener_canciones
    texto = _limpiar(fuente)
    if not texto:
        raise FuenteInvalida("No indicaste ninguna fuente.")
    if es_fuente_spotify(texto):
        return obtener_canciones(cliente(), texto)
    if es_enlace(texto):
        return _enlace(texto)
    ruta = Path(texto).expanduser()
    if ruta.is_dir():
        raise FuenteInvalida(f"Es una carpeta, no un archivo de lista: {texto}")
    if ruta.exists():
        try:
            return ruta.stem, leer_lista(ruta)
        except ValueError as e:
            raise FuenteInvalida(str(e)) from e
    raise FuenteInvalida(f"No existe el archivo ni es un enlace reconocido: {fuente}")


def cancion_de_texto(linea: str) -> Cancion | None:
    """Una canción escrita a mano: "Artista - Título" o solo el título."""
    linea = _limpiar(linea)
    if not linea:
        return None
    if " - " in linea:
        artista, titulo = linea.split(" - ", 1)
        return Cancion(titulo=titulo.strip(), artista=artista.strip())
    return Cancion(titulo=linea, artista="")


def partir(texto: str) -> list[str | list[str]]:
    """Separa lo pegado en fuentes (una por línea) y un grupo con las canciones sueltas."""
    grupos: list[str | list[str]] = []
    sueltas: list[str] = []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        (grupos if es_fuente(linea) else sueltas).append(_limpiar(linea))
    if sueltas:
        grupos.append(sueltas)
    return grupos


def cargar_grupo(grupo: str | list[str]) -> tuple[str, list[Cancion]]:
    if isinstance(grupo, str):
        return cargar_fuente(grupo)
    return NOMBRE_SUELTAS, [c for linea in grupo if (c := cancion_de_texto(linea))]


def nombre_grupo(grupo: str | list[str]) -> str:
    return grupo if isinstance(grupo, str) else NOMBRE_SUELTAS


# ------------------------------------------------------------- enlaces (yt-dlp)
def _enlace(url: str) -> tuple[str, list[Cancion]]:
    """Un video o una playlist de YouTube, SoundCloud u otro sitio que yt-dlp soporte."""
    import yt_dlp
    opciones = {
        "quiet": True, "no_warnings": True, "logger": _Silencio(), "skip_download": True,
        "extract_flat": "in_playlist", "js_runtimes": {"deno": {}, "node": {}},
    }
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise FuenteInvalida(f"No se pudo leer el enlace: {str(e).removeprefix('ERROR: ')[:200]}") from e

    entradas = info.get("entries")
    if entradas is None:
        cancion = _desde_info(info, url)
        if not cancion:
            raise FuenteInvalida(f"El enlace no tiene audio reconocible: {url}")
        return "Sueltas", [cancion]
    canciones = [c for e in entradas if e and (c := _desde_info(e))]
    return (info.get("title") or "Enlace").strip(), canciones


def _desde_info(e: dict, url: str | None = None) -> Cancion | None:
    enlace = url or e.get("webpage_url") or e.get("url") or ""
    if not enlace.startswith("http") and e.get("id") and (e.get("ie_key") or "").lower().startswith("youtube"):
        enlace = f"https://www.youtube.com/watch?v={e['id']}"
    titulo = (e.get("track") or e.get("title") or "").strip()
    if not enlace or not titulo or titulo in ("[Private video]", "[Deleted video]"):
        return None
    artistas = e.get("artists")
    artista = e.get("artist") or (", ".join(artistas) if isinstance(artistas, list) else "")
    if not artista:
        if " - " in titulo:  # títulos de video tipo "Artista - Canción"
            artista, titulo = (p.strip() for p in titulo.split(" - ", 1))
        else:
            artista = (e.get("channel") or e.get("uploader") or "").removesuffix(" - Topic").strip()
    duracion = e.get("duration")
    return Cancion(titulo=titulo, artista=artista, album=e.get("album") or "",
                   duracion=int(duracion) if duracion else None, url=enlace)
