// Ventanas sin marco: la barra de título mueve la ventana real del sistema,
// y la esquina la redimensiona. Funciona con pywebview; en el navegador no hace nada.

export const nativo = () => window.pywebview?.api;

function seguir(e, alMover) {
  if (e.button !== 0 || !nativo()) return;
  e.preventDefault();
  e.stopPropagation();
  const el = e.currentTarget;
  el.setPointerCapture?.(e.pointerId);
  const inicio = { sx: e.screenX, sy: e.screenY, wx: window.screenX, wy: window.screenY, w: window.innerWidth, h: window.innerHeight };
  let pendiente = null, enviando = false;
  async function enviar() {
    if (enviando || !pendiente) return;
    enviando = true;
    const orden = pendiente;
    pendiente = null;
    try { await orden(); } finally { enviando = false; enviar(); }
  }
  const mover = (ev) => {
    pendiente = () => alMover(ev.screenX - inicio.sx, ev.screenY - inicio.sy, inicio);
    enviar();
  };
  const soltar = () => {
    el.removeEventListener("pointermove", mover);
    el.removeEventListener("pointerup", soltar);
  };
  el.addEventListener("pointermove", mover);
  el.addEventListener("pointerup", soltar);
}

export const arrastrarVentana = (e) =>
  seguir(e, (dx, dy, i) => nativo().mover(i.wx + dx, i.wy + dy));

export const redimensionarVentana = (e, calcular) =>
  seguir(e, (dx, dy, i) => {
    const [w, h] = calcular(i.w + dx, i.h + dy);
    return nativo().tamano(Math.round(w), Math.round(h));
  });

export async function encolarEnReproductor(accion, pistas) {
  await fetch("/api/cola", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accion, pistas }),
  });
}

export const abrirVentana = (nombre) => nativo()?.abrir(nombre);

// Forma de la ventana del reproductor: unión de capas (la skin, el menú abierto...).
// Cada capa es una lista plana [x, y, w, h, ...] en píxeles CSS. Sin capas = rectangular.
const capas = {};
let envio = 0;
export function fijarForma(nombre, rects) {
  if (rects && rects.length) capas[nombre] = rects;
  else delete capas[nombre];
  cancelAnimationFrame(envio);
  envio = requestAnimationFrame(enviarForma);
}
function enviarForma() {
  nativo()?.forma(Object.values(capas).flat(), window.devicePixelRatio || 1);
}
window.addEventListener("pywebviewready", enviarForma);
export const rectDe = (el) => {
  const r = el.getBoundingClientRect();
  return [Math.floor(r.left), Math.floor(r.top), Math.ceil(r.width) + 1, Math.ceil(r.height) + 1];
};

// Silueta a partir de filas de tramos opacos ("x,largo,x,largo|..." por fila).
// piezas: [{ filas, x, y }] en coordenadas del diseño; escala: tamaño en pantalla.
export function siluetaDe(piezas, escala) {
  const rects = [];
  for (const p of piezas) {
    const filas = p.filas.split("|");
    // une filas seguidas con los mismos tramos para mandar menos rectángulos
    let y = 0;
    while (y < filas.length) {
      let fin = y + 1;
      while (fin < filas.length && filas[fin] === filas[y]) fin++;
      const t = filas[y] ? filas[y].split(",").map(Number) : [];
      const y0 = Math.floor((p.y + y) * escala), y1 = Math.ceil((p.y + fin) * escala);
      for (let i = 0; i < t.length; i += 2) {
        const x0 = Math.floor((p.x + t[i]) * escala), x1 = Math.ceil((p.x + t[i] + t[i + 1]) * escala);
        rects.push(x0, y0, x1 - x0, y1 - y0);
      }
      y = fin;
    }
  }
  return rects;
}
