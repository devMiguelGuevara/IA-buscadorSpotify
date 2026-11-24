# IA-buscadorSpotify · MigueWamp

Reproductor de escritorio con el estilo del Winamp clásico y banco de audio personal en Python. Toma tus listas de canciones, de Spotify o de un Excel, encuentra cada canción en YouTube Music, YouTube o SoundCloud y la guarda en tu equipo con sus etiquetas.

El repositorio incluye además un lector rápido de PDF y TXT.

## Qué hace hoy

- **MigueWamp**, un reproductor de escritorio con tres skins: clásica, moderna y una cabeza flotante. Tiene ecualizador, volumen nivelado, fundido entre canciones, temporizador para dormir, biblioteca por artista y álbum, y playlists propias o importadas. Con el botón **K** muestra la letra de la canción a pantalla completa, sincronizada cuando existe.
- Pega enlaces de YouTube, YouTube Music, Spotify o SoundCloud, rutas de listas o canciones sueltas, y la biblioteca se arma mientras descarga.
- Un laboratorio opcional para analizar y mejorar el audio, cambiar la afinación y separar voz e instrumentos con IA, sin tocar nunca el original.
- Lee tus playlists de Spotify o tus "me gusta", o una lista en Excel, CSV o TXT.
- Busca cada canción y elige la versión que mejor coincide con la original.
- Descarga el audio en la mejor calidad disponible, sin recodificar, con título, artista, álbum y carátula, y lo ordena por lista.
- Recuerda lo que ya bajaste: si lo vuelves a ejecutar, solo procesa lo que falta.
- Trabaja a un ritmo prudente para no saturar a los servicios.

## Instalación rápida

Necesitas Python 3.10 o superior, ffmpeg y Deno o Node.js. La guía completa para Windows, macOS y Linux está en [docs/INSTALACION.md](docs/INSTALACION.md).

```powershell
git clone https://github.com/devMiguelGuevara/IA-buscadorSpotify.git
cd IA-buscadorSpotify
py -3.13 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Cuál ejecuto

| Archivo | Para qué | Cuándo usarlo |
|---|---|---|
| `iniciar.bat` (`iniciar.sh` en macOS y Linux) | Ejecuta el proyecto desde el código, con un menú: reproductor, descargas, playlists y más | Mientras desarrollas o pruebas cambios |
| `empaquetar.bat` | Crea la versión empaquetada en `dist\MigueWamp\` y `dist\MigueWamp.zip` | Cuando quieras una versión lista para usar o llevar a otro equipo |
| `dist\MigueWamp\MigueWamp.exe` | El reproductor empaquetado: abre sin Python ni terminal | El uso diario. Cópiale tu `.env` si usas Spotify |
| `dist\MigueWamp.zip` | El mismo paquete comprimido, con ffmpeg y Node incluidos | Para compartir: se descomprime y se abre `MigueWamp.exe`, sin instalar nada más |

El `.exe` no se actualiza solo: después de cambiar el código, vuelve a correr `empaquetar.bat`. Si algo falla al abrir, el detalle queda en `miguewamp.log`, junto al programa.

## Uso rápido

En Windows, doble clic en `iniciar.bat` y elige "Abrir el reproductor". También funciona desde la terminal:

```powershell
python -m banco_audio app
```

Desde la línea de comandos:

```powershell
# Probar sin descargar nada
python -m banco_audio descargar listas/ejemplo.xlsx --simular --limite 3

# Descargar una lista en Excel (en máxima calidad; --formato mp3 para MP3 320)
python -m banco_audio descargar listas/ejemplo.xlsx

# Actualizar yt-dlp (el motor de descargas) sin reinstalar nada
python -m banco_audio actualizar

# Bajar de nuevo en máxima calidad lo que hoy es MP3 (el MP3 viejo se guarda en _reemplazados/)
python -m banco_audio mejorar --simular --limite 3

# Con Spotify configurado: ver tus playlists, exportarlas o descargarlas
python -m banco_audio playlists
python -m banco_audio exportar https://open.spotify.com/playlist/XXXX
python -m banco_audio descargar guardadas
```

Para ver todas las opciones: `python -m banco_audio descargar -h`.

## Cómo funciona

El resumen del proceso está en [docs/COMO_FUNCIONA.md](docs/COMO_FUNCIONA.md).

## Lector rápido

```powershell
python lector/lector_rapido.py
```

Muestra un PDF o TXT palabra por palabra, con velocidad ajustable.

## A futuro

- Restauración con IA en un motor remoto, para equipos con GPU.
- Instaladores para otras máquinas.

## Aviso

Es una herramienta para tu colección personal. Respeta los derechos de autor y los términos de cada servicio. El audio no se descarga de Spotify: Spotify solo aporta las listas y los datos de cada canción.
