<script setup>
// Menú principal de MigueWamp (clic derecho, botón de menú o el sol de la cabeza).
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { fijarForma, rectDe } from "../ventanas/nativo.js";

const props = defineProps({ x: Number, y: Number, items: Array });
const emit = defineEmits(["cerrar"]);
const caja = ref(null);
const pos = ref({ left: props.x + "px", top: props.y + "px" });

function fuera(e) {
  if (!caja.value?.contains(e.target)) emit("cerrar");
}
function tecla(e) {
  if (e.key === "Escape") emit("cerrar");
}
onMounted(async () => {
  await nextTick();
  const r = caja.value.getBoundingClientRect();
  pos.value = {
    left: Math.max(2, Math.min(props.x, window.innerWidth - r.width - 2)) + "px",
    top: Math.max(2, Math.min(props.y, window.innerHeight - r.height - 2)) + "px",
  };
  await nextTick();
  fijarForma("menu", rectDe(caja.value)); // el menú cuenta como parte de la ventana
  setTimeout(() => window.addEventListener("pointerdown", fuera, true));
  window.addEventListener("keydown", tecla, true);
});
onBeforeUnmount(() => {
  fijarForma("menu", null);
  window.removeEventListener("pointerdown", fuera, true);
  window.removeEventListener("keydown", tecla, true);
});
function elegir(it) {
  emit("cerrar");
  it.accion?.();
}
</script>

<template>
  <div ref="caja" class="menu-contexto" :style="pos" @contextmenu.prevent>
    <template v-for="(it, k) in items" :key="k">
      <div v-if="it === '-'" class="sep"></div>
      <div v-else-if="it.grupo" class="grupo">{{ it.grupo }}</div>
      <div v-else class="item" :class="{ marcado: it.marcado }" @click="elegir(it)">
        <span>{{ it.texto }}</span><span class="atajo">{{ it.atajo || "" }}</span>
      </div>
    </template>
  </div>
</template>
