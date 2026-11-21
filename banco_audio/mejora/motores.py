"""Catálogo de motores (procesos) del laboratorio.

Cada motor declara nivel, licencia, requisitos y parámetros; la interfaz se arma sola a
partir de ellos. Los filtros de ffmpeg seguidos se encadenan en una sola pasada; los motores
de Python (Pedalboard, Matchering) son etapas propias entre esas pasadas. Los que necesitan
paquetes que faltan aparecen como "instalables" con su comando.
"""

from __future__ import annotations

import math
import sys

from .capacidades import capacidades


def _p(id, nombre, minimo, maximo, defecto, paso=1, unidad=""):
    return {"id": id, "nombre": nombre, "min": minimo, "max": maximo, "defecto": defecto, "paso": paso, "unidad": unidad}


def _op(id, nombre, opciones, defecto):
    """Parámetro de lista: opciones = [(valor, etiqueta), ...]."""
    return {"id": id, "nombre": nombre, "opciones": [list(o) for o in opciones], "defecto": defecto}


MOTORES_AFINACION = [("auto", "Automático"), ("rubberband", "Rubber Band (ffmpeg)"),
                     ("pedalboard", "Rubber Band (Pedalboard)"), ("respaldo", "Respaldo (asetrate)")]


def motor_afinacion(pedido: str, filtros: set[str], paquetes: dict) -> str:
    """El mejor motor disponible: Rubber Band de ffmpeg, el de Pedalboard o el respaldo."""
    hay = {"rubberband": "rubberband" in filtros, "pedalboard": bool(paquetes.get("pedalboard")), "respaldo": True}
    if pedido in hay and hay[pedido]:
        return pedido
    return next(m for m in ("rubberband", "pedalboard", "respaldo") if hay[m])


def _afinacion(params: dict, filtros: set[str]) -> str:
    """Cambia la afinación sin cambiar la duración (vía ffmpeg: Rubber Band o asetrate + atempo)."""
    razon = float(params["hacia"]) / float(params["desde"])
    if abs(razon - 1) < 1e-6:
        return "anull"
    if params.get("motor") == "rubberband":
        return f"rubberband=pitch={razon:.8f}:formant=preserved:pitchq=quality"
    return f"aresample=48000,asetrate={48000 * razon:.4f},aresample=48000,atempo={1 / razon:.8f}"


MOTORES = [
    {
        "id": "normalizar", "nombre": "Normalizar sonoridad", "categoria": "masterizacion", "nivel": "base",
        "descripcion": "Lleva la canción a una sonoridad objetivo (2 pasadas de loudnorm, EBU R128).",
        "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["loudnorm"],
        "parametros": [_p("lufs", "Sonoridad objetivo", -23, -8, -14, 0.5, "LUFS"), _p("tp", "True peak máximo", -3, -0.1, -1, 0.1, "dBTP")],
        "ffmpeg": lambda p, f: f"loudnorm=I={p['lufs']}:TP={p['tp']}:LRA=11",
    },
    {
        "id": "eq", "nombre": "Ecualización (graves y agudos)", "categoria": "dsp", "nivel": "base",
        "descripcion": "Filtro de rumble/DC, realce o recorte de graves y agudos.",
        "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["bass", "treble", "highpass"],
        "parametros": [_p("hp", "Corte de graves (rumble)", 0, 80, 25, 5, "Hz"), _p("graves", "Graves", -10, 10, 0, 0.5, "dB"),
                       _p("agudos", "Agudos", -10, 10, 0, 0.5, "dB")],
        "ffmpeg": lambda p, f: ",".join(x for x in [
            f"highpass=f={p['hp']}" if p["hp"] > 0 else "",
            f"bass=g={p['graves']}:f=100" if p["graves"] else "",
            f"treble=g={p['agudos']}:f=8000" if p["agudos"] else "",
        ] if x) or "anull",
    },
    {
        "id": "compresor", "nombre": "Compresor", "categoria": "dsp", "nivel": "base",
        "descripcion": "Reduce la diferencia entre partes fuertes y suaves.",
        "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["acompressor"],
        "parametros": [_p("umbral", "Umbral", -40, 0, -18, 1, "dB"), _p("razon", "Razón", 1, 10, 2.5, 0.5, ":1")],
        "ffmpeg": lambda p, f: f"acompressor=threshold={10 ** (p['umbral'] / 20):.5f}:ratio={p['razon']}:attack=15:release=200:makeup=1",
    },
    {
        "id": "ruido", "nombre": "Reducir ruido", "categoria": "restauracion", "nivel": "base",
        "descripcion": "Reducción de ruido de fondo por FFT (afftdn).",
        "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["afftdn"],
        "parametros": [_p("reduccion", "Reducción", 3, 30, 10, 1, "dB")],
        "ffmpeg": lambda p, f: f"afftdn=nr={p['reduccion']}:nf=-30",
    },
    {
        "id": "declip", "nombre": "Reparar saturación (declip)", "categoria": "restauracion", "nivel": "base",
        "descripcion": "Reconstruye las crestas recortadas.", "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["adeclip"],
        "parametros": [], "ffmpeg": lambda p, f: "adeclip",
    },
    {
        "id": "declick", "nombre": "Quitar clics", "categoria": "restauracion", "nivel": "base",
        "descripcion": "Elimina clics y chasquidos (vinilos, cortes).", "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["adeclick"],
        "parametros": [], "ffmpeg": lambda p, f: "adeclick",
    },
    {
        "id": "estereo", "nombre": "Ancho estéreo", "categoria": "dsp", "nivel": "base",
        "descripcion": "Abre o cierra la imagen estéreo.", "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["extrastereo"],
        "parametros": [_p("ancho", "Ancho", 0, 2.5, 1.2, 0.1, "×")],
        "ffmpeg": lambda p, f: f"extrastereo=m={p['ancho']}",
    },
    {
        "id": "afinacion", "nombre": "Afinación global", "categoria": "afinacion", "nivel": "base",
        "descripcion": "Cambia la afinación de referencia sin cambiar la duración (Rubber Band; "
                       "si falta, asetrate + atempo).",
        "licencia": "Rubber Band GPL-2.0+ / FFmpeg", "filtros": ["asetrate", "atempo"],
        "parametros": [_p("desde", "Afinación actual (A4)", 415, 466, 440, 0.5, "Hz"), _p("hacia", "Afinación nueva (A4)", 415, 466, 438, 0.5, "Hz"),
                       _op("motor", "Motor", MOTORES_AFINACION, "auto")],
        "ffmpeg": _afinacion,
    },
    {
        "id": "limitador", "nombre": "Limitador", "categoria": "masterizacion", "nivel": "base",
        "descripcion": "Evita que los picos pasen del techo (va al final de la cadena).",
        "licencia": "FFmpeg (LGPL/GPL)", "filtros": ["alimiter"],
        "parametros": [_p("techo", "Techo", -3, -0.1, -1, 0.1, "dB")],
        "ffmpeg": lambda p, f: f"alimiter=limit={10 ** (p['techo'] / 20):.5f}:level=disabled",
    },
    # ---- niveles superiores (se muestran como instalables si faltan paquetes)
    {
        "id": "matchering", "nombre": "Masterizar con referencia (Matchering)", "categoria": "masterizacion", "nivel": "mejora",
        "descripcion": "Iguala tono, sonoridad y dinámica a una canción de referencia.",
        "licencia": "GPL-3.0", "paquetes": ["matchering"], "instalar": "pip install -r requirements-mejora.txt",
        "parametros": [], "referencia": True, "python": True,
    },
    {
        "id": "analisis_avanzado", "nombre": "Análisis avanzado (librosa)", "categoria": "analisis", "nivel": "mejora",
        "descripcion": "Afinación de referencia, tempo y tonalidad. Se suma solo al análisis.",
        "licencia": "ISC", "paquetes": ["librosa"], "instalar": "pip install -r requirements-mejora.txt",
        "parametros": [], "solo_analisis": True,
    },
    {
        "id": "separacion", "nombre": "Separar pistas (Demucs)", "categoria": "ia", "nivel": "ia",
        "descripcion": "Separa voz, batería, bajo y resto con IA y se queda con lo que elijas. "
                       "En CPU tarda más o menos lo que dura la canción (solo la primera vez).",
        "licencia": "MIT", "paquetes": ["torch", "demucs"], "python": True,
        "instalar": "pip install -r requirements-ia.txt",
        "parametros": [_op("salida", "Quedarse con", [
            ("sin_voz", "Sin voz (karaoke)"), ("voz", "Solo voz"), ("bateria", "Solo batería"), ("bajo", "Solo bajo"),
            ("resto", "Solo resto (instrumentos)"), ("sin_bateria", "Sin batería"), ("sin_bajo", "Sin bajo")], "sin_voz")],
    },
    {
        "id": "afinacion_instrumentos", "nombre": "Afinación por instrumento", "categoria": "afinacion", "nivel": "ia",
        "descripcion": "Separa la canción, reafina voz, bajo y resto (la batería no) y vuelve a mezclar. "
                       "Suena más natural en algunos temas, pero no conserva la mezcla original exacta.",
        "licencia": "MIT + Rubber Band", "paquetes": ["torch", "demucs"], "python": True,
        "instalar": "pip install -r requirements-ia.txt",
        "parametros": [_p("desde", "Afinación actual (A4)", 415, 466, 440, 0.5, "Hz"),
                       _p("hacia", "Afinación nueva (A4)", 415, 466, 432, 0.5, "Hz")],
    },
]

# Orden fijo en la cadena: restaurar, corregir, colorear, afinar, masterizar y limitar al final.
ORDEN = ["separacion", "afinacion_instrumentos", "declick", "declip", "ruido", "eq", "compresor", "estereo", "afinacion", "matchering", "normalizar", "limitador"]


def catalogo() -> list[dict]:
    cap = capacidades()
    filtros, paquetes = set(cap["filtros"]), cap["paquetes"]
    salida = []
    for m in MOTORES:
        faltan_filtros = [f for f in m.get("filtros", []) if f not in filtros]
        faltan_paquetes = [p for p in m.get("paquetes", []) if not paquetes.get(p)]
        motor_usado = None
        if m["id"] == "afinacion":
            motor_usado = dict(MOTORES_AFINACION)[motor_afinacion("auto", filtros, paquetes)]
        if not cap["ffmpeg"] and m["nivel"] == "base":
            estado, motivo = "no_soportado", "Falta ffmpeg"
        elif faltan_filtros:
            estado, motivo = "no_soportado", "Tu ffmpeg no trae: " + ", ".join(faltan_filtros)
        elif faltan_paquetes:
            estado, motivo = "instalable", m.get("instalar", "pip install " + " ".join(faltan_paquetes))
            if getattr(sys, "frozen", False):  # el .exe no trae el nivel Mejora ni IA
                motivo = "Se usa desde el código (iniciar.bat), tras: " + motivo
        else:
            estado, motivo = "disponible", ""
        salida.append({k: v for k, v in m.items() if k != "ffmpeg"} | {"estado": estado, "motivo": motivo, "motor": motor_usado})
    return salida


def _params(motor: dict, paso: dict) -> dict:
    dados = paso.get("params", {})
    return {q["id"]: (str(dados.get(q["id"], q["defecto"])) if "opciones" in q else float(dados.get(q["id"], q["defecto"])))
            for q in motor["parametros"]}


def etapas(receta: list[dict]) -> list[tuple[str, object]]:
    """La receta como etapas en orden: ("ffmpeg", filtros) con los filtros seguidos en una sola
    cadena, o ("python", paso) para los motores de Python (Pedalboard, Matchering)."""
    cap = capacidades()
    filtros, paquetes = set(cap["filtros"]), cap["paquetes"]
    por_id = {m["id"]: m for m in MOTORES if "ffmpeg" in m or m.get("python")}
    pasos = sorted((p for p in receta if p.get("id") in por_id), key=lambda p: ORDEN.index(p["id"]))
    # Separar y afinar por instrumento son una sola etapa: se separa una vez y se mezcla lo elegido.
    ids = [p["id"] for p in pasos]
    if "afinacion_instrumentos" in ids:
        afinar = pasos.pop(ids.index("afinacion_instrumentos"))
        dados = _params(por_id["afinacion_instrumentos"], afinar)
        razon = dados["hacia"] / dados["desde"]
        if pasos and pasos[0]["id"] == "separacion":
            pasos[0] = {**pasos[0], "razon": razon}
        else:
            pasos.insert(0, {"id": "separacion", "params": {"salida": "todas"}, "razon": razon})
    salida: list[tuple[str, object]] = []
    for paso in pasos:
        motor = por_id[paso["id"]]
        params = _params(motor, paso)
        if paso["id"] == "afinacion":
            params["motor"] = motor_afinacion(params.get("motor", "auto"), filtros, paquetes)
            if params["motor"] == "pedalboard":
                salida.append(("python", {"id": "afinacion", "params": params}))
                continue
        if motor.get("python"):
            salida.append(("python", {**paso, "params": params}))
            continue
        filtro = motor["ffmpeg"](params, filtros)
        if not filtro or filtro == "anull":
            continue
        if salida and salida[-1][0] == "ffmpeg":
            salida[-1] = ("ffmpeg", f"{salida[-1][1]},{filtro}")
        else:
            salida.append(("ffmpeg", filtro))
    return salida


def cadena(receta: list[dict]) -> str:
    """Filtros de ffmpeg de la receta, en el orden correcto (sin las etapas de Python)."""
    return ",".join(str(e) for t, e in etapas(receta) if t == "ffmpeg") or "anull"


def cents(desde: float, hacia: float) -> float:
    return round(1200 * math.log2(hacia / desde), 2)
