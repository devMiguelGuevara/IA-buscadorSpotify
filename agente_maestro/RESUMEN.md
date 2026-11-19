# IA-buscadorSpottify · Agente maestro

> Banco de audio personal: saca tus canciones de Spotify, las encuentra en YouTube Music / YouTube / SoundCloud y las descarga en MP3. Incluye además un lector rápido de PDF/TXT.

## Qué hace

### 1. Banco de audio (`banco_audio/`)

1. Lee canciones de tu cuenta de Spotify (playlists o "Tus me gusta") o de una lista en Excel/CSV/TXT.
2. Busca cada una en cascada: YouTube Music → YouTube → SoundCloud.
3. Elige el mejor resultado con un puntaje (título, artista, duración ±15 s frente a Spotify, álbum, y penaliza `live`, `cover`, `remix`, `sped up`…).
4. Descarga y convierte a MP3 con etiquetas (ffmpeg + mutagen).
5. Lleva un registro (`registro_descargas.json`) para no repetir descargas y poder reanudar.

Tiene protección anti-bloqueo: pausas aleatorias, reintentos con espera creciente, varios clientes de YouTube, enfriamiento ante errores 429 y uso opcional de cookies o proxy.

### 2. Lector rápido (`lector/lector_rapido.py`)

Muestra un PDF o TXT palabra por palabra (lectura rápida) con punto focal en rojo o negritas, velocidad ajustable y pausas en la puntuación.

## Estado

**Activo y funcional.** Última modificación: 10-sep-2026. Ya hay unas 230 canciones descargadas en `musica/` (listas *CancionesDancehall* y *CancionesFavoritasSpotify_busar*).

Repositorio público: https://github.com/devMiguelGuevara/IA-buscadorSpotify. La carpeta local conserva el nombre `IA-buscadorSpottify`.

## Cómo se usa

```powershell
.\.venv\Scripts\activate
python -m banco_audio playlists                                   # ver tus playlists
python -m banco_audio exportar <url_playlist | guardadas> -o listas/X.xlsx
python -m banco_audio descargar listas/CancionesDancehall.xlsx     # descargar
python -m banco_audio descargar <...> --simular --limite 10       # probar sin descargar
python lector/lector_rapido.py
```

El `README.md` del proyecto explica la instalación, la app de Spotify y todas las opciones.

## Archivos clave

| Archivo | Función |
|---|---|
| `banco_audio/__main__.py` | CLI: `playlists`, `exportar`, `descargar` |
| `banco_audio/spotify.py` | Acceso a Spotify (spotipy, OAuth) |
| `banco_audio/descargador.py` | Búsqueda en cascada, puntaje y descarga con yt-dlp |
| `banco_audio/limitador.py` | Control de ritmo compartido entre hilos |
| `banco_audio/listas.py` | Lectura/escritura de listas (Excel, CSV de Exportify, TXT) |
| `banco_audio/registro.py` | Registro de lo ya descargado |
| `banco_audio/cancion.py` | Modelo de canción y normalización de texto |
| `lector/lector_rapido.py` | Lector rápido (Tkinter) |
| `listas/` | Listas de entrada en Excel |
| `musica/` | Banco de audio descargado (ignorado por git) |
| `.env` | Credenciales de Spotify y ruta de ffmpeg (ignorado por git) |

## Dependencias

`spotipy`, `yt-dlp`, `ytmusicapi`, `mutagen`, `openpyxl`, `python-dotenv`, `pypdf`. Externas: **ffmpeg** y **Node.js** (yt-dlp lo usa para YouTube). Python 3.13 en `.venv`.

## Antecedentes

En `../Notas sueltas/` están la versión manual previa: el script de consola para copiar canciones de Spotify (`ScrapearMisCanciones.txt`), su resultado (`CancionesSpotify.txt`) y el comando de yt-dlp (`DescargarYoutube.txt`).

## Observaciones y pendientes

- El `.gitignore` protege `.env`, `.cache-spotify`, cookies, `musica/` y `.vscode/`.
- La carpeta local tiene una errata ("Spottify"); el repositorio de GitHub ya usa "Spotify".
- El lector rápido no tiene relación con la música; podría vivir como proyecto aparte.

## Reglas para el agente

- **Nunca** mostrar ni subir el contenido de `.env`, `.cache-spotify` ni archivos `cookies*.txt`.
- Probar cambios del descargador con `--simular --limite N` antes de lanzar descargas reales, para no provocar bloqueos de YouTube.
- Uso personal: respetar derechos de autor y términos de cada servicio.
