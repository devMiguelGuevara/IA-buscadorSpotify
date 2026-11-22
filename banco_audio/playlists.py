"""Playlists propias: archivos .m3u8 en la carpeta playlists/ (junto al proyecto o al .exe).

Guardan rutas absolutas, así que también las abre cualquier otro reproductor.
"""

from __future__ import annotations

import re
from pathlib import Path

from .spotify import RAIZ

CARPETA = RAIZ / "playlists"
# Las listas que escribe cada descarga llevan esta marca: la app las muestra como
# "listas descargadas" (no como playlists propias) y las oculta si ya no tienen canciones.
MARCA_DESCARGA = "#MIGUEWAMP:descarga"
_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _archivo(nombre: str) -> Path:
    limpio = _INVALIDOS.sub("", nombre).strip(" .")[:80]
    if not limpio:
        raise ValueError("La playlist necesita un nombre.")
    return CARPETA / f"{limpio}.m3u8"


def listar(raices: list[Path] | None = None) -> list[dict]:
    """Playlists con cuántas canciones existen hoy (canciones) y cuántas nombra (total)."""
    if not CARPETA.exists():
        return []
    descargas = raices[0].resolve() if raices else None
    salida = []
    for p in sorted(CARPETA.glob("*.m3u8"), key=lambda p: p.stem.lower()):
        rutas = [r for r, _, _ in _entradas(p) if not isinstance(r, str)]
        salida.append({"nombre": p.stem, "canciones": sum(1 for r in rutas if r.is_file()), "total": len(rutas),
                       "descarga": _es_de_descarga(p, rutas, descargas)})
    return salida


def _es_de_descarga(archivo: Path, rutas: list[Path], descargas: Path | None) -> bool:
    if MARCA_DESCARGA in _texto(archivo):
        return True
    # Listas de descargas anteriores a la marca: se llaman como la carpeta de la lista.
    for r in rutas:
        try:
            if descargas and r.resolve().relative_to(descargas).parts[0] == archivo.stem:
                return True
        except (ValueError, IndexError, OSError):
            continue
    return False


def _texto(archivo: Path) -> str:
    """Las .m3u viejas suelen venir en la codificación de Windows, no en UTF-8."""
    datos = archivo.read_bytes()
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("cp1252", errors="replace")


def _entradas(archivo: Path):
    """(ruta absoluta, título, duración) de cada entrada de un .m3u / .m3u8."""
    titulo, duracion = "", None
    for linea in _texto(archivo).splitlines():
        linea = linea.strip()
        if linea.startswith("#EXTINF:"):
            cabeza, _, titulo = linea[8:].partition(",")
            try:
                duracion = int(float(cabeza)) if float(cabeza) > 0 else None
            except ValueError:
                duracion = None
        elif linea and not linea.startswith("#"):
            if "://" in linea and not linea.lower().startswith("file:"):
                yield linea, titulo, duracion  # enlace de internet: no es un archivo
                titulo, duracion = "", None
                continue
            if linea.lower().startswith("file:"):
                from urllib.parse import unquote, urlsplit
                linea = unquote(urlsplit(linea).path).lstrip("/") if re.match(r"(?i)file:///[a-z]:", linea) else unquote(urlsplit(linea).path)
            ruta = Path(linea)
            if not ruta.is_absolute():
                ruta = (archivo.parent / ruta).resolve()
            yield ruta, titulo, duracion
            titulo, duracion = "", None


def _entradas_pls(archivo: Path):
    """(ruta absoluta, título, duración) de cada entrada de un .pls (FileN=, TitleN=, LengthN=)."""
    campos: dict[str, dict[str, str]] = {}
    for linea in _texto(archivo).splitlines():
        m = re.match(r"\s*(File|Title|Length)(\d+)\s*=\s*(.*)$", linea, re.I)
        if m:
            campos.setdefault(m.group(2), {})[m.group(1).lower()] = m.group(3).strip()
    for n in sorted(campos, key=int):
        c = campos[n]
        if not c.get("file"):
            continue
        try:
            duracion = int(c["length"]) if int(c.get("length", "-1")) > 0 else None
        except ValueError:
            duracion = None
        if "://" in c["file"]:
            yield c["file"], c.get("title", ""), duracion
            continue
        ruta = Path(c["file"])
        yield (ruta if ruta.is_absolute() else (archivo.parent / ruta).resolve()), c.get("title", ""), duracion


def importar(archivo: Path, raices: list[Path]) -> dict:
    """Trae una lista .m3u, .m3u8 o .pls de otro reproductor como playlist propia.

    Entran las canciones que están en la biblioteca. De las que existen fuera de ella se
    devuelven sus carpetas, para ofrecer agregarlas; las que no existen o son enlaces se cuentan.
    """
    entradas = _entradas_pls(archivo) if archivo.suffix.lower() == ".pls" else _entradas(archivo)
    bases = [r.resolve() for r in raices]
    pistas, fuera, faltan, enlaces = [], {}, 0, 0
    for ruta, titulo, duracion in entradas:
        if isinstance(ruta, str):
            enlaces += 1
            continue
        if not ruta.is_file():
            faltan += 1
            continue
        ruta = ruta.resolve()
        for i, base in enumerate(bases):
            if ruta.is_relative_to(base):
                artista, _, nombre_cancion = titulo.partition(" - ") if " - " in titulo else ("", "", titulo or ruta.stem)
                pistas.append({"raiz": i, "ruta": ruta.relative_to(base).as_posix(), "titulo": nombre_cancion,
                               "artista": artista, "duracion": duracion})
                break
        else:
            fuera[str(ruta.parent)] = fuera.get(str(ruta.parent), 0) + 1
    nombre = archivo.stem
    if pistas:
        if _archivo(nombre).exists():
            nombre = f"{nombre} (importada)"
        guardar(nombre, pistas, raices)
    return {"nombre": nombre if pistas else "", "canciones": len(pistas), "faltan": faltan, "enlaces": enlaces,
            "fuera": [{"carpeta": c, "canciones": n} for c, n in sorted(fuera.items(), key=lambda x: -x[1])]}


def leer(nombre: str, raices: list[Path]) -> list[dict]:
    """Pistas de la playlist que están dentro de la biblioteca, listas para reproducir."""
    archivo = _archivo(nombre)
    if not archivo.exists():
        raise FileNotFoundError(nombre)
    bases = [r.resolve() for r in raices]
    pistas = []
    for ruta, titulo, duracion in _entradas(archivo):
        if isinstance(ruta, str):
            continue
        for i, base in enumerate(bases):
            try:
                relativa = ruta.resolve().relative_to(base).as_posix()
            except ValueError:
                continue
            artista, _, nombre_cancion = titulo.partition(" - ") if " - " in titulo else ("", "", titulo or ruta.stem)
            pistas.append({"raiz": i, "ruta": relativa, "titulo": nombre_cancion, "artista": artista,
                           "duracion": duracion, "existe": ruta.exists()})
            break
    return pistas


def guardar(nombre: str, pistas: list[dict], raices: list[Path], agregar: bool = False,
            descarga: bool = False) -> int:
    """Escribe la playlist. Con agregar=True suma las pistas al final de la existente.
    descarga=True la marca como la lista de una descarga."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    archivo = _archivo(nombre)
    lineas = []
    if agregar and archivo.exists():
        previo = _texto(archivo)
        descarga = descarga or MARCA_DESCARGA in previo
        lineas = [l for l in previo.splitlines() if l.strip() and l.strip() not in ("#EXTM3U", MARCA_DESCARGA)]
    for p in pistas:
        try:
            ruta = raices[int(p["raiz"])] / p["ruta"]
        except (KeyError, IndexError, ValueError, TypeError):
            continue
        nombre_pista = f"{p.get('artista')} - {p.get('titulo')}" if p.get("artista") else (p.get("titulo") or ruta.stem)
        lineas += [f"#EXTINF:{int(p.get('duracion') or -1)},{nombre_pista}", str(ruta.resolve())]
    cabecera = "#EXTM3U\n" + (MARCA_DESCARGA + "\n" if descarga else "")
    archivo.write_text(cabecera + "\n".join(lineas) + "\n", encoding="utf-8")
    return sum(1 for l in lineas if not l.startswith("#"))


def borrar(nombre: str) -> None:
    archivo = _archivo(nombre)
    if archivo.exists():
        archivo.unlink()
