"""Abre la app: arranca el servicio interno y muestra el reproductor en el escritorio.

El reproductor y cada ventana extra (biblioteca, descargas, abrir ubicación) son
ventanas propias del sistema, sin marco de Windows: la interfaz dibuja el marco
estilo Winamp. Si pywebview no está instalado, o con --navegador, abre el navegador.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .servidor import ESTATICOS, crear_app

from .. import ajustes

# Forma de la ventana: la skin "cabeza" no es rectangular. En vez de un color
# transparente (con WebView2 deja pasar TODOS los clics), se recorta la ventana con
# la silueta que manda la interfaz: fuera no hay ventana y dentro todo recibe clics.
FONDO = "#000000"


def _recortar(ventana, rects, escala) -> None:
    """rects: lista plana [x, y, w, h, ...] en píxeles CSS; vacía = ventana rectangular.
    escala: devicePixelRatio (la ventana trabaja en píxeles reales de pantalla)."""
    try:
        from System import Action
        from System.Drawing import Rectangle, Region

        forma = ventana.native

        def aplicar():
            if not rects:
                forma.Region = None
                return
            k = float(escala or 1)
            region = Region(Rectangle(0, 0, 0, 0))
            for i in range(0, len(rects) - 3, 4):
                x, y, w, h = (round(v * k) for v in rects[i:i + 4])
                region.Union(Rectangle(x, y, max(1, w), max(1, h)))
            forma.Region = region

        forma.Invoke(Action(aplicar))
    except Exception as e:  # sin recorte se sigue viendo, solo con fondo
        print(f"No se pudo recortar la ventana: {e}")


VENTANAS = {
    "biblioteca": ("MigueWamp · Biblioteca", 700, 470),
    "descargas": ("MigueWamp · Descargas", 540, 420),
    "ubicacion": ("MigueWamp · Abrir ubicación", 640, 480),
    "laboratorio": ("MigueWamp · Laboratorio", 980, 660),
}


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class GestorVentanas:
    """Crea y recuerda las ventanas de la app. Al cerrar el reproductor se cierra todo."""

    def __init__(self, url: str):
        self.url = url
        self.ventanas: dict = {}

    def crear_reproductor(self):
        import webview
        r = ajustes.leer().get("reproductor", {})
        ancho = int(r.get("ancho", 412))
        api = ApiNativa(self, "reproductor")
        api._ventana = webview.create_window(
            "MigueWamp", self.url, width=ancho, height=int(ancho * 116 / 275 * 2 + 300),
            frameless=True, easy_drag=False, resizable=False, background_color=FONDO, js_api=api)
        self.ventanas["reproductor"] = api._ventana

    def abrir(self, nombre: str):
        import webview
        if nombre not in VENTANAS:
            return
        existente = self.ventanas.get(nombre)
        if existente is not None:
            try:
                existente.restore()
                existente.show()
                return
            except Exception:
                self.ventanas.pop(nombre, None)
        titulo, ancho, alto = VENTANAS[nombre]
        x = y = None
        reproductor = self.ventanas.get("reproductor")
        try:  # al lado del reproductor
            x, y = reproductor.x + reproductor.width + 6, reproductor.y
        except Exception:
            pass
        api = ApiNativa(self, nombre)
        ventana = webview.create_window(
            titulo, f"{self.url}#ventana={nombre}", width=ancho, height=alto, x=x, y=y,
            frameless=True, easy_drag=False, min_size=(340, 220), background_color=FONDO, js_api=api)
        api._ventana = ventana
        ventana.events.closed += lambda: self.ventanas.pop(nombre, None)
        self.ventanas[nombre] = ventana

    def cerrar_todo(self):
        for ventana in list(self.ventanas.values()):
            try:
                ventana.destroy()
            except Exception:
                pass


class ApiNativa:
    """Funciones que la interfaz llama directo a Python a través de pywebview."""

    def __init__(self, gestor: GestorVentanas | None = None, nombre: str = ""):
        self._gestor = gestor
        self._nombre = nombre
        self._ventana = None

    def abrir(self, nombre):
        if self._gestor:
            self._gestor.abrir(nombre)

    def mover(self, x, y):
        self._ventana.move(int(x), int(y))

    def tamano(self, ancho, alto):
        self._ventana.resize(int(ancho), int(alto))

    def forma(self, rects, escala=1):
        _recortar(self._ventana, rects or [], escala)

    def minimizar(self):
        self._ventana.minimize()

    def cerrar(self):
        if self._nombre == "reproductor" and self._gestor:
            self._gestor.cerrar_todo()
        else:
            self._ventana.destroy()

    def elegir_archivo(self):
        import webview
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        rutas = self._ventana.create_file_dialog(
            tipo, file_types=("Listas (*.xlsx;*.csv;*.txt)", "Todos los archivos (*.*)"))
        return rutas[0] if rutas else ""

    # Ajustes (tamaño, paneles...). El puerto cambia en cada arranque, así que el
    # localStorage del navegador no sirve: se guardan en ajustes.json.
    def leer_ajustes(self):
        return ajustes.leer()

    def guardar_ajustes(self, datos):
        return ajustes.guardar(datos)

    def elegir_lista_reproduccion(self):
        import webview
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        rutas = self._ventana.create_file_dialog(
            tipo, file_types=("Listas de reproducción (*.m3u;*.m3u8;*.pls)", "Todos los archivos (*.*)"))
        return rutas[0] if rutas else ""

    def elegir_audios(self):
        import webview
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        rutas = self._ventana.create_file_dialog(tipo, allow_multiple=True, file_types=(
            "Audio (*.mp3;*.m4a;*.opus;*.ogg;*.webm;*.flac;*.wav;*.aac;*.ape;*.wma;*.wv;*.aiff;*.aif;*.mpc;*.tta;*.ac3)",
            "Todos los archivos (*.*)"))
        return list(rutas or [])

    def elegir_carpeta(self):
        import webview
        tipo = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        rutas = self._ventana.create_file_dialog(tipo)
        return rutas[0] if rutas else ""


def _salida_sin_consola() -> None:
    """Con doble clic (pythonw o el .exe) no hay consola: sys.stdout es None y uvicorn
    se cae al arrancar. Se manda todo a miguewamp.log, junto al programa."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    from ..spotify import RAIZ
    log = open(RAIZ / "miguewamp.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log


def lanzar(destino: Path, navegador: bool = False, puerto: int = 0) -> None:
    _salida_sin_consola()
    if not (ESTATICOS / "index.html").exists():
        raise SystemExit("Falta la interfaz compilada. Ejecuta:  cd web  &&  npm install  &&  npm run build")

    puerto = puerto or _puerto_libre()
    servidor = uvicorn.Server(uvicorn.Config(crear_app(destino), host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        if not hilo.is_alive():
            raise SystemExit("No arrancó el servicio interno; revisa miguewamp.log")
        time.sleep(0.05)
    url = f"http://127.0.0.1:{puerto}/"

    try:
        import webview
    except ImportError:
        webview = None
        if not navegador:
            print("pywebview no está instalado; se abre en el navegador.")

    if navegador or webview is None:
        print(f"Banco de audio en {url}  (Ctrl+C para cerrar)")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        # El reproductor recibe órdenes de otras ventanas (biblioteca, descargas) sin un clic
        # propio: sin esto, el motor web bloquearía el sonido.
        os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--autoplay-policy=no-user-gesture-required")
        GestorVentanas(url).crear_reproductor()
        webview.start()
    servidor.should_exit = True
