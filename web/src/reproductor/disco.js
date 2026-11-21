// Cargar música desde el disco al reproductor: archivos o carpetas elegidos con el diálogo
// del sistema, o arrastrados sobre la ventana. Lo que esté fuera de la biblioteca se suma a ella.
import { pista } from "../api.js";
import { nativo } from "../ventanas/nativo.js";
import { agregar, motor } from "./motor.js";

export async function agregarRutas(rutas, sonar = false) {
  if (!rutas?.length) return 0;
  const r = await fetch("/api/agregar_rutas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rutas }),
  });
  const { pistas } = await r.json();
  if (!pistas.length) {
    motor.aviso = "No se encontró audio en lo elegido";
    return 0;
  }
  agregar(pistas.map(pista), sonar || (motor.estado === "detenido" && motor.actual < 0) || motor.lista.length === 0);
  return pistas.length;
}

export async function agregarArchivos() {
  const rutas = await nativo()?.elegir_audios();
  return agregarRutas(rutas);
}

export async function agregarCarpeta() {
  const ruta = await nativo()?.elegir_carpeta();
  return ruta ? agregarRutas([ruta]) : 0;
}

// Arrastrar archivos o carpetas sobre el reproductor (pywebview da la ruta completa).
export function soltarArchivos(e) {
  const rutas = [...(e.dataTransfer?.files || [])].map((f) => f.pywebviewFullPath || f.path).filter(Boolean);
  if (rutas.length) agregarRutas(rutas);
  else motor.aviso = "Arrastra archivos desde el Explorador de Windows";
}
