"""Qué puede hacer esta máquina: ffmpeg y sus filtros, paquetes de Python y dispositivo de IA."""

from __future__ import annotations

import functools
import importlib.util
import os
import platform
import shutil
import subprocess
from pathlib import Path

from ..descargador import buscar_ffmpeg

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ffprobe() -> str | None:
    ffmpeg = buscar_ffmpeg()
    if ffmpeg:
        candidato = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
        if candidato.exists():
            return str(candidato)
    return shutil.which("ffprobe")


@functools.lru_cache(maxsize=1)
def filtros_ffmpeg() -> frozenset[str]:
    ffmpeg = buscar_ffmpeg()
    if not ffmpeg:
        return frozenset()
    try:
        salida = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True,
                                timeout=20, creationflags=SIN_VENTANA).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    return frozenset(linea.split()[1] for linea in salida.splitlines() if len(linea.split()) > 2 and linea[:1] == " ")


def hay_paquete(nombre: str) -> bool:
    return importlib.util.find_spec(nombre) is not None


def _ram_gb() -> float | None:
    if os.name == "nt":
        import ctypes

        class Memoria(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = Memoria()
        m.dwLength = ctypes.sizeof(Memoria)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return round(m.ullTotalPhys / 1024 ** 3, 1)
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 1)
    except (ValueError, OSError, AttributeError):
        return None


def dispositivo_ia() -> dict:
    """CUDA (con VRAM), Apple MPS o CPU. Solo si PyTorch está instalado."""
    if not hay_paquete("torch"):
        return {"torch": False, "dispositivo": "cpu"}
    try:
        import torch
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
            return {"torch": True, "dispositivo": "cuda", "gpu": torch.cuda.get_device_name(0), "vram_gb": round(vram, 1)}
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return {"torch": True, "dispositivo": "mps"}
    except Exception:
        pass
    return {"torch": True, "dispositivo": "cpu"}


@functools.lru_cache(maxsize=1)
def capacidades() -> dict:
    return {
        "sistema": f"{platform.system()} {platform.release()}",
        "cpu": os.cpu_count(),
        "ram_gb": _ram_gb(),
        "ffmpeg": bool(buscar_ffmpeg()),
        "ffprobe": bool(ffprobe()),
        "filtros": sorted(filtros_ffmpeg()),
        "paquetes": {p: hay_paquete(p) for p in ("numpy", "librosa", "pedalboard", "matchering", "torch", "demucs")},
        "ia": dispositivo_ia(),
    }
