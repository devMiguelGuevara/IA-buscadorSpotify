// La presentación (doble clic en el rayo dorado). En el escritorio se abre en su propia ventana a
// pantalla completa; sin ventanas del sistema (navegador), como capa sobre la página.
// Mientras corre no se puede volver a lanzar.
import { reactive } from "vue";
import { nativo } from "./ventanas/nativo.js";

export const presentacion = reactive({ activa: false });

let cerradaEn = 0;

export function presentar() {
  if (presentacion.activa || Date.now() - cerradaEn < 1000) return; // un segundo de calma tras cerrarla
  if (nativo()) {
    nativo().abrir("presentacion"); // si ya está abierta, el escritorio solo la trae al frente
    return;
  }
  presentacion.activa = true;
}

export function terminarPresentacion() {
  presentacion.activa = false;
  cerradaEn = Date.now();
}
