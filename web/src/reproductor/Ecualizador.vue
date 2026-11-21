<script setup>
// Ecualizador gráfico de 10 bandas de MigueWamp, en vectores (lienzo de 275 x 116).
import { computed, ref } from "vue";
import { aplicarPreset, motor, PRESETS } from "./motor.js";
import { arrastrarVentana } from "../ventanas/nativo.js";

const props = defineProps({ skin: String });
const emit = defineEmits(["cerrar", "menu"]);
const svg = ref(null);
const menu = ref(false);
const moderna = computed(() => props.skin === "moderna");
const ETIQUETAS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"];
const X_BANDA = (i) => 79 + i * 18;
const ALTO = 51, Y0 = 41;
const aY = (db) => Y0 + ((12 - db) / 24) * ALTO;

function deslizar(e, aplicar) {
  if (e.button !== 0) return;
  e.preventDefault();
  const valor = (ev) => {
    const p = svg.value.createSVGPoint();
    p.x = ev.clientX;
    p.y = ev.clientY;
    const y = p.matrixTransform(svg.value.getScreenCTM().inverse()).y;
    const db = 12 - ((Math.min(Y0 + ALTO, Math.max(Y0, y - 5)) - Y0) / ALTO) * 24;
    return Math.round(db * 2) / 2;
  };
  aplicar(valor(e));
  const mover = (ev) => aplicar(valor(ev));
  const soltar = () => {
    window.removeEventListener("pointermove", mover);
    window.removeEventListener("pointerup", soltar);
  };
  window.addEventListener("pointermove", mover);
  window.addEventListener("pointerup", soltar);
}
const banda = (i) => (e) => deslizar(e, (db) => { motor.bandas[i] = db; motor.preset = ""; });
const preamp = (e) => deslizar(e, (db) => (motor.preamp = db));

const curva = computed(() => {
  const pts = motor.bandas.map((db, i) => [91 + i * 11.4, 27 - (db / 12) * 8]);
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
    d += `C${x0 + 5} ${y0} ${x1 - 5} ${y1} ${x1} ${y1}`;
  }
  return d;
});
</script>

<template>
  <svg ref="svg" class="wa-svg" viewBox="0 0 275 116" @contextmenu.prevent="emit('menu', $event)">
    <rect class="marco" x="0.5" y="0.5" width="274" height="115" />
    <rect class="marco-luz" x="1.2" y="1.2" width="272.6" height="113.6" />

    <g @pointerdown="arrastrarVentana">
      <rect x="2" y="2" width="250" height="12" fill="transparent" />
      <path class="rayas" d="M8 5h56M8 7h56M8 9h56M8 11h56M212 5h40M212 7h40M212 9h40M212 11h40" />
      <text x="138" y="10.8" class="titulo-texto">MIGUEWAMP EQUALIZER</text>
    </g>
    <g class="boton-mini" @click="emit('cerrar')"><rect x="257" y="4" width="9" height="8" rx="1" /><path d="M259.5 6l4 4M263.5 6l-4 4" /></g>

    <!-- ON / AUTO / PRESETS -->
    <g class="boton" @click="motor.eqActivo = !motor.eqActivo">
      <rect class="cara" x="14.5" y="18.5" width="26" height="12" :rx="moderna ? 6 : 0" />
      <rect x="18" y="22.5" width="3" height="4" :class="motor.eqActivo ? 'led-on' : 'led-off'" />
      <text x="31" y="27.2" class="boton-texto">ON</text>
    </g>
    <g class="boton" @click="motor.nivelar = !motor.nivelar">
      <title>Volumen nivelado: todas las canciones a la misma sonoridad{{ motor.nivelar && motor.nivelDb ? ` (esta: ${motor.nivelDb > 0 ? "+" : ""}${motor.nivelDb} dB)` : "" }}</title>
      <rect class="cara" x="41.5" y="18.5" width="33" height="12" :rx="moderna ? 6 : 0" />
      <rect x="45" y="22.5" width="3" height="4" :class="motor.nivelar ? 'led-on' : 'led-off'" />
      <text x="61" y="27.2" class="boton-texto">AUTO</text>
    </g>
    <g class="boton" @click="menu = !menu">
      <rect class="cara" x="216.5" y="18.5" width="46" height="12" :rx="moderna ? 6 : 0" />
      <text x="239.5" y="27.2" class="boton-texto">PRESETS</text>
    </g>

    <!-- gráfico -->
    <rect x="86.5" y="17.5" width="118" height="19" class="pantalla" />
    <path d="M88 27h115" stroke="var(--lcd-apagado)" stroke-width=".7" />
    <path d="M88 19v16M203 19v16" stroke="var(--lcd-apagado)" stroke-width=".5" />
    <path :d="curva" fill="none" stroke="var(--curva)" stroke-width="1" />
    <text x="201" y="35" class="info" text-anchor="end" style="font-size: 4.8px">{{ motor.preset }}</text>

    <!-- escala -->
    <text x="62" y="44.6" class="etiqueta" text-anchor="end">+12 db</text>
    <text x="62" y="69" class="etiqueta" text-anchor="end">+0 db</text>
    <text x="62" y="93.6" class="etiqueta" text-anchor="end">-12 db</text>
    <path d="M64 42.5h4M64 67h4M64 91.5h4" stroke="var(--etiqueta)" stroke-width=".6" />

    <!-- preamp -->
    <g class="clic" @pointerdown="preamp" @dblclick="motor.preamp = 0">
      <rect x="18" y="38" width="22" height="66" fill="transparent" />
      <rect x="26" y="40.5" width="6" height="61" class="ranura" />
      <rect x="26.8" y="41.3" width="4.4" height="59.4" fill="url(#g-eq)" />
      <g :transform="`translate(23 ${aY(motor.preamp)})`">
        <rect class="perilla" width="12" height="10" rx="1" /><path class="estrias" d="M3.5 4h5M3.5 6h5" />
      </g>
    </g>
    <text x="29" y="111" class="etiqueta" text-anchor="middle">PREAMP</text>

    <!-- bandas -->
    <g v-for="(db, i) in motor.bandas" :key="i" class="clic" @pointerdown="banda(i)($event)" @dblclick="motor.bandas[i] = 0">
      <rect :x="X_BANDA(i) - 7" y="38" width="16" height="66" fill="transparent" />
      <rect :x="X_BANDA(i) - 2" y="40.5" width="6" height="61" class="ranura" />
      <rect :x="X_BANDA(i) - 1.2" y="41.3" width="4.4" height="59.4" fill="url(#g-eq)" :opacity="motor.eqActivo ? 1 : 0.45" />
      <g :transform="`translate(${X_BANDA(i) - 5} ${aY(db)})`">
        <rect class="perilla" width="12" height="10" rx="1" /><path class="estrias" d="M3.5 4h5M3.5 6h5" />
      </g>
      <text :x="X_BANDA(i) + 1" y="111" class="etiqueta" text-anchor="middle">{{ ETIQUETAS[i] }}</text>
    </g>

    <!-- menú de presets -->
    <g v-if="menu" class="menu">
      <rect x="180.5" y="31.5" width="82" :height="Object.keys(PRESETS).length * 9 + 2" />
      <g v-for="(nombre, k) in Object.keys(PRESETS)" :key="nombre" class="menu-item" @click="aplicarPreset(nombre); menu = false">
        <rect x="181.5" :y="32.5 + k * 9" width="80" height="9" />
        <text x="185" :y="39 + k * 9">{{ nombre }}</text>
      </g>
    </g>
  </svg>
</template>
