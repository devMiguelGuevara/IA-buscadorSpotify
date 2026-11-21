"""Registro de lo que ya está en el banco de audio, para no descargar dos veces."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from .cancion import Cancion


class Registro:
    """Archivo JSON dentro del banco: clave de canción -> datos de la descarga.

    Solo se saltan las canciones con estado "ok" cuyo archivo sigue existiendo;
    las fallidas se vuelven a intentar en la siguiente ejecución.
    """

    def __init__(self, ruta: Path):
        self.ruta = ruta
        self._lock = threading.Lock()
        self._datos: dict[str, dict] = {}
        if ruta.exists():
            self._datos = json.loads(ruta.read_text(encoding="utf-8"))

    def ya_descargada(self, cancion: Cancion) -> Path | None:
        with self._lock:
            entrada = self._datos.get(cancion.clave)
        if entrada and entrada.get("estado") == "ok":
            archivo = self.ruta.parent / entrada["archivo"]
            if archivo.exists():
                return archivo
        return None

    def guardar(self, cancion: Cancion, estado: str, **extra) -> None:
        with self._lock:
            self._datos[cancion.clave] = {
                "titulo": cancion.titulo,
                "artista": cancion.artista,
                "album": cancion.album,
                "spotify_id": cancion.spotify_id,
                "estado": estado,
                "fecha": datetime.now().isoformat(timespec="seconds"),
                **extra,
            }
            self._escribir()

    def entradas(self) -> list[tuple[str, dict]]:
        with self._lock:
            return [(k, dict(v)) for k, v in self._datos.items()]

    def actualizar(self, clave: str, **campos) -> None:
        with self._lock:
            if clave in self._datos:
                self._datos[clave].update(campos)
                self._escribir()

    def _escribir(self) -> None:
        # Escritura atómica: si el proceso se corta no se corrompe el registro.
        temporal = self.ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(self._datos, indent=2, ensure_ascii=False), encoding="utf-8")
        temporal.replace(self.ruta)
