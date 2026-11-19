"""Modelo de canción y utilidades de texto compartidas."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Sufijos que Spotify añade al nombre del álbum y que llevan " - " dentro,
# p. ej. "Whine & Kotch - Single". Se vuelven a unir al álbum al parsear.
_SUFIJOS_ALBUM = {"single", "ep", "edición especial", "deluxe edition", "remastered"}

_RE_DURACION = re.compile(r"^(\d{1,2}):([0-5]\d)$")
_RE_NUMERO_INICIAL = re.compile(r"^\d+[\s.)-]+")


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos; útil para comparar textos."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9ñ]+", " ", texto).strip()


def duracion_a_segundos(texto: str) -> int | None:
    m = _RE_DURACION.match(texto.strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def segundos_a_duracion(segundos: int | None) -> str:
    if segundos is None:
        return ""
    return f"{segundos // 60}:{segundos % 60:02d}"


@dataclass
class Cancion:
    titulo: str
    artista: str
    album: str = ""
    duracion: int | None = None  # en segundos
    spotify_id: str = ""

    @property
    def clave(self) -> str:
        """Identificador estable para el registro de descargas."""
        artista_principal = self.artista.split(",")[0]
        return f"{normalizar(artista_principal)} - {normalizar(self.titulo)}"

    @property
    def consulta(self) -> str:
        """Texto que se usa para buscar la canción en YouTube."""
        return f"{self.artista} - {self.titulo}"

    def a_texto(self) -> str:
        """Formato "Título - Artista - Álbum - m:ss" (el de las listas en Excel)."""
        partes = [self.titulo, self.artista, self.album, segundos_a_duracion(self.duracion)]
        return " - ".join(p for p in partes if p)

    @classmethod
    def desde_texto(cls, texto: str) -> Cancion | None:
        """Interpreta una línea tipo "12 Título - Artista - Álbum - 3:42".

        El formato es ambiguo cuando el título o el álbum contienen " - ", así
        que se asume: el último bloque es la duración, el penúltimo el álbum,
        el anterior el artista y todo lo demás el título.
        """
        texto = _RE_NUMERO_INICIAL.sub("", str(texto).strip())
        partes = [p.strip() for p in texto.split(" - ")]
        if not texto:
            return None

        duracion = duracion_a_segundos(partes[-1])
        if duracion is not None:
            partes.pop()

        if len(partes) >= 3 and partes[-1].lower() in _SUFIJOS_ALBUM:
            sufijo = partes.pop()
            partes[-1] = f"{partes[-1]} - {sufijo}"

        if len(partes) >= 3:
            return cls(" - ".join(partes[:-2]), partes[-2], partes[-1], duracion)
        if len(partes) == 2:
            return cls(partes[0], partes[1], "", duracion)
        return cls(partes[0], "", "", duracion)
