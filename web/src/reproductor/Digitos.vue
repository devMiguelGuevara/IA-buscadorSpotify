<script setup>
// Dígitos de 7 segmentos en vectores, como la pantalla de Winamp. Cada celda mide 9 x 13.
const props = defineProps({ texto: String, x: Number, y: Number });

const T = 1.7;
const SEGMENTOS = {
  a: [1.9, 0, 5.2, T], b: [7.3, 1.5, T, 4.6], c: [7.3, 6.9, T, 4.6],
  d: [1.9, 11.3, 5.2, T], e: [0, 6.9, T, 4.6], f: [0, 1.5, T, 4.6], g: [1.9, 5.65, 5.2, T],
};
const MAPA = {
  0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd",
  6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg", "-": "g", " ": "",
};
const ANCHO = { ":": 5, default: 11 };

function celdas(texto) {
  let x = 0;
  return [...(texto || "")].map((ch) => {
    const celda = { ch, x, on: MAPA[ch] ?? "" };
    x += ANCHO[ch] ?? ANCHO.default;
    return celda;
  });
}
</script>

<template>
  <g :transform="`translate(${x} ${y})`">
    <g v-for="(c, i) in celdas(texto)" :key="i" :transform="`translate(${c.x} 0)`">
      <template v-if="c.ch === ':'">
        <rect x="1.5" y="3" :width="T" :height="T" class="seg on" />
        <rect x="1.5" y="8.5" :width="T" :height="T" class="seg on" />
      </template>
      <template v-else>
        <rect v-for="(s, k) in SEGMENTOS" :key="k" :x="s[0]" :y="s[1]" :width="s[2]" :height="s[3]"
              rx="0.5" class="seg" :class="{ on: c.on.includes(k) }" />
      </template>
    </g>
  </g>
</template>
