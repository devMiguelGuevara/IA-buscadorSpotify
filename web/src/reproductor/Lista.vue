<script setup>
// Lista de reproducción estilo Winamp. Sus medidas dependen de --u (la escala), así que
// se ve nítida a cualquier tamaño.
import { computed, ref } from "vue";
import { cargar, encolar, mmss, motor, moverA, moverSeleccion, posicionEnCola, quitar, reemplazar, vaciar } from "./motor.js";
import MenuContexto from "./MenuContexto.vue";
import { api, pista } from "../api.js";
import { agregarArchivos, agregarCarpeta } from "./disco.js";
import { abrirVentana, arrastrarVentana } from "../ventanas/nativo.js";

const emit = defineEmits(["cerrar", "menu"]);
const menu = ref(null);
let ultimo = -1;

const total = computed(() => motor.lista.reduce((s, p) => s + (p.duracion || 0), 0));

function clic(i, e) {
  if (recienArrastrado) return; // el clic que cierra un arrastre no cambia la selección
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
const elegidas = () => [...motor.seleccion].sort((a, b) => a - b);

// ---------- cola (Q): si todas las elegidas ya están encoladas se quitan; si no, se suman
function alternarCola(indices = elegidas()) {
  const faltan = indices.filter((k) => !posicionEnCola(motor.lista[k]));
  encolar(faltan.length ? faltan : indices);
}
function teclaLista(e) {
  if (e.key === "q" || e.key === "Q") { e.preventDefault(); alternarCola(); }
  else if (e.altKey && e.key === "ArrowUp") { e.preventDefault(); moverSeleccion(-1); }
  else if (e.altKey && e.key === "ArrowDown") { e.preventDefault(); moverSeleccion(1); }
  else if (e.key === "Enter" && motor.seleccion.size) { e.preventDefault(); cargar(elegidas()[0]); }
}

// ---------- menú de una canción (clic derecho)
const menuFila = ref(null);
function menuDeFila(i, e) {
  if (!motor.seleccion.has(i)) {
    motor.seleccion = new Set([i]);
    ultimo = i;
  }
  const sel = elegidas();
  const encoladas = sel.every((k) => posicionEnCola(motor.lista[k]));
  menuFila.value = {
    x: e.clientX, y: e.clientY,
    items: [
      { texto: "Reproducir", atajo: "Enter", accion: () => cargar(sel[0]) },
      { texto: encoladas ? "Quitar de la cola" : "Encolar (suena a continuación)", atajo: "Q", accion: () => alternarCola(sel) },
      "-",
      { texto: "Subir", atajo: "Alt+↑", accion: () => moverSeleccion(-1) },
      { texto: "Bajar", atajo: "Alt+↓", accion: () => moverSeleccion(1) },
      { texto: "Mover al principio", accion: () => moverA(sel, 0) },
      { texto: "Mover al final", accion: () => moverA(sel, motor.lista.length) },
      "-",
      { texto: sel.length > 1 ? `Quitar ${sel.length} de la lista` : "Quitar de la lista", atajo: "Supr", accion: () => quitar(sel) },
    ],
  };
}

// ---------- arrastrar para reordenar
const marca = ref(-1); // posición donde caerían (0..largo)
let arrastre = null, recienArrastrado = false;
function empezarArrastre(i, e) {
  if (e.button !== 0 || e.ctrlKey || e.shiftKey) return;
  arrastre = { i, y: e.clientY, activo: false };
  window.addEventListener("pointermove", moverArrastre);
  window.addEventListener("pointerup", soltarArrastre, { once: true });
}
function moverArrastre(e) {
  if (!arrastre) return;
  if (!arrastre.activo) {
    if (Math.abs(e.clientY - arrastre.y) < 4) return;
    arrastre.activo = true;
    if (!motor.seleccion.has(arrastre.i)) motor.seleccion = new Set([arrastre.i]);
  }
  const fila = document.elementFromPoint(e.clientX, e.clientY)?.closest(".pl-fila");
  if (!fila) return;
  const k = Number(fila.dataset.i), r = fila.getBoundingClientRect();
  marca.value = e.clientY < r.top + r.height / 2 ? k : k + 1;
}
function soltarArrastre() {
  window.removeEventListener("pointermove", moverArrastre);
  if (arrastre?.activo) {
    if (marca.value >= 0) moverA(elegidas(), marca.value);
    recienArrastrado = true;
    setTimeout(() => (recienArrastrado = false));
  }
  arrastre = null;
  marca.value = -1;
}
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
    ["Vaciar la cola", () => (motor.cola = [])],
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
  ...playlists.value.filter((p) => p.canciones)
    .map((p) => [`Cargar «${p.nombre}» (${p.canciones})${p.descarga ? " · descarga" : ""}`, () => cargarPlaylist(p.nombre)]),
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
         @keydown="teclaLista" @pointerdown="menu = null">
      <div v-for="(p, i) in motor.lista" :key="i" class="pl-fila" :data-i="i"
           :class="{ actual: i === motor.actual, sel: motor.seleccion.has(i), 'marca-antes': marca === i,
                     'marca-despues': marca === motor.lista.length && i === motor.lista.length - 1 }"
           @pointerdown="empezarArrastre(i, $event)" @click="clic(i, $event)" @dblclick="cargar(i)"
           @contextmenu.prevent.stop="menuDeFila(i, $event)">
        <span class="pl-nombre"><span v-if="posicionEnCola(p)" class="pl-cola" title="En cola: suena a continuación">[{{ posicionEnCola(p) }}]</span>{{ i + 1 }}. {{ p.artista ? p.artista + " - " : "" }}{{ p.titulo }}</span>
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

      <MenuContexto v-if="menuFila" v-bind="menuFila" @cerrar="menuFila = null" />
      <div v-if="menu" class="pl-menu" :class="'menu-' + menu">
        <div v-for="[texto, accion] in (menu === 'list' ? opcionesLista() : MENUS[menu])" :key="texto" class="pl-menu-item" @click="elegir(accion)">{{ texto }}</div>
      </div>
    </div>
  </div>
</template>
