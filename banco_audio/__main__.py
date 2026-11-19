"""Línea de comandos del banco de audio.

    python -m banco_audio playlists
    python -m banco_audio exportar <playlist | guardadas> [-o listas/archivo.xlsx]
    python -m banco_audio descargar <archivo.xlsx | playlist | guardadas> [opciones]
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from .cancion import Cancion, segundos_a_duracion
from .descargador import Descargador, Opciones, Resultado
from .limitador import Limitador
from .listas import guardar_lista, leer_lista
from .registro import Registro
from .spotify import RAIZ, cliente, es_fuente_spotify, mis_playlists, obtener_canciones

_imprimir_lock = threading.Lock()


def imprimir(*args) -> None:
    with _imprimir_lock:
        print(*args, flush=True)


def cargar_fuente(fuente: str) -> tuple[str, list[Cancion]]:
    ruta = Path(fuente)
    if ruta.exists():
        return ruta.stem, leer_lista(ruta)
    if es_fuente_spotify(fuente):
        return obtener_canciones(cliente(), fuente)
    raise SystemExit(f"No existe el archivo ni es una playlist de Spotify: {fuente}")


# ------------------------------------------------------------------ comandos
def cmd_playlists(_args) -> None:
    playlists = mis_playlists(cliente())
    for p in playlists:
        print(f"{p['canciones']:>5}  {p['nombre']}  (de {p['dueno']})\n       https://open.spotify.com/playlist/{p['id']}")
    print(f"\n{len(playlists)} playlists. Usa la URL con 'exportar' o 'descargar'.")


def cmd_exportar(args) -> None:
    nombre, canciones = obtener_canciones(cliente(), args.fuente)
    salida = Path(args.salida) if args.salida else RAIZ / "listas" / f"{nombre}.xlsx"
    guardar_lista(canciones, salida)
    print(f"{len(canciones)} canciones de «{nombre}» guardadas en {salida}")


def cmd_descargar(args) -> None:
    nombre_lista, canciones = cargar_fuente(args.fuente)
    if not canciones:
        raise SystemExit("La lista está vacía o no se pudo interpretar.")

    destino = Path(args.destino).expanduser()
    carpeta = destino if args.sin_carpeta else destino / (args.carpeta or nombre_lista)
    registro = Registro(destino / "registro_descargas.json")

    pendientes, claves, ya_estaban = [], set(), 0
    for c in canciones:
        if registro.ya_descargada(c) and not args.forzar:
            ya_estaban += 1
        elif c.clave not in claves:  # la misma canción repetida en la lista (otro álbum, etc.)
            claves.add(c.clave)
            pendientes.append(c)
    if args.limite:
        pendientes = pendientes[: args.limite]

    print(f"«{nombre_lista}»: {len(canciones)} canciones, {ya_estaban} ya en el banco, {len(pendientes)} por procesar.")
    print(f"Destino: {carpeta}" + ("   (modo simulación: no se descarga nada)" if args.simular else ""))
    if not pendientes:
        return

    opciones = Opciones(
        destino=destino,
        formato=args.formato,
        calidad=args.calidad,
        tolerancia=args.tolerancia,
        estricto=args.estricto,
        usar_soundcloud=not args.sin_soundcloud,
        cookies_navegador=args.cookies_navegador,
        cookies_archivo=args.cookies,
        proxy=args.proxy or os.getenv("BANCO_AUDIO_PROXY"),
        limite_velocidad=args.limite_velocidad,
        max_bloqueos=args.max_bloqueos,
        simular=args.simular,
    )
    descargador = Descargador(opciones, Limitador(*args.pausa))
    conteo: Counter[str] = Counter()
    para_revisar: list[tuple[Cancion, Resultado]] = []
    total = len(pendientes)

    def trabajar(i: int, cancion: Cancion) -> None:
        resultado = descargador.procesar(cancion, carpeta)
        _registrar(registro, cancion, resultado, destino, args.simular)
        with _imprimir_lock:
            conteo[resultado.estado] += 1
            if resultado.revisar and resultado.estado in ("ok", "simulado"):
                para_revisar.append((cancion, resultado))
            print(_linea(i, total, cancion, resultado), flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.hilos)) as ejecutor:
        futuros = [ejecutor.submit(trabajar, i, c) for i, c in enumerate(pendientes, 1)]
        try:
            for f in as_completed(futuros):
                f.result()
        except KeyboardInterrupt:
            imprimir("\nInterrumpido: terminando las descargas en curso...")
            descargador.detener.set()
            ejecutor.shutdown(wait=True, cancel_futures=True)

    _resumen(conteo, para_revisar, ya_estaban)


def _registrar(registro: Registro, cancion: Cancion, r: Resultado, destino: Path, simular: bool) -> None:
    if simular:
        return
    extra = {"revisar": r.revisar}
    if r.candidato:
        extra |= {"fuente": r.candidato.fuente, "url": r.candidato.url, "titulo_fuente": r.candidato.titulo}
    if r.archivo:
        extra["archivo"] = r.archivo.relative_to(destino).as_posix()
    if r.error:
        extra["error"] = r.error
    registro.guardar(cancion, r.estado, **extra)


def _linea(i: int, total: int, cancion: Cancion, r: Resultado) -> str:
    iconos = {"ok": "✓", "simulado": "→", "sin_resultados": "✗", "fallo": "✗", "pospuesta": "…"}
    base = f"[{i}/{total}] {iconos.get(r.estado, '?')} {cancion.artista} - {cancion.titulo}"
    if r.candidato:
        c = r.candidato
        dur = f"{segundos_a_duracion(c.duracion)} vs {segundos_a_duracion(cancion.duracion)}" if c.duracion else "?"
        base += f"\n        {c.fuente}: «{c.titulo}» ({dur})"
        if r.revisar:
            base += "  ⚠ revisar" + (f": {', '.join(c.motivos)}" if c.motivos else "")
    if r.estado == "pospuesta":
        base += "\n        pospuesta: YouTube está bloqueando; se reintentará en la próxima ejecución"
    elif r.error:
        base += f"\n        error: {r.error}"
    return base


def _resumen(conteo: Counter, para_revisar: list, ya_estaban: int) -> None:
    print("\n── Resumen ──")
    etiquetas = {
        "ok": "descargadas", "simulado": "encontradas (simulación)", "sin_resultados": "sin resultados",
        "fallo": "fallidas", "pospuesta": "pospuestas por bloqueo",
    }
    for estado, texto in etiquetas.items():
        if conteo[estado]:
            print(f"  {conteo[estado]:>4} {texto}")
    if ya_estaban:
        print(f"  {ya_estaban:>4} ya estaban en el banco")
    if para_revisar:
        print(f"\n  {len(para_revisar)} para revisar (el resultado no coincide del todo con Spotify):")
        for cancion, r in para_revisar:
            print(f"    - {cancion.artista} - {cancion.titulo}  →  {r.candidato.url}")
    if conteo["fallo"] or conteo["pospuesta"] or conteo["sin_resultados"]:
        print("\n  Vuelve a ejecutar el mismo comando más tarde: solo se reintentan las que faltan.")


# ---------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> None:
    load_dotenv(RAIZ / ".env")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="python -m banco_audio", description="Banco de audio: Spotify → YouTube → MP3")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("playlists", help="lista tus playlists de Spotify")
    p.set_defaults(func=cmd_playlists)

    p = sub.add_parser("exportar", help="guarda una playlist de Spotify en Excel/CSV")
    p.add_argument("fuente", help="URL de la playlist o 'guardadas' (tus me gusta)")
    p.add_argument("-o", "--salida", help="archivo .xlsx o .csv (por defecto listas/<nombre>.xlsx)")
    p.set_defaults(func=cmd_exportar)

    p = sub.add_parser("descargar", help="busca las canciones y las descarga al banco de audio")
    p.add_argument("fuente", help="archivo .xlsx/.csv/.txt, URL de playlist de Spotify o 'guardadas'")
    p.add_argument("--destino", default=os.getenv("BANCO_AUDIO_DIR", str(RAIZ / "musica")),
                   help="carpeta del banco de audio (o BANCO_AUDIO_DIR en .env)")
    p.add_argument("--carpeta", help="subcarpeta dentro del banco (por defecto, el nombre de la lista)")
    p.add_argument("--sin-carpeta", action="store_true", help="guardar directamente en el destino")
    p.add_argument("--formato", choices=["mp3", "original"], default="mp3",
                   help="mp3 necesita ffmpeg; 'original' guarda el audio sin convertir (m4a/opus)")
    p.add_argument("--calidad", default="192",
                   help="kbps del MP3 (por defecto 192; el audio de YouTube no pasa de ~160)")
    p.add_argument("--tolerancia", type=int, default=15, help="segundos de diferencia aceptables con la duración original")
    p.add_argument("--estricto", action="store_true", help="no descargar resultados dudosos")
    p.add_argument("--simular", action="store_true", help="solo buscar y mostrar qué se descargaría")
    p.add_argument("--limite", type=int, help="procesar solo las primeras N canciones pendientes")
    p.add_argument("--forzar", action="store_true", help="volver a descargar aunque ya estén en el banco")
    anti = p.add_argument_group("ritmo y anti-bloqueo")
    anti.add_argument("--hilos", type=int, default=1, help="canciones en paralelo (comparten el mismo límite de ritmo)")
    anti.add_argument("--pausa", type=float, nargs=2, default=(2.0, 6.0), metavar=("MIN", "MAX"),
                      help="pausa aleatoria entre peticiones, en segundos (por defecto 2 6)")
    anti.add_argument("--limite-velocidad", help="velocidad máxima de descarga, p. ej. 2M o 500K")
    anti.add_argument("--max-bloqueos", type=int, default=3, help="bloqueos seguidos de YouTube antes de dejarlo para otra ejecución")
    anti.add_argument("--cookies-navegador", metavar="NAVEGADOR",
                      help="usar tu sesión de YouTube de firefox, edge, chrome... (reduce los bloqueos)")
    anti.add_argument("--cookies", metavar="ARCHIVO", help="archivo cookies.txt en formato Netscape")
    anti.add_argument("--proxy", help="proxy propio, p. ej. socks5://127.0.0.1:1080 (o BANCO_AUDIO_PROXY)")
    anti.add_argument("--sin-soundcloud", action="store_true", help="no usar SoundCloud como alternativa")
    p.set_defaults(func=cmd_descargar)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
