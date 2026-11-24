<script setup>
// Letra de la canción que suena, a pantalla completa (botón K). Se busca una vez y queda guardada.
// - Sincronizada: la línea que suena se resalta solo con color; el texto no se mueve solo
//   (salvo que se active «Seguir»).
// - Solo texto: avanza despacio con la canción.
// Se lee siempre en horizontal y en grande: con la pantalla vertical, la vista aparece girada
// (la app no gira; solo esta vista). Los tamaños se miden sobre la vista ya girada.
// remoto: la ventana propia del escritorio, que sigue al reproductor a través del servicio interno.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { motor, pistaActual } from "../reproductor/motor.js";
import { buscarLetra } from "../letras.js";

const props = defineProps({ remoto: { type: Boolean, default: false } });
const emit = defineEmits(["cerrar"]);

// ---------- qué suena y en qué segundo
const lejos = reactive({ url: "", titulo: "", artista: "", duracion: 0, tiempo: 0, estado: "detenido", velocidad: 1, recibido: 0 });
const reloj = ref(performance.now());
const pista = computed(() => {
  if (!props.remoto) return pistaActual();
  return lejos.url ? { url: lejos.url, titulo: lejos.titulo, artista: lejos.artista } : null;
});
const duracion = computed(() => (props.remoto ? lejos.duracion : motor.duracion) || 0);
const tiempo = computed(() => {
  if (!props.remoto) return motor.tiempo || 0;
  const avance = lejos.estado === "sonando" ? ((reloj.value - lejos.recibido) / 1000) * (lejos.velocidad || 1) : 0;
  return lejos.tiempo + avance;
});

async function preguntar() {
  try {
    const r = await fetch("/api/sonando");
    if (!r.ok) return;
    const d = await r.json();
    Object.assign(lejos, d, { recibido: performance.now() - (d.estado === "sonando" ? (d.edad || 0) * 1000 : 0) });
  } catch { /* el reproductor se cerró: queda lo último */ }
}

// ---------- la letra
const resultado = ref({ tipo: "buscando", lineas: [] });
let turno = 0;
async function cargar(forzar = false) {
  const p = pista.value;
  const mio = ++turno; // si cambia la canción mientras busca, esta respuesta ya no cuenta
  if (!p) {
    resultado.value = { tipo: "sin_cancion", lineas: [] };
    return;
  }
  resultado.value = { tipo: "buscando", lineas: [] };
  const r = await buscarLetra(p, { forzar });
  if (mio !== turno) return;
  resultado.value = r;
  await nextTick();
  if (cuerpo.value) cuerpo.value.scrollTop = 0;
}
watch(() => pista.value?.url, () => cargar());

const sincronizada = computed(() => resultado.value.tipo === "sincronizada");
const activa = computed(() => {
  if (!sincronizada.value) return -1;
  const t = tiempo.value + 0.15; // un pelo antes: se lee justo cuando se canta
  const lineas = resultado.value.lineas;
  for (let i = lineas.length - 1; i >= 0; i--) if (lineas[i][0] <= t) return i;
  return -1;
});

// ---------- desplazamiento
const cuerpo = ref(null);
const seguir = ref(false);
let tocadoEn = 0;
const tocar = () => (tocadoEn = performance.now());
watch(activa, async (i) => {
  if (!seguir.value || i < 0) return;
  await nextTick();
  cuerpo.value?.querySelector(".lt-linea.activa")?.scrollIntoView({ block: "center", behavior: "smooth" });
});
// Solo texto: baja al ritmo de la canción, salvo unos segundos después de moverlo a mano.
watch(tiempo, (t) => {
  const c = cuerpo.value;
  if (resultado.value.tipo !== "texto" || !c || !duracion.value || performance.now() - tocadoEn < 6000) return;
  const progreso = Math.min(1, Math.max(0, (t - 8) / Math.max(1, duracion.value - 20)));
  c.scrollTop = progreso * (c.scrollHeight - c.clientHeight);
});

// Con la pantalla vertical, la vista se gira para leer en horizontal.
const pantalla = reactive({ ancho: window.innerWidth, alto: window.innerHeight });
const medir = () => Object.assign(pantalla, { ancho: window.innerWidth, alto: window.innerHeight });
const girada = computed(() => pantalla.alto > pantalla.ancho);
const estiloGiro = computed(() => (girada.value
  ? { width: `${pantalla.alto}px`, height: `${pantalla.ancho}px`, transform: `translateX(${pantalla.ancho}px) rotate(90deg)` }
  : {}));

function tecla(e) {
  if (e.key === "Escape") emit("cerrar");
}

let consulta = 0, tic = 0;
onMounted(async () => {
  window.addEventListener("keydown", tecla);
  window.addEventListener("resize", medir);
  if (props.remoto) {
    await preguntar();
    consulta = setInterval(preguntar, 500);
    tic = setInterval(() => (reloj.value = performance.now()), 200);
  }
  cargar();
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", tecla);
  window.removeEventListener("resize", medir);
  clearInterval(consulta);
  clearInterval(tic);
});
</script>

<template>
  <div class="lt" @contextmenu.prevent>
    <div class="lt-marco" :class="{ girada }" :style="estiloGiro">
      <header class="lt-cabeza">
        <div class="lt-cancion">
          <b>{{ pista?.titulo || "MigueWamp" }}</b>
          <span v-if="pista?.artista"> · {{ pista.artista }}</span>
        </div>
        <button v-if="sincronizada" class="lt-seguir" :class="{ activo: seguir }" title="Que la letra siga a la canción"
                @click="seguir = !seguir">Seguir</button>
        <button class="lt-cerrar" title="Cerrar (Esc)" aria-label="Cerrar" @click="emit('cerrar')">✕</button>
      </header>

      <main ref="cuerpo" class="lt-cuerpo" :class="resultado.tipo" @wheel="tocar" @touchstart="tocar" @pointerdown="tocar">
        <p v-if="resultado.tipo === 'buscando'" class="lt-aviso">Buscando la letra…</p>
        <p v-else-if="resultado.tipo === 'sin_cancion'" class="lt-aviso">No hay ninguna canción sonando.</p>
        <p v-else-if="resultado.tipo === 'instrumental'" class="lt-aviso">♪ Instrumental ♪</p>
        <div v-else-if="resultado.tipo === 'ninguna'" class="lt-aviso">
          <p>No encontré la letra de esta canción.</p>
          <button class="lt-boton" @click="cargar(true)">Buscar de nuevo</button>
        </div>
        <template v-else>
          <p v-for="([segundos, texto], i) in resultado.lineas" :key="i" class="lt-linea"
             :class="{ activa: i === activa, pasada: sincronizada && i < activa, vacia: !texto }">{{ texto || "♪" }}</p>
        </template>
      </main>
    </div>
  </div>
</template>

<style scoped>
.lt { position: fixed; inset: 0; z-index: 10001; background: #050506; color: #f3efe6; overflow: hidden;
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; user-select: text; }
.lt-marco { position: absolute; inset: 0; display: flex; flex-direction: column; container-type: size; }
.lt-marco.girada { inset: auto; top: 0; left: 0; transform-origin: top left; }

.lt-cabeza { display: flex; align-items: center; gap: 12px; padding: max(12px, env(safe-area-inset-top, 0px)) 16px 10px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, .08); }
.lt-cancion { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 15px; opacity: .8; }
.lt-cancion span { opacity: .7; }
.lt-seguir, .lt-boton { background: transparent; color: inherit; border: 1px solid rgba(255, 255, 255, .25); border-radius: 999px;
  padding: 6px 14px; font: inherit; font-size: 13px; cursor: pointer; }
.lt-seguir.activo { background: #ffd36b; color: #1a1300; border-color: #ffd36b; }
.lt-cerrar { width: 44px; height: 44px; flex: none; border-radius: 50%; border: 0; background: rgba(255, 255, 255, .08);
  color: inherit; font-size: 20px; cursor: pointer; }
.lt-cerrar:hover { background: rgba(255, 255, 255, .18); }

.lt-cuerpo { flex: 1; overflow-y: auto; padding: 6cqh 6cqw 30cqh; text-align: center; scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, .2) transparent; overscroll-behavior: contain; }
.lt-linea { margin: 0 auto .5em; max-width: 1400px; line-height: 1.25; font-size: clamp(24px, 4.2cqw, 64px);
  opacity: .55; transition: color .25s, opacity .25s; }
.lt-linea.pasada { opacity: .35; }
.lt-linea.activa { opacity: 1; color: #ffd36b; font-weight: 700; text-shadow: 0 0 18px rgba(255, 200, 90, .35); }
.lt-linea.vacia { opacity: .25; }
.lt-cuerpo.texto .lt-linea { opacity: .92; font-size: clamp(22px, 3.6cqw, 54px); margin-bottom: .3em; }
.lt-aviso { margin-top: 20cqh; font-size: clamp(18px, 2.6cqw, 28px); opacity: .75; }
.lt-aviso p { margin: 0 0 18px; }
/* Vista bajita (la del teléfono, girada): cabecera mínima para dejarle el espacio a la letra. */
@container (max-height: 520px) {
  .lt-cabeza { padding-top: 6px; padding-bottom: 4px; }
  .lt-cerrar { width: 38px; height: 38px; }
  .lt-cuerpo { padding: 3cqh 5cqw 40cqh; }
  .lt-aviso { margin-top: 12cqh; }
}
</style>
