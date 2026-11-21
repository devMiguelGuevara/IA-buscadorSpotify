# Receta de PyInstaller para MigueWamp. Se usa desde empaquetar.bat.
# Genera dist/MigueWamp/MigueWamp.exe (carpeta, no un solo archivo: arranca más rápido
# y pywebview funciona más estable así).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

RAIZ = Path(SPECPATH).parent

datos = [(str(RAIZ / "banco_audio" / "app" / "static"), "banco_audio/app/static")]
datos += collect_data_files("ytmusicapi")
datos += collect_data_files("yt_dlp_ejs")
datos += collect_data_files("webview")

ocultos = collect_submodules("uvicorn") + collect_submodules("yt_dlp_ejs") + ["clr"]

a = Analysis(
    [str(RAIZ / "MigueWamp.py")],
    pathex=[str(RAIZ)],
    datas=datos,
    hiddenimports=ocultos,
    # El nivel Mejora (librosa, Pedalboard, Matchering) es opcional y no va en el .exe: aparece como "instalable".
    excludes=["tkinter", "pypdf", "pytest", "librosa", "pedalboard", "matchering", "numba", "llvmlite",
              "scipy", "sklearn", "pandas", "statsmodels", "soundfile", "resampy", "soxr", "numpy"],
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
