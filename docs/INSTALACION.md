# Manual de instalación

Guía para instalar el banco de audio en Windows, macOS o Linux. Para entender qué hace, mira [COMO_FUNCIONA.md](COMO_FUNCIONA.md).

## Requisitos

| Programa | Para qué sirve | ¿Obligatorio? |
|---|---|---|
| Python 3.10 o superior | Ejecuta el programa | Sí |
| ffmpeg | Convierte el audio a MP3 y pone la carátula | Sí, salvo con `--formato original` |
| Deno o Node.js | yt-dlp lo necesita para leer YouTube. Deno es el recomendado | Sí |
| Git | Descarga el proyecto y sus actualizaciones | Recomendado |
| App de Spotify for Developers | Leer tus playlists y tus "me gusta" | No |

## Windows

En PowerShell:

```powershell
winget install Python.Python.3.13
winget install Gyan.FFmpeg
winget install DenoLand.Deno
winget install Git.Git
```

Cierra la terminal y abre una nueva, para que reconozca los programas. Luego:

```powershell
git clone https://github.com/devMiguelGuevara/IA-buscadorSpotify.git
cd IA-buscadorSpotify
py -3.13 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Si PowerShell no deja activar el entorno porque la ejecución de scripts está deshabilitada, ejecuta esto una vez y vuelve a intentar:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## macOS

Con [Homebrew](https://brew.sh):

```bash
brew install python@3.13 ffmpeg deno git
git clone https://github.com/devMiguelGuevara/IA-buscadorSpotify.git
cd IA-buscadorSpotify
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Linux (Debian o Ubuntu)

```bash
sudo apt update
sudo apt install python3 python3-venv ffmpeg git
curl -fsSL https://deno.land/install.sh | sh
git clone https://github.com/devMiguelGuevara/IA-buscadorSpotify.git
cd IA-buscadorSpotify
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

En otras distribuciones, instala los mismos programas con su gestor de paquetes.

## Configurar el archivo `.env`

El archivo `.env` guarda tus ajustes en tu equipo y nunca se sube a GitHub. Todas las líneas son opcionales.

| Variable | Qué hace |
|---|---|
| `SPOTIPY_CLIENT_ID` y `SPOTIPY_CLIENT_SECRET` | Credenciales de tu app de Spotify |
| `SPOTIPY_REDIRECT_URI` | Dirección de retorno de Spotify. Déjala en `http://127.0.0.1:8888/callback` |
| `BANCO_AUDIO_DIR` | Carpeta donde se guarda la música. Por defecto, `musica/` |
| `FFMPEG_PATH` | Ruta a ffmpeg, solo si no está en el PATH |
| `BANCO_AUDIO_PROXY` | Un proxy propio, si usas uno |

## Conectar Spotify (opcional)

Sin Spotify puedes usar listas en Excel, CSV o TXT. Para leer tus playlists:

1. Entra a <https://developer.spotify.com/dashboard> y crea una app.
2. En *Redirect URIs* pon exactamente `http://127.0.0.1:8888/callback` y marca **Web API**.
3. Copia el *Client ID* y el *Client secret* a tu `.env`.

La primera vez que uses un comando de Spotify se abre el navegador para que lo autorices. El permiso queda guardado en `.cache-spotify`, que tampoco se sube a GitHub. No lo compartas.

## Comprobar la instalación

Con el entorno activado, prueba la lista de ejemplo sin descargar nada:

```bash
python -m banco_audio descargar listas/ejemplo.xlsx --simular --limite 1
```

Debe mostrar la canción encontrada y su duración comparada con la original.

## Mantenerlo al día

YouTube cambia a menudo y yt-dlp se actualiza para seguirle el paso. Si algo que funcionaba deja de hacerlo, actualízalo desde la ventana Descargas ("Buscar actualización") o con:

```bash
python -m banco_audio actualizar
```

Baja la versión oficial, la verifica y la usa desde el siguiente arranque. Funciona igual en la versión empaquetada, sin volver a empaquetar.

Para actualizar el proyecto completo:

```bash
git pull
pip install -r requirements.txt
```

## Problemas comunes

| Mensaje o síntoma | Solución |
|---|---|
| No se encontró ffmpeg | Instálalo y abre una terminal nueva. También puedes poner su ruta en `FFMPEG_PATH` o usar `--formato original` |
| Faltan las credenciales de Spotify | Solo hacen falta para los comandos de Spotify. Rellena el `.env` o usa una lista en Excel, CSV o TXT |
| `INVALID_CLIENT: Invalid redirect URI` | La dirección de retorno del panel de Spotify debe ser idéntica a la del `.env` |
| yt-dlp avisa que falta un intérprete de JavaScript | Instala Deno o Node.js y abre una terminal nueva |
| YouTube pide confirmar que no eres un bot, o responde 429 | El programa pausa y reintenta solo. Vuelve a ejecutar más tarde: solo procesará lo que falta. Usar las cookies de tu navegador ayuda: `--cookies-navegador firefox` |
| Falla algo que antes funcionaba | Actualiza yt-dlp |

## Abrir MigueWamp

```bash
python -m banco_audio app
```

En Windows también puedes usar `iniciar.bat`, opción 1. La ventana usa el motor web del sistema: en Windows es WebView2, que ya viene con Windows 11.

### Versión empaquetada para Windows

`empaquetar.bat` crea `dist\MigueWamp\MigueWamp.exe` y `dist\MigueWamp.zip`. El paquete incluye ffmpeg, ffprobe y Node en su carpeta `bin`, copiados del equipo donde se empaqueta. Por eso ese equipo necesita tenerlos instalados.

Quien recibe el `.zip` solo lo descomprime y abre `MigueWamp.exe`. No necesita instalar Python, ffmpeg ni Node. Solo necesita WebView2, que ya viene con Windows 11. Si usa Spotify, pone su `.env` junto al `.exe`.

Si algo falla al abrir, el detalle queda en `miguewamp.log`, junto al programa.

### Laboratorio de mejora (opcional)

Con ffmpeg ya funciona el nivel básico: sonoridad, ecualización, compresor, ruido, declip, declick, ancho estéreo, afinación y limitador. Para el nivel Mejora, que ocupa unos 200 MB y corre solo en CPU:

```bash
pip install -r requirements-mejora.txt
```

Agrega la afinación de referencia, el tempo y la tonalidad en el análisis, la masterización con una canción de referencia y un segundo motor de afinación.

Para el nivel IA, que separa voz, batería, bajo y resto y permite afinar por instrumento (unos 1,2 GB, funciona solo con CPU):

```bash
pip install -r requirements-ia.txt
```

La primera separación baja el modelo, de unos 80 MB. En un equipo de escritorio común tarda más o menos lo que dura la canción; después, elegir otra pista de la misma canción es inmediato.

El laboratorio muestra qué tiene disponible tu equipo y el comando para lo que falte. En la versión empaquetada (`.exe`), los niveles Mejora e IA se instalan con el botón del laboratorio: quedan en la carpeta `complementos`, junto al programa.
