"""Servicio interno de la app: sirve la interfaz, la biblioteca, las playlists y las descargas.

Solo escucha en 127.0.0.1; las ventanas de la app son su único cliente.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import actualizador, ajustes, complementos, conversion, niveles, playlists
from ..biblioteca import EXTENSIONES, escanear, pista
from ..cancion import segundos_a_duracion
from ..descargador import FORMATOS, METODOS, Descargador, Opciones
from ..fuentes import FuenteInvalida, cargar_grupo, nombre_grupo, partir
from ..limitador import Limitador
from ..lote import ejecutar, escribir_lista, mejorar_banco, para_mejorar, planificar
from ..registro import Registro
from ..mejora import motores as mejora_motores
from ..mejora.capacidades import capacidades
from ..mejora.laboratorio import VERSIONES, Laboratorio, espectrograma, listar_versiones

ESTATICOS = Path(__file__).parent / "static"


class Texto(BaseModel):
    texto: str
    simular: bool = False
    metodo: str = "auto"
    formato: str = "original"


class Mejora(BaseModel):
    simular: bool = False
    limite: int | None = None


class Orden(BaseModel):
    accion: str
    pistas: list[dict]


class Ruta(BaseModel):
    ruta: str


class Rutas(BaseModel):
    rutas: list[str]


def _dentro(ruta: Path, base: Path) -> bool:
    try:
        ruta.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


class Cancion(BaseModel):
    raiz: int = 0
    ruta: str = ""
    version: str = ""   # ruta de una versión (relativa a versiones/), en vez de raiz + ruta
    titulo: str = ""
    artista: str = ""


class Proceso(Cancion):
    receta: list[dict]
    formato: str = "flac"


class Playlist(BaseModel):
    pistas: list[dict]
    agregar: bool = False


class GestorDescargas:
    """Cola de trabajos en hilos. Todos comparten el limitador; el registro va con la carpeta de descargas."""

    def __init__(self):
        self.limitador = Limitador()
        self.trabajos: dict[str, dict] = {}
        self._descargadores: dict[str, Descargador] = {}  # para pausar, reanudar o cancelar
        self._registro: Registro | None = None

    def controlar(self, id_: str, accion: str) -> dict:
        t, d = self.trabajos.get(id_), self._descargadores.get(id_)
        if not t:
            raise KeyError(id_)
        if d and t["estado"] in ("descargando", "pausado"):
            if accion == "pausar":
                d.pausado.set()
                t["estado"] = "pausado"
            elif accion == "reanudar":
                d.pausado.clear()
                t["estado"] = "descargando"
            elif accion == "cancelar":
                d.detener.set()
                d.pausado.clear()
                t["estado"] = "cancelando"
        return t

    @property
    def destino(self) -> Path:
        return ajustes.carpetas()[0]

    @property
    def registro(self) -> Registro:
        archivo = self.destino / "registro_descargas.json"
        if self._registro is None or self._registro.ruta != archivo:
            self._registro = Registro(archivo)
        return self._registro

    def resolver(self, texto: str) -> list[dict]:
        listas = []
        for grupo in partir(texto):
            fuente = nombre_grupo(grupo)
            try:
                nombre, canciones = cargar_grupo(grupo)
            except (FuenteInvalida, SystemExit) as e:
                listas.append({"fuente": fuente, "nombre": fuente, "error": str(e), "items": []})
                continue
            items = []
            for c in canciones:
                archivo = self.registro.ya_descargada(c)
                items.append({
                    "titulo": c.titulo, "artista": c.artista, "album": c.album,
                    "duracion": segundos_a_duracion(c.duracion), "url": c.url,
                    "archivo": archivo.relative_to(self.destino).as_posix() if archivo else "",
                })
            listas.append({"fuente": fuente, "nombre": nombre, "error": "", "items": items})
        return listas

    def iniciar(self, texto: str, simular: bool, metodo: str = "auto", formato: str = "original") -> list[str]:
        metodo = metodo if metodo in METODOS else "auto"
        formato = formato if formato in FORMATOS else "original"
        ids = []
        for grupo in partir(texto):
            t = {"id": uuid.uuid4().hex[:8], "grupo": grupo, "nombre": nombre_grupo(grupo), "estado": "preparando",
                 "simular": simular, "metodo": metodo, "formato": formato,
                 "ya_estaban": 0, "error": "", "items": []}
            self.trabajos[t["id"]] = t
            ids.append(t["id"])
            threading.Thread(target=self._correr, args=(t,), daemon=True).start()
        return ids

    def _correr(self, t: dict) -> None:
        try:
            destino, registro = self.destino, self.registro
            destino.mkdir(parents=True, exist_ok=True)
            nombre, canciones = cargar_grupo(t.pop("grupo"))
            plan = planificar(canciones, registro)
            t["nombre"], t["ya_estaban"] = nombre, plan.ya_estaban
            t["items"] = [{"titulo": c.titulo, "artista": c.artista, "album": c.album,
                           "duracion": segundos_a_duracion(c.duracion), "estado": "en_cola",
                           "fuente": "", "url": c.url, "archivo": "", "revisar": False, "error": ""}
                          for c in plan.pendientes]
            t["estado"] = "descargando"
            descargador = Descargador(Opciones(destino=destino, simular=t["simular"], metodo=t["metodo"],
                                               formato=t["formato"]), self.limitador)
            self._descargadores[t["id"]] = descargador

            def al_resultado(i, _total, _cancion, r):
                item = t["items"][i - 1]
                item.update(estado=r.estado, revisar=r.revisar, error=r.error)
                if r.candidato:
                    item.update(fuente=r.candidato.fuente, url=r.candidato.url, titulo_fuente=r.candidato.titulo)
                if r.archivo:
                    item["archivo"] = r.archivo.relative_to(destino).as_posix()
                if r.calidad:
                    item["calidad"] = r.calidad

            ejecutar(descargador, plan.pendientes, destino / nombre, registro=registro,
                     destino=destino, simular=t["simular"], al_resultado=al_resultado)
            if not t["simular"]:  # la lista queda como playlist, con lo que ya estaba por otra lista
                t["lista"] = escribir_lista(nombre, canciones, registro, destino)
            t["estado"] = "cancelado" if descargador.detener.is_set() else "terminado"
        except (FuenteInvalida, SystemExit) as e:
            t.update(estado="error", error=str(e))
        except Exception as e:  # un trabajo que falla no debe tumbar la app
            t.update(estado="error", error=f"{type(e).__name__}: {e}")


    def mejorar(self, simular: bool, limite: int | None) -> str:
        t = {"id": uuid.uuid4().hex[:8], "nombre": "Mejorar calidad del banco", "estado": "preparando",
             "simular": simular, "metodo": "auto", "formato": "original", "ya_estaban": 0, "error": "", "items": []}
        self.trabajos[t["id"]] = t
        threading.Thread(target=self._correr_mejora, args=(t, limite), daemon=True).start()
        return t["id"]

    def _correr_mejora(self, t: dict, limite: int | None) -> None:
        try:
            destino, registro = self.destino, self.registro
            candidatas = para_mejorar(registro, destino)[:limite or None]
            t["items"] = [{"titulo": e.get("titulo", ""), "artista": e.get("artista", ""), "album": e.get("album", ""),
                           "duracion": "", "estado": "en_cola", "fuente": e.get("fuente", ""), "url": e.get("url", ""),
                           "archivo": e.get("archivo", ""), "revisar": False, "error": ""} for _, e in candidatas]
            t["estado"] = "descargando"
            descargador = Descargador(Opciones(destino=destino, simular=t["simular"]), self.limitador)
            self._descargadores[t["id"]] = descargador

            def al_resultado(i, _total, _cancion, r):
                item = t["items"][i - 1]
                item.update(estado=r.estado, error=r.error)
                if r.archivo:
                    item["archivo"] = r.archivo.relative_to(destino).as_posix()
                if r.calidad:
                    item["calidad"] = r.calidad

            mejorar_banco(descargador, registro, destino, limite=limite, simular=t["simular"], al_resultado=al_resultado)
            t["estado"] = "cancelado" if descargador.detener.is_set() else "terminado"
        except Exception as e:
            t.update(estado="error", error=f"{type(e).__name__}: {e}")


def crear_app(destino: Path) -> FastAPI:
    ajustes.fijar_defecto(destino)
    ajustes.carpetas()[0].mkdir(parents=True, exist_ok=True)
    gestor = GestorDescargas()
    app = FastAPI(title="MigueWamp", docs_url=None, redoc_url=None)

    # ---------------- biblioteca y carpetas
    @app.get("/api/biblioteca")
    def biblioteca():
        canciones = []
        for i, raiz in enumerate(ajustes.carpetas()):
            for c in escanear(raiz):
                canciones.append({**c, "raiz": i})
        return {"canciones": canciones}

    @app.get("/api/carpetas")
    def ver_carpetas():
        return {"carpetas": [{"i": i, "ruta": str(p), "existe": p.exists(), "descargas": i == 0}
                             for i, p in enumerate(ajustes.carpetas())]}

    @app.post("/api/carpetas")
    def agregar_carpeta(datos: Ruta):
        try:
            ajustes.agregar_carpeta(datos.ruta)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return ver_carpetas()

    @app.post("/api/carpetas/quitar")
    def quitar_carpeta(datos: Ruta):
        ajustes.quitar_carpeta(datos.ruta)
        return ver_carpetas()

    @app.post("/api/carpetas/descargas")
    def carpeta_descargas(datos: Ruta):
        try:
            ajustes.cambiar_descargas(datos.ruta)
        except OSError as e:
            raise HTTPException(400, f"No se pudo usar esa carpeta: {e}") from e
        return ver_carpetas()

    @app.post("/api/agregar_rutas")
    def agregar_rutas(datos: Rutas):
        """Archivos o carpetas elegidos en el disco: si están fuera de la biblioteca,
        su carpeta se agrega a la biblioteca para poder reproducirlos."""
        pistas = []
        for texto in datos.rutas:
            ruta = Path(texto.strip().strip('"')).expanduser()
            if not ruta.exists():
                continue
            raices = ajustes.carpetas()
            if not any(_dentro(ruta, r) for r in raices):
                ajustes.agregar_carpeta(str(ruta if ruta.is_dir() else ruta.parent))
                raices = ajustes.carpetas()
            i, base = next((i, r) for i, r in enumerate(raices) if _dentro(ruta, r))
            base = base.resolve()
            if ruta.is_dir():
                archivos = sorted(a for a in ruta.resolve().rglob("*") if a.suffix.lower() in EXTENSIONES)
            elif ruta.suffix.lower() in EXTENSIONES:
                archivos = [ruta.resolve()]
            else:
                archivos = []
            pistas += [{**pista(a, base), "raiz": i} for a in archivos]
        return {"pistas": pistas}

    @app.get("/media/{i}/{ruta:path}")
    def media(i: int, ruta: str):
        raices = ajustes.carpetas()
        if not 0 <= i < len(raices):
            raise HTTPException(404)
        base = raices[i].resolve()
        archivo = (base / ruta).resolve()
        if not archivo.is_relative_to(base) or not archivo.is_file():
            raise HTTPException(404)
        if conversion.necesita(archivo):  # APE, WMA...: la ventana no los reproduce
            try:
                return FileResponse(conversion.para_reproducir(archivo), media_type="audio/flac")
            except RuntimeError as e:
                raise HTTPException(415, str(e)) from e
        return FileResponse(archivo)

    @app.get("/api/nivel")
    def nivel(url: str):
        """Ganancia para el volumen nivelado de una pista del reproductor (/media/... o /versiones/...)."""
        ruta = unquote(urlsplit(url).path)
        partes = ruta.lstrip("/").split("/", 2)
        if partes[0] == "media" and len(partes) == 3 and partes[1].isdigit():
            raices = ajustes.carpetas()
            if not int(partes[1]) < len(raices):
                raise HTTPException(404)
            base = raices[int(partes[1])].resolve()
            archivo = (base / partes[2]).resolve()
        elif partes[0] == "versiones" and len(partes) > 1:
            base = VERSIONES.resolve()
            archivo = (base / ruta.lstrip("/").split("/", 1)[1]).resolve()
        else:
            raise HTTPException(404)
        if not archivo.is_relative_to(base) or not archivo.is_file():
            raise HTTPException(404)
        return niveles.nivel(archivo)

    # ---------------- playlists
    @app.get("/api/playlists")
    def ver_playlists():
        return {"playlists": playlists.listar()}

    @app.get("/api/playlists/{nombre}")
    def ver_playlist(nombre: str):
        try:
            return {"nombre": nombre, "pistas": playlists.leer(nombre, ajustes.carpetas())}
        except FileNotFoundError as e:
            raise HTTPException(404, "No existe esa playlist") from e

    @app.put("/api/playlists/{nombre}")
    def guardar_playlist(nombre: str, datos: Playlist):
        try:
            n = playlists.guardar(nombre, datos.pistas, ajustes.carpetas(), agregar=datos.agregar)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {"nombre": nombre, "canciones": n}

    @app.post("/api/playlists/importar")
    def importar_playlist(datos: Ruta):
        archivo = Path(datos.ruta.strip().strip('"')).expanduser()
        if archivo.suffix.lower() not in (".m3u", ".m3u8", ".pls") or not archivo.is_file():
            raise HTTPException(400, "Elige un archivo .m3u, .m3u8 o .pls")
        return playlists.importar(archivo, ajustes.carpetas())

    @app.delete("/api/playlists/{nombre}")
    def borrar_playlist(nombre: str):
        playlists.borrar(nombre)
        return ver_playlists()

    # ---------------- descargas
    @app.post("/api/resolver")
    def resolver(datos: Texto):
        return {"listas": gestor.resolver(datos.texto)}

    @app.post("/api/descargas")
    def descargar(datos: Texto):
        return {"trabajos": gestor.iniciar(datos.texto, datos.simular, datos.metodo, datos.formato)}

    @app.post("/api/descargas/{id_}/{accion}")
    def controlar(id_: str, accion: str):
        if accion not in ("pausar", "reanudar", "cancelar"):
            raise HTTPException(400, "Acción no válida")
        try:
            return gestor.controlar(id_, accion)
        except KeyError as e:
            raise HTTPException(404, "No existe ese trabajo") from e

    # ---------------- yt-dlp actualizable
    @app.get("/api/ytdlp")
    def ytdlp_estado():
        return actualizador.estado()

    @app.get("/api/ytdlp/buscar")
    def ytdlp_buscar():
        try:
            return actualizador.hay_nueva()
        except actualizador.ErrorActualizacion as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/ytdlp/actualizar")
    def ytdlp_actualizar():
        if any(t["estado"] in ("preparando", "descargando", "pausado", "cancelando") for t in gestor.trabajos.values()):
            raise HTTPException(409, "Espera a que terminen las descargas en curso")
        try:
            return actualizador.actualizar()
        except actualizador.ErrorActualizacion as e:
            raise HTTPException(502, str(e)) from e

    @app.get("/api/mejorar")
    def ver_mejorables():
        return {"canciones": len(para_mejorar(gestor.registro, gestor.destino))}

    @app.post("/api/mejorar")
    def mejorar(datos: Mejora):
        return {"trabajo": gestor.mejorar(datos.simular, datos.limite)}

    @app.get("/api/descargas")
    def descargas():
        return {"trabajos": list(gestor.trabajos.values())[::-1]}

    # ---------------- laboratorio de mejora
    laboratorio = Laboratorio()
    seleccion_lab: dict = {}

    def _archivo(c: Cancion) -> Path:
        if c.version:
            base, archivo = VERSIONES.resolve(), (VERSIONES / c.version).resolve()
        else:
            raices = ajustes.carpetas()
            if not 0 <= c.raiz < len(raices):
                raise HTTPException(404)
            base = raices[c.raiz].resolve()
            archivo = (base / c.ruta).resolve()
        if not archivo.is_relative_to(base) or not archivo.is_file():
            raise HTTPException(404, "No existe el archivo")
        return archivo

    @app.get("/api/mejora/capacidades")
    def ver_capacidades():
        return capacidades()

    @app.get("/api/complementos")
    def ver_complementos():
        return complementos.estado()

    @app.post("/api/complementos/{nivel}")
    def instalar_complemento(nivel: str):
        try:
            complementos.iniciar(nivel)
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
        return complementos.estado()

    @app.delete("/api/complementos/{nivel}")
    def cancelar_complemento(nivel: str):
        complementos.cancelar(nivel)
        return complementos.estado()

    @app.get("/api/mejora/motores")
    def ver_motores():
        return {"motores": mejora_motores.catalogo()}

    @app.post("/api/mejora/seleccion")
    def elegir_para_lab(c: Cancion):
        seleccion_lab.clear()
        seleccion_lab.update(c.model_dump() | {"n": seleccion_lab.get("n", 0) + 1})
        return seleccion_lab

    @app.get("/api/mejora/seleccion")
    def ver_seleccion_lab():
        return seleccion_lab

    @app.post("/api/mejora/analizar")
    def analizar(c: Cancion):
        return _limpio(laboratorio.analizar(_archivo(c)))

    @app.post("/api/mejora/procesar")
    def procesar(p: Proceso):
        if not p.receta:
            raise HTTPException(400, "Elige al menos un proceso")
        receta = []
        for paso in p.receta:
            if paso.get("id") == "matchering":
                ref = paso.get("referencia") or {}
                if not ref.get("ruta"):
                    raise HTTPException(400, "Elige la canción de referencia para Matchering")
                paso = {**paso, "referencia_ruta": str(_archivo(Cancion(**{k: ref[k] for k in ("raiz", "ruta", "version") if k in ref})))}
            receta.append(paso)
        return _limpio(laboratorio.procesar(_archivo(p), receta, p.formato))

    def _limpio(t: dict) -> dict:
        return {k: v for k, v in t.items() if not k.startswith("_")}

    @app.get("/api/mejora/trabajos")
    def trabajos_lab():
        return {"trabajos": [_limpio(t) for t in list(laboratorio.trabajos.values())[::-1][:30]]}

    @app.post("/api/mejora/trabajos/{id_}/cancelar")
    def cancelar_lab(id_: str):
        t = laboratorio.cancelar(id_)
        if not t:
            raise HTTPException(404)
        return _limpio(t)

    @app.post("/api/mejora/versiones")
    def versiones(c: Cancion):
        return {"versiones": listar_versiones(_archivo(c))}

    @app.post("/api/mejora/espectro")
    def espectro(c: Cancion):
        archivo = _archivo(c)
        nombre = hashlib.md5(str(archivo).encode()).hexdigest() + ".png"
        return FileResponse(espectrograma(archivo, VERSIONES / "_espectros" / nombre), media_type="image/png")

    @app.get("/versiones/{ruta:path}")
    def archivo_version(ruta: str):
        base = VERSIONES.resolve()
        archivo = (base / ruta).resolve()
        if not archivo.is_relative_to(base) or not archivo.is_file():
            raise HTTPException(404)
        return FileResponse(archivo)

    # ---------------- órdenes de las ventanas sueltas para el reproductor
    cola: list[dict] = []

    @app.post("/api/cola")
    def encolar(orden: Orden):
        cola.append({"accion": orden.accion, "pistas": orden.pistas})
        return {"n": len(cola)}

    @app.get("/api/cola")
    def leer_cola(desde: int = 0):
        return {"ordenes": cola[desde:], "n": len(cola)}

    if ESTATICOS.exists():
        app.mount("/", StaticFiles(directory=ESTATICOS, html=True), name="interfaz")
    return app
