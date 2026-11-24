<script setup>
// Página de una ventana suelta: biblioteca, descargas o abrir ubicación.
// Lo que se manda a reproducir llega al reproductor a través del servicio interno.
import { onBeforeUnmount, onMounted } from "vue";
import Biblioteca from "../components/Biblioteca.vue";
import Descargas from "../components/Descargas.vue";
import AbrirUbicacion from "../components/AbrirUbicacion.vue";
import Laboratorio from "../components/Laboratorio.vue";
import Presentacion from "../components/Presentacion.vue";
import Letra from "../components/Letra.vue";
import { cargarBiblioteca, descargasActivas, revisarDescargas } from "../estado.js";
import { abrirVentana, encolarEnReproductor, nativo } from "./nativo.js";

const props = defineProps({ nombre: String });
const cerrar = () => (nativo() ? nativo().cerrar() : window.close());
const reproducir = (pistas) => encolarEnReproductor("reproducir", pistas);
const encolar = (pistas) => encolarEnReproductor("encolar", pistas);

function iniciada() {
  abrirVentana("descargas");
  cerrar();
}

function teclas(e) {
  if (e.key === "Escape" && props.nombre === "ubicacion") cerrar();
}

// Las ventanas sueltas toman la skin activa del reproductor (y la siguen si cambia).
async function seguirSkin() {
  const r = (await nativo()?.leer_ajustes())?.reproductor;
  const skin = r?.skin === "compacta" ? r.baseCompacta || "clasica" : r?.skin;
  if (skin) document.documentElement.dataset.skin = skin;
}

let reloj = 0, vueltas = 0;
onMounted(() => {
  if (props.nombre === "presentacion" || props.nombre === "letra") return; // nada que cargar: solo esa vista
  if (nativo()) seguirSkin();
  else window.addEventListener("pywebviewready", seguirSkin, { once: true });
  window.addEventListener("keydown", teclas);
  cargarBiblioteca();
  revisarDescargas();
  reloj = setInterval(() => {
    if (++vueltas % 2 === 0) seguirSkin();
    if (props.nombre === "descargas" || descargasActivas().length) revisarDescargas();
  }, 1500);
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", teclas);
  clearInterval(reloj);
});
</script>

<template>
  <Presentacion v-if="nombre === 'presentacion'" @fin="cerrar" />
  <Letra v-else-if="nombre === 'letra'" remoto @cerrar="cerrar" />
  <Biblioteca v-else-if="nombre === 'biblioteca'" @cerrar="cerrar" @reproducir="reproducir" @encolar="encolar" @abrir="abrirVentana" />
  <Descargas v-else-if="nombre === 'descargas'" @cerrar="cerrar" @abrir="abrirVentana" />
  <Laboratorio v-else-if="nombre === 'laboratorio'" @cerrar="cerrar" />
  <AbrirUbicacion v-else @cerrar="cerrar" @iniciada="iniciada" @reproducir="reproducir" />
</template>
