"""Línea de comandos del banco de audio.

    python -m banco_audio playlists
    python -m banco_audio exportar <playlist | guardadas> [-o listas/archivo.xlsx]
    python -m banco_audio descargar <archivo | enlace de Spotify/YouTube/SoundCloud | guardadas> [opciones]
    python -m banco_audio mejorar      (re-descarga en máxima calidad lo que hoy es MP3)
    python -m banco_audio actualizar   (yt-dlp a su última versión, verificada)
    python -m banco_audio app          (el reproductor MigueWamp)
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from .cancion import Cancion, segundos_a_duracion
from .descargador import FORMATOS, METODOS, Descargador, Opciones, Resultado
from .fuentes import FuenteInvalida, cargar_fuente as cargar
from .limitador import Limitador
from .listas import guardar_lista
from .lote import ejecutar, escribir_lista, mejorar_banco, para_mejorar, planificar
from .registro import Registro
from .spotify import RAIZ, cliente, mis_playlists, obtener_canciones


def cargar_fuente(fuente: str) -> tuple[str, list[Cancion]]:
    try:
        return cargar(fuente)
    except FuenteInvalida as e:
        raise SystemExit(str(e)) from e


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
    plan = planificar(canciones, registro, forzar=args.forzar, limite=args.limite)

    print(f"«{nombre_lista}»: {len(canciones)} canciones, {plan.ya_estaban} ya en el banco, {len(plan.pendientes)} por procesar.")
    print(f"Destino: {carpeta}" + ("   (modo simulación: no se descarga nada)" if args.simular else ""))
    nombre_m3u = args.carpeta or nombre_lista
    if plan.pendientes:
        balance = ejecutar(
            Descargador(_opciones(args, destino), Limitador(*args.pausa)), plan.pendientes, carpeta,
            registro=registro, destino=destino, simular=args.simular, hilos=args.hilos,
            al_resultado=lambda i, total, c, r: print(_linea(i, total, c, r), flush=True),
            al_interrumpir=lambda: print("\nInterrumpido: terminando las descargas en curso...", flush=True),
        )
        _resumen(balance.conteo, balance.para_revisar, plan.ya_estaban)
    # La lista referencia todo lo suyo que está en el banco, también lo bajado por otra lista.
    if not args.simular and (n := escribir_lista(nombre_m3u, canciones, registro, destino)):
        print(f"\nLista «{nombre_m3u}» guardada en playlists/ ({n} canciones).")


def cmd_mejorar(args) -> None:
    destino = Path(args.destino).expanduser()
    registro = Registro(destino / "registro_descargas.json")
    candidatas = para_mejorar(registro, destino)
    total = min(len(candidatas), args.limite or len(candidatas))
    print(f"{len(candidatas)} canciones en MP3 con su enlace guardado; se procesan {total}.")
    print("Cada una se baja en su formato original; el MP3 viejo pasa a _reemplazados/ tras verificarla."
          + ("   (modo simulación)" if args.simular else ""))
    if not total:
        return
    args.formato, args.metodo = "original", "auto"
    descargador = Descargador(_opciones(args, destino), Limitador(*args.pausa))
    try:
        conteo = mejorar_banco(descargador, registro, destino, limite=args.limite, simular=args.simular,
                               al_resultado=lambda i, t, c, r: print(_linea(i, t, c, r), flush=True))
    except KeyboardInterrupt:
        descargador.detener.set()
        print("\nInterrumpido.")
        return
    _resumen(conteo, [], 0)


def _opciones(args, destino: Path) -> Opciones:
    return Opciones(
        destino=destino,
        formato=args.formato,
        metodo=args.metodo,
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
        recordar=not args.sin_memoria,
    )


def cmd_actualizar(_args) -> None:
    from .actualizador import ErrorActualizacion, actualizar, hay_nueva
    try:
        e = hay_nueva()
        print(f"yt-dlp en uso: {e['version']}" + (f" (ya bajada: {e['pendiente']})" if e["pendiente"] else "")
              + f"  ·  última: {e['ultima']}")
        if not e["hay_nueva"]:
            print("Está al día.")
            return
        r = actualizar()
    except ErrorActualizacion as err:
        raise SystemExit(str(err)) from err
    print(f"yt-dlp {r['version']} instalada y verificada (SHA-256). Se usa desde la próxima ejecución.")


def cmd_app(args) -> None:
    from .app.ventana import lanzar
    lanzar(Path(args.destino).expanduser(), navegador=args.navegador, puerto=args.puerto)


def _linea(i: int, total: int, cancion: Cancion, r: Resultado) -> str:
    iconos = {"ok": "✓", "simulado": "→", "sin_resultados": "✗", "fallo": "✗", "pospuesta": "…"}
    base = f"[{i}/{total}] {iconos.get(r.estado, '?')} {cancion.artista} - {cancion.titulo}"
    if r.candidato:
        c = r.candidato
        dur = f"{segundos_a_duracion(c.duracion)} vs {segundos_a_duracion(cancion.duracion)}" if c.duracion else "?"
        base += f"\n        {c.fuente}: «{c.titulo}» ({dur})"
        if r.calidad:
            q = r.calidad
            base += f"  [{q.get('codec') or '?'} {q.get('kbps') or '?'} kbps {q.get('khz') or '?'} kHz]"
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


def _opciones_comunes(p: argparse.ArgumentParser) -> None:
    """Opciones que comparten 'descargar' y 'mejorar'."""
    p.add_argument("--destino", default=os.getenv("BANCO_AUDIO_DIR", str(RAIZ / "musica")),
                   help="carpeta del banco de audio (o BANCO_AUDIO_DIR en .env)")
    p.add_argument("--calidad", default="320", help="kbps del MP3 (por defecto 320)")
    p.add_argument("--tolerancia", type=int, default=15, help="segundos de diferencia aceptables con la duración original")
    p.add_argument("--estricto", action="store_true", help="no descargar resultados dudosos")
    p.add_argument("--simular", action="store_true", help="solo buscar y mostrar qué se haría")
    p.add_argument("--sin-memoria", action="store_true", help="buscar de nuevo, sin usar la memoria de búsquedas")
    p.add_argument("--limite", type=int, help="procesar solo las primeras N canciones pendientes")
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
    p.add_argument("--carpeta", help="subcarpeta dentro del banco (por defecto, el nombre de la lista)")
    p.add_argument("--sin-carpeta", action="store_true", help="guardar directamente en el destino")
    p.add_argument("--formato", choices=FORMATOS, default="original",
                   help="original (por defecto): el mejor audio tal cual, sin recodificar; mp3: compatibilidad")
    p.add_argument("--metodo", choices=list(METODOS), default="auto",
                   help="auto (YouTube Music, YouTube y SoundCloud en cascada) o una sola fuente")
    p.add_argument("--forzar", action="store_true", help="volver a descargar aunque ya estén en el banco")
    _opciones_comunes(p)
    p.set_defaults(func=cmd_descargar)

    p = sub.add_parser("mejorar", help="re-descarga en máxima calidad las canciones del banco que son MP3")
    _opciones_comunes(p)
    p.set_defaults(func=cmd_mejorar)

    p = sub.add_parser("actualizar", help="actualiza yt-dlp (el motor de descargas) a su última versión")
    p.set_defaults(func=cmd_actualizar)

    p = sub.add_parser("app", help="abre el reproductor estilo Winamp con la biblioteca")
    p.add_argument("--destino", default=os.getenv("BANCO_AUDIO_DIR", str(RAIZ / "musica")),
                   help="carpeta del banco de audio (o BANCO_AUDIO_DIR en .env)")
    p.add_argument("--navegador", action="store_true", help="abrir en el navegador en vez de la ventana")
    p.add_argument("--puerto", type=int, default=0, help="puerto del servicio interno (por defecto, uno libre)")
    p.set_defaults(func=cmd_app)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
