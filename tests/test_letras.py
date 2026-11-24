"""Letras: limpieza, formato LRC, elección del resultado y caché (sin red)."""

import pytest

from banco_audio import letras as L


@pytest.mark.parametrize("sucio, limpio", [
    ("Si Tu No Estas Aqui - Angeles Del Infierno (Live TV)", "Si Tu No Estas Aqui - Angeles Del Infierno"),
    ("Despacito (Official Music Video) ft. Daddy Yankee", "Despacito"),
    ("Bohemian Rhapsody [Remastered 2011] | Queen", "Bohemian Rhapsody"),
    ("Vestido De Cristal, Kraken - Video", "Vestido De Cristal, Kraken"),
    ("Video Killed the Radio Star", "Video Killed the Radio Star"),  # «Video» es parte del nombre
    ("Mãe Sereia 🌊", "Mãe Sereia"),
])
def test_limpiar_titulo(sucio, limpio):
    assert L.limpiar_titulo(sucio) == limpio


def test_limpiar_artista_y_coincidencia():
    assert L.limpiar_artista("Angeles del Infierno - Topic") == "Angeles del Infierno"
    assert L.limpiar_artista("QueenVEVO") == "Queen"
    assert L.coincide_artista("Ángeles del Infierno", "Angeles Del Infierno")
    assert L.coincide_artista("Iron Maiden feat. X", "Iron Maiden")
    assert not L.coincide_artista("Mägo de Oz", "Angeles del Infierno")


def test_lrc_ida_y_vuelta():
    lineas = L.leer_lrc("[ar:Queen]\n[00:12.50]Hola\n[00:05.00][00:30.1]Coro\n[offset:+500]\n")
    assert lineas == [[4.5, "Coro"], [12.0, "Hola"], [29.6, "Coro"]]
    assert L.leer_lrc(L.escribir_lrc(lineas)) == lineas
    texto = L.leer_lrc("\nPrimera\n\nSegunda\n\n")
    assert texto == [[None, "Primera"], [None, ""], [None, "Segunda"]]


def _registro(nombre, artista, duracion, sincronizada=True, texto="Hola"):
    return {"trackName": nombre, "artistName": artista, "duration": duracion,
            "syncedLyrics": f"[00:01.00]{texto}" if sincronizada else None, "plainLyrics": texto}


def test_elige_artista_correcto_y_sincronizada(monkeypatch):
    respuestas = {
        "get": None,
        "search": [_registro("Si Tú No Estás Aquí", "Mägo de Oz", 240, texto="otra"),
                   _registro("Si Tú No Estás Aquí", "Ángeles del Infierno", 250, sincronizada=False, texto="sin tiempos"),
                   _registro("Si Tú No Estás Aquí", "Ángeles del Infierno", 251, texto="la buena")],
    }
    monkeypatch.setattr(L, "_pedir", lambda ruta, parametros: respuestas[ruta])
    lineas = L.buscar_lrclib("Si Tu No Estas Aqui", "Angeles del Infierno", duracion=252)
    assert lineas == [[1.0, "la buena"]]


def test_sin_coincidencia_no_inventa(monkeypatch):
    monkeypatch.setattr(L, "_pedir", lambda ruta, parametros: [_registro("Otra", "Otro artista", 100)] if ruta == "search" else None)
    assert L.buscar_lrclib("Mi canción", "Mi artista", duracion=300) is None


def test_obtener_guarda_una_vez_y_anota_las_que_faltan(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "SIN_RESULTADO", tmp_path / "sin.json")
    monkeypatch.setattr(L, "CACHE", tmp_path / "cache")
    llamadas = []
    monkeypatch.setattr(L, "buscar_lrclib", lambda *a, **k: llamadas.append(a) or [[1.0, "Hola"]])
    monkeypatch.setattr(L, "buscar_youtube_music", lambda *a, **k: None)
    cancion = tmp_path / "Queen - Algo.mp3"
    cancion.write_bytes(b"")
    assert L.obtener(cancion, "Queen", "Algo", 200)["tipo"] == "sincronizada"
    assert (tmp_path / "Queen - Algo.lrc").read_text(encoding="utf-8") == "[00:01.00]Hola\n"
    assert L.obtener(cancion, "Queen", "Algo", 200)["fuente"] == "guardada"
    assert len(llamadas) == 1  # la segunda vez no sale a internet

    monkeypatch.setattr(L, "buscar_lrclib", lambda *a, **k: llamadas.append(a) or None)
    otra = tmp_path / "Nadie - Nada.mp3"
    otra.write_bytes(b"")
    assert L.obtener(otra, "Nadie", "Nada", 100)["tipo"] == "ninguna"
    assert L.obtener(otra, "Nadie", "Nada", 100)["tipo"] == "ninguna"
    assert len(llamadas) == 2  # la que no se encontró no se busca otra vez enseguida
    L.obtener(otra, "Nadie", "Nada", 100, forzar=True)
    assert len(llamadas) == 3  # «Buscar de nuevo» sí sale


def test_id_de_video():
    assert L._id_video("https://music.youtube.com/watch?v=fJ9rUzIMcZQ&si=x") == "fJ9rUzIMcZQ"
    assert L._id_video("https://youtu.be/fJ9rUzIMcZQ") == "fJ9rUzIMcZQ"
    assert L._id_video("https://soundcloud.com/a/b") == ""
