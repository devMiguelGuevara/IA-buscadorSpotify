"""Trabajos del laboratorio: analizar, procesar (una sola pasada desde el original) y control de calidad.

Los trabajos pesados van en su propia cola, de a uno, separada de las descargas.
Cada versión queda en versiones/<nombre>/<id>.<formato> con su receta.json.
"""

from __future__ import annotations

import hashlib
import json
import queue
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path

from ..descargador import buscar_ffmpeg
from ..spotify import RAIZ
from . import analisis, motores, procesos_python
from .capacidades import SIN_VENTANA

VERSIONES = RAIZ / "versiones"
FORMATOS = {
    "flac": ["-c:a", "flac", "-sample_fmt", "s32"],
    "wav": ["-c:a", "pcm_s24le"],
    "mp3": ["-c:a", "libmp3lame", "-b:a", "320k"],
}
INTERMEDIO = ["-c:a", "pcm_f32le"]


def _hash(archivo: Path) -> str:
    h = hashlib.sha256()
    with archivo.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _carpeta_versiones(original: Path) -> Path:
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", original.stem)[:90].strip(" .") or "cancion"
    return VERSIONES / nombre


def listar_versiones(original: Path) -> list[dict]:
    carpeta = _carpeta_versiones(original)
    salida = []
    for receta in sorted(carpeta.glob("*.json"), reverse=True):
        try:
            datos = json.loads(receta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        archivo = carpeta / datos.get("archivo", "")
        if archivo.exists():
            salida.append(datos | {"ruta": archivo.relative_to(VERSIONES).as_posix()})
    return salida


class Cancelado(Exception):
    pass


def _revisar(t: dict) -> None:
    if t.get("cancelar"):
        raise Cancelado


class Laboratorio:
    def __init__(self):
        self.trabajos: dict[str, dict] = {}
        self.cola: queue.Queue = queue.Queue()
        threading.Thread(target=self._bucle, daemon=True).start()

    def _nuevo(self, tipo: str, original: Path, **extra) -> dict:
        t = {"id": uuid.uuid4().hex[:8], "tipo": tipo, "original": str(original), "nombre": original.stem,
             "estado": "en_cola", "progreso": 0, "error": "", "resultado": None, **extra}
        self.trabajos[t["id"]] = t
        self.cola.put(t)
        return t

    def analizar(self, original: Path) -> dict:
        return self._nuevo("analisis", original)

    def procesar(self, original: Path, receta: list[dict], formato: str) -> dict:
        return self._nuevo("proceso", original, receta=receta, formato=formato if formato in FORMATOS else "flac")

    def cancelar(self, id_: str) -> dict | None:
        """Detiene un trabajo: si espera, no corre; si corre, se corta ffmpeg ya y los motores
        de Python en su próximo punto de control (Demucs entre bloques)."""
        t = self.trabajos.get(id_)
        if t and t["estado"] in ("en_cola", "procesando"):
            t["cancelar"] = True
            proc = t.get("_proc")
            if proc and proc.poll() is None:
                proc.terminate()
        return t

    def _bucle(self):
        while True:
            t = self.cola.get()
            if t.get("cancelar"):
                t["estado"] = "cancelado"
                continue
            t["estado"] = "procesando"
            try:
                original = Path(t["original"])
                t["resultado"] = analisis.analizar(original) if t["tipo"] == "analisis" else self._render(t, original)
                t["estado"] = "terminado"
                t["progreso"] = 100
            except Cancelado:
                t["estado"] = "cancelado"
            except Exception as e:  # un trabajo que falla no tumba el laboratorio
                if t.get("cancelar"):
                    t["estado"] = "cancelado"
                else:
                    t.update(estado="error", error=f"{type(e).__name__}: {e}")
            finally:
                t.pop("_proc", None)

    def _render(self, t: dict, original: Path) -> dict:
        """Etapas en orden: las de ffmpeg en una sola pasada cada una y las de Python entre medio.
        Solo hay intermedios (WAV de 32 bits flotantes) si la receta usa motores de Python."""
        ffmpeg = buscar_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("Falta ffmpeg")
        hash_antes = _hash(original)
        receta = t["receta"]
        pasos = motores.etapas(receta) or [("ffmpeg", "anull")]
        duracion = analisis.formato(original).get("duracion") or 0
        carpeta = _carpeta_versiones(original)
        carpeta.mkdir(parents=True, exist_ok=True)
        vid = datetime.now().strftime("%Y%m%d-%H%M%S")
        salida = carpeta / f"{vid}.{t['formato']}"
        temporal = carpeta / f"_tmp_{vid}"
        temporal.mkdir(exist_ok=True)
        descripcion = []
        try:
            actual, n = original, len(pasos)
            for i, (tipo, etapa) in enumerate(pasos):
                _revisar(t)
                rango = (int(95 * i / n), int(95 * (i + 1) / n))
                ultimo = i == n - 1
                if tipo == "ffmpeg":
                    filtros = etapa
                    if "loudnorm=" in filtros:  # 2 pasadas: medir y aplicar lineal
                        filtros = self._loudnorm_lineal(ffmpeg, actual, filtros)
                    destino = salida if ultimo else temporal / f"{i}.wav"
                    self._pasada(t, ffmpeg, actual, original, filtros, destino,
                                 FORMATOS[t["formato"]] if ultimo else INTERMEDIO, duracion, rango)
                    descripcion.append(filtros)
                else:
                    if actual.suffix.lower() != ".wav":  # Pedalboard y Matchering leen WAV
                        wav = temporal / "entrada.wav"
                        self._pasada(t, ffmpeg, actual, original, "anull", wav, INTERMEDIO, duracion, (rango[0], rango[0]))
                        actual = wav
                    ref = etapa.get("referencia_ruta")
                    if ref and Path(ref).suffix.lower() not in (".wav", ".flac"):
                        wav_ref = temporal / "referencia.wav"
                        self._pasada(t, ffmpeg, Path(ref), Path(ref), "anull", wav_ref, INTERMEDIO, 0, (rango[0], rango[0]))
                        etapa = {**etapa, "referencia_ruta": str(wav_ref)}
                    destino = temporal / f"{i}.wav"
                    etapa = {**etapa, "clave_original": hash_antes}

                    def avance(x, r=rango):
                        _revisar(t)  # Demucs llama aquí entre bloques: se puede detener
                        t["progreso"] = r[0] + int(x * (r[1] - r[0]))
                    procesos_python.correr(etapa, actual, destino, avance)
                    t["progreso"] = rango[1]
                    motor = {"afinacion": "Pedalboard", "matchering": "Matchering"}.get(etapa["id"], "Demucs")
                    extra = f" {etapa['params'].get('salida', '')}" if etapa["id"] == "separacion" else ""
                    extra += f" afinada ×{etapa['razon']:.4f}" if etapa.get("razon") else ""
                    descripcion.append(f"[{etapa['id']}: {motor}{extra}]")
                    if ultimo:
                        self._pasada(t, ffmpeg, destino, original, "anull", salida, FORMATOS[t["formato"]], duracion, (rango[1], rango[1]))
                actual = destino
        except BaseException:
            salida.unlink(missing_ok=True)  # nada de versiones a medias
            raise
        finally:
            shutil.rmtree(temporal, ignore_errors=True)
        if _hash(original) != hash_antes:  # regla no destructiva
            raise RuntimeError("¡El original cambió durante el proceso!")

        t["progreso"] = 96
        antes, despues = analisis.analizar(original), analisis.analizar(salida)
        calidad = control_calidad(antes, despues, receta)
        datos = {
            "id": vid, "archivo": salida.name, "original": str(original), "sha256_original": hash_antes,
            "formato": t["formato"], "receta": [{k: v for k, v in p.items() if k != "referencia_ruta"} for p in receta],
            "filtros_ffmpeg": " → ".join(descripcion),
            "fecha": datetime.now().isoformat(timespec="seconds"), "antes": antes, "despues": despues, "calidad": calidad,
        }
        (carpeta / f"{vid}.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        return datos | {"ruta": salida.relative_to(VERSIONES).as_posix()}

    @staticmethod
    def _pasada(t: dict, ffmpeg: str, entrada: Path, original: Path, filtros: str, destino: Path,
                codec: list[str], duracion: float, rango: tuple[int, int]) -> None:
        """Una pasada de ffmpeg; las etiquetas siempre salen del original."""
        args = [ffmpeg, "-hide_banner", "-y", "-i", str(entrada)]
        if entrada != original:
            args += ["-i", str(original)]
        args += ["-map", "0:a:0", "-map_metadata", "1" if entrada != original else "0",
                 "-af", filtros, *codec, "-progress", "pipe:1", "-nostats", str(destino)]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", creationflags=SIN_VENTANA)
        t["_proc"] = proc
        errores: list[str] = []
        lector = threading.Thread(target=lambda: errores.extend(proc.stderr), daemon=True)
        lector.start()
        for linea in proc.stdout:
            if linea.startswith("out_time_us=") and duracion:
                try:
                    avance = int(linea.split("=")[1]) / 1e6 / duracion
                    t["progreso"] = min(rango[1], rango[0] + int(avance * (rango[1] - rango[0])))
                except ValueError:
                    pass
        lector.join()
        _revisar(t)
        if proc.wait() != 0:
            raise RuntimeError(errores[-1].strip() if errores else "ffmpeg falló")

    @staticmethod
    def _loudnorm_lineal(ffmpeg: str, original: Path, filtros: str) -> str:
        previo, _, resto = filtros.partition("loudnorm=")
        params, _, despues = resto.partition(",")
        medicion = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostats", "-i", str(original), "-vn", "-af",
             f"{previo}loudnorm={params}:print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=SIN_VENTANA).stderr
        try:
            m = json.loads(medicion[medicion.rindex("{"):medicion.rindex("}") + 1])
        except ValueError:
            return filtros
        medido = (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
                  f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
        return f"{previo}loudnorm={params}{medido}" + (f",{despues}" if despues else "")


def control_calidad(antes: dict, despues: dict, receta: list[dict]) -> dict:
    """Compara el resultado con el original: duración, saturación, true peak y sonoridad."""
    chequeos = []
    fa, fd = antes.get("formato", {}), despues.get("formato", {})
    sa, sd = antes.get("sonoridad", {}), despues.get("sonoridad", {})

    def chequeo(nombre, ok, detalle, grave=True):
        chequeos.append({"nombre": nombre, "ok": bool(ok), "detalle": detalle, "grave": grave})

    if fa.get("duracion") and fd.get("duracion"):
        dif = abs(fa["duracion"] - fd["duracion"])
        chequeo("Duración igual", dif < 0.15, f"diferencia de {dif:.2f} s")
    if sd.get("true_peak") is not None:
        techo = next((float(p.get("params", {}).get("techo", -1)) for p in receta if p.get("id") == "limitador"), None)
        limite = (techo if techo is not None else 0) + 0.3
        chequeo("True peak bajo control", sd["true_peak"] <= limite, f"{sd['true_peak']:.1f} dBTP")
    if sd.get("plano") is not None:
        chequeo("Sin saturación nueva", sd["plano"] <= max(2, (sa.get("plano") or 0) + 0.5), f"flat factor {sd['plano']:.1f}")
    norma = next((p for p in receta if p.get("id") == "normalizar"), None)
    if norma and sd.get("lufs") is not None:
        objetivo = float(norma.get("params", {}).get("lufs", -14))
        chequeo("Sonoridad en el objetivo", abs(sd["lufs"] - objetivo) <= 1, f"{sd['lufs']:.1f} LUFS (objetivo {objetivo})")
    if sd.get("rms_db") is not None:
        separa = any(p.get("id") == "separacion" for p in receta)
        if separa and sd["rms_db"] <= -60:  # p. ej. "solo voz" de un tema instrumental
            chequeo("Hay audio", False, "la pista elegida casi no suena: puede que la canción no la tenga", grave=False)
        else:
            chequeo("Hay audio", sd["rms_db"] > -60, f"RMS {sd['rms_db']:.1f} dB")
    fallos = [c for c in chequeos if not c["ok"] and c["grave"]]
    avisos = [c for c in chequeos if not c["ok"] and not c["grave"]]
    veredicto = "aviso" if not fallos and avisos else "ok" if not fallos else ("falla" if any(c["nombre"] in ("Duración igual", "Hay audio") for c in fallos) else "aviso")
    return {"veredicto": veredicto, "chequeos": chequeos}


def espectrograma(archivo: Path, destino: Path) -> Path:
    """Imagen del espectro (ffmpeg showspectrumpic), para comparar antes y después."""
    if not destino.exists() or destino.stat().st_mtime < archivo.stat().st_mtime:
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([buscar_ffmpeg(), "-hide_banner", "-y", "-i", str(archivo), "-lavfi",
                        "showspectrumpic=s=640x240:legend=0:scale=log:color=intensity", str(destino)],
                       capture_output=True, creationflags=SIN_VENTANA, timeout=180)
    return destino
