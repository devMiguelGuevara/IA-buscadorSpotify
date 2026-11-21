// Estado compartido entre ventanas: biblioteca y cola de descargas.
import { reactive } from "vue";
import { api, pista } from "./api.js";

export const estado = reactive({ canciones: [], trabajos: [], playlists: [] });

const agregadas = new Set(); // descargas que ya entraron al playlist
let alTerminar = null;

export function alTerminarDescarga(fn) {
  alTerminar = fn;
}

export async function cargarBiblioteca() {
  try {
    estado.canciones = (await api.biblioteca()).canciones;
  } catch {}
}

export async function cargarPlaylists() {
  try {
    estado.playlists = (await api.playlists()).playlists;
  } catch {}
}

export const descargasActivas = () =>
  estado.trabajos.filter((t) => ["preparando", "descargando", "pausado", "cancelando"].includes(t.estado));

export async function revisarDescargas() {
  try {
    estado.trabajos = (await api.descargas()).trabajos;
  } catch {
    return;
  }
  const nuevas = [];
  for (const t of estado.trabajos)
    for (const it of t.items)
      if (it.estado === "ok" && it.archivo && !agregadas.has(it.archivo)) {
        agregadas.add(it.archivo);
        nuevas.push(pista({ raiz: 0, ruta: it.archivo, titulo: it.titulo, artista: it.artista }));
      }
  if (nuevas.length) {
    alTerminar?.(nuevas); // la biblioteca se va armando mientras descarga
    cargarBiblioteca();
  }
}
