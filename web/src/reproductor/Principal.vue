<script setup>
// Ventana principal de MigueWamp, en vectores (lienzo de 275 x 116).
// Skin clásica: botones plateados biselados. Skin moderna: botones redondos y esquinas suaves.
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import Digitos from "./Digitos.vue";
import { crearVisualizador } from "./visualizador.js";
import { anterior, detener, irA, mmss, motor, pausa, pistaActual, reproducir, siguiente } from "./motor.js";
import { abrirVentana, arrastrarVentana, nativo } from "../ventanas/nativo.js";
import { agregarArchivos } from "./disco.js";

// holgura: espacio extra (en unidades del dibujo) arriba y abajo de la barra de tiempo. Lo usa
// la vista compacta para arrastrarla con el dedo sin tocar el volumen ni los botones.
const props = defineProps({ eq: Boolean, pl: Boolean, skin: String, holgura: { type: Number, default: 0 } });
const emit = defineEmits(["alternar-eq", "alternar-pl", "menu"]);
const svg = ref(null);
const moderna = computed(() => props.skin === "moderna");

// ---------- deslizadores
function punto(e) {
  const p = svg.value.createSVGPoint();
  p.x = e.clientX;
  p.y = e.clientY;
  return p.matrixTransform(svg.value.getScreenCTM().inverse());
}
function deslizar(e, x0, ancho, alMover, alSoltar) {
  if (e.button !== 0) return;
  e.preventDefault();
  const valor = (ev) => Math.min(1, Math.max(0, (punto(ev).x - x0) / ancho));
  alMover(valor(e));
  const mover = (ev) => alMover(valor(ev));
  const soltar = (ev) => {
    window.removeEventListener("pointermove", mover);
    window.removeEventListener("pointerup", soltar);
    alSoltar?.(valor(ev));
  };
  window.addEventListener("pointermove", mover);
  window.addEventListener("pointerup", soltar);
}
const buscando = ref(null);
const posicion = computed(() => buscando.value ?? (motor.duracion ? motor.tiempo / motor.duracion : 0));
const buscar = (e) => motor.duracion && deslizar(e, 30, 220,
  (v) => (buscando.value = v), (v) => { irA(v * motor.duracion); buscando.value = null; });
const volumen = (e) => deslizar(e, 107, 54, (v) => (motor.volumen = v));
const balance = (e) => deslizar(e, 177, 24, (v) => (motor.balance = Math.round((v * 2 - 1) * 20) / 20));

// ---------- pantalla
const tiempo = computed(() => {
  if (motor.estado === "detenido") return "  :  ";
  const s = motor.restante ? Math.max(0, motor.duracion - motor.tiempo) : motor.tiempo;
  return `${String(Math.min(99, Math.floor(s / 60))).padStart(2, " ")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
});
const texto = computed(() => {
  if (motor.aviso) return motor.aviso.toUpperCase();
  const p = pistaActual();
  if (!p) return "MIGUEWAMP  ***  CTRL+L PARA PEGAR ENLACES O RUTAS  ***";
  const nombre = p.artista ? `${p.artista} - ${p.titulo}` : p.titulo;
  return `${motor.actual + 1}. ${nombre} (${mmss(p.duracion || motor.duracion)})`.toUpperCase();
});
const marquesina = ref(null);
const desplazamiento = ref(0);
const anchoTexto = ref(0);

const vis = crearVisualizador(19);
const osciloscopio = ref(false);
const barras = ref(""), picos = ref(""), onda = ref("");
let ultimoT = 0, cuadro = 0;
function dibujar(t) {
  cuadro = requestAnimationFrame(dibujar);
  const dt = Math.min(0.1, (t - ultimoT) / 1000 || 0);
  ultimoT = t;
  if (marquesina.value) {
    anchoTexto.value = marquesina.value.getComputedTextLength?.() || 0;
    desplazamiento.value = anchoTexto.value > 150 ? (desplazamiento.value + dt * 22) % (anchoTexto.value + 30) : 0;
  }
  const r = vis.leer(dt, osciloscopio.value);
  if (r.onda) {
    onda.value = r.onda.map((v, i) => `${i ? "L" : "M"}${22 + i} ${44 + v * 16}`).join("");
    barras.value = picos.value = "";
    return;
  }
  onda.value = "";
  barras.value = r.barras.map((h, i) => (h > 0.02 ? `M${22 + i * 4} 60h3v${(-h * 16).toFixed(2)}h-3z` : "")).join("");
  picos.value = r.cimas.map((h, i) => (h > 0.04 ? `M${22 + i * 4} ${(60 - h * 16).toFixed(2)}h3v0.8h-3z` : "")).join("");
}
onMounted(() => (cuadro = requestAnimationFrame(dibujar)));
onBeforeUnmount(() => cancelAnimationFrame(cuadro));

const estereo = computed(() => pistaActual() && motor.estado !== "detenido");
const TRANSPORTE = [
  { x: 16, w: 23, accion: anterior, icono: "M6.5 5.5v7M16 5.5l-8 3.5 8 3.5z" },
  { x: 39, w: 23, accion: reproducir, icono: "M8.5 5l8 4-8 4z" },
  { x: 62, w: 23, accion: pausa, icono: "M8.5 5.5v7M13.5 5.5v7" },
  { x: 85, w: 23, accion: detener, icono: "M8 5.5h7v7H8z" },
  { x: 108, w: 22, accion: () => siguiente(), icono: "M6 5.5l8 3.5-8 3.5zM15.5 5.5v7" },
];
</script>

<template>
  <svg ref="svg" class="wa-svg" :viewBox="`0 0 275 ${116 + 2 * holgura}`" @contextmenu.prevent="emit('menu', $event)">
    <!-- marco -->
    <rect class="marco" x="0.5" y="0.5" width="274" :height="115 + 2 * holgura" />
    <rect class="marco-luz" x="1.2" y="1.2" width="272.6" :height="113.6 + 2 * holgura" />

    <!-- barra de título: arrastra la ventana real -->
    <g @pointerdown="arrastrarVentana" @dblclick="emit('menu', $event)">
      <rect x="2" y="2" width="236" height="12" fill="transparent" />
      <path class="rayas" d="M22 5h74M22 7h74M22 9h74M22 11h74M180 5h58M180 7h58M180 9h58M180 11h58" />
      <text x="138" y="10.8" class="titulo-texto">MIGUEWAMP</text>
    </g>
    <g class="boton" @click="emit('menu', $event)" title="Menú de MigueWamp">
      <rect class="cara" x="6" y="4" width="9" height="8" rx="1" />
      <path class="rayo-menu" d="M11.4 4.8 8.3 8.5h2l-1.1 2.9 3.6-4.2h-2.1l1.4-2.4z" />
    </g>
    <g class="boton-mini" @click="nativo()?.minimizar()"><rect x="243" y="4" width="9" height="8" rx="1" /><path d="M245.5 10h4" /></g>
    <g class="boton-mini" @click="nativo()?.cerrar()"><rect x="257" y="4" width="9" height="8" rx="1" /><path d="M259.5 6l4 4M263.5 6l-4 4" /></g>

    <!-- pantalla izquierda -->
    <rect x="9.5" y="21.5" width="95" height="42" class="pantalla" />
    <g v-if="!moderna">
      <rect x="10.5" y="22.5" width="7" height="40" fill="#14141c" />
      <text v-for="(l, i) in 'OAIDU'" :key="l" x="14" :y="30 + i * 7.5" class="barra-lateral" text-anchor="middle">{{ l }}</text>
    </g>
    <path v-if="motor.estado === 'sonando'" d="M22 27l5 3-5 3z" class="led" />
    <path v-else-if="motor.estado === 'pausado'" d="M22 27h1.6v6H22zM25 27h1.6v6H25z" class="led" />
    <rect v-else x="22" y="27.5" width="5" height="5" class="led" opacity=".35" />
    <g class="clic" @click="motor.restante = !motor.restante">
      <rect x="34" y="24" width="68" height="16" fill="transparent" />
      <text v-if="motor.restante && motor.estado !== 'detenido'" x="40" y="35.5" class="menos">-</text>
      <Digitos :texto="tiempo" :x="48" :y="25" />
    </g>
    <g class="clic" @click="osciloscopio = !osciloscopio">
      <rect x="22" y="43" width="78" height="18" fill="transparent" />
      <path :d="barras" fill="url(#g-vis)" />
      <path :d="picos" fill="#c8c8cc" />
      <path :d="onda" fill="none" stroke="var(--lcd)" stroke-width="0.9" />
    </g>

    <!-- información -->
    <rect x="110.5" y="22.5" width="155" height="12" class="pantalla" />
    <clipPath id="recorte-marquesina"><rect x="112" y="23" width="152" height="11" /></clipPath>
    <g clip-path="url(#recorte-marquesina)">
      <text ref="marquesina" :x="114 - desplazamiento" y="31" class="marquesina">{{ texto }}</text>
      <text v-if="desplazamiento" :x="114 - desplazamiento + anchoTexto + 30" y="31" class="marquesina">{{ texto }}</text>
    </g>
    <rect x="110.5" y="38.5" width="17" height="9" class="pantalla" />
    <text x="119" y="45.4" class="info" text-anchor="middle">{{ pistaActual()?.kbps || "" }}</text>
    <text x="130" y="45.4" class="etiqueta">kbps</text>
    <rect x="155.5" y="38.5" width="12" height="9" class="pantalla" />
    <text x="161.5" y="45.4" class="info" text-anchor="middle">{{ pistaActual()?.khz ? Math.round(pistaActual().khz) : "" }}</text>
    <text x="170" y="45.4" class="etiqueta">kHz</text>
    <text x="214" y="45.4" class="etiqueta apagada">mono</text>
    <text x="237" y="45.4" class="etiqueta" :class="estereo ? 'encendido' : 'apagada'">stereo</text>

    <!-- volumen -->
    <g class="clic" @pointerdown="volumen">
      <rect x="107" y="56" width="68" height="14" fill="transparent" />
      <rect x="107.5" y="59.5" width="67" height="7" rx="1" class="ranura" />
      <rect x="108.2" y="60.2" :width="65.6 * motor.volumen" height="5.6" rx=".8" fill="url(#g-volumen)" />
      <g :transform="`translate(${107 + 54 * motor.volumen} 57.5)`">
        <rect class="perilla" width="14" height="11" rx="1" />
        <path class="estrias" d="M5 3v5M7 3v5M9 3v5" />
      </g>
    </g>
    <!-- balance -->
    <g class="clic" @pointerdown="balance" @dblclick="motor.balance = 0">
      <rect x="177" y="56" width="38" height="14" fill="transparent" />
      <rect x="177.5" y="59.5" width="37" height="7" rx="1" class="ranura" />
      <rect x="178.2" y="60.2" width="35.6" height="5.6" rx=".8" fill="url(#g-balance)" :opacity="0.45 + Math.abs(motor.balance) * 0.55" />
      <g :transform="`translate(${177 + 24 * (motor.balance + 1) / 2} 57.5)`">
        <rect class="perilla" width="14" height="11" rx="1" />
        <path class="estrias" d="M5 3v5M7 3v5M9 3v5" />
      </g>
    </g>

    <!-- EQ y PL -->
    <g class="boton" @click="emit('alternar-eq')">
      <rect class="cara" x="219.5" y="58" width="23" height="11" rx="1" />
      <rect x="222.5" y="61.5" width="3" height="4" :class="props.eq ? 'led-on' : 'led-off'" />
      <text x="234.5" y="66" class="boton-texto">EQ</text>
    </g>
    <g class="boton" @click="emit('alternar-pl')">
      <rect class="cara" x="243.5" y="58" width="23" height="11" rx="1" />
      <rect x="246.5" y="61.5" width="3" height="4" :class="props.pl ? 'led-on' : 'led-off'" />
      <text x="258.5" y="66" class="boton-texto">PL</text>
    </g>

    <!-- posición (con holgura, baja y su zona táctil ocupa el espacio libre) -->
    <g class="clic" :transform="`translate(0 ${holgura})`" @pointerdown="buscar">
      <rect x="16" :y="71 - holgura * 0.7" width="248" :height="12 + holgura * 1.4" fill="transparent" />
      <rect x="16.5" y="74.5" width="247" height="6" rx="1" class="ranura" />
      <g v-if="motor.duracion && motor.estado !== 'detenido'" :transform="`translate(${16 + 219 * posicion} 72)`">
        <rect class="perilla-pos" width="29" height="10" rx="1" />
        <path class="estrias" d="M12 2.5v5M14.5 2.5v5M17 2.5v5" />
      </g>
    </g>

    <!-- transporte, aleatorio, repetir y logo: bajan con la holgura -->
    <g :transform="`translate(0 ${2 * holgura})`">
    <template v-if="!moderna">
      <g v-for="b in TRANSPORTE" :key="b.x" class="boton" :transform="`translate(${b.x} 88)`" @click="b.accion">
        <rect class="cara" x="0.5" y="0.5" :width="b.w - 1" height="17" />
        <path class="brillo" :d="`M1.3 16.7V1.3h${b.w - 2.6}`" />
        <path :d="b.icono" class="icono" transform="translate(0 0.5)" />
      </g>
      <g class="boton" transform="translate(136 89)" @click="agregarArchivos">
        <rect class="cara" x="0.5" y="0.5" width="21" height="15" />
        <path class="brillo" d="M1.3 14.7V1.3h19.4" />
        <path d="M6 8.5l5-4.5 5 4.5zM6 10.5h10v1.8H6z" class="icono" />
      </g>
    </template>
    <template v-else>
      <g v-for="(b, i) in TRANSPORTE" :key="b.x" class="boton" :transform="`translate(${14 + i * 21} 88)`" @click="b.accion">
        <circle class="cara" cx="10" cy="9" :r="i === 1 ? 9.5 : 8.5" />
        <path :d="b.icono" class="icono" transform="translate(-1.4 0) scale(1)" />
      </g>
      <g class="boton" transform="translate(124 88)" @click="agregarArchivos">
        <circle class="cara" cx="10" cy="9" r="8.5" />
        <path d="M5.5 9l4.5-4 4.5 4zM5.5 11h9v1.6h-9z" class="icono" />
      </g>
    </template>

    <!-- aleatorio y repetir -->
    <g class="boton" @click="motor.aleatorio = !motor.aleatorio">
      <rect class="cara" x="164.5" y="89.5" width="46" height="14" :rx="moderna ? 7 : 0" />
      <rect x="168" y="94.5" width="3" height="4" :class="motor.aleatorio ? 'led-on' : 'led-off'" />
      <text x="190.5" y="99.2" class="boton-texto">SHUFFLE</text>
    </g>
    <g class="boton" @click="motor.repetir = !motor.repetir">
      <rect class="cara" x="211.5" y="89.5" width="28" height="14" :rx="moderna ? 7 : 0" />
      <rect x="215" y="94.5" width="3" height="4" :class="motor.repetir ? 'led-on' : 'led-off'" />
      <path d="M221 94.5h10a2 2 0 0 1 0 4h-7" fill="none" stroke="var(--icono)" stroke-width="1" />
      <path d="M224 96.8l-2 1.7 2 1.7" fill="none" stroke="var(--icono)" stroke-width="1" />
    </g>

    <!-- logo: abre la biblioteca -->
    <g class="clic" @click="abrirVentana('biblioteca')">
      <rect x="248" y="87" width="20" height="19" fill="transparent" />
      <path d="M260 88.5l-7 9h5l-3 8.5 9-11h-5l3-6.5z" :fill="'var(--logo)'" stroke="#4a3a00" stroke-width="0.6" />
    </g>
    </g>
  </svg>
</template>
