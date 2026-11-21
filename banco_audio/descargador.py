"""Buscar canciones en YouTube Music / YouTube / SoundCloud y descargarlas.

Estrategia para no depender de un solo método (y no quemar la IP):

1. Búsqueda en cascada: YouTube Music vía ytmusicapi (audio oficial, con
   duración y álbum para comparar con Spotify) -> búsqueda de YouTube vía
   yt-dlp -> SoundCloud. Se pasa a la siguiente fuente solo si la anterior no
   dio un resultado convincente.
2. Descarga con varios clientes de YouTube: si uno falla (formato no
   disponible, 403, token...) se prueba el siguiente, y luego el siguiente
   candidato de la búsqueda.
3. Todas las peticiones pasan por un `Limitador` compartido: pausas
   aleatorias entre peticiones y enfriamiento exponencial si YouTube responde
   con 429 / "confirma que no eres un bot". Tras varios bloqueos seguidos se
   deja de insistir con YouTube y se usa SoundCloud o se pospone la canción.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
import yt_dlp
from yt_dlp.utils import DownloadError, parse_bytes
from ytmusicapi import YTMusic

from .cancion import Cancion, normalizar
from .limitador import Limitador, es_bloqueo
from .memoria import Memoria

YOUTUBE = "youtube"
SOUNDCLOUD = "soundcloud"
OTRO = "otro"  # cualquier otro sitio que yt-dlp soporte

# Clientes de YouTube que se prueban en orden. None = los que yt-dlp elija por defecto.
# Los dos primeros dan audio de ~128 kbps; el resto solo el formato 18 (peor, pero sirve
# de último recurso). YouTube cambia esto a menudo: si uno deja de ir, basta con quitarlo.
CLIENTES_YOUTUBE: list[tuple[str, ...] | None] = [
    None, ("web_embedded",), ("android_vr",), ("tv_simply",), ("mweb",),
]

# Palabras que delatan una versión distinta a la de Spotify (si el título original no las tiene).
PALABRAS_SOSPECHOSAS = [
    "live", "en vivo", "concierto", "cover", "karaoke", "remix", "8d", "slowed", "sped up",
    "reverb", "instrumental", "acustico", "acoustic", "tutorial", "reaccion", "reaction",
    "nightcore", "bass boosted", "loop", "1 hour", "1 hora",
]

_CARACTERES_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# Métodos de búsqueda: qué fuentes se recorren y en qué orden.
METODOS = {
    "auto": ["YouTube Music", "YouTube", "SoundCloud"],
    "ytmusic": ["YouTube Music"],
    "youtube": ["YouTube"],
    "soundcloud": ["SoundCloud"],
}
FORMATOS = ("original", "mp3")


@dataclass
class Opciones:
    destino: Path
    # "original": el mejor stream de audio tal cual (Opus o AAC), sin recodificar: máxima calidad.
    # "mp3": convierte (compatibilidad); recodificar no suma calidad.
    formato: str = "original"
    calidad: str = "320"              # kbps del mp3
    metodo: str = "auto"              # ver METODOS
    tolerancia: int = 15              # segundos de diferencia aceptables con Spotify
    estricto: bool = False            # no descargar si ningún resultado es convincente
    usar_soundcloud: bool = True
    cookies_navegador: str | None = None
    cookies_archivo: str | None = None
    proxy: str | None = None
    limite_velocidad: str | None = None   # p. ej. "2M" (bytes/s) para no saturar la conexión
    max_bloqueos: int = 3             # bloqueos seguidos de YouTube antes de abandonarlo
    simular: bool = False
    recordar: bool = True             # memoria de búsquedas (memoria_busquedas.json en el banco)


@dataclass
class Candidato:
    url: str
    titulo: str
    canal: str
    duracion: int | None
    fuente: str
    album: str = ""
    puntaje: float = 0.0
    motivos: list[str] = field(default_factory=list)
    por_isrc: bool = False  # encontrado buscando el ISRC: la misma grabación

    @property
    def servicio(self) -> str:
        if self.fuente == "SoundCloud":
            return SOUNDCLOUD
        return OTRO if self.fuente == "Enlace" else YOUTUBE


def fuente_de_url(url: str) -> str:
    dominio = url.lower()
    if "soundcloud.com" in dominio:
        return "SoundCloud"
    if "youtube.com" in dominio or "youtu.be" in dominio:
        return "YouTube"
    return "Enlace"


@dataclass
class Resultado:
    estado: str                      # "ok", "simulado", "sin_resultados", "fallo", "pospuesta"
    candidato: Candidato | None = None
    archivo: Path | None = None
    revisar: bool = False
    error: str = ""
    calidad: dict = field(default_factory=dict)  # códec, kbps y kHz medidos con ffprobe


class _LoggerSilencioso:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def buscar_ffmpeg() -> str | None:
    ruta = os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")
    return ruta if ruta and Path(ruta).exists() else None


def medir_calidad(archivo: Path) -> dict:
    """Códec, kbps, kHz y duración del audio con ffprobe ({} si no se puede medir)."""
    ffmpeg = buscar_ffmpeg()
    ffprobe = shutil.which("ffprobe") or (str(Path(ffmpeg).with_name("ffprobe.exe")) if ffmpeg else None)
    if not ffprobe or not Path(ffprobe).exists():
        return {}
    try:
        salida = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=codec_name,bit_rate,sample_rate:format=bit_rate,duration", "-of", "json", str(archivo)],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        datos = json.loads(salida.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {}
    pista = (datos.get("streams") or [{}])[0]
    formato = datos.get("format") or {}
    bits = pista.get("bit_rate") or formato.get("bit_rate")
    return {
        "codec": pista.get("codec_name", ""),
        "kbps": round(int(bits) / 1000) if bits else None,
        "khz": round(int(pista["sample_rate"]) / 1000, 1) if pista.get("sample_rate") else None,
        "duracion": round(float(formato["duration"])) if formato.get("duration") else None,
    }


def nombre_archivo(cancion: Cancion) -> str:
    artista = cancion.artista.split(",")[0].strip() or "Desconocido"
    nombre = _CARACTERES_INVALIDOS.sub("", f"{artista} - {cancion.titulo}")
    return nombre.strip(" .")[:150]


class Descargador:
    def __init__(self, opciones: Opciones, limitador: Limitador | None = None):
        self.op = opciones
        self.limitador = limitador or Limitador()
        self.detener = threading.Event()
        self.pausado = threading.Event()  # mientras esté puesto, no se hace ninguna petición nueva
        self._local = threading.local()
        self.ffmpeg = buscar_ffmpeg()
        self.memoria = Memoria(Path(self.op.destino) / "memoria_busquedas.json") if self.op.recordar else None
        if self.op.formato == "mp3" and not self.ffmpeg and not self.op.simular:
            raise SystemExit(
                "No se encontró ffmpeg, necesario para convertir a MP3.\n"
                "  Instálalo con:  winget install Gyan.FFmpeg   (y abre una terminal nueva)\n"
                "  o define FFMPEG_PATH en .env, o usa --formato original."
            )

    # ------------------------------------------------------------------ yt-dlp
    def _opciones_base(self) -> dict:
        op = {
            "quiet": True,
            "no_warnings": True,
            # yt-dlp imprime sus errores aunque luego otro método funcione; los errores
            # igual llegan como excepción y el resultado final se muestra en la línea de la canción.
            "logger": _LoggerSilencioso(),
            "noprogress": True,
            "noplaylist": True,
            # yt-dlp necesita un intérprete de JavaScript para YouTube; se acepta Deno o Node.
            "js_runtimes": {"deno": {}, "node": {}},
            "retries": 5,
            "fragment_retries": 5,
            "extractor_retries": 2,
            "retry_sleep_functions": {
                "http": lambda n: min(2 ** n, 30),
                "fragment": lambda n: min(2 ** n, 30),
                "extractor": lambda n: 5 * (n + 1),
            },
            "sleep_interval_requests": 0.75,   # pausa entre peticiones internas de una misma extracción
            "socket_timeout": 30,
        }
        if self.op.cookies_navegador:
            op["cookiesfrombrowser"] = (self.op.cookies_navegador,)
        if self.op.cookies_archivo:
            op["cookiefile"] = self.op.cookies_archivo
        if self.op.proxy:
            op["proxy"] = self.op.proxy
        if self.op.limite_velocidad:
            op["ratelimit"] = parse_bytes(self.op.limite_velocidad)
        if self.ffmpeg:
            op["ffmpeg_location"] = self.ffmpeg
        return op

    def _youtube_disponible(self) -> bool:
        return self.limitador.bloqueos_seguidos(YOUTUBE) < self.op.max_bloqueos

    def _esperar_pausa(self) -> None:
        while self.pausado.is_set() and not self.detener.is_set():
            time.sleep(0.3)

    def _con_limite(self, servicio: str, funcion):
        """Ejecuta `funcion()` respetando el limitador; registra bloqueos y éxitos.

        Cualquier error se re-lanza como DownloadError para tratar igual todos los métodos.
        """
        self._esperar_pausa()
        self.limitador.esperar(servicio, self.detener)
        self._esperar_pausa()  # la pausa pudo llegar mientras esperaba su turno
        if self.detener.is_set():
            raise InterruptedError
        try:
            resultado = funcion()
        except Exception as e:
            if es_bloqueo(e):
                segundos, seguidos = self.limitador.registrar_bloqueo(servicio)
                print(f"    ⚠ {servicio} está limitando las peticiones (bloqueo #{seguidos}); "
                      f"enfriando {segundos / 60:.1f} min", flush=True)
            raise e if isinstance(e, DownloadError) else DownloadError(str(e)) from e
        self.limitador.registrar_exito(servicio)
        return resultado

    def _llamar(self, servicio: str, url: str, opciones: dict, descargar: bool) -> dict:
        def extraer():
            with yt_dlp.YoutubeDL(opciones) as ydl:
                return ydl.extract_info(url, download=descargar)
        return self._con_limite(servicio, extraer)

    def _ytmusic(self) -> YTMusic:
        # Una sesión por hilo: requests.Session no garantiza ser segura entre hilos.
        if not hasattr(self._local, "ytmusic"):
            proxies = {"http": self.op.proxy, "https": self.op.proxy} if self.op.proxy else None
            self._local.ytmusic = YTMusic(proxies=proxies)
        return self._local.ytmusic

    # ---------------------------------------------------------------- búsqueda
    def _buscar_en(self, fuente: str, consulta: str) -> list[Candidato]:
        if fuente == "YouTube Music":
            # ytmusicapi da duración, artistas y álbum; yt-dlp solo daría el título.
            resultados = self._con_limite(
                YOUTUBE, lambda: self._ytmusic().search(consulta, filter="songs", limit=6)
            )
            return [
                Candidato(
                    url=f"https://www.youtube.com/watch?v={r['videoId']}",
                    titulo=r.get("title") or "",
                    canal=", ".join(a["name"] for a in r.get("artists") or [] if a.get("name")),
                    duracion=r.get("duration_seconds"),
                    fuente=fuente,
                    album=(r.get("album") or {}).get("name", ""),
                )
                for r in resultados[:6]
                if r.get("videoId")
            ]

        if fuente == "YouTube":
            url, servicio = f"ytsearch6:{consulta}", YOUTUBE
        else:
            url, servicio = f"scsearch5:{consulta}", SOUNDCLOUD
        opciones = {**self._opciones_base(), "extract_flat": "in_playlist", "playlistend": 6}
        info = self._llamar(servicio, url, opciones, descargar=False)

        candidatos = []
        for e in info.get("entries") or []:
            if not e:
                continue
            if servicio == YOUTUBE:
                if not e.get("id") or e.get("ie_key") not in (None, "Youtube"):
                    continue  # descarta canales, playlists y álbumes
                enlace = f"https://www.youtube.com/watch?v={e['id']}"
            else:
                enlace = e.get("url") or e.get("webpage_url")
            if not enlace:
                continue
            duracion = e.get("duration")
            candidatos.append(Candidato(
                url=enlace,
                titulo=e.get("title") or "",
                canal=e.get("channel") or e.get("uploader") or "",
                duracion=int(duracion) if duracion else None,
                fuente=fuente,
            ))
        return candidatos

    def _puntuar(self, cancion: Cancion, c: Candidato) -> None:
        titulo_c = normalizar(f"{c.titulo} {c.canal}")
        palabras = set(normalizar(cancion.titulo).split())
        if palabras:
            coincidencia = len(palabras & set(titulo_c.split())) / len(palabras)
            c.puntaje += 40 * coincidencia

        artista = normalizar(cancion.artista.split(",")[0])
        if artista and artista in titulo_c:
            c.puntaje += 20

        if cancion.album and c.album and normalizar(cancion.album) == normalizar(c.album):
            c.puntaje += 10  # mismo álbum: casi seguro la misma grabación

        if cancion.duracion and c.duracion:
            diferencia = abs(cancion.duracion - c.duracion)
            if diferencia <= self.op.tolerancia:
                c.puntaje += 30 - diferencia
            else:
                c.puntaje -= min(diferencia, 60)
                c.motivos.append(f"duración distinta ({diferencia}s)")

        original = normalizar(cancion.titulo)
        for palabra in PALABRAS_SOSPECHOSAS:
            if re.search(rf"\b{palabra}\b", titulo_c) and not re.search(rf"\b{palabra}\b", original):
                c.puntaje -= 25
                c.motivos.append(f'"{palabra}"')

        if c.fuente == "YouTube Music" or c.canal.endswith("- Topic"):
            c.puntaje += 10  # audio oficial subido por la discográfica
        if c.por_isrc:
            c.puntaje += 30  # mismo código de grabación que en Spotify
            c.motivos.append("ISRC")

    def _es_convincente(self, cancion: Cancion, c: Candidato) -> bool:
        duracion_ok = not (cancion.duracion and c.duracion) or abs(cancion.duracion - c.duracion) <= self.op.tolerancia
        return c.puntaje >= 45 and duracion_ok

    def _clave_memoria(self, cancion: Cancion) -> str:
        return f"{self.op.metodo}|{int(self.op.usar_soundcloud)}|{cancion.clave}"

    def buscar(self, cancion: Cancion) -> list[Candidato]:
        """Como _buscar, pero primero mira la memoria de búsquedas y guarda lo encontrado."""
        if self.memoria:
            recordados = self.memoria.leer(self._clave_memoria(cancion), Candidato)
            if recordados:
                return recordados
        candidatos = self._buscar(cancion)
        if self.memoria:
            self.memoria.guardar(self._clave_memoria(cancion), candidatos)
        return candidatos

    def _buscar(self, cancion: Cancion) -> list[Candidato]:
        """Candidatos ordenados de mejor a peor, recorriendo las fuentes del método en cascada.

        Si la canción trae ISRC (viene de Spotify), primero se busca ese código en
        YouTube Music: cuando aparece, es la misma grabación.
        """
        fuentes = [f for f in METODOS.get(self.op.metodo, METODOS["auto"])
                   if f != "SoundCloud" or self.op.usar_soundcloud or self.op.metodo == "soundcloud"]
        vistos: dict[str, Candidato] = {}
        if cancion.isrc and "YouTube Music" in fuentes and self._youtube_disponible():
            # YouTube Music no indexa el ISRC de forma fiable: a veces devuelve otra canción.
            # Solo cuenta si además coincide al menos la mitad de las palabras del título.
            palabras = set(normalizar(cancion.titulo).split())
            try:
                for c in self._buscar_en("YouTube Music", cancion.isrc):
                    if palabras and len(palabras & set(normalizar(c.titulo).split())) / len(palabras) < 0.5:
                        continue
                    c.por_isrc = True
                    self._puntuar(cancion, c)
                    vistos[c.url] = c
            except DownloadError:
                pass
            ordenados = sorted(vistos.values(), key=lambda c: c.puntaje, reverse=True)
            if ordenados and self._es_convincente(cancion, ordenados[0]):
                return ordenados
        for fuente in fuentes:
            if fuente != "SoundCloud" and not self._youtube_disponible():
                continue
            try:
                encontrados = self._buscar_en(fuente, cancion.consulta)
            except DownloadError:
                continue  # esta fuente falló; se sigue con la siguiente
            for c in encontrados:
                if c.url not in vistos:
                    self._puntuar(cancion, c)
                    vistos[c.url] = c
            ordenados = sorted(vistos.values(), key=lambda c: c.puntaje, reverse=True)
            if ordenados and self._es_convincente(cancion, ordenados[0]):
                break
        return sorted(vistos.values(), key=lambda c: c.puntaje, reverse=True)

    # --------------------------------------------------------------- descarga
    def _opciones_descarga(self, carpeta: Path, nombre: str, clientes: tuple[str, ...] | None) -> dict:
        op = {
            **self._opciones_base(),
            "outtmpl": str(carpeta / f"{nombre}.%(ext)s"),
            "format": "bestaudio/best",
            "overwrites": True,
        }
        if clientes:
            op["extractor_args"] = {"youtube": {"player_client": list(clientes)}}
        if self.op.formato == "mp3":
            extraer = {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": self.op.calidad}
        else:
            # Máxima calidad: el mejor stream de audio, sin las variantes con rango dinámico
            # comprimido (DRC). "best" lo saca del video a su contenedor propio (Opus u M4A)
            # copiando el audio, sin recodificar.
            op["format"] = "bestaudio[format_id!*=drc]/bestaudio/best"
            extraer = {"key": "FFmpegExtractAudio", "preferredcodec": "best"}
        if self.ffmpeg:
            op["writethumbnail"] = True
            op["postprocessors"] = [
                extraer,
                {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
                {"key": "EmbedThumbnail"},
            ]
        return op

    def _descargar_candidato(self, c: Candidato, carpeta: Path, nombre: str) -> Path:
        clientes = CLIENTES_YOUTUBE if c.servicio == YOUTUBE else [None]
        ultimo_error: Exception | None = None
        for cliente in clientes:
            if c.servicio == YOUTUBE and not self._youtube_disponible():
                break
            try:
                info = self._llamar(c.servicio, c.url, self._opciones_descarga(carpeta, nombre, cliente), descargar=True)
                descargas = info.get("requested_downloads") or [{}]
                return Path(descargas[0].get("filepath") or info["filepath"])
            except DownloadError as e:
                ultimo_error = e
                if es_bloqueo(e):
                    break  # cambiar de cliente no sirve si la IP está limitada
        raise ultimo_error or DownloadError("YouTube no disponible por bloqueos")

    def descargar_url(self, cancion: Cancion, url: str, carpeta: Path) -> Resultado:
        """Descarga un enlace concreto, sin buscar: un enlace pegado o un candidato elegido a mano."""
        c = Candidato(url=url, titulo=cancion.titulo, canal=cancion.artista,
                      duracion=cancion.duracion, fuente=fuente_de_url(url))
        if self.op.simular:
            return Resultado("simulado", c)
        if c.servicio == YOUTUBE and not self._youtube_disponible():
            return Resultado("pospuesta", c)
        carpeta.mkdir(parents=True, exist_ok=True)
        try:
            archivo = self._descargar_candidato(c, carpeta, nombre_archivo(cancion))
        except InterruptedError:
            return Resultado("pospuesta", c)
        except DownloadError as e:
            estado = "pospuesta" if c.servicio == YOUTUBE and not self._youtube_disponible() else "fallo"
            return Resultado(estado, c, error=str(e).removeprefix("ERROR: ")[:300])
        etiquetar(archivo, cancion, c)
        return Resultado("ok", c, archivo, calidad=medir_calidad(archivo))

    def procesar(self, cancion: Cancion, carpeta: Path) -> Resultado:
        if cancion.url:
            return self.descargar_url(cancion, cancion.url, carpeta)
        try:
            candidatos = self.buscar(cancion)
        except InterruptedError:
            return Resultado("pospuesta")
        if not candidatos:
            estado = "pospuesta" if not self._youtube_disponible() else "sin_resultados"
            return Resultado(estado)

        mejor = candidatos[0]
        revisar = not self._es_convincente(cancion, mejor)
        if revisar and self.op.estricto:
            return Resultado("sin_resultados", mejor, revisar=True)
        if self.op.simular:
            return Resultado("simulado", mejor, revisar=revisar)

        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = nombre_archivo(cancion)
        ultimo_error = ""
        for c in candidatos[:3]:
            if c.servicio == YOUTUBE and not self._youtube_disponible():
                continue
            try:
                archivo = self._descargar_candidato(c, carpeta, nombre)
            except InterruptedError:
                return Resultado("pospuesta")
            except DownloadError as e:
                ultimo_error = str(e).removeprefix("ERROR: ")[:300]
                continue
            etiquetar(archivo, cancion, c)
            return Resultado("ok", c, archivo, revisar=(c is not mejor) or revisar, calidad=medir_calidad(archivo))

        if not self._youtube_disponible():
            return Resultado("pospuesta", mejor, error=ultimo_error)
        if self.memoria:  # ninguno se pudo bajar: la próxima vez se busca de nuevo
            self.memoria.olvidar(self._clave_memoria(cancion))
        return Resultado("fallo", mejor, error=ultimo_error)


def etiquetar(archivo: Path, cancion: Cancion, c: Candidato) -> None:
    """Escribe título/artista/álbum de Spotify en el archivo (ID3 o MP4)."""
    try:
        import mutagen
        audio = mutagen.File(archivo, easy=True)
        if audio is None:
            return
        if audio.tags is None:
            audio.add_tags()
        audio["title"] = cancion.titulo
        audio["artist"] = cancion.artista
        extras = {
            "album": cancion.album,
            "albumartist": cancion.artista.split(",")[0].strip() if cancion.album else "",
            "tracknumber": str(cancion.numero) if cancion.numero else "",
            "date": cancion.anio,
            "isrc": cancion.isrc,
        }
        for clave, valor in extras.items():
            if valor:
                try:
                    audio[clave] = valor
                except (KeyError, ValueError):
                    pass  # ese formato no admite esta etiqueta
        audio.save()
    except Exception as e:  # las etiquetas son un extra; no deben tumbar la descarga
        print(f"    (no se pudieron escribir las etiquetas: {e})")
