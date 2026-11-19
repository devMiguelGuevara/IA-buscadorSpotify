"""Sacar canciones de tu cuenta de Spotify (playlists y "Tus me gusta")."""

from __future__ import annotations

import os
import re
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .cancion import Cancion

RAIZ = Path(__file__).resolve().parent.parent
PERMISOS = "user-library-read playlist-read-private playlist-read-collaborative"
# Spotify ya no acepta "localhost" como redirect URI; debe ser la IP de loopback.
REDIRECT_URI_POR_DEFECTO = "http://127.0.0.1:8888/callback"

_RE_PLAYLIST = re.compile(r"(?:open\.spotify\.com/(?:intl-[a-z]+/)?playlist/|spotify:playlist:)([A-Za-z0-9]+)")
PALABRAS_GUARDADAS = {"guardadas", "me-gusta", "megusta", "liked", "favoritas"}


def es_fuente_spotify(fuente: str) -> bool:
    return fuente.lower() in PALABRAS_GUARDADAS or bool(_RE_PLAYLIST.search(fuente))


def cliente() -> spotipy.Spotify:
    if not (os.getenv("SPOTIPY_CLIENT_ID") and os.getenv("SPOTIPY_CLIENT_SECRET")):
        raise SystemExit(
            "Faltan las credenciales de Spotify. Copia .env.example a .env y rellena "
            "SPOTIPY_CLIENT_ID y SPOTIPY_CLIENT_SECRET (ver README)."
        )
    autenticacion = SpotifyOAuth(
        scope=PERMISOS,
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", REDIRECT_URI_POR_DEFECTO),
        cache_path=str(RAIZ / ".cache-spotify"),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=autenticacion, retries=5, status_retries=5, backoff_factor=0.5)


def _paginar(sp: spotipy.Spotify, pagina: dict):
    while pagina:
        yield from pagina["items"]
        pagina = sp.next(pagina) if pagina.get("next") else None


def mis_playlists(sp: spotipy.Spotify) -> list[dict]:
    return [
        {
            "nombre": p["name"],
            "id": p["id"],
            "canciones": (p.get("items") or p.get("tracks") or {}).get("total", "?"),
            "dueno": p["owner"].get("display_name") or p["owner"]["id"],
        }
        for p in _paginar(sp, sp.current_user_playlists(limit=50))
        if p
    ]


def _a_cancion(pista: dict | None) -> Cancion | None:
    if not pista or pista.get("type", "track") != "track" or not pista.get("name"):
        return None
    return Cancion(
        titulo=pista["name"],
        artista=", ".join(a["name"] for a in pista.get("artists", []) if a.get("name")),
        album=(pista.get("album") or {}).get("name", ""),
        duracion=round(pista["duration_ms"] / 1000) if pista.get("duration_ms") else None,
        spotify_id=pista.get("id") or "",
    )


def obtener_canciones(sp: spotipy.Spotify, fuente: str) -> tuple[str, list[Cancion]]:
    """Devuelve (nombre de la lista, canciones) para una playlist o tus guardadas."""
    if fuente.lower() in PALABRAS_GUARDADAS:
        nombre = "Tus me gusta"
        entradas = _paginar(sp, sp.current_user_saved_tracks(limit=50))
    else:
        playlist_id = _RE_PLAYLIST.search(fuente).group(1)
        nombre = sp.playlist(playlist_id, fields="name")["name"]
        entradas = _paginar(sp, sp.playlist_items(playlist_id, limit=50, additional_types=("track",)))

    canciones = []
    for entrada in entradas:
        # Spotify renombró "track" a "item" en las respuestas de playlists; se aceptan ambos.
        if cancion := _a_cancion(entrada.get("item") or entrada.get("track")):
            canciones.append(cancion)
    return nombre, canciones
