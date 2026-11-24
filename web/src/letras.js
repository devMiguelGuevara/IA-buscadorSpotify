// Letras de las canciones (botón K). En el escritorio se abren en su propia ventana a pantalla
// completa; sin ventanas del sistema (navegador), como capa sobre la página.
import { reactive } from "vue";
import { nativo } from "./ventanas/nativo.js";
import * as plataforma from "./plataforma.js";

export const letra = reactive({ activa: false });

export function abrirLetra() {
  if (letra.activa) return;
  if (nativo()) {
    nativo().abrir("letra"); // si ya está abierta, el escritorio solo la trae al frente
    return;
  }
  letra.activa = true;
}

export function cerrarLetra() {
  letra.activa = false;
}

const NINGUNA = { tipo: "ninguna", lineas: [], fuente: "" };

// La letra de una pista: { tipo: sincronizada | texto | instrumental | ninguna, lineas: [[segundo|null, texto]] }.
// soloGuardada: no busca en internet (para saber si ya está). forzar: busca de nuevo.
export async function buscarLetra(pista, { forzar = false, soloGuardada = false } = {}) {
  if (!pista?.url) return { ...NINGUNA };
  if (plataforma.buscarLetra) return plataforma.buscarLetra(pista, { forzar, soloGuardada });
  const q = new URLSearchParams({ url: pista.url });
  if (forzar) q.set("forzar", "true");
  if (soloGuardada) q.set("solo_cache", "true");
  try {
    const r = await fetch("/api/letra?" + q);
    return r.ok ? await r.json() : { ...NINGUNA };
  } catch {
    return { ...NINGUNA, error: true };
  }
}
