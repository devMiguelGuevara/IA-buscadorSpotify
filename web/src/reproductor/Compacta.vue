<script setup>
// Vista compacta vertical: una sola columna. El reproductor queda siempre arriba y los
// módulos (lista, biblioteca, descargas, agregar, ecualizador) se cambian con pestañas.
// En el escritorio es la skin angosta; en el navegador, una página propia.
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import Defs from "./Defs.vue";
import Principal from "./Principal.vue";
import Ecualizador from "./Ecualizador.vue";
import Lista from "./Lista.vue";
import MenuContexto from "./MenuContexto.vue";
import Biblioteca from "../components/Biblioteca.vue";
import Descargas from "../components/Descargas.vue";
import AbrirUbicacion from "../components/AbrirUbicacion.vue";
import { agregar, motor, programarDormir, reemplazar } from "./motor.js";
import { alAbrirVentana, nativo } from "../ventanas/nativo.js";
import { conServicio, estadoPlataforma, pestanas } from "../plataforma.js";
import { alTerminarDescarga, cargarBiblioteca, cargarPlaylists, descargasActivas, estado, revisarDescargas } from "../estado.js";

const props = defineProps({
  base: { type: String, default: "clasica" }, // aspecto: clásica o moderna
  sola: { type: Boolean, default: false },     // página propia (en el navegador), sin el escritorio
});
const emit = defineEmits(["skin", "menu-escritorio"]);

// Buscar: pegar enlaces o canciones y descargar. Descargas: el avance y lo ya bajado.
const PESTANAS_TODAS = [["lista", "Lista"], ["biblioteca", "Biblioteca"], ["ubicacion", "Buscar"], ["descargas", "Descargas"], ["eq", "EQ"]];
const PESTANAS = computed(() => pestanas(PESTANAS_TODAS));
const pestana = ref("lista");
const raiz = ref(null);
const ancho = ref(375);
const u = computed(() => ancho.value / 275);

// Los botones que en el escritorio abren otra ventana, aquí cambian de pestaña.
alAbrirVentana((nombre) => {
  if (PESTANAS.value.some(([id]) => id === nombre)) pestana.value = nombre;
  else if (nombre === "laboratorio") nativo()?.abrir("laboratorio"); // solo existe en el escritorio
});

let observador = null, reloj = 0;
onMounted(() => {
  observador = new ResizeObserver(([e]) => (ancho.value = e.contentRect.width));
  observador.observe(raiz.value);
  alTerminarDescarga((pistas) => agregar(pistas, motor.estado === "detenido" && motor.actual < 0));
  if (conServicio) {
    cargarBiblioteca();
    cargarPlaylists();
    revisarDescargas();
  }
  const revisar = () => (conServicio || estadoPlataforma.descargas) && (pestana.value === "descargas" || descargasActivas().length) && revisarDescargas();
  if (props.sola) reloj = setInterval(revisar, 1500);
});
onBeforeUnmount(() => {
  observador?.disconnect();
  clearInterval(reloj);
  alAbrirVentana(null);
});
watch(() => props.base, (b) => props.sola && (document.documentElement.dataset.skin = b), { immediate: true });

// Menú (clic derecho o el botón de menú del reproductor).
const menu = ref(null);
// Opciones de reproducción en botones (pestaña EQ): no repiten nada del ecualizador.
const OPCIONES = [
  { titulo: "Velocidad", valores: [[0.75, "0,75×"], [1, "1×"], [1.25, "1,25×"], [1.5, "1,5×"]],
    actual: () => motor.velocidad, elegir: (v) => (motor.velocidad = v) },
  { titulo: "Fundido entre canciones", valores: [[0, "No"], [3, "3 s"], [6, "6 s"], [10, "10 s"]],
    actual: () => motor.fundido, elegir: (v) => (motor.fundido = v) },
  { titulo: "Dormir", valores: [[0, "No"], [15, "15 min"], [30, "30 min"], [60, "60 min"], ["cancion", "Al terminar"]],
    actual: () => motor.dormir, elegir: (v) => programarDormir(v) },
];
const quedaDormir = computed(() => (motor.dormirFin ? Math.max(1, Math.ceil((motor.dormirFin - Date.now()) / 60000)) : 0));
function abrirMenu(e) {
  menu.value = {
    x: e?.clientX ?? 20, y: e?.clientY ?? 20,
    items: [
      { grupo: "Aspecto" },
      { texto: "Clásica", marcado: props.base === "clasica", accion: () => emit("skin", "clasica") },
      { texto: "Moderna", marcado: props.base === "moderna", accion: () => emit("skin", "moderna") },
      ...(props.sola ? [] : [{ texto: "Volver al reproductor completo", accion: () => emit("skin", "completo") }]),
      ...(nativo() ? ["-", { texto: "Laboratorio de mejora…", accion: () => nativo().abrir("laboratorio") },
        { texto: "Salir", accion: () => nativo().cerrar() }] : []),
    ],
  };
}

const reproducirYVer = (pistas) => { reemplazar(pistas); pestana.value = "lista"; };
const encolarYAvisar = (pistas) => agregar(pistas);
const cantidad = computed(() => ({
  lista: motor.lista.length || "",
  descargas: descargasActivas().length ? "●" : "",
}));
</script>

<template>
  <div ref="raiz" class="compacta" :class="{ sola }" :data-skin="base" :style="{ '--u': u }">
    <Defs :skin="base" />
    <header class="c-reproductor">
      <Principal :eq="pestana === 'eq'" :pl="pestana === 'lista'" :skin="base" :holgura="9"
                 @alternar-eq="pestana = 'eq'" @alternar-pl="pestana = 'lista'" @menu="abrirMenu" />
      <nav class="c-pestanas">
        <button v-for="[id, nombre] in PESTANAS" :key="id" :class="{ activa: pestana === id }" @click="pestana = id">
          {{ nombre }}<small v-if="cantidad[id]"> {{ cantidad[id] }}</small>
        </button>
      </nav>
    </header>
    <main class="c-modulo">
      <Lista v-if="pestana === 'lista'" @menu="abrirMenu" @cerrar="pestana = 'lista'" />
      <Biblioteca v-else-if="pestana === 'biblioteca'" compacta @reproducir="reproducirYVer" @encolar="encolarYAvisar" />
      <Descargas v-else-if="pestana === 'descargas'" @abrir="(n) => (pestana = n)" />
      <AbrirUbicacion v-else-if="pestana === 'ubicacion'" @iniciada="pestana = 'descargas'" @reproducir="reproducirYVer"
                      @cerrar="pestana = 'lista'" />
      <template v-else-if="pestana === 'eq'">
        <Ecualizador :skin="base" @menu="abrirMenu" @cerrar="pestana = 'lista'" />
        <!-- Opciones de reproducción (lo que no está en el ecualizador) -->
        <div class="c-eq">
          <div v-for="o in OPCIONES" :key="o.titulo" class="c-opcion">
            <div class="c-opcion-titulo">{{ o.titulo }}<span v-if="o.titulo === 'Dormir' && quedaDormir"> · faltan {{ quedaDormir }} min</span></div>
            <div class="c-opcion-botones">
              <button v-for="[v, etiqueta] in o.valores" :key="v" class="wa-boton"
                      :class="{ 'wa-principal': o.actual() === v }" @click="o.elegir(v)">{{ etiqueta }}</button>
            </div>
          </div>
        </div>
      </template>
    </main>
    <MenuContexto v-if="menu" v-bind="menu" @cerrar="menu = null" />
  </div>
</template>
