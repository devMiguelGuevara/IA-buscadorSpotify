"""Punto de entrada de MigueWamp (el ejecutable empaquetado arranca aquí).

Sin argumentos abre el reproductor. Con argumentos funciona igual que
`python -m banco_audio`, por ejemplo:  MigueWamp.exe descargar lista.xlsx --simular
"""

import multiprocessing
import os
import sys
from pathlib import Path


def _preparar_entorno() -> None:
    raiz = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    # Herramientas que viajan con el paquete (ffmpeg, ffprobe, node): se usan antes que las del sistema.
    herramientas = raiz / "bin"
    if herramientas.is_dir():
        os.environ["PATH"] = str(herramientas) + os.pathsep + os.environ.get("PATH", "")
    # Sin consola (doble clic) no hay dónde escribir: todo va a miguewamp.log.
    if sys.stdout is None or sys.stderr is None:
        log = open(raiz / "miguewamp.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _preparar_entorno()
    from banco_audio.__main__ import main
    main(sys.argv[1:] or ["app"])
