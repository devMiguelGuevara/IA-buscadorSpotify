<script setup>
// "Abrir ubicación": pegar enlaces de YouTube, Spotify, SoundCloud..., rutas de listas
// o canciones sueltas, una por línea. Revisa qué hay y descarga.
import { computed, onMounted, ref } from "vue";
import VentanaWinamp from "./VentanaWinamp.vue";
import { api, nativo, pista } from "../api.js";

const emit = defineEmits(["cerrar", "iniciada", "reproducir"]);
const texto = ref("");
const listas = ref(null);
const ocupado = ref(false);
const error = ref("");
const area = ref(null);
const hayNativo = ref(false);
// Cómo descargar: se recuerda en ajustes.json
const metodo = ref("auto");
const formato = ref("original");
const METODOS = { auto: "Automático", ytmusic: "Solo YouTube Music", youtube: "Solo YouTube", soundcloud: "Solo SoundCloud" };
const FORMATOS = { original: "Máxima calidad (original)", mp3: "MP3 320 (compatibilidad)" };

async function leerPreferencias() {
  hayNativo.value = true;
  const d = (await nativo()?.leer_ajustes())?.descargas || {};
  if (METODOS[d.metodo]) metodo.value = d.metodo;
  if (FORMATOS[d.formato]) formato.value = d.formato;
}
const guardarPreferencias = () =>
  nativo()?.guardar_ajustes({ descargas: { metodo: metodo.value, formato: formato.value } });

onMounted(() => {
  area.value?.focus();
  if (nativo()) leerPreferencias();
  else window.addEventListener("pywebviewready", leerPreferencias, { once: true });
});

const resumen = computed(() => {
  if (!listas.value) return null;
  const items = listas.value.flatMap((l) => l.items);
  return { total: items.length, tengo: items.filter((i) => i.archivo).length };
});

async function elegirArchivo() {
  const ruta = await nativo()?.elegir_archivo();
  if (ruta) texto.value = (texto.value.trim() ? texto.value.trim() + "\n" : "") + ruta;
}

function limpiar() {
  texto.value = "";
  listas.value = null;
  error.value = "";
}

async function revisar() {
  if (!texto.value.trim()) return;
  ocupado.value = true;
  error.value = "";
  try {
    listas.value = (await api.resolver(texto.value)).listas;
  } catch (e) {
    error.value = String(e);
  } finally {
    ocupado.value = false;
  }
}

async function descargar(simular) {
  ocupado.value = true;
  try {
    await api.descargar(texto.value, simular, metodo.value, formato.value);
    emit("iniciada");
  } catch (e) {
    error.value = String(e);
    ocupado.value = false;
  }
}

function agregarLasQueTengo() {
  const pistas = listas.value.flatMap((l) => l.items).filter((i) => i.archivo)
    .map((i) => pista({ raiz: 0, ruta: i.archivo, titulo: i.titulo, artista: i.artista }));
  if (pistas.length) emit("reproducir", pistas);
  emit("cerrar");
}

</script>

<template>
  <VentanaWinamp titulo="MigueWamp · Abrir ubicación" @cerrar="emit('cerrar')">
    <div class="ou">
      <label class="ou-ayuda">Enlaces, rutas o canciones, uno por línea:</label>
      <textarea ref="area" v-model="texto" class="wa-entrada ou-texto" spellcheck="false"
                placeholder="https://www.youtube.com/watch?v=…&#10;https://open.spotify.com/playlist/…&#10;C:\Música\lista.xlsx&#10;Caifanes - Afuera"
                @keydown.ctrl.enter.prevent="revisar"></textarea>
      <p class="ou-ejemplos">YouTube y YouTube Music · Spotify: playlist, álbum, canción o <b>guardadas</b> · SoundCloud · Excel, CSV o TXT · "Artista - Título"</p>

      <div class="ou-opciones">
        <label>Buscar en
          <select v-model="metodo" class="wa-entrada" @change="guardarPreferencias">
            <option v-for="(t, k) in METODOS" :key="k" :value="k">{{ t }}</option>
          </select>
        </label>
        <label>Guardar como
          <select v-model="formato" class="wa-entrada" @change="guardarPreferencias">
            <option v-for="(t, k) in FORMATOS" :key="k" :value="k">{{ t }}</option>
          </select>
        </label>
      </div>
      <p v-if="formato === 'mp3'" class="ou-ejemplos">Convertir a MP3 no suma calidad: solo sirve para equipos que no leen Opus o M4A.</p>

      <p v-if="error" class="wa-error">{{ error }}</p>

      <div v-if="listas" class="ou-vista">
        <div v-for="l in listas" :key="l.fuente">
          <div class="ou-lista"><b>{{ l.nombre }}</b><span v-if="!l.error" class="tenue"> · {{ l.items.length }} canciones</span></div>
          <p v-if="l.error" class="wa-error">{{ l.error }}</p>
          <table class="wa-tabla" v-else>
            <tbody>
              <tr v-for="(it, i) in l.items" :key="i">
                <td>{{ it.artista }}</td><td>{{ it.titulo }}</td><td class="num">{{ it.duracion }}</td>
                <td :class="it.archivo ? 'ou-tengo' : 'ou-nueva'">{{ it.archivo ? "ya en biblioteca" : it.url ? "nueva · enlace" : "nueva · buscar" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <template #pie>
      <button v-if="hayNativo" class="wa-boton" @click="elegirArchivo">Archivo…</button>
      <button class="wa-boton" :disabled="ocupado || !texto.trim()" @click="revisar">{{ ocupado && !listas ? "Revisando…" : "Revisar" }}</button>
      <span class="wa-estado" v-if="resumen">{{ resumen.total - resumen.tengo }} nuevas · {{ resumen.tengo }} ya están</span>
      <span class="wa-espacio"></span>
      <template v-if="listas">
        <button class="wa-boton" :disabled="!resumen?.tengo" @click="agregarLasQueTengo">Agregar las que tengo</button>
        <button class="wa-boton" :disabled="ocupado" @click="descargar(true)">Probar</button>
        <button class="wa-boton wa-principal" :disabled="ocupado || !resumen?.total" @click="descargar(false)">Descargar</button>
      </template>
      <button class="wa-boton" :disabled="!texto && !listas" title="Vacía el texto y la vista previa" @click="limpiar">Limpiar</button>
      <button class="wa-boton" @click="emit('cerrar')">Cancelar</button>
    </template>
  </VentanaWinamp>
</template>
