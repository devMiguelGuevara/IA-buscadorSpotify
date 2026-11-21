"""Memoria de búsquedas: canción -> candidatos ya encontrados, para no buscar dos veces.

Ahorra peticiones (menos riesgo de bloqueo) al reintentar fallidas o pospuestas, al pasar
de simular a descargar y al usar --forzar. Vive en <banco>/memoria_busquedas.json y cada
entrada vence a los 30 días, porque los resultados de YouTube cambian.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, fields
from pathlib import Path

VIGENCIA = 30 * 24 * 3600


class Memoria:
    def __init__(self, ruta: Path):
        self.ruta = ruta
        self._lock = threading.Lock()
        self._datos: dict[str, dict] = {}
        try:
            self._datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    def leer(self, clave: str, tipo) -> list | None:
        """Los candidatos recordados (como objetos `tipo`), o None si no hay o venció."""
        with self._lock:
            entrada = self._datos.get(clave)
        if not entrada or time.time() - entrada.get("fecha", 0) > VIGENCIA:
            return None
        campos = {f.name for f in fields(tipo)}
        try:
            return [tipo(**{k: v for k, v in c.items() if k in campos}) for c in entrada["candidatos"]]
        except (TypeError, KeyError):
            return None

    def guardar(self, clave: str, candidatos: list) -> None:
        if not candidatos:
            return
        with self._lock:
            self._datos[clave] = {"fecha": int(time.time()), "candidatos": [asdict(c) for c in candidatos[:5]]}
            self._escribir()

    def olvidar(self, clave: str) -> None:
        with self._lock:
            if self._datos.pop(clave, None) is not None:
                self._escribir()

    def _escribir(self) -> None:
        ahora = time.time()
        self._datos = {k: v for k, v in self._datos.items() if ahora - v.get("fecha", 0) <= VIGENCIA}
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.ruta.with_suffix(".tmp")
            temporal.write_text(json.dumps(self._datos, ensure_ascii=False), encoding="utf-8")
            temporal.replace(self.ruta)
        except OSError:
            pass  # la memoria es una ayuda: si no se puede escribir, se busca de nuevo
