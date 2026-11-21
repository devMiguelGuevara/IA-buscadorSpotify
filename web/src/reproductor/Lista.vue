<script setup>
// Lista de reproducción estilo Winamp. Sus medidas dependen de --u (la escala), así que
// se ve nítida a cualquier tamaño.
import { computed, ref } from "vue";
import { cargar, mmss, motor, quitar, reemplazar, vaciar } from "./motor.js";
import { api, pista } from "../api.js";
import { agregarArchivos, agregarCarpeta } from "./disco.js";
import { abrirVentana, arrastrarVentana } from "../ventanas/nativo.js";

const emit = defineEmits(["cerrar", "menu"]);
const menu = ref(null);
let ultimo = -1;

const total = computed(() => motor.lista.reduce((s, p) => s + (p.duracion || 0), 0));

function clic(i, e) {
  let s = new Set(e.ctrlKey ? motor.seleccion : []);
  if (e.shiftKey && ultimo >= 0) {
    s = new Set();
    for (let k = Math.min(ultimo, i); k <= Math.max(ultimo, i); k++) s.add(k);
  } else if (e.ctrlKey && s.has(i)) s.delete(i);
  else s.add(i);
  motor.seleccion = s;
  if (!e.shiftKey) ultimo = i;
}
const quitarSeleccion = () => motor.seleccion.size && quitar([...motor.seleccion]);
const seleccionarTodo = () => (motor.seleccion = new Set(motor.lista.map((_, i) => i)));

function reordenar(fn) {
  const actual = motor.lista[motor.actual];
  motor.lista = fn([...motor.lista]);
  motor.actual = motor.lista.indexOf(actual);
  motor.seleccion = new Set();
  menu.value = null;
}
const porCampo = (campo) => (l) => l.sort((a, b) => (a[campo] || "").localeCompare(b[campo] || ""));
const aleatorizar = (l) => {
  for (let i = l.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [l[i], l[j]] = [l[j], l[i]];
  }
  return l;
};

const MENUS = {
  add: [
    ["Agregar archivos…", agregarArchivos],
    ["Agregar carpeta…", agregarCarpeta],
    ["Desde la biblioteca…  Alt+L", () => abrirVentana("biblioteca")],
    ["Abrir ubicación (enlaces)…  Ctrl+L", () => abrirVentana("ubicacion")],
    ["Descargas…  Alt+D", () => abrirVentana("descargas")],
  ],
  misc: [
    ["Ordenar por título", () => reordenar(porCampo("titulo"))],
    ["Ordenar por artista", () => reordenar(porCampo("artista"))],
    ["Invertir lista", () => reordenar((l) => l.reverse())],
    ["Mezclar lista", () => reordenar(aleatorizar)],
  ],
};
const playlists = ref([]);
const aviso = ref("");

async function guardarComoPlaylist() {
  const pistas = motor.lista.filter((p) => p.ruta !== undefined);
  if (!pistas.length) return avisar("La lista está vacía");
  const nombre = (window.prompt("Nombre de la playlist:", "") || "").trim();
  if (!nombre) return;
  try {
    const r = await api.guardarPlaylist(nombre, pistas);
    avisar(`Guardada «${nombre}» · ${r.canciones}`);
  } catch (e) {
    avisar("No se pudo guardar");
  }
}
async function cargarPlaylist(nombre) {
  const r = await api.playlist(nombre);
  reemplazar(r.pistas.filter((p) => p.existe !== false).map(pista));
}
function avisar(texto) {
  aviso.value = texto;
  setTimeout(() => aviso.value === texto && (aviso.value = ""), 3000);
}
async function abrirMenuLista() {
  if (menu.value === "list") return (menu.value = null);
  menu.value = "list";
  try { playlists.value = (await api.playlists()).playlists; } catch { playlists.value = []; }
}
const opcionesLista = () => [
  ["Guardar como playlist…", guardarComoPlaylist],
  ...playlists.value.map((p) => [`Cargar «${p.nombre}» (${p.canciones})`, () => cargarPlaylist(p.nombre)]),
  ["Vaciar lista", () => vaciar()],
  ["Biblioteca y playlists…", () => abrirVentana("biblioteca")],
];
function elegir(accion) {
  menu.value = null;
  accion();
}
</script>

<template>
  <div class="pl" @pointerdown.self="menu = null" @contextmenu.prevent="emit('menu', $event)">
    <div class="pl-titulo" @pointerdown="arrastrarVentana">
      <span class="pl-rayas"></span><span class="pl-texto">MIGUEWAMP PLAYLIST</span><span class="pl-rayas"></span>
      <button class="pl-x" title="Cerrar" @pointerdown.stop @click="emit('cerrar')"></button>
    </div>

    <div class="pl-lista" tabindex="0" @keydown.delete.prevent="quitarSeleccion" @keydown.ctrl.a.prevent="seleccionarTodo"
         @pointerdown="menu = null">
      <div v-for="(p, i) in motor.lista" :key="i" class="pl-fila"
           :class="{ actual: i === motor.actual, sel: motor.seleccion.has(i) }"
           @click="clic(i, $event)" @dblclick="cargar(i)">
        <span class="pl-nombre">{{ i + 1 }}. {{ p.artista ? p.artista + " - " : "" }}{{ p.titulo }}</span>
        <span class="pl-dur">{{ mmss(p.duracion) }}</span>
      </div>
      <div v-if="!motor.lista.length" class="pl-vacia">Lista vacía.<br />Arrastra música aquí, usa ADD o abre la biblioteca (Alt+L).</div>
    </div>

    <div class="pl-pie">
      <div class="pl-grupo">
        <button class="pl-boton" @click="menu = menu === 'add' ? null : 'add'">ADD</button>
        <button class="pl-boton" @click="quitarSeleccion">REM</button>
        <button class="pl-boton" @click="seleccionarTodo">SEL</button>
        <button class="pl-boton" @click="menu = menu === 'misc' ? null : 'misc'">MISC</button>
      </div>
      <div class="pl-lcd">{{ aviso || `${mmss(motor.tiempo)}/${mmss(total)}` }}</div>
      <button class="pl-boton" @click="abrirMenuLista">LIST</button>

      <div v-if="menu" class="pl-menu" :class="'menu-' + menu">
        <div v-for="[texto, accion] in (menu === 'list' ? opcionesLista() : MENUS[menu])" :key="texto" class="pl-menu-item" @click="elegir(accion)">{{ texto }}</div>
      </div>
    </div>
  </div>
</template>
