"""Letras de las canciones: se buscan una vez y quedan guardadas junto a la canción.

Orden de búsqueda:
1. Lo ya guardado: `<canción>.lrc` junto al audio (o en cache/letras si esa carpeta no deja escribir).
2. LRCLIB (lrclib.net): gratis, sin clave, con letras sincronizadas. Primero la búsqueda exacta y
   luego varios intentos con el título limpio, porque los títulos de YouTube traen basura.
3. YouTube Music: la letra que muestra la app, a veces con tiempos.

Una letra sincronizada (con tiempos por línea) gana a una de solo texto. Las que no se encuentran
se anotan y no se vuelven a buscar en unos días, salvo que se pida de nuevo.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from .limitador import Limitador
from .spotify import RAIZ

LRCLIB = "https://lrclib.net/api"
AGENTE = "MigueWamp/1.0 (https://github.com/devMiguelGuevara/IA-buscadorSpotify)"
CACHE = RAIZ / "cache" / "letras"
SIN_RESULTADO = RAIZ / "cache" / "letras_sin_resultado.json"
DIAS_SIN_REINTENTAR = 7
TOLERANCIA_DURACION = 10  # segundos: las versiones en vivo o editadas duran distinto

# Si es False, las descargas no buscan su letra (lo cambia quien no guarda junto al audio).
AL_DESCARGAR = True

_limitador = Limitador(pausa_min=0.2, pausa_max=0.6, enfriamiento_base=30, enfriamiento_max=300)
_candados: dict[str, threading.Lock] = {}
_candados_lock = threading.Lock()
_sin_resultado_lock = threading.Lock()
_en_fondo = ThreadPoolExecutor(max_workers=1, thread_name_prefix="letras")

# ---------------- limpieza de títulos y artistas (lo que manda YouTube)
# Entre paréntesis o corchetes, cualquier nota de video o versión sobra: (Official Video), [HD]...
_ENTRE_PARENTESIS = re.compile(
    r"[\(\[][^\)\]]*\b(?:official|oficial|video|v[ií]deo|audio|lyrics?|letra|visualizer|live|en\s+vivo|"
    r"remaster(?:ed)?|hd|hq|4k|clip|ft|feat|featuring)\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
# Sueltas en el título, solo las frases inequívocas (un título puede llamarse «Video Killed...»).
_SUELTAS = re.compile(
    r"\b(?:official\s+(?:music\s+)?(?:video|audio)|music\s+video|video\s+oficial|audio\s+oficial|lyric\s+video|"
    r"visualizer|live\s+tv|remastered(?:\s+\d{4})?|\d{4}\s+remaster(?:ed)?|hd|hq|4k)\b",
    re.IGNORECASE,
)
_FEAT = re.compile(r"\s(?:ft\.?|feat\.?|featuring)\s.*$", re.IGNORECASE)  # «Canción ft. Otro»: se corta ahí
_COLA = re.compile(r"\s[-–—]\s*(?:video|v[ií]deo|audio|lyrics?|letra|clip)\s*$", re.IGNORECASE)  # «... - Video»
_SIMBOLOS = re.compile(r"[☀-➿\U0001F300-\U0001FAFF♪♫♬♩]+")


def limpiar_titulo(texto: str) -> str:
    texto = (texto or "").split("|")[0]
    texto = _SIMBOLOS.sub(" ", texto)
    texto = _ENTRE_PARENTESIS.sub(" ", texto)
    texto = _SUELTAS.sub(" ", texto)
    texto = _FEAT.sub("", texto)
    texto = _COLA.sub("", texto)
    texto = re.sub(r"[\(\[]\s*[\)\]]", " ", texto)  # paréntesis que quedaron vacíos
    return re.sub(r"\s+", " ", texto).strip(" -–—_.,")


def limpiar_artista(texto: str) -> str:
    texto = (texto or "").split("|")[0]
    texto = re.sub(r"\s*-\s*topic\s*$", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s*vevo\s*$", "", texto, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", texto).strip(" -–—_.,")


def _plano(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar nombres."""
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in texto if not unicodedata.combining(c))).strip()


def coincide_artista(encontrado: str, esperado: str) -> bool:
    """«Ángeles del Infierno» = «Angeles del Infierno»; «Iron Maiden» está en «Iron Maiden feat. X»."""
    a, b = _plano(encontrado), _plano(esperado)
    if not a or not b:
        return False
    principal = _plano(esperado.split(",")[0].split("&")[0])
    return a in b or b in a or (bool(principal) and principal in a)


# ---------------- formato LRC
_MARCA = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def leer_lrc(texto: str) -> list[list]:
    """Líneas [segundo, texto]; sin tiempos, el segundo es None. Ignora etiquetas como [ar:...]."""
    desfase = 0.0
    m = re.search(r"\[offset:\s*([+-]?\d+)\s*\]", texto, re.IGNORECASE)
    if m:
        desfase = int(m.group(1)) / 1000
    con_tiempo, sin_tiempo = [], []
    for linea in texto.splitlines():
        marcas = list(_MARCA.finditer(linea))
        if marcas:
            letra = linea[marcas[-1].end():].strip()
            for marca in marcas:
                fraccion = marca.group(3) or "0"
                segundos = int(marca.group(1)) * 60 + int(marca.group(2)) + int(fraccion) / 10 ** len(fraccion)
                con_tiempo.append([round(max(0.0, segundos - desfase), 2), letra])
        elif not re.match(r"^\s*\[[a-z]+:.*\]\s*$", linea, re.IGNORECASE):
            sin_tiempo.append([None, linea.rstrip()])
    if con_tiempo:
        return sorted(con_tiempo, key=lambda l: l[0])
    while sin_tiempo and not sin_tiempo[0][1]:
        sin_tiempo.pop(0)
    while sin_tiempo and not sin_tiempo[-1][1]:
        sin_tiempo.pop()
    return sin_tiempo


def escribir_lrc(lineas: list[list]) -> str:
    salida = []
    for segundos, letra in lineas:
        if segundos is None:
            salida.append(letra)
        else:
            m, s = divmod(segundos, 60)
            salida.append(f"[{int(m):02d}:{s:05.2f}]{letra}")
    return "\n".join(salida) + "\n"


def _resultado(lineas: list[list], fuente: str) -> dict:
    if len(lineas) == 1 and "instrumental" in (lineas[0][1] or "").lower():
        tipo = "instrumental"
    elif lineas and lineas[0][0] is not None:
        tipo = "sincronizada"
    elif lineas:
        tipo = "texto"
    else:
        tipo = "ninguna"
    return {"tipo": tipo, "lineas": lineas, "fuente": fuente}


NINGUNA = {"tipo": "ninguna", "lineas": [], "fuente": ""}

# ---------------- dónde se guarda
def _clave_cache(archivo: Path) -> Path:
    return CACHE / (hashlib.sha1(str(archivo.resolve()).lower().encode()).hexdigest()[:20] + ".lrc")


def guardada(archivo: Path) -> dict | None:
    for ruta in (archivo.with_suffix(".lrc"), _clave_cache(archivo)):
        try:
            if ruta.is_file():
                return _resultado(leer_lrc(ruta.read_text(encoding="utf-8", errors="replace")), "guardada")
        except OSError:
            continue
    return None


def guardar(archivo: Path, lineas: list[list]) -> None:
    texto = escribir_lrc(lineas)
    try:
        archivo.with_suffix(".lrc").write_text(texto, encoding="utf-8")
        return
    except OSError:
        pass  # carpeta de solo lectura: va a la caché de la app
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        _clave_cache(archivo).write_text(texto, encoding="utf-8")
    except OSError:
        pass


def _leer_sin_resultado() -> dict:
    try:
        return json.loads(SIN_RESULTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _anotar_sin_resultado(clave: str, quitar: bool = False) -> None:
    with _sin_resultado_lock:
        datos = _leer_sin_resultado()
        if quitar:
            if datos.pop(clave, None) is None:
                return
        else:
            datos[clave] = datetime.now().isoformat(timespec="seconds")
        try:
            SIN_RESULTADO.parent.mkdir(parents=True, exist_ok=True)
            SIN_RESULTADO.write_text(json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass


def _buscada_hace_poco(clave: str) -> bool:
    fecha = _leer_sin_resultado().get(clave)
    try:
        return bool(fecha) and datetime.now() - datetime.fromisoformat(fecha) < timedelta(days=DIAS_SIN_REINTENTAR)
    except ValueError:
        return False


# ---------------- LRCLIB
def _pedir(ruta: str, parametros: dict) -> object | None:
    parametros = {k: v for k, v in parametros.items() if v not in (None, "")}
    url = f"{LRCLIB}/{ruta}?{urllib.parse.urlencode(parametros)}"
    _limitador.esperar("lrclib")
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _limitador.registrar_bloqueo("lrclib")
        return None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _calificar(r: dict, artista: str, duracion: float | None) -> tuple[int, bool]:
    """(prioridad, sincronizada): 3 = artista y duración, 2 = artista, 1 = duración, 0 = ninguno."""
    por_artista = coincide_artista(r.get("artistName", ""), artista) if artista else False
    por_duracion = bool(duracion and r.get("duration")) and abs(float(r["duration"]) - duracion) <= TOLERANCIA_DURACION
    if not artista and por_duracion:
        por_artista = True  # sin artista conocido, manda la duración
    prioridad = 3 if por_artista and (por_duracion or not duracion) else 2 if por_artista else 1 if por_duracion else 0
    return prioridad, bool(r.get("syncedLyrics"))


def _letra_de(r: dict) -> list[list] | None:
    if r.get("instrumental"):
        return [[None, "♪ Instrumental ♪"]]
    if r.get("syncedLyrics"):
        return leer_lrc(r["syncedLyrics"])
    if r.get("plainLyrics"):
        return leer_lrc(r["plainLyrics"])
    return None


def _intentos(titulo: str, artista: str) -> list[dict]:
    """Los intentos de búsqueda, del más preciso al más suelto, sin repetir."""
    t, a = limpiar_titulo(titulo), limpiar_artista(artista)
    intentos = []
    if a:
        intentos.append({"q": f"{t} {a}"})
        intentos.append({"track_name": t, "artist_name": a})
    for separador in (" - ", " – ", " — "):
        if separador in t:
            x, y = (p.strip() for p in t.split(separador, 1))
            intentos += [{"track_name": y, "artist_name": x}, {"track_name": x, "artist_name": y}]
            break
    if "," in t:
        x, y = (p.strip() for p in t.split(",", 1))
        intentos.append({"track_name": x, "artist_name": y})
    intentos.append({"q": t})
    vistos, unicos = set(), []
    for i in intentos:
        clave = json.dumps(i, sort_keys=True, ensure_ascii=False).lower()
        if clave not in vistos and all(i.values()):
            vistos.add(clave)
            unicos.append(i)
    return unicos


def buscar_lrclib(titulo: str, artista: str, album: str = "", duracion: float | None = None) -> list[list] | None:
    t, a = limpiar_titulo(titulo), limpiar_artista(artista)
    mejor, puesto = None, (-1, False)
    if t and a and duracion:
        exacta = _pedir("get", {"track_name": t, "artist_name": a, "album_name": album, "duration": int(duracion)})
        if isinstance(exacta, dict) and (exacta.get("syncedLyrics") or exacta.get("instrumental")):
            return _letra_de(exacta)
        if isinstance(exacta, dict) and exacta.get("plainLyrics"):
            mejor, puesto = exacta, _calificar(exacta, a, duracion)  # sin tiempos: se sigue buscando una con tiempos
    for intento in _intentos(titulo, artista):
        resultados = _pedir("search", intento)
        if not isinstance(resultados, list):
            continue
        for r in resultados:
            if not (r.get("syncedLyrics") or r.get("plainLyrics") or r.get("instrumental")):
                continue
            calif = _calificar(r, a, duracion)
            if calif > puesto:
                mejor, puesto = r, calif
        if puesto >= (3, True) or (puesto[0] >= 2 and puesto[1]):
            break  # el artista coincide y la letra es sincronizada: no hace falta seguir
    if mejor is None or puesto[0] == 0:
        return None  # otra canción con el mismo nombre: mejor sin letra que con la de otro
    return _letra_de(mejor)


# ---------------- YouTube Music
def _id_video(url_o_id: str | None) -> str:
    if not url_o_id:
        return ""
    if re.fullmatch(r"[\w-]{11}", url_o_id):
        return url_o_id
    partes = urllib.parse.urlsplit(url_o_id)
    if "youtu.be" in partes.netloc:
        return partes.path.strip("/")[:11]
    return (urllib.parse.parse_qs(partes.query).get("v") or [""])[0][:11]


def buscar_youtube_music(titulo: str, artista: str, video: str = "") -> list[list] | None:
    try:
        from ytmusicapi import YTMusic
        yt = YTMusic()
        video = _id_video(video)
        if not video:
            canciones = yt.search(f"{limpiar_artista(artista)} {limpiar_titulo(titulo)}".strip(), filter="songs", limit=3)
            for c in canciones or []:
                nombres = " ".join(x.get("name", "") for x in c.get("artists") or [])
                if not artista or coincide_artista(nombres, limpiar_artista(artista)):
                    video = c.get("videoId") or ""
                    break
        if not video:
            return None
        navegador = (yt.get_watch_playlist(videoId=video, limit=1) or {}).get("lyrics")
        if not navegador:
            return None
        letra = yt.get_lyrics(navegador, timestamps=True)
    except Exception:
        return None
    if not letra:
        return None
    if letra.get("hasTimestamps"):
        return [[round(l.start_time / 1000, 2), l.text] for l in letra["lyrics"]]
    return leer_lrc(letra.get("lyrics") or "") or None


# ---------------- la búsqueda completa
def _candado(clave: str) -> threading.Lock:
    with _candados_lock:
        return _candados.setdefault(clave, threading.Lock())


def obtener(archivo: Path, artista: str, titulo: str, duracion: float | None = None, album: str = "",
            video: str = "", forzar: bool = False, solo_guardada: bool = False) -> dict:
    """La letra de una canción: guardada, o buscada y guardada. Nunca falla: sin letra, tipo «ninguna»."""
    archivo = Path(archivo)
    clave = str(archivo.resolve()).lower()
    with _candado(clave):  # la misma canción pedida dos veces a la vez se busca una sola vez
        if not forzar:
            ya = guardada(archivo)
            if ya:
                return ya
            if solo_guardada or _buscada_hace_poco(clave):
                return dict(NINGUNA)
        elif solo_guardada:
            return guardada(archivo) or dict(NINGUNA)
        lineas = buscar_lrclib(titulo, artista, album, duracion)
        fuente = "lrclib"
        if not lineas or lineas[0][0] is None:  # sin tiempos: YouTube Music puede tenerlos
            otra = buscar_youtube_music(titulo, artista, video)
            if otra and (otra[0][0] is not None or not lineas):
                lineas, fuente = otra, "youtube music"
        if not lineas:
            _anotar_sin_resultado(clave)
            return dict(NINGUNA)
        guardar(archivo, lineas)
        _anotar_sin_resultado(clave, quitar=True)
        return _resultado(lineas, fuente)


def video_del_registro(archivo: Path) -> str:
    """El video de YouTube de una canción descargada (registro_descargas.json de su carpeta)."""
    archivo = Path(archivo).resolve()
    for carpeta in list(archivo.parents)[:4]:
        registro = carpeta / "registro_descargas.json"
        if not registro.is_file():
            continue
        try:
            datos = json.loads(registro.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        relativo = archivo.relative_to(carpeta).as_posix()
        for entrada in datos.values():
            if entrada.get("archivo") == relativo:
                return _id_video(entrada.get("url", ""))
        return ""
    return ""


def para_archivo(archivo: Path, forzar: bool = False, solo_guardada: bool = False) -> dict:
    """La letra de un archivo de la biblioteca, con los datos de sus etiquetas."""
    from .biblioteca import _leer_recordando
    datos = _leer_recordando(Path(archivo))
    video = "" if solo_guardada else video_del_registro(archivo)
    r = obtener(archivo, datos.get("artista", ""), datos.get("titulo", ""), datos.get("duracion"),
                datos.get("album", ""), video, forzar=forzar, solo_guardada=solo_guardada)
    return {**r, "titulo": datos.get("titulo", ""), "artista": datos.get("artista", "")}


def al_descargar(archivo: Path, artista: str, titulo: str, duracion: float | None, album: str, url: str) -> None:
    """Recién descargada: busca su letra en segundo plano, con los datos limpios de la fuente."""
    if not AL_DESCARGAR:
        return
    _en_fondo.submit(obtener, archivo, artista, titulo, duracion, album, _id_video(url))
