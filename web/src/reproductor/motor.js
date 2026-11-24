// Motor de audio del reproductor: lista, transporte, ecualizador de 10 bandas,
// balance y analizador para el visualizador. Usa el audio del motor web + Web Audio.
import { reactive, watch } from "vue";

export const BANDAS = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000];

export const PRESETS = {
  Plano: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  Rock: [8, 5, -5, -8, -3, 4, 8, 11, 11, 11],
  Pop: [-2, 5, 7, 8, 5, 0, -2, -2, -2, -2],
  Clásica: [0, 0, 0, 0, 0, 0, -7, -7, -7, -9],
  Dance: [10, 8, 2, 0, 0, -6, -7, -7, 0, 0],
  Graves: [10, 10, 10, 6, 2, -4, -8, -10, -11, -11],
  Agudos: [-10, -10, -10, -4, 2, 11, 16, 16, 16, 16],
  Voz: [-4, -2, 0, 4, 7, 7, 4, 0, -2, -4],
  Reggae: [0, 0, -1, -6, 0, 6, 6, 0, 0, 0],
};

export const motor = reactive({
  lista: [],          // { url, titulo, artista, duracion, kbps, khz }
  actual: -1,
  cola: [],           // pistas encoladas (Q): suenan antes que el orden de la lista
  seleccion: new Set(),
  estado: "detenido", // detenido | sonando | pausado
  tiempo: 0,
  duracion: 0,
  volumen: 0.8,
  balance: 0,
  aleatorio: false,
  repetir: false,
  restante: false,
  eqActivo: true,
  preamp: 0,
  bandas: [...PRESETS.Plano],
  preset: "Plano",
  nivelar: true,      // volumen nivelado (botón AUTO del ecualizador)
  nivelDb: 0,         // ganancia aplicada a la canción actual
  fundido: 0,         // segundos de fundido entre canciones (0 = sin fundido)
  velocidad: 1,       // velocidad de reproducción (conserva el tono)
  dormir: 0,          // temporizador: 0, minutos o "cancion" (al terminar la canción)
  dormirFin: 0,       // hora (ms) en que se apaga
  aviso: "", // mensaje breve para la pantalla (errores, confirmaciones)
});

let relojAviso = 0;
watch(() => motor.aviso, (a) => {
  clearTimeout(relojAviso);
  if (a) relojAviso = setTimeout(() => (motor.aviso = ""), 5000);
});

// Dos reproductores ("platos") que se turnan: así el fundido cruza una canción con la
// siguiente. Cada plato tiene su ganancia (volumen nivelado y fundido) antes del ecualizador.
const platos = [0, 1].map(() => {
  const audio = new Audio();
  audio.preload = "auto";
  return { audio, nivel: null };
});
let actualP = 0;
const A = () => platos[actualP].audio;
let ctx = null, preamp = null, filtros = [], panner = null, analizador = null;

function grafo() {
  if (ctx) return;
  ctx = new AudioContext();
  preamp = ctx.createGain();
  for (const p of platos) {
    p.nivel = ctx.createGain();
    p.nivel.gain.value = 0;
    ctx.createMediaElementSource(p.audio).connect(p.nivel);
    p.nivel.connect(preamp);
  }
  platos[actualP].nivel.gain.value = gananciaNivel(motor.nivelDb);
  filtros = BANDAS.map((f, i) => {
    const b = ctx.createBiquadFilter();
    b.type = i === 0 ? "lowshelf" : i === BANDAS.length - 1 ? "highshelf" : "peaking";
    b.frequency.value = f;
    b.Q.value = 1.4;
    return b;
  });
  panner = ctx.createStereoPanner();
  analizador = ctx.createAnalyser();
  analizador.fftSize = 2048;
  analizador.smoothingTimeConstant = 0.55;
  [preamp, ...filtros, panner, analizador, ctx.destination].reduce((a, b) => (a.connect(b), b));
  aplicarEq();
}

export function aplicarEq() {
  if (!ctx) return;
  const on = motor.eqActivo;
  preamp.gain.value = on ? 10 ** (motor.preamp / 20) : 1;
  filtros.forEach((b, i) => (b.gain.value = on ? motor.bandas[i] : 0));
  panner.pan.value = motor.balance;
}
watch(() => [motor.eqActivo, motor.preamp, motor.balance, ...motor.bandas], aplicarEq);
watch(() => motor.volumen, (v) => platos.forEach((p) => (p.audio.volume = v)), { immediate: true });
watch(() => motor.velocidad, (v) => platos.forEach((p) => {
  p.audio.defaultPlaybackRate = v; // se mantiene al cambiar de canción
  p.audio.playbackRate = v;
}), { immediate: true });

// ---------- volumen nivelado: cada canción a -14 LUFS (medido una vez por el servicio)
const niveles = new Map(); // url -> Promise<dB>
const medidas = [];         // dB ya medidos: su mediana es el volumen provisional
function nivelDe(url) {
  if (!niveles.has(url))
    niveles.set(url, fetch("/api/nivel?url=" + encodeURIComponent(url))
      .then((r) => (r.ok ? r.json() : {})).then((d) => {
        const db = d.ganancia_db ?? 0;
        if (d.lufs != null) medidas.push(db);
        return db;
      }).catch(() => 0));
  return niveles.get(url);
}
function provisional() {
  if (!medidas.length) return -4; // lo típico de una canción actual (unos -10 LUFS)
  const o = [...medidas].sort((a, b) => a - b);
  return o[Math.floor(o.length / 2)];
}
// El servicio mide en segundo plano lo que entra a la lista: al tocarlo ya suena nivelado.
const pedidas = new Set();
function precalcular(pistas) {
  const urls = pistas.map((p) => p.url).filter((u) => u && !pedidas.has(u) && /^\/(media|versiones)\//.test(u));
  if (!urls.length) return;
  urls.forEach((u) => pedidas.add(u));
  fetch("/api/nivel/lote", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rutas: urls }) }).catch(() => {});
}
const gananciaNivel = (db) => (motor.nivelar ? 10 ** (db / 20) : 1);
function fijarGanancia(plato, g, segundos = 0) {
  if (!plato.nivel) return;
  const param = plato.nivel.gain, t = ctx.currentTime;
  param.cancelScheduledValues(t);
  if (!segundos) { param.value = g; return; }
  param.setValueAtTime(param.value, t);
  param.linearRampToValueAtTime(g, t + segundos);
}
function aplicarNivel(db, suave = false) {
  motor.nivelDb = db;
  fijarGanancia(platos[actualP], gananciaNivel(db), suave ? 0.4 : 0);
}
watch(() => motor.nivelar, (on) => {
  aplicarNivel(motor.nivelDb, true);
  if (on) precalcular(motor.lista);
});
// Medida de una pista: espera como mucho `ms`; si no llega, devuelve null.
async function medidaRapida(url, ms) {
  if (!motor.nivelar) return 0;
  const limite = new Promise((r) => setTimeout(() => r(null), ms));
  return Promise.race([nivelDe(url), limite]);
}

export const analizadorActual = () => analizador;
export const pistaActual = () => motor.lista[motor.actual] || null;

for (const p of platos) {
  const es = () => p === platos[actualP];
  p.audio.addEventListener("timeupdate", () => {
    if (!es()) return;
    motor.tiempo = p.audio.currentTime;
    revisarFundido();
  });
  p.audio.addEventListener("loadedmetadata", () => es() && (motor.duracion = p.audio.duration || pistaActual()?.duracion || 0));
  p.audio.addEventListener("ended", () => {
    if (!es()) return;
    if (motor.dormir === "cancion") return dormirAhora(false);
    siguiente(true);
  });
  // Si el sistema pausa o reanuda el audio por su cuenta (una llamada, otra app que suena), el
  // reproductor lo refleja. No cuentan el final de la canción ni los cambios de canción.
  p.audio.addEventListener("pause", () => {
    if (es() && p.audio.paused && !p.audio.ended && motor.estado === "sonando" && !fundiendo) motor.estado = "pausado";
  });
  p.audio.addEventListener("play", () => {
    if (es() && !p.audio.paused && motor.estado === "pausado") motor.estado = "sonando";
  });
  p.audio.addEventListener("error", () => {
    if (!es() || !p.audio.getAttribute("src")) return;
    motor.aviso = `No se pudo abrir «${pistaActual()?.titulo || "la canción"}»`;
    if (motor.estado === "sonando") setTimeout(() => siguiente(true), 800);
  });
}

// ---------- fundido entre canciones
let fundiendo = null; // { viejo, nuevo, cambiado, reloj }
function cortarFundido() {
  if (!fundiendo) return;
  const f = fundiendo;
  fundiendo = null;
  clearTimeout(f.reloj);
  const sobra = f.cambiado ? f.viejo : f.nuevo; // nunca el plato que está sonando
  sobra.audio.pause();
  sobra.audio.removeAttribute("src");
  sobra.audio.load();
  fijarGanancia(sobra, 0);
}
function indiceSiguiente() {
  const n = motor.lista.length;
  if (!n) return null;
  const encolada = motor.cola.find((p) => motor.lista.includes(p));
  if (encolada) return motor.lista.indexOf(encolada);
  let i = motor.aleatorio ? Math.floor(Math.random() * n) : motor.actual + 1;
  if (i >= n) {
    if (!motor.repetir) return null;
    i = 0;
  }
  return i;
}
function revisarFundido() {
  if (!motor.fundido || fundiendo || !ctx || motor.estado !== "sonando" || motor.dormir === "cancion") return;
  const a = A(), resta = a.duration - a.currentTime;
  if (!isFinite(resta) || a.duration < motor.fundido * 3) return;
  if (resta > motor.fundido) {
    if (resta < motor.fundido + 12 && motor.nivelar) { // medir la siguiente con tiempo
      const s = motor.lista[indiceSiguiente() ?? -1];
      if (s) nivelDe(s.url);
    }
    return;
  }
  const i = indiceSiguiente();
  if (i != null) cruzar(i, resta);
}
async function cruzar(i, segundos) {
  const viejo = platos[actualP], nuevo = platos[1 - actualP], p = motor.lista[i];
  const yo = { viejo, nuevo, cambiado: false, reloj: 0 };
  fundiendo = yo;
  nuevo.audio.src = p.url;
  const db = (await medidaRapida(p.url, 800)) ?? 0;
  if (fundiendo !== yo) return; // se cortó mientras tanto
  actualP = 1 - actualP;
  yo.cambiado = true;
  sacarDeCola(p);
  motor.actual = i;
  motor.tiempo = 0;
  motor.duracion = p.duracion || 0;
  motor.nivelDb = db;
  fijarGanancia(nuevo, 0);
  fijarGanancia(nuevo, gananciaNivel(db), segundos);
  fijarGanancia(viejo, 0, segundos);
  nuevo.audio.play().catch(() => {});
  yo.reloj = setTimeout(cortarFundido, segundos * 1000 + 300);
}

// ---------- temporizador para dormir: minutos o "al terminar la canción"
let relojDormir = 0;
export function programarDormir(valor) {
  clearInterval(relojDormir);
  motor.dormir = valor || 0;
  motor.dormirFin = typeof valor === "number" && valor > 0 ? Date.now() + valor * 60000 : 0;
  if (motor.dormirFin)
    relojDormir = setInterval(() => {
      if (Date.now() >= motor.dormirFin) dormirAhora(true);
    }, 1000);
}
function dormirAhora(desvanecer) {
  clearInterval(relojDormir);
  motor.dormir = 0;
  motor.dormirFin = 0;
  if (motor.estado !== "sonando") return;
  if (!desvanecer || !ctx) {
    detener();
    motor.aviso = "Temporizador: buenas noches";
    return;
  }
  cortarFundido();
  const plato = platos[actualP];
  fijarGanancia(plato, 0, 8); // se apaga suave en 8 s
  setTimeout(() => {
    if (motor.estado === "sonando") pausa();
    fijarGanancia(plato, gananciaNivel(motor.nivelDb));
    motor.aviso = "Temporizador: buenas noches";
  }, 8200);
}

export function cargar(i, sonar = true) {
  const p = motor.lista[i];
  if (!p) return;
  cortarFundido();
  sacarDeCola(p);
  motor.actual = i;
  motor.tiempo = 0;
  motor.duracion = p.duracion || 0;
  A().src = p.url;
  const mio = ++turno;
  // Suena enseguida: si la medida no está en 0,3 s, arranca con un volumen provisional
  // y se ajusta suave cuando llega (casi siempre ya está, medida de antemano).
  medidaRapida(p.url, 300).then((db) => {
    if (mio !== turno) return; // ya se cambió de canción
    if (db == null) {
      aplicarNivel(provisional());
      nivelDe(p.url).then((d) => mio === turno && aplicarNivel(d, true));
    } else aplicarNivel(db);
    if (sonar) reproducir();
    const sig = motor.aleatorio && !motor.cola.length ? null : motor.lista[indiceSiguiente() ?? -1];
    if (sig && motor.nivelar) nivelDe(sig.url); // la siguiente queda medida de antemano
  });
}
let turno = 0;

export function reproducir() {
  grafo();
  ctx.resume();
  if (motor.actual < 0) {
    if (motor.lista.length) cargar(0);
    return;
  }
  if (motor.estado === "detenido" && !A().src) return cargar(motor.actual);
  A().play().catch((e) => {
    if (e.name === "AbortError") return; // se cambió de canción antes de empezar
    motor.estado = "detenido";
    motor.aviso = e.name === "NotAllowedError"
      ? "Pulsa play para empezar a sonar" : `No se pudo reproducir: ${e.message || e.name}`;
  });
  motor.estado = "sonando";
}

export function pausa() {
  if (motor.estado === "sonando") {
    cortarFundido();
    A().pause();
    motor.estado = "pausado";
  } else if (motor.estado === "pausado") {
    reproducir();
  }
}

export function detener() {
  cortarFundido();
  A().pause();
  if (A().src) A().currentTime = 0;
  motor.tiempo = 0;
  motor.estado = "detenido";
}

export function siguiente(automatico = false) {
  const n = motor.lista.length;
  if (!n) return;
  const i = indiceSiguiente();
  if (i == null) {
    if (automatico) return detener();
    return cargar(0);
  }
  cargar(i);
}

// ---------- cola (Q) y reordenar
const sacarDeCola = (p) => (motor.cola = motor.cola.filter((x) => x !== p));
export function encolar(indices) {
  for (const i of indices) {
    const p = motor.lista[i];
    if (!p) continue;
    if (motor.cola.includes(p)) sacarDeCola(p);
    else motor.cola = [...motor.cola, p];
  }
}
export const posicionEnCola = (p) => motor.cola.indexOf(p) + 1; // 0 = no encolada

// Mueve las pistas elegidas para que queden antes de la posición `destino` (0..largo).
export function moverA(indices, destino) {
  const elegidos = new Set(indices);
  const actual = motor.lista[motor.actual];
  const mover = motor.lista.filter((_, i) => elegidos.has(i));
  const antes = motor.lista.slice(0, destino).filter((_, i) => !elegidos.has(i));
  const despues = motor.lista.slice(destino).filter((_, i) => !elegidos.has(i + destino));
  motor.lista = [...antes, ...mover, ...despues];
  motor.actual = motor.lista.indexOf(actual);
  motor.seleccion = new Set(mover.map((_, k) => antes.length + k));
}
export function moverSeleccion(delta) {
  const indices = [...motor.seleccion].sort((a, b) => a - b);
  if (!indices.length) return;
  if (delta < 0 && indices[0] === 0) return;
  if (delta > 0 && indices.at(-1) === motor.lista.length - 1) return;
  moverA(indices, delta < 0 ? indices[0] - 1 : indices.at(-1) + 2);
}

export function anterior() {
  if (A().currentTime > 3) {
    A().currentTime = 0;
    return;
  }
  if (motor.lista.length) cargar(Math.max(0, motor.actual - 1));
}

export function irA(segundos) {
  if (motor.estado === "detenido") return;
  cortarFundido();
  A().currentTime = segundos;
}

export const adelantar = (s) => irA(Math.min(motor.duracion, Math.max(0, A().currentTime + s)));

export function agregar(pistas, sonarYa = false) {
  if (motor.nivelar) precalcular(pistas);
  const inicio = motor.lista.length;
  motor.lista.push(...pistas);
  if (sonarYa && pistas.length) cargar(inicio);
}

export function reemplazar(pistas) {
  if (motor.nivelar) precalcular(pistas);
  detener();
  liberar(motor.lista.filter((p) => !pistas.includes(p)));
  motor.lista = [...pistas];
  motor.seleccion = new Set();
  motor.actual = -1;
  motor.cola = [];
  if (pistas.length) cargar(0);
}

// Las pistas elegidas con el selector son enlaces a memoria (blob:): se liberan al quitarlas.
function liberar(pistas) {
  for (const p of pistas) if (p.local && p.url?.startsWith("blob:")) URL.revokeObjectURL(p.url);
}

export function quitar(indices) {
  const quitar = new Set(indices);
  liberar(motor.lista.filter((_, i) => quitar.has(i) && i !== motor.actual));
  const actual = motor.lista[motor.actual];
  motor.lista = motor.lista.filter((_, i) => !quitar.has(i));
  motor.cola = motor.cola.filter((p) => motor.lista.includes(p));
  motor.seleccion = new Set();
  const nuevo = motor.lista.indexOf(actual);
  if (nuevo < 0 && quitar.has(motor.actual)) {
    detener();
    A().removeAttribute("src");
  }
  motor.actual = nuevo;
}

export function vaciar() {
  detener();
  liberar(motor.lista);
  A().removeAttribute("src");
  motor.lista = [];
  motor.actual = -1;
  motor.cola = [];
  motor.seleccion = new Set();
}

export function aplicarPreset(nombre) {
  motor.bandas = [...PRESETS[nombre]];
  motor.preset = nombre;
}

export function mmss(s) {
  if (!s && s !== 0) return "";
  s = Math.max(0, Math.floor(s));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
