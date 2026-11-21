# IA-buscadorSpottify · Agente maestro

> Banco de audio personal: saca tus canciones de Spotify o de una lista en Excel, las encuentra en YouTube Music, YouTube o SoundCloud y las descarga con sus etiquetas. Incluye además un lector rápido de PDF y TXT.

## Qué hace

### 1. Banco de audio (`banco_audio/`)

1. Lee canciones de Spotify, como playlists o "Tus me gusta", o de una lista en Excel, CSV o TXT.
2. Busca cada una en YouTube Music, YouTube y SoundCloud, en ese orden.
3. Elige la versión que mejor coincide con la original.
4. Descarga el audio con etiquetas y carátula.
5. Lleva un registro para no repetir descargas y poder reanudar.

### 2. Lector rápido (`lector/lector_rapido.py`)

Muestra un PDF o TXT palabra por palabra, con velocidad ajustable.

## Estado

**Activo y funcional.** Ya es MigueWamp: reproductor de escritorio estilo Winamp con 3 skins (la "Cabeza" en vectores, con forma de ventana real), biblioteca con carpetas y playlists, descargas en máxima calidad con varios métodos (Fase 2), y laboratorio de mejora y afinación (niveles Base y Mejora: librosa, Pedalboard, Matchering). Se empaqueta como `.exe` y `.zip` portátil (incluye ffmpeg y Node) con `empaquetar.bat`. Fase 7 hecha: yt-dlp actualizable, memoria de búsquedas, volumen nivelado, fundido y temporizador, artistas y álbumes, importar .m3u/.pls y formatos APE/WMA/WV/AIFF/MPC/TTA/AC3. Siguiente: IA (8), instalación (9) y Rust (10).

Repositorio público: https://github.com/devMiguelGuevara/IA-buscadorSpotify. La carpeta local conserva el nombre `IA-buscadorSpottify`.

## Cómo se usa

```powershell
.\.venv\Scripts\activate
python -m banco_audio playlists
python -m banco_audio exportar <url_playlist | guardadas> -o listas/X.xlsx
python -m banco_audio descargar listas/ejemplo.xlsx --simular --limite 3
python -m banco_audio descargar <lista | url_playlist | guardadas>
python lector/lector_rapido.py
```

La instalación completa está en `docs/INSTALACION.md`.

## Archivos clave

| Archivo | Función |
|---|---|
| `banco_audio/` | Código del banco de audio y su CLI |
| `banco_audio/app/` | Ventanas (pywebview) y servicio interno (FastAPI) de MigueWamp |
| `banco_audio/mejora/` | Laboratorio: capacidades, análisis, motores y control de calidad |
| `web/` | Interfaz (Vue 3 + Vite). `npm run build` la deja en `banco_audio/app/static/` |
| `iniciar.bat`, `empaquetar.bat` | Lanzador con menú y empaquetado del `.exe` |
| `lector/lector_rapido.py` | Lector rápido con Tkinter |
| `listas/ejemplo.xlsx` | Lista de ejemplo. Las listas personales no se suben |
| `docs/INSTALACION.md` | Manual de instalación, público |
| `docs/COMO_FUNCIONA.md` | Resumen de cómo funciona, público |
| `privado/MANUAL_DETALLADO.md` | Detalle técnico, estado del banco y hoja de ruta. Solo local, ignorado por git |
| `musica/` | Banco de audio descargado, ignorado por git |
| `.env` | Credenciales y ajustes, ignorado por git |

## Dependencias

`spotipy`, `yt-dlp[default]`, `ytmusicapi`, `mutagen`, `openpyxl`, `python-dotenv`, `fastapi`, `uvicorn`, `pywebview` y `pypdf`. Para empaquetar: `pyinstaller` y `pillow`. Para compilar la interfaz: Node. Externas: **ffmpeg** y **Deno o Node.js**, que yt-dlp usa para YouTube. Python 3.10 o superior.

## Observaciones y pendientes

- El detalle técnico y la hoja de ruta por fases están en `privado/MANUAL_DETALLADO.md`.
- La carpeta local tiene una errata ("Spottify"); el repositorio de GitHub ya usa "Spotify".
- El lector rápido no tiene relación con la música; podría vivir como proyecto aparte.

## Reglas para el agente

- **Nunca** mostrar ni subir el contenido de `.env`, `.cache-spotify` ni archivos `cookies*.txt`.
- Probar cambios del descargador con `--simular --limite N` antes de lanzar descargas reales, para no provocar bloqueos de YouTube.
- Lo público, que es el README, `docs/` y este resumen, queda general. El detalle va a `privado/MANUAL_DETALLADO.md`.
- Trabajar solo dentro de esta carpeta.
- Commits sin atribución de Claude, y push solo cuando lo pida el usuario.
- Uso personal: respetar derechos de autor y términos de cada servicio.
