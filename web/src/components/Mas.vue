<script setup>
// Marca al final de una lista larga: cuando aparece en pantalla pide más filas.
// Así se dibujan de a 50 y el resto llega al seguir bajando (rápido aunque la lista sea enorme).
import { onBeforeUnmount, onMounted, ref } from "vue";

defineProps({ quedan: { type: Number, default: 0 } });
const emit = defineEmits(["ver"]);
const el = ref(null);
let observador = null;
onMounted(() => {
  observador = new IntersectionObserver((e) => e.some((x) => x.isIntersecting) && emit("ver"), { rootMargin: "300px" });
  observador.observe(el.value);
});
onBeforeUnmount(() => observador?.disconnect());
</script>

<template>
  <div ref="el" class="mas" @click="emit('ver')">{{ quedan }} más…</div>
</template>
