"""Actualizar yt-dlp sin reempaquetar: baja la versión oficial de GitHub y la verifica.

YouTube cambia seguido y yt-dlp lo sigue con versiones nuevas. El archivo "yt-dlp" de cada
versión es un zip de Python; se guarda en componentes/yt-dlp.zip solo si su SHA-256 coincide
con el publicado en SHA2-256SUMS. Se activa al reiniciar la app (ver banco_audio/__init__.py).
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
import zipfile
from datetime import datetime

from . import YTDLP_ZIP, version_tupla

API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
AGENTE = {"User-Agent": "MigueWamp (actualizador de yt-dlp)"}


class ErrorActualizacion(Exception):
    pass


def _bajar(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=timeout) as r:
        return r.read()


def version_en_uso() -> str:
    import yt_dlp.version
    return yt_dlp.version.__version__


def estado() -> dict:
    """Versión en uso, si viene del zip actualizado y si hay una bajada que espera reinicio."""
    import yt_dlp
    en_uso = version_en_uso()
    bajada = None
    try:
        bajada = json.loads(YTDLP_ZIP.with_suffix(".json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        pass
    return {
        "version": en_uso,
        "actualizada": str(YTDLP_ZIP) in (getattr(yt_dlp, "__file__", "") or ""),
        "pendiente": bajada if bajada and version_tupla(bajada) > version_tupla(en_uso) else None,
    }


def ultima() -> dict:
    try:
        datos = json.loads(_bajar(API, 20))
    except Exception as e:
        raise ErrorActualizacion(f"No se pudo consultar GitHub: {e}") from e
    archivos = {a["name"]: a["browser_download_url"] for a in datos.get("assets", [])}
    if "yt-dlp" not in archivos or "SHA2-256SUMS" not in archivos:
        raise ErrorActualizacion("La versión publicada no trae los archivos esperados")
    return {"version": datos["tag_name"], "url": archivos["yt-dlp"], "sumas": archivos["SHA2-256SUMS"]}


def hay_nueva() -> dict:
    e = estado()
    u = ultima()
    referencia = e["pendiente"] or e["version"]
    return e | {"ultima": u["version"], "hay_nueva": version_tupla(u["version"]) > version_tupla(referencia)}


def actualizar() -> dict:
    """Baja, verifica (SHA-256 y contenido) e instala la última versión. Pide reiniciar."""
    u = ultima()
    sumas = _bajar(u["sumas"], 30).decode("utf-8", "replace")
    esperado = next((l.split()[0].lower() for l in sumas.splitlines()
                     if len(l.split()) == 2 and l.split()[1].lstrip("*") == "yt-dlp"), None)
    if not esperado:
        raise ErrorActualizacion("SHA2-256SUMS no trae la suma de yt-dlp")
    contenido = _bajar(u["url"], 180)
    if hashlib.sha256(contenido).hexdigest() != esperado:
        raise ErrorActualizacion("La descarga no coincide con su SHA-256: no se instaló")

    YTDLP_ZIP.parent.mkdir(parents=True, exist_ok=True)
    temporal = YTDLP_ZIP.with_suffix(".descarga")
    temporal.write_bytes(contenido)
    try:
        with zipfile.ZipFile(temporal) as z:
            texto = z.read("yt_dlp/version.py").decode("utf-8")
        version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", texto).group(1)
    except (zipfile.BadZipFile, KeyError, AttributeError) as e:
        temporal.unlink(missing_ok=True)
        raise ErrorActualizacion("El archivo bajado no es un yt-dlp válido") from e
    temporal.replace(YTDLP_ZIP)
    YTDLP_ZIP.with_suffix(".json").write_text(json.dumps({
        "version": version, "sha256": esperado, "fecha": datetime.now().isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    return {"version": version, "reiniciar": True}
