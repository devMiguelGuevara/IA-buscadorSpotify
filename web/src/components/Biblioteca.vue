<script setup>
// Biblioteca multimedia de MigueWamp: lo descargado y tus carpetas, las playlists propias
// y el manejo de rutas (carpeta de descargas y carpetas extra).
import { computed, onMounted, reactive, ref, watch } from "vue";
import Mas from "./Mas.vue";
import VentanaWinamp from "./VentanaWinamp.vue";
import { api, clave, duracion, nativo, pista } from "../api.js";
import { cargarBiblioteca, cargarPlaylists, estado } from "../estado.js";

const props = defineProps({ compacta: Boolean }); // dentro de la vista compacta
const emit = defineEmits(["cerrar", "reproducir", "encolar", "abrir"]);
const arbolAbierto = ref(false); // en la vista compacta, el árbol es un desplegable
const POR_PAGINA = 50;
const mostrar = ref(POR_PAGINA); // filas dibujadas: al bajar se suman 50 más
const nodo = ref("todas");        // todas | explorar | lista:<x> | carpeta:<i> | playlist:<nombre> | carpetas
const filtro = ref("");
const seleccion = ref(new Set());
const pistasPlaylist = ref([]);
const carpetas = ref([]);
const aviso = ref("");
const formulario = ref(null);     // { modo: "nueva" | "agregar", nombre }
const rutaNueva = ref("");

onMounted(() => {
  cargarPlaylists();
  cargarCarpetas();
});

async function cargarCarpetas() {
  try { carpetas.value = (await api.carpetas()).carpetas; } catch {}
}
function avisar(texto) {
  aviso.value = texto;
  setTimeout(() => aviso.value === texto && (aviso.value = ""), 3500);
}

// ---------- vistas
// Cada descarga deja su carpeta y su lista (.m3u8, que también nombra lo bajado antes por otra
// lista). Se muestran juntas, una vez, y solo si todavía tienen canciones.
const listas = computed(() => {
  const conteo = {};
  for (const c of estado.canciones) if (c.raiz === 0 && c.lista) conteo[c.lista] = (conteo[c.lista] || 0) + 1;
  for (const p of estado.playlists)
    if (p.descarga && p.canciones) conteo[p.nombre] = Math.max(conteo[p.nombre] || 0, p.canciones);
  return Object.entries(conteo).sort((a, b) => a[0].localeCompare(b[0], "es", { sensitivity: "base" }));
});
const esListaDescargada = (nombre) => estado.playlists.some((p) => p.descarga && p.nombre === nombre && p.canciones);
const propias = computed(() => estado.playlists.filter((p) => !p.descarga));
const carpetasVisibles = computed(() => carpetas.value.slice(1).filter((c) => c.existe));
const enPlaylist = computed(() => nodo.value.startsWith("playlist:"));
const nombrePlaylist = computed(() => (enPlaylist.value ? nodo.value.slice(9) : ""));

// ---------- explorar por artista y álbum (como la Media Library de Winamp)
const SIN_ARTISTA = "(sin artista)", SIN_ALBUM = "(sin álbum)";
const artistaDe = (c) => c.artista_album || c.artista || SIN_ARTISTA;
const albumDe = (c) => c.album || SIN_ALBUM;
const explorar = reactive({ artista: null, album: null });
const agrupar = (lista, f) => {
  const conteo = new Map();
  for (const c of lista) conteo.set(f(c), (conteo.get(f(c)) || 0) + 1);
  return [...conteo].sort((a, b) => a[0].localeCompare(b[0], "es", { sensitivity: "base" }));
};
const artistas = computed(() => agrupar(estado.canciones, artistaDe));
const delArtista = computed(() => (explorar.artista == null ? estado.canciones : estado.canciones.filter((c) => artistaDe(c) === explorar.artista)));
const albumes = computed(() => agrupar(delArtista.value, albumDe));
function elegirArtista(a) {
  explorar.artista = a;
  explorar.album = null;
  seleccion.value = new Set();
}
function elegirAlbum(a) {
  explorar.album = a;
  seleccion.value = new Set();
}
const porAlbum = (a, b) =>
  artistaDe(a).localeCompare(artistaDe(b), "es", { sensitivity: "base" }) ||
  albumDe(a).localeCompare(albumDe(b), "es", { sensitivity: "base" }) ||
  (a.numero ?? 999) - (b.numero ?? 999) || a.titulo.localeCompare(b.titulo, "es");

const visibles = computed(() => {
  let lista = estado.canciones;
  if (nodo.value === "explorar") {
    lista = delArtista.value;
    if (explorar.album != null) lista = lista.filter((c) => albumDe(c) === explorar.album);
    lista = [...lista].sort(porAlbum);
  }
  if (nodo.value.startsWith("lista:"))
    lista = esListaDescargada(nodo.value.slice(6)) ? pistasPlaylist.value.filter((c) => c.existe !== false)
      : lista.filter((c) => c.raiz === 0 && c.lista === nodo.value.slice(6));
  else if (nodo.value.startsWith("carpeta:")) lista = lista.filter((c) => c.raiz === Number(nodo.value.slice(8)));
  else if (enPlaylist.value) lista = pistasPlaylist.value;
  const f = filtro.value.trim().toLowerCase();
  if (f) lista = lista.filter((c) => `${c.artista} ${c.titulo} ${c.album || ""}`.toLowerCase().includes(f));
  return lista;
});

const nombreNodo = computed(() => {
  const n = nodo.value;
  if (n === "todas") return "Todo";
  if (n === "explorar") return "Artistas y álbumes";
  if (n === "carpetas") return "Carpetas de música";
  return n.slice(n.indexOf(":") + 1);
});
watch(filtro, () => (mostrar.value = POR_PAGINA));
watch(() => [explorar.artista, explorar.album], () => (mostrar.value = POR_PAGINA));

async function ir(destino) {
  nodo.value = destino;
  arbolAbierto.value = false;
  mostrar.value = POR_PAGINA;
  seleccion.value = new Set();
  formulario.value = null;
  const nombre = destino.startsWith("playlist:") ? destino.slice(9)
    : destino.startsWith("lista:") && esListaDescargada(destino.slice(6)) ? destino.slice(6) : null;
  if (nombre != null) {
    try { pistasPlaylist.value = (await api.playlist(nombre)).pistas; } catch { pistasPlaylist.value = []; }
  }
  if (destino === "carpetas") cargarCarpetas();
}

// ---------- selección
let ultimo = -1;
function elegir(c, i, e) {
  let s = new Set(e.ctrlKey ? seleccion.value : []);
  if (e.shiftKey && ultimo >= 0) {
    s = new Set();
    for (let k = Math.min(ultimo, i); k <= Math.max(ultimo, i); k++) s.add(clave(visibles.value[k]));
  } else if (e.ctrlKey && s.has(clave(c))) s.delete(clave(c));
  else s.add(clave(c));
  seleccion.value = s;
  if (!e.shiftKey) ultimo = i;
}
const seleccionadas = () => {
  const s = visibles.value.filter((c) => seleccion.value.has(clave(c)));
  return s.length ? s : visibles.value;
};

// ---------- playlists
function abrirFormulario(modo) {
  formulario.value = { modo, nombre: modo === "agregar" ? propias.value[0]?.nombre || "" : "" };
}
async function guardarEnPlaylist() {
  const f = formulario.value;
  const nombre = (f.nombre || "").trim();
  if (!nombre) return;
  const pistas = seleccionadas().map(pista);
  try {
    const r = await api.guardarPlaylist(nombre, pistas, f.modo === "agregar");
    avisar(`Playlist «${nombre}»: ${r.canciones} canciones`);
    formulario.value = null;
    await cargarPlaylists();
    if (nodo.value === "playlist:" + nombre) ir(nodo.value);
  } catch (e) {
    avisar(String(e));
  }
}
async function quitarDePlaylist() {
  const quitar = new Set(seleccion.value);
  const quedan = pistasPlaylist.value.filter((c) => !quitar.has(clave(c)));
  await api.guardarPlaylist(nombrePlaylist.value, quedan.map(pista));
  await ir(nodo.value);
  cargarPlaylists();
}
const confirmarBorrado = ref(false);
async function borrarPlaylist() {
  if (!confirmarBorrado.value) {
    confirmarBorrado.value = true;
    setTimeout(() => (confirmarBorrado.value = false), 3000);
    return;
  }
  confirmarBorrado.value = false;
  await api.borrarPlaylist(nombrePlaylist.value);
  await cargarPlaylists();
  ir("todas");
}

// ---------- laboratorio: la canción seleccionada (o la primera visible)
async function aLaboratorio() {
  const c = visibles.value.find((x) => seleccion.value.has(clave(x))) || null;
  if (c) await fetch("/api/mejora/seleccion", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raiz: c.raiz ?? 0, ruta: c.ruta, titulo: c.titulo, artista: c.artista }) });
  emit("abrir", "laboratorio");
}

// ---------- importar .m3u / .m3u8 / .pls de otro reproductor
const importacion = ref(null); // resultado, con las carpetas de fuera de la biblioteca
async function importarLista() {
  const ruta = await nativo()?.elegir_lista_reproduccion();
  if (ruta) await importarDesde(ruta);
}
async function importarDesde(ruta) {
  try {
    const r = await api.importarPlaylist(ruta);
    const extra = [r.faltan && `${r.faltan} no existen`, r.enlaces && `${r.enlaces} enlaces`].filter(Boolean).join(", ");
    avisar(r.canciones ? `Importada «${r.nombre}»: ${r.canciones} canciones` + (extra ? ` (${extra})` : "") : "Ninguna canción de esa lista está en la biblioteca");
    importacion.value = r.fuera.length ? { ...r, ruta } : null;
    await cargarPlaylists();
    if (r.nombre) ir("playlist:" + r.nombre);
  } catch (e) {
    avisar(String(e).replace(/^Error: \d+ /, ""));
  }
}
async function agregarCarpetasEImportar() {
  const { fuera, ruta, nombre } = importacion.value;
  for (const c of fuera) await api.agregarCarpeta(c.carpeta).catch(() => {});
  await cargarBiblioteca();
  await cargarCarpetas();
  if (nombre) await api.borrarPlaylist(nombre).catch(() => {}); // se rehace completa
  await importarDesde(ruta);
}

// ---------- carpetas
async function elegirCarpeta() {
  const ruta = await nativo()?.elegir_carpeta();
  if (ruta) rutaNueva.value = ruta;
}
async function accionCarpeta(fn, ruta) {
  try {
    carpetas.value = (await fn(ruta)).carpetas;
    rutaNueva.value = "";
    cargarBiblioteca();
  } catch (e) {
    avisar(String(e).replace(/^Error: \d+ /, ""));
  }
}
</script>

<template>
  <VentanaWinamp titulo="MigueWamp · Biblioteca multimedia" @cerrar="emit('cerrar')">
    <div class="ml" :class="{ compacta }">
      <button v-if="compacta" class="wa-boton ml-ver" @click="arbolAbierto = !arbolAbierto">Ver: {{ nombreNodo }} ▾</button>
      <nav class="ml-arbol" :class="{ abierto: arbolAbierto }">
        <div class="ml-grupo">Biblioteca</div>
        <a :class="{ activo: nodo === 'todas' }" @click="ir('todas')">Todo ({{ estado.canciones.length }})</a>
        <a class="hijo" :class="{ activo: nodo === 'explorar' }" @click="ir('explorar')">Artistas y álbumes ({{ artistas.length }})</a>
        <a v-for="[l, n] in listas" :key="l" class="hijo" :class="{ activo: nodo === 'lista:' + l }" @click="ir('lista:' + l)">{{ l }} ({{ n }})</a>
        <template v-for="c in carpetasVisibles" :key="c.i">
          <a class="hijo" :class="{ activo: nodo === 'carpeta:' + c.i }" :title="c.ruta" @click="ir('carpeta:' + c.i)">📁 {{ c.ruta.split(/[\\/]/).pop() }}</a>
        </template>

        <div class="ml-grupo">Playlists</div>
        <a v-for="p in propias" :key="p.nombre" :class="{ activo: nodo === 'playlist:' + p.nombre }" @click="ir('playlist:' + p.nombre)"
           :title="p.total > p.canciones ? `${p.total - p.canciones} canciones de esta playlist ya no existen` : ''">
          {{ p.nombre }} ({{ p.canciones }}<template v-if="p.total > p.canciones"> de {{ p.total }}</template>)
        </a>
        <a class="tenue" @click="ir('todas'); abrirFormulario('nueva')">+ Nueva playlist…</a>
        <a v-if="nativo()" class="tenue" title="Trae una lista .m3u, .m3u8 o .pls de otro reproductor" @click="importarLista">+ Importar lista…</a>

        <div class="ml-grupo">Rutas</div>
        <a :class="{ activo: nodo === 'carpetas' }" @click="ir('carpetas')">Carpetas de música</a>

        <template v-if="!compacta">
          <div class="ml-grupo">Mejora</div>
          <a @click="aLaboratorio">Laboratorio…</a>
        </template>

        <div class="ml-grupo">Agregar</div>
        <a @click="emit('abrir', 'ubicacion')">Abrir ubicación…</a>
        <a @click="emit('abrir', 'descargas')">Descargas</a>
      </nav>

      <!-- ===== carpetas ===== -->
      <div v-if="nodo === 'carpetas'" class="ml-contenido">
        <div class="ml-tabla">
          <table class="wa-tabla">
            <thead><tr><th>Carpeta</th><th>Uso</th><th></th></tr></thead>
            <tbody>
              <tr v-for="c in carpetas" :key="c.i">
                <td :title="c.ruta" style="max-width: 330px">{{ c.ruta }}<span v-if="!c.existe" class="wa-error"> (no existe)</span></td>
                <td>{{ c.descargas ? "Descargas" : "Biblioteca" }}</td>
                <td class="num">
                  <template v-if="!c.descargas">
                    <button class="wa-boton" @click="accionCarpeta(api.carpetaDescargas, c.ruta)">Usar para descargas</button>
                    <button class="wa-boton" @click="accionCarpeta(api.quitarCarpeta, c.ruta)">Quitar</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="ml-carpetas-ayuda">
            <p>Las descargas se guardan en la carpeta marcada como <b>Descargas</b>. Las demás carpetas solo se leen: su música aparece en la biblioteca para reproducir y armar playlists.</p>
            <div class="ml-filtro">
              <input v-model="rutaNueva" class="wa-entrada" placeholder="Pega la ruta de una carpeta, p. ej. D:\Música" />
              <button v-if="nativo()" class="wa-boton" @click="elegirCarpeta">Examinar…</button>
            </div>
            <div class="ml-filtro">
              <button class="wa-boton" :disabled="!rutaNueva.trim()" @click="accionCarpeta(api.agregarCarpeta, rutaNueva)">Agregar a la biblioteca</button>
              <button class="wa-boton" :disabled="!rutaNueva.trim()" @click="accionCarpeta(api.carpetaDescargas, rutaNueva)">Usar para descargas</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== canciones (biblioteca o playlist) ===== -->
      <div v-else class="ml-contenido">
        <div v-if="nodo === 'explorar'" class="ml-explorar">
          <div class="ml-columna">
            <div :class="{ activo: explorar.artista == null }" @click="elegirArtista(null)">Todos los artistas ({{ artistas.length }})</div>
            <div v-for="[a, n] in artistas" :key="a" :class="{ activo: explorar.artista === a }" @click="elegirArtista(a)">{{ a }} <span class="tenue">({{ n }})</span></div>
          </div>
          <div class="ml-columna">
            <div :class="{ activo: explorar.album == null }" @click="elegirAlbum(null)">Todos los álbumes ({{ albumes.length }})</div>
            <div v-for="[a, n] in albumes" :key="a" :class="{ activo: explorar.album === a }" @click="elegirAlbum(a)">{{ a }} <span class="tenue">({{ n }})</span></div>
          </div>
        </div>
        <div class="ml-filtro">
          <span>Buscar:</span>
          <input v-model="filtro" class="wa-entrada" />
          <button class="wa-boton" @click="filtro = ''">Limpiar</button>
        </div>
        <div v-if="importacion" class="ml-filtro ml-formulario">
          <span>{{ importacion.fuera.reduce((n, c) => n + c.canciones, 0) }} canciones de la lista están en
            {{ importacion.fuera.length === 1 ? "una carpeta" : importacion.fuera.length + " carpetas" }} fuera de la biblioteca
            <span class="tenue">({{ importacion.fuera.map((c) => c.carpeta).join(" · ") }})</span></span>
          <button class="wa-boton wa-principal" @click="agregarCarpetasEImportar">Agregarlas e importar todo</button>
          <button class="wa-boton" @click="importacion = null">No</button>
        </div>
        <div v-if="formulario" class="ml-filtro ml-formulario">
          <template v-if="formulario.modo === 'nueva'">
            <span>Nueva playlist:</span>
            <input v-model="formulario.nombre" class="wa-entrada" placeholder="Nombre" @keydown.enter="guardarEnPlaylist" />
          </template>
          <template v-else>
            <span>Agregar a:</span>
            <select v-model="formulario.nombre" class="wa-entrada">
              <option v-for="p in propias" :key="p.nombre" :value="p.nombre">{{ p.nombre }}</option>
            </select>
          </template>
          <span class="tenue">{{ seleccion.size || visibles.length }} canciones</span>
          <button class="wa-boton wa-principal" @click="guardarEnPlaylist">Guardar</button>
          <button class="wa-boton" @click="formulario = null">Cancelar</button>
        </div>
        <div class="ml-tabla">
          <table class="wa-tabla" v-if="visibles.length">
            <thead><tr><th v-if="nodo === 'explorar'" class="num">#</th><th>Artista</th><th>Título</th><th class="col-extra">Álbum</th><th class="num">Duración</th><th class="col-extra">Calidad</th><th class="col-extra">Lista</th></tr></thead>
            <tbody>
              <tr v-for="(c, i) in visibles.slice(0, mostrar)" :key="clave(c) + i" :class="{ sel: seleccion.has(clave(c)) }"
                  @click="elegir(c, i, $event)" @dblclick="emit('reproducir', [pista(c)])">
                <td v-if="nodo === 'explorar'" class="num">{{ c.numero || "" }}</td>
                <td>{{ c.artista }}</td><td>{{ c.titulo }}</td><td class="col-extra">{{ c.album }}<span v-if="c.anio" class="tenue"> · {{ c.anio }}</span></td>
                <td class="num">{{ duracion(c.duracion) }}</td>
                <td class="col-extra">{{ c.formato }}{{ c.kbps ? ` ${c.kbps}k` : "" }}</td>
                <td class="col-extra">{{ c.lista }}</td>
              </tr>
              <tr v-if="visibles.length > mostrar" class="fila-mas">
                <td colspan="7"><Mas :quedan="visibles.length - mostrar" @ver="mostrar += POR_PAGINA" /></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="wa-vacio">
            <template v-if="enPlaylist"><p>Esta playlist está vacía.</p><p>Selecciona canciones en «Todo» y usa «A playlist».</p></template>
            <template v-else-if="estado.canciones.length"><p>Nada coincide con la búsqueda.</p></template>
            <template v-else>
              <p>La biblioteca está vacía.</p>
              <p>Descarga con «Abrir ubicación» o agrega una carpeta con música en «Carpetas de música».</p>
              <div class="ml-filtro">
                <button class="wa-boton" @click="emit('abrir', 'ubicacion')">Abrir ubicación…</button>
                <button class="wa-boton" @click="ir('carpetas')">Carpetas…</button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <template #pie>
      <template v-if="nodo !== 'carpetas'">
        <button class="wa-boton" :disabled="!visibles.length" @click="emit('reproducir', seleccionadas().map(pista))">Reproducir</button>
        <button class="wa-boton" :disabled="!visibles.length" @click="emit('encolar', seleccionadas().map(pista))">Encolar</button>
        <template v-if="!enPlaylist">
          <button class="wa-boton" :disabled="!visibles.length" @click="abrirFormulario('nueva')">Nueva playlist</button>
          <button class="wa-boton" :disabled="!visibles.length || !propias.length" @click="abrirFormulario('agregar')">A playlist</button>
        </template>
        <template v-else>
          <button class="wa-boton" :disabled="!seleccion.size" @click="quitarDePlaylist">Quitar</button>
          <button class="wa-boton" @click="borrarPlaylist">{{ confirmarBorrado ? "¿Seguro? Clic otra vez" : "Borrar playlist" }}</button>
        </template>
      </template>
      <button v-if="nodo !== 'carpetas' && !compacta" class="wa-boton" :disabled="!seleccion.size" @click="aLaboratorio">Mejorar…</button>
      <button class="wa-boton" @click="cargarBiblioteca(); cargarPlaylists(); cargarCarpetas()">Actualizar</button>
      <span class="wa-estado">{{ aviso || (nodo === "carpetas" ? carpetas.length + " carpetas" : visibles.length + " elementos" + (seleccion.size ? ` · ${seleccion.size} seleccionadas` : "")) }}</span>
    </template>
  </VentanaWinamp>
</template>
