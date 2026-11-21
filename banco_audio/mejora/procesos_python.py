"""Motores del nivel Mejora que corren en Python (Pedalboard y Matchering).

Cada uno lee un WAV intermedio y escribe otro; el laboratorio los encadena entre las
pasadas de ffmpeg. Los paquetes se importan aquí dentro, solo si se usan.
"""

from __future__ import annotations

import math
from pathlib import Path


def afinar_pedalboard(entrada: Path, salida: Path, desde: float, hacia: float) -> None:
    """Afinación global con el Rubber Band de Pedalboard: conserva la duración."""
    from pedalboard import PitchShift
    from pedalboard.io import AudioFile

    semitonos = 12 * math.log2(hacia / desde)
    with AudioFile(str(entrada)) as f:
        audio, sr = f.read(f.frames), f.samplerate
    procesado = PitchShift(semitones=semitonos)(audio, sr)
    with AudioFile(str(salida), "w", samplerate=sr, num_channels=procesado.shape[0], bit_depth=32) as f:
        f.write(procesado)


def masterizar_con_referencia(entrada: Path, salida: Path, referencia: Path) -> None:
    """Matchering: iguala respuesta en frecuencia, sonoridad y anchura estéreo a la referencia."""
    import matchering as mg

    mg.log(default_handler=lambda *_: None, warning_handler=lambda *_: None, info_handler=lambda *_: None)
    mg.process(target=str(entrada), reference=str(referencia), results=[mg.pcm24(str(salida))])


def correr(paso: dict, entrada: Path, salida: Path) -> None:
    p = paso.get("params", {})
    if paso["id"] == "afinacion":
        afinar_pedalboard(entrada, salida, float(p["desde"]), float(p["hacia"]))
    elif paso["id"] == "matchering":
        ref = paso.get("referencia_ruta")
        if not ref or not Path(ref).is_file():
            raise RuntimeError("Matchering necesita una canción de referencia")
        masterizar_con_referencia(entrada, salida, Path(ref))
    else:
        raise RuntimeError(f"Motor de Python desconocido: {paso['id']}")
