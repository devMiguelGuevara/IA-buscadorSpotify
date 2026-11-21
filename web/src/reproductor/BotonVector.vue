<script setup>
// Botones de la skin "Cabeza" dibujados en vectores (normal / encima / presionado).
import { ref } from "vue";

const props = defineProps({
  x: Number, y: Number, w: Number, h: Number,
  forma: String, // anterior, reproducir, pausa, detener, siguiente, menu, minimizar, cerrar, x, eq, lista, pestana-izq, pestana-der, reset
  abierto: Boolean, // pestañas de los cajones: la flecha apunta hacia dentro
  titulo: String,
});
const emit = defineEmits(["click"]);
let n = 0;
const id = `bv${Math.random().toString(36).slice(2, 8)}${n++}`;
const estado = ref("normal");

// colores por estado de los botones redondos: [claro, medio, oscuro]
const BOLAS = {
  normal: ["#f4c8ff", "#c24fe0", "#5d1580"],
  encima: ["#c8f4ff", "#2fb6f0", "#0b4f86"],
  presionado: ["#d8ffd0", "#5ccc54", "#1d6b16"],
};
const BOLA_MENU = { ...BOLAS, normal: ["#fff2b0", "#f2b11d", "#8a5200"] };
const redondo = ["anterior", "reproducir", "pausa", "detener", "siguiente", "menu"];
const bola = () => (props.forma === "menu" ? BOLA_MENU : BOLAS)[estado.value];
const brillo = () => (estado.value === "encima" ? "#7ad9ff" : estado.value === "presionado" ? "#d6ff5c" : "#b8ff3a");
</script>

<template>
  <svg class="bv" :style="{ left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' }"
       :viewBox="`0 0 ${w} ${h}`" :title="titulo"
       @pointerenter="estado = 'encima'" @pointerleave="estado = 'normal'"
       @pointerdown.stop="estado = 'presionado'" @pointerup="estado = 'encima'" @click.stop="emit('click', $event)">
    <title>{{ titulo }}</title>

    <!-- ===== botones redondos del reproductor ===== -->
    <template v-if="redondo.includes(forma)">
      <defs>
        <radialGradient :id="`${id}-aro`" cx="40%" cy="30%" r="75%">
          <stop offset="0" stop-color="#f0ffb8" /><stop offset=".55" stop-color="#8ee012" /><stop offset="1" stop-color="#3f8a00" />
        </radialGradient>
        <radialGradient :id="`${id}-bola`" cx="38%" cy="30%" r="72%">
          <stop offset="0" :stop-color="bola()[0]" /><stop offset=".5" :stop-color="bola()[1]" /><stop offset="1" :stop-color="bola()[2]" />
        </radialGradient>
      </defs>
      <circle cx="12.5" cy="12.5" r="12" :fill="`url(#${id}-aro)`" />
      <circle cx="12.5" cy="12.5" r="9.4" fill="#2c6400" opacity=".55" />
      <circle cx="12.5" cy="12.6" r="8.6" :fill="`url(#${id}-bola)`" />
      <ellipse cx="11" cy="8.3" rx="4.6" ry="2.4" fill="#fff" opacity=".45" />
      <g fill="#0c0c0c" :transform="estado === 'presionado' ? 'translate(.4 .4)' : ''">
        <template v-if="forma === 'anterior'">
          <rect x="7.4" y="8.6" width="1.6" height="8" /><path d="M13.2 8.6v8L9.2 12.6zM17.6 8.6v8l-4-4z" />
        </template>
        <path v-else-if="forma === 'reproducir'" d="M10.2 8.2v8.8l7-4.4z" />
        <template v-else-if="forma === 'pausa'">
          <rect x="9.3" y="8.4" width="2.4" height="8.4" /><rect x="13.5" y="8.4" width="2.4" height="8.4" />
        </template>
        <rect v-else-if="forma === 'detener'" x="8.8" y="8.9" width="7.4" height="7.4" />
        <template v-else-if="forma === 'siguiente'">
          <path d="M7.6 8.6v8l4-4zM12 8.6v8l4-4z" /><rect x="16.2" y="8.6" width="1.6" height="8" />
        </template>
        <g v-else stroke="#0c0c0c" stroke-width="1.5" stroke-linecap="round">
          <path v-for="a in 8" :key="a" :transform="`rotate(${a * 22.5} 12.5 12.6)`" d="M12.5 7.4v10.4" />
        </g>
      </g>
    </template>

    <!-- ===== minimizar / cerrar (arriba de la cabeza) ===== -->
    <template v-else-if="forma === 'minimizar' || forma === 'cerrar'">
      <rect x=".5" y=".5" :width="w - 1" :height="h - 1" rx="2"
            :fill="estado === 'normal' ? '#7fd61c' : estado === 'encima' ? '#22d63a' : '#0fae22'" stroke="#c6ff6a" />
      <rect x="2" y="2" :width="w - 4" :height="h - 4" rx="1" fill="#000" opacity=".08" />
      <rect v-if="forma === 'minimizar'" x="3.5" :y="h - 5.5" :width="w - 7" height="2" fill="#1f4a00" />
      <path v-else :d="`M4 4.5L${w - 4} ${h - 4.5}M${w - 4} 4.5L4 ${h - 4.5}`" stroke="#1f4a00" stroke-width="2.2" stroke-linecap="round" />
    </template>

    <!-- ===== cerrar cajón ===== -->
    <path v-else-if="forma === 'x'" d="M2.2 2.2L8.8 8.8M8.8 2.2L2.2 8.8" stroke-width="2.4" stroke-linecap="round"
          :stroke="estado === 'normal' ? '#173d00' : '#d6ff8a'" />

    <!-- ===== mostrar ecualizador / lista ===== -->
    <template v-else-if="forma === 'eq' || forma === 'lista'">
      <rect :width="w" :height="h" rx="1.5" :fill="estado === 'presionado' ? '#2f8f00' : '#3f9c06'" />
      <g v-if="forma === 'eq'" :fill="estado === 'encima' ? '#56d8ff' : '#c4ff3a'">
        <rect x="4" y="5" width="2" height="10" /><rect x="7.5" y="9" width="2" height="6" /><rect x="11" y="6.5" width="2" height="8.5" />
        <rect x="14.5" y="10" width="2" height="5" /><rect x="3" y="15" width="14.5" height="1.6" />
      </g>
      <g v-else fill="none" :stroke="estado === 'encima' ? '#56d8ff' : '#c4ff3a'" stroke-width="1.4">
        <path d="M5 3.5h6.5l3 3V16.5H5z" /><path d="M7.5 8h5M7.5 10.5h5M7.5 13h5" />
      </g>
    </template>

    <!-- ===== pestañas laterales de los cajones (hoja con rayas y flecha) ===== -->
    <template v-else-if="forma === 'pestana-izq' || forma === 'pestana-der'">
      <defs>
        <linearGradient :id="`${id}-hoja`" x1="0" x2="1">
          <stop offset="0" stop-color="#2e8a00" /><stop offset=".55" :stop-color="estado === 'normal' ? '#5ec210' : '#79dd22'" /><stop offset="1" stop-color="#b6ff3c" />
        </linearGradient>
        <pattern :id="`${id}-rayas`" width="4" height="2" patternUnits="userSpaceOnUse">
          <rect width="4" height="1" fill="#1d6200" opacity=".35" />
        </pattern>
      </defs>
      <g :transform="forma === 'pestana-der' ? `translate(${w} 0) scale(-1 1)` : ''">
        <path :d="`M${w * .7} 1C${w * 1.05} ${h * .3} ${w * 1.02} ${h * .7} ${w * .62} ${h - 1}C${w * .05} ${h * .72} ${-w * .02} ${h * .3} ${w * .7} 1Z`"
              :fill="`url(#${id}-hoja)`" stroke="#1f5600" stroke-width=".6" />
        <path :d="`M${w * .7} 1C${w * 1.05} ${h * .3} ${w * 1.02} ${h * .7} ${w * .62} ${h - 1}C${w * .05} ${h * .72} ${-w * .02} ${h * .3} ${w * .7} 1Z`"
              :fill="`url(#${id}-rayas)`" />
        <!-- la flecha apunta hacia fuera si está cerrado (abrir) y hacia dentro si está abierto -->
        <path :d="abierto ? `M${w * .72} ${h / 2 - 6}v12l-7-6z` : `M${w * .3} ${h / 2 - 6}v12l7-6z`"
              :fill="estado === 'presionado' ? '#e8ff9a' : '#c8ff4a'" stroke="#2e7a00" stroke-width=".5" />
      </g>
    </template>

    <!-- ===== reset del ecualizador ===== -->
    <text v-else-if="forma === 'reset'" :x="w / 2" :y="h - 2" text-anchor="middle"
          font-family="Tahoma, Verdana, sans-serif" font-size="9.5" :fill="estado === 'normal' ? '#d6f0ff' : '#ffffff'">reset</text>
  </svg>
</template>

<style>
.bv { position: absolute; cursor: pointer; overflow: visible; }
</style>
