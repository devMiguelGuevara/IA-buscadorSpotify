# IA-buscadorSpotify

Herramientas personales en Python:

| Carpeta | Qué hace |
|---|---|
| `banco_audio/` | Saca tus canciones de Spotify, las busca en YouTube Music / YouTube / SoundCloud y las descarga en MP3 a tu banco de audio. |
| `listas/` | Tus listas de canciones en Excel (entrada del banco de audio). |
| `lector/` | Lector rápido: muestra un PDF o TXT palabra por palabra. |

## Instalación

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
winget install Gyan.FFmpeg      # necesario para convertir a MP3 (si no queda en el PATH, pon FFMPEG_PATH en .env)
copy .env.example .env          # y rellena las credenciales de Spotify
```

yt-dlp necesita un intérprete de JavaScript para YouTube: usa **Node.js** (ya instalado) o Deno.

---

## Banco de audio

### 1. Crear la app de Spotify (una sola vez)

1. Entra a <https://developer.spotify.com/dashboard> → **Create app**.
2. En *Redirect URIs* pon exactamente `http://127.0.0.1:8888/callback`
   (Spotify ya no acepta `localhost`) y marca **Web API**.
3. Copia *Client ID* y *Client secret* a tu `.env`.

La primera vez que uses un comando de Spotify se abrirá el navegador para autorizar;
el token queda guardado en `.cache-spotify`.

### 2. Comandos

```powershell
# Ver tus playlists con sus URLs
python -m banco_audio playlists

# Guardar una playlist (o tus "me gusta") en Excel
python -m banco_audio exportar https://open.spotify.com/playlist/XXXX
python -m banco_audio exportar guardadas -o listas/MeGusta.xlsx

# Descargar al banco: desde un Excel, una playlist o tus "me gusta"
python -m banco_audio descargar listas/CancionesDancehall.xlsx
python -m banco_audio descargar https://open.spotify.com/playlist/XXXX
python -m banco_audio descargar guardadas

# Probar primero sin descargar nada (muestra qué video elegiría)
python -m banco_audio descargar listas/CancionesDancehall.xlsx --simular --limite 10
```

Las listas en Excel pueden tener el formato antiguo (`Título - Artista - Álbum - 3:42` en una
celda) o columnas `Título / Artista / Álbum / Duración`. También lee CSV de
[Exportify](https://exportify.net) y TXT (una canción por línea).

### 3. Cómo elige la canción correcta

Cada resultado recibe un puntaje según coincidencia de título y artista, **duración frente a la
de Spotify** (±15 s por defecto), mismo álbum y palabras sospechosas (`live`, `cover`, `remix`,
`sped up`, `8d`…) que no estén en el título original. Si el mejor resultado no convence, se
descarga igual pero aparece en el resumen como **⚠ revisar** (usa `--estricto` para no
descargarlo).

### 4. Anti-bloqueo: varios métodos y ritmo controlado

- **Búsqueda en cascada:** YouTube Music (`ytmusicapi`, audio oficial) → búsqueda de YouTube
  (`yt-dlp`) → SoundCloud. Solo pasa a la siguiente fuente si la anterior no da un buen resultado.
- **Varios clientes de YouTube:** si la descarga falla con uno (formato no disponible, 403…),
  prueba otros (`web_embedded`, `android_vr`, `tv_simply`, `mweb`) y luego el siguiente candidato.
- **Limitador compartido:** pausa aleatoria entre peticiones (`--pausa 2 6`) aunque uses varios
  `--hilos`, reintentos con espera creciente y `--limite-velocidad 2M` opcional.
- **Enfriamiento ante bloqueos:** si YouTube responde 429 o "confirma que no eres un bot", espera
  1, 2, 4… minutos. Tras `--max-bloqueos` seguidos deja YouTube en paz, sigue con SoundCloud y
  marca el resto como *pospuestas*.
- **No bloqueante:** un fallo nunca detiene el lote. El registro (`registro_descargas.json` en
  el banco) guarda el avance: vuelve a ejecutar el mismo comando y solo se procesan las que faltan.
- **Cookies de tu sesión** (reducen mucho los bloqueos): `--cookies-navegador firefox`
  (en Windows, Chrome/Edge cifran sus cookies y yt-dlp a veces no puede leerlas; Firefox sí)
  o `--cookies cookies.txt`.
- `--proxy` para usar tu propio proxy/VPN.

Otras opciones: `--destino`, `--carpeta`, `--formato original` (sin ffmpeg, guarda m4a/opus),
`--calidad 192`, `--forzar`. Ver todas con `python -m banco_audio descargar -h`.

> Úsalo para tu colección personal y respeta los derechos de autor y los términos de cada servicio.

---

## Lector rápido

```powershell
python lector/lector_rapido.py
```

Técnicas: *punto focal* (letra de reconocimiento en rojo), *negrita inicio*, *negrita final*.
Pausa automática más larga en signos de puntuación.

Atajos: `Espacio` play/pausa · `←` `→` línea anterior/siguiente · `↑` `↓` velocidad ·
`Ctrl+O` abrir · `Inicio` volver al principio.
