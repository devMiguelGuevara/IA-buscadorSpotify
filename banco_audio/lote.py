"""Planificar y ejecutar un lote de descargas.

Separado de la CLI para que la futura app lo reutilice: avisa del avance por
callbacks y no imprime nada por su cuenta.
"""

from __future__ import annotations

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import playlists
from .cancion import Cancion
from .descargador import Resultado, medir_calidad
from .registro import Registro

# (posición, total, canción, resultado)
AlResultado = Callable[[int, int, Cancion, Resultado], None]


@dataclass
class Plan:
    pendientes: list[Cancion] = field(default_factory=list)
    ya_estaban: int = 0


@dataclass
class Balance:
    conteo: Counter = field(default_factory=Counter)
    para_revisar: list[tuple[Cancion, Resultado]] = field(default_factory=list)
    interrumpido: bool = False


def planificar(canciones: list[Cancion], registro: Registro, forzar: bool = False,
               limite: int | None = None) -> Plan:
    """Quita lo que ya está en el banco y las canciones repetidas en la lista."""
    plan, claves = Plan(), set()
    for c in canciones:
        if registro.ya_descargada(c) and not forzar:
            plan.ya_estaban += 1
        elif c.clave not in claves:  # la misma canción repetida en la lista (otro álbum, etc.)
            claves.add(c.clave)
            plan.pendientes.append(c)
    if limite:
        plan.pendientes = plan.pendientes[:limite]
    return plan


def registrar(registro: Registro, cancion: Cancion, r: Resultado, destino: Path, simular: bool) -> None:
    if simular:
        return
    extra = {"revisar": r.revisar}
    if r.candidato:
        extra |= {"fuente": r.candidato.fuente, "url": r.candidato.url, "titulo_fuente": r.candidato.titulo}
    if r.archivo:
        extra["archivo"] = r.archivo.relative_to(destino).as_posix()
    if r.error:
        extra["error"] = r.error
    if r.calidad:
        extra["calidad"] = r.calidad
    registro.guardar(cancion, r.estado, **extra)


def escribir_lista(nombre: str, canciones: list[Cancion], registro: Registro, destino: Path) -> int:
    """Playlist .m3u8 con todas las canciones de la lista que están en el banco.

    Una canción que ya estaba por otra lista no se vuelve a bajar: la lista la referencia.
    """
    pistas, vistas = [], set()
    for c in canciones:
        archivo = registro.ya_descargada(c)
        if not archivo or archivo in vistas:
            continue
        vistas.add(archivo)
        pistas.append({"raiz": 0, "ruta": archivo.relative_to(destino).as_posix(),
                       "titulo": c.titulo, "artista": c.artista, "duracion": c.duracion})
    if not pistas:
        return 0
    return playlists.guardar(nombre, pistas, [destino], descarga=True)


def ejecutar(descargador, pendientes: list[Cancion], carpeta: Path, *, registro: Registro,
             destino: Path, simular: bool, hilos: int = 1,
             al_resultado: AlResultado | None = None,
             al_interrumpir: Callable[[], None] | None = None) -> Balance:
    """Procesa las canciones en paralelo y guarda cada resultado en el registro."""
    balance, lock, total = Balance(), threading.Lock(), len(pendientes)

    def trabajar(i: int, cancion: Cancion) -> None:
        resultado = descargador.procesar(cancion, carpeta)
        registrar(registro, cancion, resultado, destino, simular)
        with lock:
            balance.conteo[resultado.estado] += 1
            if resultado.revisar and resultado.estado in ("ok", "simulado"):
                balance.para_revisar.append((cancion, resultado))
            if al_resultado:
                al_resultado(i, total, cancion, resultado)

    with ThreadPoolExecutor(max_workers=max(1, hilos)) as ejecutor:
        futuros = [ejecutor.submit(trabajar, i, c) for i, c in enumerate(pendientes, 1)]
        try:
            for f in as_completed(futuros):
                f.result()
        except KeyboardInterrupt:
            balance.interrumpido = True
            if al_interrumpir:
                al_interrumpir()
            descargador.detener.set()
            ejecutor.shutdown(wait=True, cancel_futures=True)
    return balance


# ------------------------------------------------------------ re-descargar en máxima calidad
def para_mejorar(registro: Registro, destino: Path) -> list[tuple[str, dict]]:
    """Canciones del banco en MP3 que tienen su enlace guardado: se pueden bajar en mejor calidad."""
    return [(k, e) for k, e in registro.entradas()
            if e.get("estado") == "ok" and e.get("url") and str(e.get("archivo", "")).lower().endswith(".mp3")
            and (destino / e["archivo"]).exists()]


def mejorar_banco(descargador, registro: Registro, destino: Path, *, limite: int | None = None,
                  simular: bool = False, al_resultado: AlResultado | None = None) -> Counter:
    """Baja de nuevo, en el formato original, las canciones que hoy son MP3.

    El archivo nuevo se verifica (misma duración, ±3 s) antes de retirar el viejo, que no se
    borra: se mueve a <banco>/_reemplazados/ con la misma ruta.
    """
    if descargador.op.formato != "original":
        raise ValueError("La mejora de calidad usa el formato original.")
    conteo, lista = Counter(), para_mejorar(registro, destino)[:limite or None]
    for i, (clave, e) in enumerate(lista, 1):
        if descargador.detener.is_set():
            break
        viejo = destino / e["archivo"]
        cancion = Cancion(titulo=e.get("titulo", ""), artista=e.get("artista", ""), album=e.get("album", ""),
                          spotify_id=e.get("spotify_id", ""), url=e["url"])
        r = descargador.descargar_url(cancion, e["url"], viejo.parent)
        if r.estado == "ok" and r.archivo:
            antes = medir_calidad(viejo).get("duracion")
            ahora = r.calidad.get("duracion")
            if antes and ahora and abs(antes - ahora) > 3:
                r.estado, r.error = "fallo", f"la duración no coincide ({antes}s antes, {ahora}s ahora)"
                r.archivo.unlink(missing_ok=True)
            else:
                retirado = destino / "_reemplazados" / e["archivo"]
                retirado.parent.mkdir(parents=True, exist_ok=True)
                viejo.replace(retirado)
                registro.actualizar(clave, archivo=r.archivo.relative_to(destino).as_posix(),
                                    calidad=r.calidad, fuente=r.candidato.fuente if r.candidato else e.get("fuente"))
        conteo[r.estado] += 1
        if al_resultado:
            al_resultado(i, len(lista), cancion, r)
    return conteo
