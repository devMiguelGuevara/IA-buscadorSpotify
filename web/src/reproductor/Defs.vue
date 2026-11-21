<script setup>
// Degradados compartidos por todas las piezas del reproductor. Toman los colores de la skin.
defineProps({ skin: String });
const VIS = {
  clasica: ["#1aa51a", "#d8d800", "#e8361c"],
  moderna: ["#2a58b6", "#7fb0ff", "#ffffff"],
};
</script>

<template>
  <svg width="0" height="0" style="position: absolute">
    <defs>
      <linearGradient id="g-marco" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" style="stop-color: var(--marco1)" /><stop offset="1" style="stop-color: var(--marco2)" />
      </linearGradient>
      <linearGradient id="g-boton" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" style="stop-color: var(--boton1)" /><stop offset="1" style="stop-color: var(--boton2)" />
      </linearGradient>
      <linearGradient id="g-perilla" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" style="stop-color: var(--perilla1)" /><stop offset="1" style="stop-color: var(--perilla2)" />
      </linearGradient>
      <linearGradient id="g-posicion" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" style="stop-color: var(--pos1)" /><stop offset="1" style="stop-color: var(--pos2)" />
      </linearGradient>
      <linearGradient id="g-volumen" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" style="stop-color: var(--vol1)" /><stop offset="1" style="stop-color: var(--vol2)" />
      </linearGradient>
      <linearGradient id="g-balance" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" style="stop-color: var(--bal1)" /><stop offset="1" style="stop-color: var(--bal2)" />
      </linearGradient>
      <linearGradient id="g-eq" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" style="stop-color: var(--eq-alto)" /><stop offset="1" style="stop-color: var(--eq-bajo)" />
      </linearGradient>
      <linearGradient id="g-vis" x1="0" y1="60" x2="0" y2="44" gradientUnits="userSpaceOnUse">
        <stop offset="0" :stop-color="(VIS[skin] || VIS.clasica)[0]" />
        <stop offset=".55" :stop-color="(VIS[skin] || VIS.clasica)[1]" />
        <stop offset="1" :stop-color="(VIS[skin] || VIS.clasica)[2]" />
      </linearGradient>
    </defs>
  </svg>
</template>
