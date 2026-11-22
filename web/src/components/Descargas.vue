<script setup>
// Descargas: la cola de trabajos, cada uno con sus canciones y su estado.
import { computed, onMounted, ref } from "vue";
import VentanaWinamp from "./VentanaWinamp.vue";
import { estado, revisarDescargas } from "../estado.js";
import { api, pista } from "../api.js";
import { encolarEnReproductor } from "../ventanas/nativo.js";

const emit = defineEmits(["cerrar", "abrir"]);
const descargadas = (t) => t.items.filter((i) => i.estado === "ok" && i.archivo)
  .map((i) => pista({ raiz: 0, ruta: i.archivo, titulo: i.titulo, artista: i.artista }));

const etiquetaEstado = {
  en_cola: "en cola", ok: "descargada", simulado: "encontrada", sin_resultados: "sin resultados",
  fallo: "falló", pospuesta: "pospuesta",
};
const etiquetaTrabajo = {
  preparando: "preparando…", descargando: "descargando…", pausado: "en pausa", cancelando: "cancelando…",
  cancelado: "cancelado", terminado: "terminado", error: "error",
};
async function controlar(t, accion) {
  Object.assign(t, await api.controlar(t.id, accion));
}
const calidad = (q) => (q ? `${q.codec || "?"} ${q.kbps || "?"} kbps` : "");

// Re-descargar en máxima calidad lo que hoy es MP3 (el MP3 se conserva en _reemplazados/)
const mejorables = ref(0);
const confirmando = ref(false);
onMounted(async () => {
  try { mejorables.value = (await api.mejorables()).canciones; } catch {}
});
async function mejorar() {
  confirmando.value = false;
  await api.mejorar(false);
  mejorables.value = 0;
  revisarDescargas();
}

// yt-dlp: el motor de descargas. Se actualiza desde aquí, sin reempaquetar.
const detalle = (e) => { const m = String(e.message).replace(/^\d+ /, ""); try { return JSON.parse(m).detail || m; } catch { return m; } };
const yt = ref({ texto: "", ocupado: false, nueva: null });
async function ytEstado() {
  try {
    const e = await api.ytdlp();
    yt.value.texto = e.pendiente ? `yt-dlp ${e.pendiente} lista: reinicia la app` : `yt-dlp ${e.version}`;
  } catch {}
}
onMounted(ytEstado);
async function ytBuscar() {
  yt.value.ocupado = true;
  try {
    const e = await api.ytdlpBuscar();
    yt.value.nueva = e.hay_nueva ? e.ultima : null;
    if (!e.hay_nueva) yt.value.texto = `yt-dlp ${e.pendiente || e.version}: al día`;
  } catch (e) {
    yt.value.texto = "No se pudo revisar: " + detalle(e);
  }
  yt.value.ocupado = false;
}
async function ytActualizar() {
  yt.value.ocupado = true;
  try {
    const r = await api.ytdlpActualizar();
    yt.value.texto = `yt-dlp ${r.version} lista: reinicia la app`;
    yt.value.nueva = null;
  } catch (e) {
    yt.value.texto = detalle(e);
  }
  yt.value.ocupado = false;
}

// Limpiar: saca de la lista lo terminado, cancelado o con error.
const terminados = computed(() => estado.trabajos.filter((t) => ["terminado", "cancelado", "error"].includes(t.estado)).length);
async function limpiarTerminados() {
  try { await api.limpiarDescargas(); } catch {}
  await revisarDescargas();
}

function progreso(t) {
  const hechos = t.items.filter((i) => i.estado !== "en_cola").length;
  return t.items.length ? Math.round((hechos / t.items.length) * 100) : 0;
}

</script>

<template>
  <VentanaWinamp titulo="MigueWamp · Descargas" @cerrar="emit('cerrar')">
    <div class="dl">
      <div v-if="!estado.trabajos.length" class="wa-vacio">
        <p>No hay descargas.</p>
        <button class="wa-boton" @click="emit('abrir', 'ubicacion')">Abrir ubicación…</button>
      </div>
      <div v-for="t in estado.trabajos" :key="t.id" class="dl-trabajo">
        <div class="dl-cabeza">
          <span class="dl-nombre">{{ t.nombre }}</span>
          <span class="dl-insignia" :class="t.estado">{{ etiquetaTrabajo[t.estado] }}</span>
          <span v-if="t.simular" class="dl-insignia">simulación</span>
          <span v-if="t.ya_estaban" class="tenue">{{ t.ya_estaban }} ya estaban</span>
          <span v-if="t.formato === 'mp3'" class="dl-insignia">MP3</span>
          <span v-if="t.lista" class="tenue">lista con {{ t.lista }}</span>
          <span class="wa-espacio"></span>
          <button v-if="t.estado === 'descargando'" class="wa-boton" @click="controlar(t, 'pausar')">Pausar</button>
          <button v-if="t.estado === 'pausado'" class="wa-boton" @click="controlar(t, 'reanudar')">Reanudar</button>
          <button v-if="t.estado === 'descargando' || t.estado === 'pausado'" class="wa-boton"
                  title="Lo que falte queda pendiente para otra vez" @click="controlar(t, 'cancelar')">Cancelar</button>
          <button v-if="descargadas(t).length" class="wa-boton" @click="encolarEnReproductor('reproducir', descargadas(t))">Reproducir ({{ descargadas(t).length }})</button>
        </div>
        <div class="wa-barra"><div :style="{ width: progreso(t) + '%' }"></div></div>
        <p v-if="t.error" class="wa-error">{{ t.error }}</p>
        <table class="wa-tabla" v-if="t.items.length">
          <tbody>
            <tr v-for="(it, i) in t.items" :key="i">
              <td>{{ it.artista }}</td><td>{{ it.titulo }}</td><td class="num">{{ it.duracion }}</td>
              <td class="dl-estado" :class="it.estado">{{ etiquetaEstado[it.estado] || it.estado }}<span v-if="it.revisar" class="dl-revisar"> · revisar</span></td>
              <td class="tenue">{{ it.fuente }}</td>
              <td class="tenue num">{{ calidad(it.calidad) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <template #pie>
      <button class="wa-boton" @click="emit('abrir', 'ubicacion')">Buscar…</button>
      <button class="wa-boton" :disabled="!terminados" title="Quita de la lista lo ya terminado (los archivos se quedan)"
              @click="limpiarTerminados">Limpiar ({{ terminados }})</button>
      <template v-if="mejorables">
        <button v-if="!confirmando" class="wa-boton" title="Bajar de nuevo en su formato original las canciones que hoy son MP3"
                @click="confirmando = true">Mejorar calidad ({{ mejorables }})</button>
        <template v-else>
          <span class="wa-estado">¿Re-descargar {{ mejorables }}? Los MP3 se guardan en _reemplazados</span>
          <button class="wa-boton wa-principal" @click="mejorar">Sí</button>
          <button class="wa-boton" @click="confirmando = false">No</button>
        </template>
      </template>
      <span class="wa-estado">{{ estado.trabajos.length }} trabajos</span>
      <span class="wa-espacio"></span>
      <span class="wa-estado" title="El motor de descargas. YouTube cambia seguido: conviene tenerlo al día">{{ yt.texto }}</span>
      <button v-if="yt.nueva" class="wa-boton wa-principal" :disabled="yt.ocupado" @click="ytActualizar">Actualizar a {{ yt.nueva }}</button>
      <button v-else class="wa-boton" :disabled="yt.ocupado" @click="ytBuscar">{{ yt.ocupado ? "Revisando…" : "Buscar actualización" }}</button>
    </template>
  </VentanaWinamp>
</template>
