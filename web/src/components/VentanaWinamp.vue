<script setup>
// Marco Winamp para una ventana suelta del escritorio: ocupa toda la ventana del sistema,
// la barra de título la mueve y la esquina la redimensiona.
import { arrastrarVentana, redimensionarVentana } from "../ventanas/nativo.js";

defineProps({ titulo: String, redimensionable: { type: Boolean, default: true } });
const emit = defineEmits(["cerrar"]);
const agrandar = (e) => redimensionarVentana(e, (w, h) => [Math.max(340, w), Math.max(220, h)]);
</script>

<template>
  <div class="wa-ventana">
    <div class="wa-titulo" @pointerdown="arrastrarVentana">
      <span class="wa-rayas"></span>
      <span class="wa-texto">{{ titulo }}</span>
      <span class="wa-rayas"></span>
      <button class="wa-x" title="Cerrar" @pointerdown.stop @click="emit('cerrar')"></button>
    </div>
    <div class="wa-cuerpo"><slot /></div>
    <div class="wa-pie" v-if="$slots.pie"><slot name="pie" /></div>
    <div v-if="redimensionable" class="wa-redim" @pointerdown="agrandar"></div>
  </div>
</template>
