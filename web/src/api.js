// Llamadas al servicio interno de Python.

async function pedir(ruta, datos, metodo = "POST") {
  const r = await fetch(ruta, datos === undefined && metodo === "POST" ? {} : {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  biblioteca: () => pedir("/api/biblioteca"),
  resolver: (texto) => pedir("/api/resolver", { texto }),
  descargar: (texto, simular, metodo = "auto", formato = "original") =>
    pedir("/api/descargas", { texto, simular, metodo, formato }),
  controlar: (id, accion) => pedir(`/api/descargas/${id}/${accion}`, {}),
  mejorables: () => pedir("/api/mejorar", undefined, "GET"),
  mejorar: (simular = false) => pedir("/api/mejorar", { simular }),
  descargas: () => pedir("/api/descargas"),
  ytdlp: () => pedir("/api/ytdlp", undefined, "GET"),
  ytdlpBuscar: () => pedir("/api/ytdlp/buscar", undefined, "GET"),
  ytdlpActualizar: () => pedir("/api/ytdlp/actualizar", {}),
  carpetas: () => pedir("/api/carpetas"),
  agregarCarpeta: (ruta) => pedir("/api/carpetas", { ruta }),
  quitarCarpeta: (ruta) => pedir("/api/carpetas/quitar", { ruta }),
  carpetaDescargas: (ruta) => pedir("/api/carpetas/descargas", { ruta }),
  playlists: () => pedir("/api/playlists"),
  playlist: (nombre) => pedir("/api/playlists/" + encodeURIComponent(nombre)),
  guardarPlaylist: (nombre, pistas, agregar = false) =>
    pedir("/api/playlists/" + encodeURIComponent(nombre), { pistas, agregar }, "PUT"),
  importarPlaylist: (ruta) => pedir("/api/playlists/importar", { ruta }),
  borrarPlaylist: (nombre) => pedir("/api/playlists/" + encodeURIComponent(nombre), undefined, "DELETE"),
};

// Identificador único de una canción de la biblioteca (carpeta + ruta).
export const clave = (c) => `${c.raiz ?? 0}/${c.ruta}`;

// Pista en el formato del reproductor. Guarda carpeta y ruta para poder armar playlists.
export function pista(c) {
  const raiz = c.raiz ?? 0;
  return {
    raiz,
    ruta: c.ruta,
    url: c.url || `/media/${raiz}/` + c.ruta.split("/").map(encodeURIComponent).join("/"),
    titulo: c.titulo || c.ruta,
    artista: c.artista || "",
    duracion: typeof c.duracion === "number" ? c.duracion : undefined,
    kbps: c.kbps || null,
    khz: c.khz || null,
  };
}

export function duracion(s) {
  if (!s && s !== 0) return "";
  if (typeof s === "string") return s;
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// Funciones nativas de la ventana (pywebview). En el navegador no existen.
export const nativo = () => window.pywebview?.api;
