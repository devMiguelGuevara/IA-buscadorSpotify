"""Niveles opcionales del laboratorio (Mejora e IA), instalables desde la propia app.

- Desde el código: se instalan en el entorno de Python en uso (pip install -r requirements-x.txt).
- En el .exe: pip viaja dentro del programa e instala ruedas ya compiladas en complementos/,
  junto al .exe; al arrancar, esa carpeta se suma a sys.path (ver banco_audio/__init__.py).

La instalación corre en un proceso aparte (el mismo programa con "instalar-complemento") y
escribe su avance en un archivo de texto que la app lee para mostrarlo.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import threading
from pathlib import Path

from . import COMPLEMENTOS, RAIZ_APP, activar_complementos

NIVELES = {
    "mejora": {"nombre": "Mejora", "archivo": "requirements-mejora.txt", "tamano": "≈ 200 MB",
               "paquetes": ["librosa", "pedalboard", "matchering"]},
    "ia": {"nombre": "IA", "archivo": "requirements-ia.txt", "tamano": "≈ 1,2 GB",
           "paquetes": ["torch", "demucs"]},
}
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CONGELADO = bool(getattr(sys, "frozen", False))

_trabajos: dict[str, dict] = {}


def _requisitos(nivel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", RAIZ_APP))
    return base / NIVELES[nivel]["archivo"]


def instalado(nivel: str) -> bool:
    importlib.invalidate_caches()
    return all(importlib.util.find_spec(p) is not None for p in NIVELES[nivel]["paquetes"])


def estado() -> dict:
    salida = {}
    for nivel, datos in NIVELES.items():
        t = _trabajos.get(nivel, {})
        if t.get("estado") == "instalando":
            t["linea"] = _ultima_linea(t["registro"])
        salida[nivel] = {"nombre": datos["nombre"], "tamano": datos["tamano"], "instalado": instalado(nivel),
                         "estado": t.get("estado", ""), "linea": t.get("linea", ""), "error": t.get("error", "")}
    return salida


def _ultima_linea(registro: Path) -> str:
    try:
        lineas = [l.strip() for l in registro.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    except OSError:
        return ""
    utiles = [l for l in lineas if l.startswith(("Collecting", "Downloading", "Installing", "Successfully", "ERROR"))]
    return (utiles or lineas or [""])[-1][:160]


def iniciar(nivel: str) -> dict:
    if nivel not in NIVELES:
        raise ValueError("Nivel desconocido")
    if _trabajos.get(nivel, {}).get("estado") == "instalando":
        return _trabajos[nivel]
    registro = RAIZ_APP / "cache" / f"instalar-{nivel}.log"
    registro.parent.mkdir(parents=True, exist_ok=True)
    registro.write_text("", encoding="utf-8")
    if CONGELADO:
        orden = [sys.executable, "instalar-complemento", nivel, "--registro", str(registro)]
    else:
        orden = [sys.executable, "-m", "banco_audio", "instalar-complemento", nivel, "--registro", str(registro)]
    t = {"estado": "instalando", "registro": registro, "linea": "Preparando…", "error": ""}
    _trabajos[nivel] = t

    def correr():
        proc = subprocess.Popen(orden, creationflags=SIN_VENTANA, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t["_proc"] = proc
        codigo = proc.wait()
        t.pop("_proc", None)
        activar_complementos()
        importlib.invalidate_caches()
        from .mejora import capacidades
        capacidades.capacidades.cache_clear()
        if t.get("cancelar"):
            t.update(estado="cancelado", linea="Instalación detenida: puedes retomarla cuando quieras")
        elif codigo == 0 and instalado(nivel):
            t.update(estado="listo", linea="Instalado")
        else:
            t.update(estado="error", error=_ultima_linea(registro) or f"pip terminó con código {codigo}")

    threading.Thread(target=correr, daemon=True).start()
    return t


def cancelar(nivel: str) -> None:
    t = _trabajos.get(nivel)
    if t and t.get("estado") == "instalando":
        t["cancelar"] = True
        proc = t.get("_proc")
        if proc and proc.poll() is None:
            proc.terminate()


def instalar_aqui(nivel: str, registro: Path) -> int:
    """Corre pip en este proceso (también dentro del .exe) y devuelve su código de salida."""
    salida = open(registro, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = salida
    argumentos = ["install", "-r", str(_requisitos(nivel)), "--disable-pip-version-check",
                  "--no-input", "--progress-bar", "off", "--no-cache-dir"]
    if CONGELADO:
        # Solo ruedas compiladas: dentro del .exe no hay compilador ni intérprete aparte.
        COMPLEMENTOS.mkdir(parents=True, exist_ok=True)
        argumentos += ["--target", str(COMPLEMENTOS), "--only-binary=:all:", "--upgrade",
                       "--no-warn-script-location"]
    print(f"pip {' '.join(argumentos)}", flush=True)
    from pip._internal.cli.main import main as pip_main
    codigo = pip_main(argumentos)
    print(f"Fin (código {codigo})", flush=True)
    return codigo
