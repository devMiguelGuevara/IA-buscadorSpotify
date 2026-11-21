<script setup>
// Una pieza de la skin en vectores: silueta nítida y sombreado suave por dentro.
// datos: { silueta, base, capas: [{ d, color }] } (ver cabezaVectores.js).
defineProps({
  datos: Object,
  id: String,
  suave: { type: Number, default: 1.2 }, // difuminado de las sombras, en unidades del dibujo
});
</script>

<template>
  <g>
    <defs>
      <clipPath :id="`${id}-borde`"><path :d="datos.silueta" /></clipPath>
      <filter :id="`${id}-suave`" x="-5%" y="-5%" width="110%" height="110%">
        <feGaussianBlur :stdDeviation="suave" />
      </filter>
    </defs>
    <path :d="datos.silueta" :fill="datos.base" />
    <g :clip-path="`url(#${id}-borde)`">
      <g :filter="`url(#${id}-suave)`">
        <path v-for="(c, i) in datos.capas" :key="i" :d="c.d" :fill="c.color" fill-rule="evenodd" />
      </g>
      <slot />
    </g>
  </g>
</template>
