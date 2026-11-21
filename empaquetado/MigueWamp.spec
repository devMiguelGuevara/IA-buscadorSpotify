# Receta de PyInstaller para MigueWamp. Se usa desde empaquetar.bat.
# Genera dist/MigueWamp/MigueWamp.exe (carpeta, no un solo archivo: arranca más rápido
# y pywebview funciona más estable así).
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

RAIZ = Path(SPECPATH).parent

datos = [(str(RAIZ / "banco_audio" / "app" / "static"), "banco_audio/app/static")]
datos += collect_data_files("ytmusicapi")
datos += collect_data_files("yt_dlp_ejs")
datos += collect_data_files("webview")

ocultos = collect_submodules("uvicorn") + collect_submodules("yt_dlp_ejs") + ["clr"]

# Los niveles Mejora e IA se instalan desde la app en complementos/ (ver banco_audio/complementos.py):
# para eso viajan pip, los archivos de requisitos y la biblioteca estándar completa, que esas
# librerías usan aunque MigueWamp no la importe.
datos += collect_data_files("pip")
datos += [(str(RAIZ / "requirements-mejora.txt"), "."), (str(RAIZ / "requirements-ia.txt"), ".")]
ocultos += collect_submodules("pip")
# Las extensiones de esos paquetes usan python3.dll (ABI estable) y el runtime de C++ (MSVCP140),
# que PyInstaller no incluye porque MigueWamp no los necesita; se suman para que carguen en cualquier equipo.
binarios = [(str(Path(sys.base_prefix) / "python3.dll"), ".")]
_SISTEMA = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
binarios += [(str(_SISTEMA / n), ".") for n in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll") if (_SISTEMA / n).exists()]
_NO_STDLIB = {"tkinter", "turtle", "turtledemo", "idlelib", "test", "ensurepip", "pydoc_data", "this", "antigravity"}
for _m in sorted(sys.stdlib_module_names - _NO_STDLIB):
    try:
        ocultos += collect_submodules(_m, filter=lambda n: ".test" not in n and ".tests" not in n and "idle_test" not in n)
    except Exception:
        pass

a = Analysis(
    [str(RAIZ / "MigueWamp.py")],
    pathex=[str(RAIZ)],
    datas=datos,
    binaries=binarios,
    hiddenimports=ocultos,
    # pip, como archivos .py normales: su distlib no reconoce el cargador comprimido de PyInstaller.
    module_collection_mode={"pip": "py"},
    # Los niveles Mejora e IA no van dentro del .exe: se instalan aparte, desde la app, en complementos/.
    excludes=["tkinter", "pypdf", "pytest", "librosa", "pedalboard", "matchering", "numba", "llvmlite",
              "scipy", "sklearn", "pandas", "statsmodels", "soundfile", "resampy", "soxr", "numpy",
              "torch", "torchaudio", "demucs", "dora", "julius", "openunmix", "huggingface_hub"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="MigueWamp",
    icon=str(Path(SPECPATH) / "MigueWamp.ico"),
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MigueWamp")
