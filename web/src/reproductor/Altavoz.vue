<script setup>
// Altavoz de los cajones de la skin "Cabeza": aro plateado, cono gris y tapa central.
defineProps({ cx: Number, cy: Number, r: Number });
</script>

<template>
  <g>
    <defs>
      <radialGradient id="alt-aro" cx="40%" cy="30%" r="80%">
        <stop offset="0" stop-color="#f2f2f4" /><stop offset=".6" stop-color="#a9a9ad" /><stop offset="1" stop-color="#4e4e52" />
      </radialGradient>
      <radialGradient id="alt-cono" cx="45%" cy="40%" r="70%">
        <stop offset="0" stop-color="#e8e2da" /><stop offset=".55" stop-color="#9b958c" /><stop offset="1" stop-color="#4a4640" />
      </radialGradient>
      <radialGradient id="alt-tapa" cx="40%" cy="35%" r="70%">
        <stop offset="0" stop-color="#ffffff" /><stop offset=".7" stop-color="#bdb8b0" /><stop offset="1" stop-color="#77726a" />
      </radialGradient>
    </defs>
    <circle :cx="cx" :cy="cy + 1" :r="r" fill="#1d4a00" opacity=".5" />
    <circle :cx="cx" :cy="cy" :r="r" fill="url(#alt-aro)" />
    <circle :cx="cx" :cy="cy" :r="r * .8" fill="#1b1b1c" />
    <circle :cx="cx" :cy="cy" :r="r * .7" fill="url(#alt-cono)" />
    <circle :cx="cx" :cy="cy" :r="r * .3" fill="url(#alt-tapa)" />
    <circle v-for="a in 4" :key="a" :cx="cx + Math.cos(a * 1.5708 + .785) * r * .88" :cy="cy + Math.sin(a * 1.5708 + .785) * r * .88"
            r="1.1" fill="#333" />
  </g>
</template>
