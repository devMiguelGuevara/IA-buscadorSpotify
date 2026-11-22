// Estado compartido entre ventanas: biblioteca y cola de descargas.
import { reactive } from "vue";
import { api, pista } from "./api.js";

export const estado = reactive({ canciones: [], trabajos: [], playlists: [] });

const agregadas = new Set(); // descargas que ya entraron al playlist
const terminados = new Set(); // trabajos cuya lista ya se recargó
let alTerminar = null;

export function alTerminarDescarga(fn) {
  alTerminar = fn;
}

// Si llegan varios pedidos seguidos (cada descarga que termina pide uno), se hace una
// lectura en curso y, como mucho, otra al final: nunca una por cada pedido.
let leyendo = null, otraVez = false;
export async function cargarBiblioteca() {
  if (leyendo) {
    otraVez = true;
    return leyendo;
  }
  leyendo = (async () => {
    do {
      otraVez = false;
      try { estado.canciones = (await api.biblioteca()).canciones; } catch {}
    } while (otraVez);
    leyendo = null;
  })();
  return leyendo;
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
  // Al terminar una descarga se escribe su lista (.m3u8): se recargan las listas.
  const recien = estado.trabajos.filter((t) => ["terminado", "cancelado"].includes(t.estado) && !terminados.has(t.id));
  if (recien.length) {
    recien.forEach((t) => terminados.add(t.id));
    cargarPlaylists();
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
