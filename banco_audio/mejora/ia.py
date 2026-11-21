"""Nivel IA del laboratorio: separar pistas con Demucs (CPU o GPU) y afinar por instrumento.

La separación de una canción se guarda en cache/separaciones/<hash>/ (FLAC de 24 bits por
pista), así que elegir otra pista de la misma canción no vuelve a separar. Los modelos se
bajan una sola vez a modelos/ (junto al proyecto o al .exe).
En un i7-7700 (4 núcleos, solo CPU) tarda más o menos lo que dura la canción.
"""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from .. import RAIZ_APP
from ..descargador import buscar_ffmpeg
from .capacidades import SIN_VENTANA

MODELOS = RAIZ_APP / "modelos"
SEPARACIONES = RAIZ_APP / "cache" / "separaciones"
PISTAS = ("vocals", "drums", "bass", "other")
NOMBRES = {"vocals": "voz", "drums": "batería", "bass": "bajo", "other": "resto"}
# Qué pistas suenan en cada salida.
SALIDAS = {
    "sin_voz": ("drums", "bass", "other"),
    "voz": ("vocals",),
    "bateria": ("drums",),
    "bajo": ("bass",),
    "resto": ("other",),
    "sin_bateria": ("vocals", "bass", "other"),
    "sin_bajo": ("vocals", "drums", "other"),
    "todas": ("vocals", "drums", "bass", "other"),
}
# Afinación por instrumento: la batería no tiene una afinación que corregir.
AFINABLES = ("vocals", "bass", "other")

_modelo = None
_lock = threading.Lock()


def _preparar_rutas() -> None:
    os.environ.setdefault("HF_HOME", str(MODELOS / "huggingface"))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TORCH_HOME", str(MODELOS / "torch"))


def dispositivo() -> str:
    """CUDA solo si la GPU tiene memoria suficiente (htdemucs necesita unos 3 GB)."""
    import torch
    try:
        if torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory >= 3.5 * 1024 ** 3:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _cargar_modelo():
    global _modelo
    if _modelo is None:
        _preparar_rutas()
        import torch
        torch.hub.set_dir(str(MODELOS / "torch"))
        from demucs.pretrained import get_model
        _modelo = get_model("htdemucs")
        _modelo.eval()
    return _modelo


def separar(entrada_wav: Path, clave: str, al_progreso=None) -> dict[str, Path]:
    """Las 4 pistas de la canción (de la caché si ya se separó). `clave` identifica el original."""
    carpeta = SEPARACIONES / clave[:24]
    pistas = {p: carpeta / f"{p}.flac" for p in PISTAS}
    if all(f.is_file() for f in pistas.values()):
        return pistas
    with _lock:  # de a una: usa todos los núcleos
        if all(f.is_file() for f in pistas.values()):
            return pistas
        import soundfile as sf
        import torch
        from demucs.apply import apply_model

        modelo = _cargar_modelo()
        datos, sr = sf.read(str(entrada_wav), dtype="float32", always_2d=True)
        if sr != modelo.samplerate or datos.shape[1] != 2:
            raise RuntimeError("La entrada debe ser WAV estéreo a 44,1 kHz")
        audio = torch.from_numpy(datos.T.copy())
        ref = audio.mean(0)
        media, desvio = ref.mean(), ref.std() + 1e-8
        audio = (audio - media) / desvio

        def avance(d: dict) -> None:
            if al_progreso and d.get("audio_length"):
                al_progreso(min(1.0, d.get("segment_offset", 0) / d["audio_length"]))

        with torch.no_grad():
            fuentes = apply_model(modelo, audio[None], device=dispositivo(), shifts=1, split=True,
                                  overlap=0.25, progress=False, callback=avance)[0]
        fuentes = fuentes * desvio + media
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre, f in zip(modelo.sources, fuentes):
            temporal = carpeta / f"{nombre}.tmp.flac"
            sf.write(str(temporal), f.numpy().T, sr, subtype="PCM_24", format="FLAC")
            temporal.replace(carpeta / f"{nombre}.flac")
    return pistas


def mezclar(pistas: dict[str, Path], cuales: tuple[str, ...], salida: Path,
            razon_afinacion: float | None = None) -> None:
    """Suma las pistas elegidas (sin normalizar: la suma de las 4 vuelve a la mezcla original).
    Con razon_afinacion, reafina voz, bajo y resto con Rubber Band; la batería queda igual."""
    from .capacidades import filtros_ffmpeg
    from .motores import _afinacion
    hay_rubberband = "rubberband" in filtros_ffmpeg()
    ffmpeg = buscar_ffmpeg()
    args, filtros, etiquetas = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"], [], []
    for i, p in enumerate(cuales):
        args += ["-i", str(pistas[p])]
        if razon_afinacion and abs(razon_afinacion - 1) > 1e-6 and p in AFINABLES:
            filtro = _afinacion({"desde": 1.0, "hacia": razon_afinacion,
                                 "motor": "rubberband" if hay_rubberband else "respaldo"}, set())
            filtros.append(f"[{i}:a]{filtro}[p{i}]")
        else:
            filtros.append(f"[{i}:a]anull[p{i}]")
        etiquetas.append(f"[p{i}]")
    if len(cuales) > 1:
        filtros.append(f"{''.join(etiquetas)}amix=inputs={len(cuales)}:normalize=0:duration=longest[s]")
    else:
        filtros[-1] = filtros[-1].rsplit("[", 1)[0] + "[s]"
    args += ["-filter_complex", ";".join(filtros), "-map", "[s]", "-c:a", "pcm_f32le", str(salida)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=SIN_VENTANA)
    if r.returncode != 0:
        raise RuntimeError((r.stderr.strip().splitlines() or ["ffmpeg no pudo mezclar"])[-1])
