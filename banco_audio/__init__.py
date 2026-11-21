"""Banco de audio: saca tus canciones de Spotify, las busca en YouTube y las descarga en MP3."""

import json
import os
import sys
import zipimport
from pathlib import Path

# yt-dlp actualizado desde la app: componentes/yt-dlp.zip (la versión oficial de GitHub,
# verificada con SHA-256). Si es más nuevo que el incluido, se usa ese. Va aquí porque
# tiene que activarse antes de cualquier "import yt_dlp".
RAIZ_APP = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
YTDLP_ZIP = RAIZ_APP / "componentes" / "yt-dlp.zip"
# Niveles opcionales instalados desde el .exe (librosa, Demucs...): ver complementos.py.
COMPLEMENTOS = RAIZ_APP / "complementos"


def activar_complementos() -> None:
    """En el .exe, suma complementos/ a sys.path (al final: lo incluido en el .exe manda)."""
    if getattr(sys, "frozen", False) and COMPLEMENTOS.is_dir() and str(COMPLEMENTOS) not in sys.path:
        sys.path.append(str(COMPLEMENTOS))


def version_tupla(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


class _ImportadorYtDlp:
    """Sirve yt_dlp.* desde el zip, antes que la copia incluida (también en el .exe)."""

    def __init__(self, zip_: Path):
        self.zip = str(zip_)

    def find_spec(self, nombre, ruta=None, objetivo=None):
        if nombre != "yt_dlp" and not nombre.startswith("yt_dlp."):
            return None
        carpeta = os.path.join(self.zip, *nombre.split(".")[:-1])
        try:
            return zipimport.zipimporter(carpeta).find_spec(nombre)
        except zipimport.ZipImportError:
            return None


def _activar_ytdlp() -> None:
    info = YTDLP_ZIP.with_suffix(".json")
    if not YTDLP_ZIP.is_file() or not info.is_file() or "yt_dlp" in sys.modules:
        return
    try:
        nueva = json.loads(info.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return
    try:
        from importlib.metadata import version
        incluida = version("yt-dlp")
    except Exception:  # el .exe no trae los metadatos: se asume más vieja
        incluida = "0"
    if version_tupla(nueva) > version_tupla(incluida):
        sys.meta_path.insert(0, _ImportadorYtDlp(YTDLP_ZIP))


_activar_ytdlp()
activar_complementos()
