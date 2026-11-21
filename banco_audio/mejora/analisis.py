"""Análisis técnico con ffmpeg (nivel Base, sin dependencias extra) y diagnóstico de problemas.

Mide: formato (ffprobe), sonoridad integrada (LUFS), rango de sonoridad (LU), true peak,
pico y RMS, DC, muestras saturadas y el corte de agudos típico de las fuentes con pérdida.
Si librosa está instalada, también estima afinación (A4 en Hz), tempo y tonalidad.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

from ..descargador import buscar_ffmpeg
from .capacidades import SIN_VENTANA, ffprobe, hay_paquete


def _correr(args: list[str], timeout: int = 600) -> str:
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, creationflags=SIN_VENTANA)
    return r.stdout + r.stderr


def formato(archivo: Path) -> dict:
    probe = ffprobe()
    if not probe:
        return {}
    salida = _correr([probe, "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(archivo)], 60)
    try:
        datos = json.loads(salida[salida.index("{"):])
    except ValueError:
        return {}
    audio = next((s for s in datos.get("streams", []) if s.get("codec_type") == "audio"), {})
    f = datos.get("format", {})
    bitrate = audio.get("bit_rate") or f.get("bit_rate")
    return {
        "codec": audio.get("codec_name", ""),
        "kbps": round(int(bitrate) / 1000) if bitrate else None,
        "hz": int(audio.get("sample_rate") or 0) or None,
        "canales": audio.get("channels"),
        "duracion": round(float(f.get("duration") or audio.get("duration") or 0), 2),
    }


def _num(patron: str, texto: str) -> float | None:
    m = re.findall(patron, texto)
    if not m:
        return None
    try:
        v = float(m[-1])
        return None if math.isinf(v) or math.isnan(v) else v
    except ValueError:
        return None


def sonoridad(archivo: Path) -> dict:
    """Una sola pasada: ebur128 (LUFS, LRA, true peak) + astats (pico, RMS, DC, saturación)."""
    ffmpeg = buscar_ffmpeg()
    salida = _correr([ffmpeg, "-hide_banner", "-nostats", "-i", str(archivo), "-vn",
                      "-af", "ebur128=peak=true,astats=measure_overall=Peak_level+RMS_level+DC_offset+Flat_factor+Peak_count:measure_perchannel=none",
                      "-f", "null", "-"])
    resumen = salida[salida.rfind("Summary:"):] if "Summary:" in salida else salida
    return {
        "lufs": _num(r"I:\s+(-?[\d.]+) LUFS", resumen),
        "lra": _num(r"LRA:\s+(-?[\d.]+) LU", resumen),
        "true_peak": _num(r"Peak:\s+(-?[\d.]+) dBFS", resumen),
        "pico_db": _num(r"Peak level dB:\s+(-?[\d.inf]+)", salida),
        "rms_db": _num(r"RMS level dB:\s+(-?[\d.inf]+)", salida),
        "dc": _num(r"DC offset:\s+(-?[\d.e-]+)", salida),
        "plano": _num(r"Flat factor:\s+(-?[\d.]+)", salida),
        "picos": _num(r"Peak count:\s+(-?[\d.]+)", salida),
    }


def corte_agudos(archivo: Path, duracion: float | None) -> int | None:
    """Frecuencia donde se acaban los agudos: compara la energía sobre 16, 18 y 19,5 kHz."""
    ffmpeg = buscar_ffmpeg()
    inicio = max(0.0, (duracion or 0) / 2 - 30)
    energias = {}
    for f in (16000, 18000, 19500):
        salida = _correr([ffmpeg, "-hide_banner", "-nostats", "-ss", str(inicio), "-t", "60", "-i", str(archivo),
                          "-vn", "-af", f"highpass=f={f}:poles=2,highpass=f={f}:poles=2,astats=measure_overall=RMS_level:measure_perchannel=none",
                          "-f", "null", "-"], 120)
        energias[f] = _num(r"RMS level dB:\s+(-?[\d.inf]+)", salida)
    for f in (16000, 18000, 19500):
        if energias[f] is None or energias[f] < -75:
            return f
    return None


NOTAS = ["Do", "Do#", "Re", "Mib", "Mi", "Fa", "Fa#", "Sol", "Lab", "La", "Sib", "Si"]
# Perfiles de Krumhansl-Kessler: peso de cada grado en tonalidad mayor y menor.
MAYOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MENOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _tonalidad(cromas) -> str:
    import numpy as np
    perfil = cromas.mean(axis=1)
    mejor, nombre = -2.0, ""
    for modo, base in (("mayor", MAYOR), ("menor", MENOR)):
        for t in range(12):
            r = float(np.corrcoef(perfil, np.roll(base, t))[0, 1])
            if r > mejor:
                mejor, nombre = r, f"{NOTAS[t]} {modo}"
    return nombre


def avanzado(archivo: Path) -> dict:
    """Afinación de referencia (A4 en Hz), tempo y tonalidad. Necesita librosa (nivel Mejora)."""
    if not hay_paquete("librosa"):
        return {}
    try:
        import librosa
        y, sr = librosa.load(str(archivo), sr=22050, mono=True, offset=20, duration=60)
        if len(y) < sr * 5:  # canción corta: se toma desde el inicio
            y, sr = librosa.load(str(archivo), sr=22050, mono=True, duration=60)
        desvio = float(librosa.estimate_tuning(y=y, sr=sr))  # fracción de semitono
        tempo = librosa.beat.beat_track(y=y, sr=sr)[0]
        cromas = librosa.feature.chroma_cqt(y=y, sr=sr, tuning=desvio)
        return {
            "afinacion_hz": round(440 * 2 ** (desvio / 12), 2),
            "tempo_bpm": round(float(getattr(tempo, "item", lambda: tempo)()), 1),
            "tonalidad": _tonalidad(cromas),
        }
    except Exception as e:  # el análisis básico sigue; se informa por qué faltó el avanzado
        return {"error": f"{type(e).__name__}: {e}"[:300]}


def analizar(archivo: Path) -> dict:
    datos = {"formato": formato(archivo)}
    datos["sonoridad"] = sonoridad(archivo)
    datos["corte_hz"] = corte_agudos(archivo, datos["formato"].get("duracion"))
    extra = avanzado(archivo)
    datos["afinacion_hz"] = extra.get("afinacion_hz")
    datos["tempo_bpm"] = extra.get("tempo_bpm")
    datos["tonalidad"] = extra.get("tonalidad")
    if extra.get("error"):
        datos["error_avanzado"] = extra["error"]
    datos["problemas"] = diagnosticar(datos)
    return datos


def diagnosticar(d: dict) -> list[dict]:
    """Problemas detectados y el proceso que se sugiere para cada uno."""
    s, f, p = d.get("sonoridad", {}), d.get("formato", {}), []

    def agregar(codigo, severidad, mensaje, sugerencia=None):
        p.append({"codigo": codigo, "severidad": severidad, "mensaje": mensaje, "sugerencia": sugerencia})

    if (s.get("plano") or 0) > 2 or ((s.get("pico_db") or -99) >= -0.1 and (s.get("picos") or 0) > 50):
        agregar("saturacion", "alta", "Hay muestras saturadas (clipping).", "declip")
    if s.get("true_peak") is not None and s["true_peak"] > -1:
        agregar("true_peak", "media", f"True peak de {s['true_peak']:.1f} dBTP: puede distorsionar al convertir.", "limitador")
    if s.get("lufs") is not None:
        if s["lufs"] < -18:
            agregar("bajo", "media", f"Volumen bajo ({s['lufs']:.1f} LUFS frente a -14 de las plataformas).", "normalizar")
        elif s["lufs"] > -8:
            agregar("alto", "media", f"Muy comprimido o fuerte ({s['lufs']:.1f} LUFS).", "normalizar")
    if s.get("lra") is not None and s["lra"] < 3:
        agregar("dinamica", "baja", f"Poco rango dinámico ({s['lra']:.1f} LU): suena aplastado.", None)
    if s.get("dc") is not None and abs(s["dc"]) > 0.005:
        agregar("dc", "baja", "Desplazamiento de continua (DC).", "eq")
    if d.get("corte_hz"):
        agregar("perdida", "info", f"Fuente con pérdida: no hay agudos sobre ~{d['corte_hz'] / 1000:.1f} kHz. "
                "El DSP no los recupera; sería tarea de restauración con IA.", None)
    if f.get("kbps") and f["kbps"] < 128:
        agregar("bitrate", "media", f"Bitrate bajo ({f['kbps']} kbps).", None)
    if d.get("afinacion_hz") and abs(d["afinacion_hz"] - 440) > 1.5:
        agregar("afinacion", "info", f"Afinación de referencia en {d['afinacion_hz']} Hz.", "afinacion")
    if not p:
        agregar("ok", "info", "No se detectaron problemas técnicos.", None)
    return p
