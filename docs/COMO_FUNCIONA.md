# Cómo funciona

Resumen general del banco de audio. Para instalarlo, mira [INSTALACION.md](INSTALACION.md).

## El proceso en cinco pasos

1. **Lee tu lista.** Puede venir de Spotify, como una playlist o tus "me gusta", o de un archivo Excel, CSV o TXT.
2. **Busca cada canción.** Empieza por YouTube Music, que suele tener el audio oficial. Si no encuentra una buena coincidencia, sigue con YouTube y luego con SoundCloud.
3. **Elige la versión correcta.** Compara título, artista, álbum y duración con los datos de la lista. Evita versiones en vivo, covers, remixes y parecidas, salvo que la original también lo sea.
4. **Descarga y etiqueta.** Guarda el audio con título, artista, álbum y carátula.
5. **Anota lo que hizo.** Un registro guarda lo descargado, así la siguiente ejecución solo procesa lo que falta.

## Qué listas acepta

| Fuente | Cómo se indica |
|---|---|
| Playlist de Spotify | Su enlace, por ejemplo `https://open.spotify.com/playlist/...` |
| Tus "me gusta" de Spotify | La palabra `guardadas` |
| Excel | Columnas Título, Artista, Álbum y Duración, o una canción por celda |
| CSV | Por ejemplo, el que genera [Exportify](https://exportify.net) |
| TXT | Una canción por línea: `Título - Artista - Álbum - 3:42` |

La lista de ejemplo `listas/ejemplo.xlsx` muestra el formato de columnas.

## Calidad

- **Por defecto guarda la máxima calidad:** el mejor audio que ofrece la fuente, tal cual, sin convertirlo. En YouTube suele ser Opus de unos 130 a 160 kbps. Le pone carátula y etiquetas.
- **MP3 a 320 kbps:** queda como opción para equipos que no leen Opus o M4A. Convertir no mejora el sonido.
- **Calidad visible:** cada descarga registra su códec, kbps y kHz.
- **Mejorar el banco:** lo que bajaste antes en MP3 se puede bajar de nuevo en máxima calidad. El MP3 viejo no se borra: se guarda en `_reemplazados/`.
- **Si una coincidencia no convence del todo,** la descarga igual pero la marca para revisar al final. Con `--estricto` no la descarga.

## Métodos de búsqueda

| Método | Qué hace |
|---|---|
| Automático | YouTube Music, luego YouTube y luego SoundCloud, hasta encontrar una buena coincidencia |
| Solo YouTube Music, solo YouTube o solo SoundCloud | Busca en una sola fuente |

Si la canción viene de Spotify, primero busca la grabación exacta por su código ISRC. Un enlace pegado se descarga directo, sin buscar.

Cada lista descargada queda también como playlist, con todas sus canciones, incluso las que ya estaban por otra lista. Así una canción repetida se baja una sola vez.

## Cuidado con los servicios

El programa espera entre una petición y otra. Si un servicio pide bajar el ritmo, se detiene un rato, reintenta y deja para la siguiente ejecución lo que no pudo bajar. Un fallo nunca detiene el resto de la lista.

## Qué guarda y dónde

| Carpeta o archivo | Qué contiene |
|---|---|
| `listas/` | Tus listas de entrada. En GitHub solo está la de ejemplo |
| `musica/<lista>/` | Las canciones descargadas, una carpeta por lista. Puedes cambiar la carpeta en el `.env` |
| `musica/registro_descargas.json` | Lo que ya se descargó |
| `musica/memoria_busquedas.json` | Las búsquedas recientes, para no repetirlas al reintentar |
| `cache/` | Medidas de volumen y copias para escuchar formatos como APE o WMA. Se puede borrar |
| `componentes/` | yt-dlp actualizado desde la app |
| `.env` | Tus credenciales y ajustes. No se sube a GitHub |
| `.cache-spotify` | El permiso de tu cuenta de Spotify. No se sube a GitHub |

## El reproductor MigueWamp

- Tres skins: clásica y moderna, dibujadas en vectores para verse nítidas a cualquier tamaño, y "Cabeza", que flota sola sobre el escritorio.
- La biblioteca reúne tus carpetas de música. Ahí reproduces, encolas y armas playlists, que se guardan como `.m3u8`.
- "Abrir ubicación" (Ctrl+L) acepta enlaces, rutas y canciones sueltas, una por línea. Cada descarga terminada entra sola a la lista.
- **Volumen nivelado** (botón AUTO del ecualizador): todas las canciones suenan parejo, sin tocar los archivos.
- **Fundido entre canciones** y **temporizador para dormir**, en el menú del reproductor.
- **Artistas y álbumes** en la biblioteca, e **importar listas** `.m3u`, `.m3u8` y `.pls` de otros reproductores.
- Reproduce también APE, WMA, WavPack, AIFF, Musepack, TTA y AC3: los convierte una vez, solo para escucharlos.

## Laboratorio de mejora

1. **Analiza** la canción: sonoridad, rango dinámico, picos, saturación y si viene de una fuente con pérdida. Con el nivel Mejora, también la afinación, el tempo y la tonalidad.
2. **Sugiere procesos** según lo que encuentra. Solo ofrece los que tu equipo puede correr.
3. **Procesa en una sola pasada** desde el original y guarda una versión nueva. El original nunca se modifica.
4. **Revisa la calidad** del resultado y permite **comparar A/B** con el volumen igualado.

La afinación global, por ejemplo de 440 a 438 Hz, cambia el tono sin cambiar la duración.

La masterización con referencia toma una canción que suena como quieres y ajusta la otra a su tono, sonoridad y anchura estéreo.

Con el nivel IA, el laboratorio separa la canción en voz, batería, bajo y resto: sirve para una versión karaoke, para escuchar solo la voz o para afinar cada instrumento y volver a mezclar.

## Lo que no hace

- No descarga audio de Spotify. Ese audio está protegido, así que Spotify solo aporta las listas y los datos de cada canción.
- No comparte tu música ni tus listas con nadie.
