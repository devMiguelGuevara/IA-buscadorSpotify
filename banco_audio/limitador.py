"""Control de ritmo para no saturar a YouTube/SoundCloud ni quemar la IP."""

from __future__ import annotations

import random
import threading
import time

# Frases con las que yt-dlp reporta que el servicio nos está limitando.
SENALES_BLOQUEO = (
    "http error 429",
    "too many requests",
    "sign in to confirm",
    "not a bot",
    "rate-limit",
    "rate limit",
    "try again later",
)


def es_bloqueo(error: Exception | str) -> bool:
    mensaje = str(error).lower()
    return any(senal in mensaje for senal in SENALES_BLOQUEO)


class Limitador:
    """Reparte las peticiones en el tiempo, por servicio y entre hilos.

    - Cada petición reserva un turno separado del anterior por una pausa
      aleatoria, así varios hilos nunca golpean el servicio a la vez.
    - Si el servicio responde con un bloqueo, se "enfría" con una espera que
      crece exponencialmente (1 min, 2 min, 4 min... hasta `enfriamiento_max`).
    """

    def __init__(
        self,
        pausa_min: float = 2.0,
        pausa_max: float = 6.0,
        enfriamiento_base: float = 60.0,
        enfriamiento_max: float = 900.0,
    ):
        self.pausa_min = pausa_min
        self.pausa_max = max(pausa_min, pausa_max)
        self.enfriamiento_base = enfriamiento_base
        self.enfriamiento_max = enfriamiento_max
        self._lock = threading.Lock()
        self._proximo_turno: dict[str, float] = {}
        self._bloqueos_seguidos: dict[str, int] = {}

    def esperar(self, servicio: str, detener: threading.Event | None = None) -> None:
        """Bloquea el hilo hasta que sea su turno de hablar con `servicio`."""
        with self._lock:
            ahora = time.monotonic()
            turno = max(ahora, self._proximo_turno.get(servicio, 0.0))
            self._proximo_turno[servicio] = turno + random.uniform(self.pausa_min, self.pausa_max)
        espera = turno - ahora
        if espera > 0:
            if detener:
                detener.wait(espera)
            else:
                time.sleep(espera)

    def registrar_bloqueo(self, servicio: str) -> tuple[float, int]:
        """Pone el servicio en enfriamiento. Devuelve (segundos, bloqueos seguidos)."""
        with self._lock:
            n = self._bloqueos_seguidos.get(servicio, 0) + 1
            self._bloqueos_seguidos[servicio] = n
            duracion = min(self.enfriamiento_base * 2 ** (n - 1), self.enfriamiento_max)
            duracion *= random.uniform(1.0, 1.25)
            fin = time.monotonic() + duracion
            self._proximo_turno[servicio] = max(self._proximo_turno.get(servicio, 0.0), fin)
            return duracion, n

    def registrar_exito(self, servicio: str) -> None:
        with self._lock:
            self._bloqueos_seguidos[servicio] = 0

    def bloqueos_seguidos(self, servicio: str) -> int:
        with self._lock:
            return self._bloqueos_seguidos.get(servicio, 0)
