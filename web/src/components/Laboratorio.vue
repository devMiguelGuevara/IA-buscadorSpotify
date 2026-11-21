<script setup>
// Laboratorio de mejora: analizar, elegir procesos (según lo que tenga la máquina),
// procesar sin tocar el original y comparar A/B con el volumen igualado.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import VentanaWinamp from "./VentanaWinamp.vue";
import { clave, duracion } from "../api.js";
import { estado } from "../estado.js";
import { encolarEnReproductor } from "../ventanas/nativo.js";

const emit = defineEmits(["cerrar"]);
const cap = ref(null);
const motores = ref([]);
const cancion = ref(null);            // { raiz, ruta, titulo, artista }
const buscar = ref("");
const analisisT = ref(null);          // trabajo de análisis
const procesoT = ref(null);           // trabajo de proceso
const versiones = ref([]);
const version = ref(null);            // versión elegida para A/B
const formato = ref("flac");
const receta = reactive({});          // id -> { activo, params }
const aviso = ref("");
let selN = -1, reloj = 0;

const post = async (url, datos) => {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r;
};

onMounted(async () => {
  cap.value = await (await fetch("/api/mejora/capacidades")).json();
  motores.value = (await (await fetch("/api/mejora/motores")).json()).motores;
  for (const m of motores.value)
    receta[m.id] = { activo: false, params: Object.fromEntries(m.parametros.map((p) => [p.id, p.defecto])) };
  await revisarSeleccion();
  reloj = setInterval(tic, 1000);
});
onBeforeUnmount(() => clearInterval(reloj));

async function revisarSeleccion() {
  const s = await (await fetch("/api/mejora/seleccion")).json();
  if (s.n && s.n !== selN) {
    selN = s.n;
    elegir(s);
  }
}
async function tic() {
  revisarSeleccion();
  if (![analisisT.value, procesoT.value].some((t) => t && ["en_cola", "procesando"].includes(t.estado))) return;
  const { trabajos } = await (await fetch("/api/mejora/trabajos")).json();
  const buscarT = (t) => t && (trabajos.find((x) => x.id === t.id) || t);
  analisisT.value = buscarT(analisisT.value);
  const antes = procesoT.value?.estado;
  procesoT.value = buscarT(procesoT.value);
  if (antes !== "terminado" && procesoT.value?.estado === "terminado") {
    await cargarVersiones();
    version.value = versiones.value.find((v) => v.ruta === procesoT.value.resultado.ruta) || versiones.value[0];
  }
}

// ---------- canción
const candidatas = computed(() => {
  const f = buscar.value.trim().toLowerCase();
  if (!f) return [];
  return estado.canciones.filter((c) => `${c.artista} ${c.titulo}`.toLowerCase().includes(f)).slice(0, 8);
});
async function elegir(c) {
  cancion.value = { raiz: c.raiz ?? 0, ruta: c.ruta, titulo: c.titulo, artista: c.artista };
  buscar.value = "";
  analisisT.value = procesoT.value = version.value = null;
  await cargarVersiones();
  analizar();
}
async function analizar() {
  if (!cancion.value) return;
  analisisT.value = await (await post("/api/mejora/analizar", cancion.value)).json();
}
async function cargarVersiones() {
  versiones.value = cancion.value ? (await (await post("/api/mejora/versiones", cancion.value)).json()).versiones : [];
}
const analisis = computed(() => analisisT.value?.resultado);

// ---------- procesos
const procesa = (m) => m.estado === "disponible" && !m.solo_analisis;
const disponibles = computed(() => motores.value.filter(procesa));
const otros = computed(() => motores.value.filter((m) => !procesa(m)));

// ---------- instalar los niveles Mejora e IA desde aquí (también en el .exe)
const complementos = ref({});
let relojComp = 0;
const faltan = computed(() => Object.entries(complementos.value)
  .filter(([nivel, c]) => !c.instalado && motores.value.some((m) => m.nivel === nivel && m.estado === "instalable")));
async function revisarComplementos() {
  try { complementos.value = await (await fetch("/api/complementos")).json(); } catch { return; }
  const instalando = Object.values(complementos.value).some((c) => c.estado === "instalando");
  if (!instalando && relojComp) {
    clearInterval(relojComp);
    relojComp = 0;
    cap.value = await (await fetch("/api/mejora/capacidades")).json();
    motores.value = (await (await fetch("/api/mejora/motores")).json()).motores;
    for (const m of motores.value)
      receta[m.id] ??= { activo: false, params: Object.fromEntries(m.parametros.map((q) => [q.id, q.defecto])) };
  }
}
async function instalarNivel(nivel) {
  await fetch(`/api/complementos/${nivel}`, { method: "POST" });
  await revisarComplementos();
  if (!relojComp) relojComp = setInterval(revisarComplementos, 1500);
}
onMounted(async () => {
  await revisarComplementos();
  if (Object.values(complementos.value).some((c) => c.estado === "instalando")) relojComp = setInterval(revisarComplementos, 1500);
});
onBeforeUnmount(() => clearInterval(relojComp));
// Matchering: canción de referencia elegida de la biblioteca.
const referencia = ref(null);
const buscarRef = ref("");
const candidatasRef = computed(() => {
  const f = buscarRef.value.trim().toLowerCase();
  if (!f) return [];
  return estado.canciones.filter((c) => `${c.artista} ${c.titulo}`.toLowerCase().includes(f)).slice(0, 8);
});
function elegirReferencia(c) {
  referencia.value = { raiz: c.raiz ?? 0, ruta: c.ruta, titulo: c.titulo, artista: c.artista };
  buscarRef.value = "";
}
function aplicarSugerencias() {
  for (const p of analisis.value?.problemas || [])
    if (p.sugerencia && receta[p.sugerencia]) receta[p.sugerencia].activo = true;
  if (analisis.value?.afinacion_hz) receta.afinacion.params.desde = analisis.value.afinacion_hz;
}
const cents = computed(() => {
  const p = receta.afinacion?.params;
  return p ? (1200 * Math.log2(p.hacia / p.desde)).toFixed(1) : "0";
});
const elegidos = computed(() => Object.entries(receta).filter(([, r]) => r.activo).map(([id, r]) =>
  id === "matchering" ? { id, params: {}, referencia: referencia.value } : { id, params: { ...r.params } }));
const faltaReferencia = computed(() => receta.matchering?.activo && !referencia.value);
async function procesar() {
  aviso.value = "";
  try {
    procesoT.value = await (await post("/api/mejora/procesar", { ...cancion.value, receta: elegidos.value, formato: formato.value })).json();
  } catch (e) {
    aviso.value = String(e.message || e);
  }
}

// ---------- A/B
const a = new Audio(), b = new Audio();
const ab = reactive({ cual: "a", sonando: false, igualar: true, tiempo: 0 });
const srcA = computed(() => cancion.value && `/media/${cancion.value.raiz}/` + cancion.value.ruta.split("/").map(encodeURIComponent).join("/"));
const srcB = computed(() => version.value && "/versiones/" + version.value.ruta.split("/").map(encodeURIComponent).join("/"));
watch([srcA, srcB], () => {
  pararAB();
  if (srcA.value) a.src = srcA.value;
  if (srcB.value) b.src = srcB.value;
});
function volumenes() {
  const la = version.value?.antes?.sonoridad?.lufs, lb = version.value?.despues?.sonoridad?.lufs;
  let va = 1, vb = 1;
  if (ab.igualar && la != null && lb != null) {
    const dif = lb - la; // si B es más fuerte, se baja B (y al revés)
    if (dif > 0) vb = 10 ** (-dif / 20); else va = 10 ** (dif / 20);
  }
  a.volume = ab.cual === "a" ? va : 0;
  b.volume = ab.cual === "b" ? vb : 0;
}
watch(() => [ab.cual, ab.igualar], volumenes);
function alternarAB() {
  if (!srcB.value) return;
  if (ab.sonando) { a.pause(); b.pause(); ab.sonando = false; return; }
  b.currentTime = a.currentTime;
  volumenes();
  a.play(); b.play();
  ab.sonando = true;
}
function cambiar(cual) {
  ab.cual = cual;
  if (Math.abs(a.currentTime - b.currentTime) > 0.05) b.currentTime = a.currentTime;
}
function pararAB() {
  a.pause(); b.pause();
  ab.sonando = false;
}
a.addEventListener("timeupdate", () => (ab.tiempo = a.currentTime));
onBeforeUnmount(pararAB);

const espectros = reactive({ a: "", b: "" });
async function imagen(datos) {
  const r = await post("/api/mejora/espectro", datos);
  return URL.createObjectURL(await r.blob());
}
watch(version, async (v) => {
  espectros.a = espectros.b = "";
  if (!v || !cancion.value) return;
  espectros.a = await imagen(cancion.value);
  espectros.b = await imagen({ version: v.ruta });
});

const activo = (t) => t && ["en_cola", "procesando"].includes(t.estado);
async function detener(t) {
  if (!t) return;
  await fetch(`/api/mejora/trabajos/${t.id}/cancelar`, { method: "POST" });
}
async function detenerInstalacion(nivel) {
  await fetch(`/api/complementos/${nivel}`, { method: "DELETE" });
  await revisarComplementos();
}

function enviarVersion() {
  const v = version.value;
  encolarEnReproductor("encolar", [{
    url: srcB.value, titulo: `${cancion.value.titulo} (mejorada)`, artista: cancion.value.artista,
    duracion: v.despues?.formato?.duracion ? Math.round(v.despues.formato.duracion) : undefined,
  }]);
  aviso.value = "Versión agregada al reproductor";
}

const fmt = (x, d = 1, u = "") => (x == null ? "—" : `${Number(x).toFixed(d)}${u}`);
const METRICAS = [
  ["Sonoridad", (s) => fmt(s.sonoridad?.lufs, 1, " LUFS")],
  ["Rango (LRA)", (s) => fmt(s.sonoridad?.lra, 1, " LU")],
  ["True peak", (s) => fmt(s.sonoridad?.true_peak, 1, " dBTP")],
  ["RMS", (s) => fmt(s.sonoridad?.rms_db, 1, " dB")],
  ["Formato", (s) => `${s.formato?.codec || ""} ${s.formato?.kbps ? s.formato.kbps + "k" : ""} ${s.formato?.hz ? s.formato.hz / 1000 + " kHz" : ""}`],
  ["Agudos hasta", (s) => (s.corte_hz ? `~${(s.corte_hz / 1000).toFixed(1)} kHz` : "completos")],
  ["Afinación A4", (s) => (s.afinacion_hz ? s.afinacion_hz + " Hz" : "requiere librosa")],
  ["Tempo", (s) => (s.tempo_bpm ? s.tempo_bpm + " BPM" : "—")],
  ["Tonalidad", (s) => s.tonalidad || "—"],
];
</script>

<template>
  <VentanaWinamp titulo="MigueWamp · Laboratorio de mejora" @cerrar="emit('cerrar')">
    <div class="lab">
      <!-- canción -->
      <div class="lab-barra">
        <span class="lab-cancion">{{ cancion ? `${cancion.artista ? cancion.artista + " - " : ""}${cancion.titulo}` : "Elige una canción de tu biblioteca" }}</span>
        <div class="lab-buscar">
          <input v-model="buscar" class="wa-entrada" placeholder="Buscar canción…" />
          <div v-if="candidatas.length" class="lab-sugerencias">
            <div v-for="c in candidatas" :key="clave(c)" @click="elegir(c)">{{ c.artista }} - {{ c.titulo }}</div>
          </div>
        </div>
        <button class="wa-boton" :disabled="!cancion" @click="analizar">Analizar</button>
      </div>

      <div class="lab-cuerpo">
        <!-- análisis -->
        <section class="lab-panel">
          <h3>Análisis</h3>
          <p v-if="!analisisT" class="tenue">Sin analizar.</p>
          <p v-else-if="!analisis" class="wa-vivo">
            {{ analisisT.estado === "error" ? analisisT.error : analisisT.estado === "cancelado" ? "Análisis detenido." : "Analizando…" }}
            <a v-if="activo(analisisT)" @click="detener(analisisT)">Detener</a>
          </p>
          <template v-else>
            <table class="wa-tabla lab-metricas"><tbody>
              <tr v-for="[n, f] in METRICAS" :key="n"><td>{{ n }}</td><td class="num">{{ f(analisis) }}</td></tr>
            </tbody></table>
            <h3>Diagnóstico</h3>
            <div v-for="p in analisis.problemas" :key="p.codigo" class="lab-problema" :class="p.severidad">{{ p.mensaje }}</div>
            <button class="wa-boton" @click="aplicarSugerencias">Aplicar sugerencias</button>
          </template>
        </section>

        <!-- procesos -->
        <section class="lab-panel lab-procesos">
          <h3>Procesos</h3>
          <div v-for="m in disponibles" :key="m.id" class="lab-motor" :class="{ activo: receta[m.id]?.activo }">
            <label :title="m.descripcion + ' · ' + m.licencia">
              <input type="checkbox" v-model="receta[m.id].activo" /> {{ m.nombre }}
              <span v-if="m.motor" class="tenue"> · {{ m.motor }}</span>
            </label>
            <template v-if="receta[m.id]?.activo">
              <div v-for="p in m.parametros" :key="p.id" class="lab-param">
                <span>{{ p.nombre }}</span>
                <select v-if="p.opciones" v-model="receta[m.id].params[p.id]" class="wa-entrada">
                  <option v-for="[v, etiqueta] in p.opciones" :key="v" :value="v">{{ etiqueta }}</option>
                </select>
                <template v-else>
                  <input type="range" :min="p.min" :max="p.max" :step="p.paso" v-model.number="receta[m.id].params[p.id]" />
                  <b>{{ receta[m.id].params[p.id] }} {{ p.unidad }}</b>
                </template>
              </div>
              <div v-if="m.referencia" class="lab-param lab-referencia">
                <span>Referencia</span>
                <div class="lab-buscar">
                  <input v-model="buscarRef" class="wa-entrada" :placeholder="referencia ? `${referencia.artista} - ${referencia.titulo}` : 'Buscar la canción que suena como quieres…'" />
                  <div v-if="candidatasRef.length" class="lab-sugerencias">
                    <div v-for="c in candidatasRef" :key="clave(c)" @click="elegirReferencia(c)">{{ c.artista }} - {{ c.titulo }}</div>
                  </div>
                </div>
              </div>
              <div v-if="m.id === 'afinacion'" class="tenue lab-param">
                Cambio: {{ cents }} cents. La duración se conserva.
                <a @click="receta.afinacion.params.hacia = 432">432 Hz</a> · <a @click="receta.afinacion.params.hacia = 438">438 Hz</a> · <a @click="receta.afinacion.params.hacia = 440">440 Hz</a>
              </div>
            </template>
          </div>
          <h3>Según tu equipo</h3>
          <div v-for="m in otros" :key="m.id" class="lab-otro">
            <b>{{ m.nombre }}</b> <span class="tenue">({{ m.estado === "disponible" ? "activo" : m.estado === "instalable" ? "instalable" : "no disponible" }})</span>
            <div class="tenue">{{ m.estado === "disponible" ? m.descripcion : m.motivo }}</div>
          </div>
          <div v-for="[nivel, c] in faltan" :key="nivel" class="lab-instalar">
            <button class="wa-boton wa-principal" :disabled="c.estado === 'instalando'" @click="instalarNivel(nivel)">
              {{ c.estado === "instalando" ? `Instalando nivel ${c.nombre}…` : `Instalar nivel ${c.nombre} (${c.tamano})` }}
            </button>
            <div v-if="c.estado === 'instalando'" class="tenue">{{ c.linea }}
              <a @click="detenerInstalacion(nivel)">Detener</a></div>
            <div v-else-if="c.estado === 'cancelado'" class="tenue">{{ c.linea }}</div>
            <div v-else-if="c.estado === 'error'" class="wa-error">No se pudo: {{ c.error }}</div>
          </div>
          <p v-if="cap" class="tenue lab-cap">
            {{ cap.cpu }} núcleos · {{ cap.ram_gb }} GB RAM · ffmpeg {{ cap.ffmpeg ? "✓" : "✗" }} ·
            IA: {{ cap.ia.torch ? cap.ia.dispositivo.toUpperCase() : "no instalada" }}
          </p>
        </section>

        <!-- versiones y A/B -->
        <section class="lab-panel">
          <h3>Versiones</h3>
          <p v-if="!versiones.length" class="tenue">Aún no hay versiones. El original nunca se modifica.</p>
          <div v-for="v in versiones" :key="v.ruta" class="lab-version" :class="{ activo: version?.ruta === v.ruta }" @click="version = v">
            <span>{{ v.id }} · {{ v.formato.toUpperCase() }}</span>
            <span :class="'qc-' + v.calidad?.veredicto">{{ { ok: "QC ok", aviso: "QC aviso", falla: "QC falla" }[v.calidad?.veredicto] }}</span>
            <div class="tenue">{{ v.receta.map((p) => p.id).join(" + ") }}</div>
          </div>

          <template v-if="version">
            <h3>Comparar A/B</h3>
            <div class="lab-ab">
              <button class="wa-boton" @click="alternarAB">{{ ab.sonando ? "Pausa" : "Reproducir" }}</button>
              <button class="wa-boton" :class="{ activo: ab.cual === 'a' }" @click="cambiar('a')">A · original</button>
              <button class="wa-boton" :class="{ activo: ab.cual === 'b' }" @click="cambiar('b')">B · mejorada</button>
              <label><input type="checkbox" v-model="ab.igualar" /> igualar volumen</label>
              <span class="tenue">{{ duracion(Math.floor(ab.tiempo)) }}</span>
            </div>
            <table class="wa-tabla lab-metricas">
              <thead><tr><th></th><th class="num">A</th><th class="num">B</th></tr></thead>
              <tbody><tr v-for="[n, f] in METRICAS.slice(0, 4)" :key="n"><td>{{ n }}</td><td class="num">{{ f(version.antes) }}</td><td class="num">{{ f(version.despues) }}</td></tr></tbody>
            </table>
            <div v-for="c in version.calidad?.chequeos" :key="c.nombre" class="lab-chequeo" :class="{ ok: c.ok }">{{ c.ok ? "✓" : "✗" }} {{ c.nombre }} <span class="tenue">· {{ c.detalle }}</span></div>
            <div class="lab-espectros">
              <figure><img v-if="espectros.a" :src="espectros.a" /><figcaption>A · original</figcaption></figure>
              <figure><img v-if="espectros.b" :src="espectros.b" /><figcaption>B · mejorada</figcaption></figure>
            </div>
          </template>
        </section>
      </div>
    </div>

    <template #pie>
      <span>Formato:</span>
      <select v-model="formato" class="wa-entrada"><option value="flac">FLAC</option><option value="wav">WAV 24 bits</option><option value="mp3">MP3 320</option></select>
      <button class="wa-boton wa-principal" :disabled="!cancion || !elegidos.length || faltaReferencia || ['en_cola', 'procesando'].includes(procesoT?.estado)" :title="faltaReferencia ? 'Elige la canción de referencia' : ''" @click="procesar">
        Procesar ({{ elegidos.length }})
      </button>
      <div v-if="activo(procesoT)" class="wa-barra lab-progreso"><div :style="{ width: procesoT.progreso + '%' }"></div></div>
      <button v-if="activo(procesoT)" class="wa-boton" @click="detener(procesoT)">Detener</button>
      <span class="wa-estado">{{ aviso || (procesoT?.estado === "error" ? procesoT.error : procesoT?.estado === "terminado" ? "Listo: versión creada"
        : procesoT?.estado === "cancelado" ? "Proceso detenido: no se creó ninguna versión" : "") }}</span>
      <span class="wa-espacio"></span>
      <button class="wa-boton" :disabled="!version" @click="enviarVersion">Al reproductor</button>
    </template>
  </VentanaWinamp>
</template>
