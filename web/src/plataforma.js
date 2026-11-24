// Dónde corre la interfaz y qué tiene disponible: el reproductor de escritorio, con su
// servicio interno (biblioteca, playlists y descargas).
import { reactive } from "vue";

export const conServicio = true;          // hay servicio interno
export const vistaCompacta = false;       // abrir siempre la vista compacta
export const estadoPlataforma = reactive({ descargas: true });

export const pestanas = (todas) => todas;          // pestañas de la vista compacta
export const menuAgregar = (base) => base;         // opciones del botón ADD de la lista
export const agregarArchivos = null;               // null: el diálogo del sistema de siempre
export const agregarCarpeta = null;

export const conPlaylists = true;                  // LIST: guardar, cargar y borrar playlists
export const guardable = (p) => p.ruta !== undefined; // canciones que pueden ir a una playlist

export const conLetras = () => true;               // botón K (letras de las canciones)
export const buscarLetra = null;                   // null: las busca el servicio interno (/api/letra)
