<script setup>
// Skin "Cabeza" en vectores (lienzo 760 x 394), con la skin HeadAMP de Winamp 5 como referencia.
// Botones, pantalla, barra, altavoces y deslizadores están dibujados a mano en SVG; la silueta
// y el sombreado de la cabeza y los cajones vienen ya calculados en cabezaVectores.js.
// Todo es vectorial: escala nítida a cualquier tamaño.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import BotonVector from "./BotonVector.vue";
import Trazo from "./Trazo.vue";
import Altavoz from "./Altavoz.vue";
import { crearVisualizador } from "./visualizador.js";
import { anterior, cargar, detener, irA, mmss, motor, pausa, pistaActual, reproducir, siguiente } from "./motor.js";
import { abrirVentana, arrastrarVentana, fijarForma, nativo, siluetaDe } from "../ventanas/nativo.js";
import { agregarArchivos } from "./disco.js";

const props = defineProps({ escala: { type: Number, default: 1 } });
const emit = defineEmits(["menu"]);
import V from "./cabezaVectores.js";
const P = 206; // desplazamiento del grupo del reproductor en el layout
// altavoces de los cajones (centro y radio, medidos sobre el original)
const ALTAVOCES_IZQ = [{ cx: 33.5, cy: 37.5, r: 25 }, { cx: 51, cy: 88.5, r: 23.5 }, { cx: 49.5, cy: 137.5, r: 23 }];
const ALTAVOCES_DER = [{ cx: 237.5, cy: 37.5, r: 25 }, { cx: 219.5, cy: 88.5, r: 23.5 }, { cx: 221.5, cy: 137.5, r: 23 }];

const izquierdo = ref(true);   // cajón del ecualizador abierto
const derecho = ref(true);     // cajón de la lista abierto

// ---------- deslizadores (miden contra el elemento, así funcionan a cualquier escala)
function deslizar(e, eje, aplicar) {
  if (e.button !== 0) return;
  e.preventDefault();
  e.stopPropagation();
  const caja = e.currentTarget.getBoundingClientRect();
  const valor = (ev) => eje === "x"
    ? Math.min(1, Math.max(0, (ev.clientX - caja.left) / caja.width))
    : Math.min(1, Math.max(0, (ev.clientY - caja.top) / caja.height));
  aplicar(valor(e));
  const mover = (ev) => aplicar(valor(ev));
  const soltar = () => {
    window.removeEventListener("pointermove", mover);
    window.removeEventListener("pointerup", soltar);
  };
  window.addEventListener("pointermove", mover);
  window.addEventListener("pointerup", soltar);
}
const balance = (e) => deslizar(e, "x", (f) => (motor.balance = Math.round((f * 2 - 1) * 20) / 20));
const volumen = (e) => deslizar(e, "x", (f) => (motor.volumen = f));
const banda = (i) => (e) => deslizar(e, "y", (f) => { motor.bandas[i] = Math.round((12 - f * 24) * 2) / 2; motor.preset = ""; });
const buscando = ref(null);
const buscar = (e) => motor.duracion && deslizar(e, "x", (f) => (buscando.value = f));
watch(buscando, () => {});
function soltarBusqueda() {
  if (buscando.value !== null) irA(buscando.value * motor.duracion);
  buscando.value = null;
}
onMounted(() => window.addEventListener("pointerup", soltarBusqueda));
onBeforeUnmount(() => window.removeEventListener("pointerup", soltarBusqueda));
const posicion = computed(() => buscando.value ?? (motor.duracion ? motor.tiempo / motor.duracion : 0));

const pausaVisible = computed(() => motor.estado === "sonando");

// ---------- visualizador (en la pantalla de la cabeza, estilo AVS)
const lienzo = ref(null);
const vis = crearVisualizador(48);
const modoVis = ref(0); // 0 flor, 1 barras, 2 osciloscopio
let cuadro = 0, ultimoT = 0, giro = 0;
function dibujar(t) {
  cuadro = requestAnimationFrame(dibujar);
  const c = lienzo.value;
  if (!c) return;
  const dt = Math.min(0.1, (t - ultimoT) / 1000 || 0);
  ultimoT = t;
  const g = c.getContext("2d");
  const W = c.width, H = c.height;
  g.fillStyle = "rgba(0,0,0,0.18)";
  g.fillRect(0, 0, W, H);
  const r = vis.leer(dt, modoVis.value === 2);
  if (modoVis.value === 2 && r.onda) {
    g.strokeStyle = "#7dff3a";
    g.lineWidth = 2;
    g.beginPath();
    r.onda.forEach((v, i) => (i ? g.lineTo : g.moveTo).call(g, (i / 75) * W, H / 2 + (v - 0.5) * H * 0.9));
    g.stroke();
    return;
  }
  if (modoVis.value === 1) {
    const n = r.barras.length, ancho = W / n;
    r.barras.forEach((h, i) => {
      g.fillStyle = `hsl(${100 - h * 100} 90% 50%)`;
      g.fillRect(i * ancho + 1, H - h * H * 0.9, ancho - 2, h * H * 0.9);
    });
    return;
  }
  // flor giratoria: cada banda es un pétalo, en verde y rojo como el original
  const energia = r.barras.reduce((s, h) => s + h, 0) / r.barras.length;
  giro += dt * (0.4 + energia * 3);
  g.save();
  g.translate(W / 2, H / 2);
  r.barras.forEach((h, i) => {
    if (h < 0.02) return;
    const ang = giro + (i / r.barras.length) * Math.PI * 2;
    const largo = 12 + h * Math.min(W, H) * 0.55;
    g.rotate((Math.PI * 2) / r.barras.length);
    g.strokeStyle = i % 2 ? `hsla(110, 95%, ${40 + h * 30}%, .9)` : `hsla(${10 + h * 20}, 95%, ${45 + h * 20}%, .85)`;
    g.lineWidth = 2 + h * 4;
    g.beginPath();
    g.moveTo(Math.cos(ang) * 6, Math.sin(ang) * 6);
    g.quadraticCurveTo(Math.cos(ang + 0.6) * largo * 0.6, Math.sin(ang + 0.6) * largo * 0.6, Math.cos(ang) * largo, Math.sin(ang) * largo);
    g.stroke();
  });
  g.restore();
}
onMounted(() => (cuadro = requestAnimationFrame(dibujar)));
onBeforeUnmount(() => cancelAnimationFrame(cuadro));

// ---------- título en pantalla al cambiar de canción
const aviso = ref("");
let reloj = 0;
watch(() => motor.aviso, (a) => {
  if (!a) return;
  aviso.value = a;
  clearTimeout(reloj);
  reloj = setTimeout(() => (aviso.value = ""), 4500);
});
watch(() => motor.actual, () => {
  const p = pistaActual();
  if (!p) return;
  aviso.value = `${p.artista ? p.artista + " - " : ""}${p.titulo}`;
  clearTimeout(reloj);
  reloj = setTimeout(() => (aviso.value = ""), 4000);
});

// ---------- forma de la ventana: solo la cabeza y los cajones reciben clics y se ven
const piezas = (izq, der) => [
  { filas: V.izquierdo.filas, x: izq ? 0 : 207, y: 86 },
  { filas: V.derecho.filas, x: der ? 488 : 277, y: 86 },
  { filas: V.cabeza.filas, x: P + 54, y: 0 },
];
let finCajon = 0;
function actualizarForma(antes) {
  const ahora = piezas(izquierdo.value, derecho.value);
  clearTimeout(finCajon);
  if (antes) { // mientras el cajón se desliza: la unión de ambas posiciones
    fijarForma("skin", siluetaDe([...ahora, ...piezas(...antes)], props.escala));
    finCajon = setTimeout(() => actualizarForma(), 420);
  } else {
    fijarForma("skin", siluetaDe(ahora, props.escala));
  }
}
watch([izquierdo, derecho], (_, antes) => actualizarForma(antes));
watch(() => props.escala, () => actualizarForma());
onMounted(() => actualizarForma());
onBeforeUnmount(() => { clearTimeout(finCajon); fijarForma("skin", null); });

// ---------- lista
const lista = ref(null);
watch(() => motor.actual, async () => {
  await nextTick();
  lista.value?.querySelector(".ha-fila.actual")?.scrollIntoView({ block: "nearest" });
});
</script>

<template>
  <div class="headamp" :style="{ transform: `scale(${escala})` }" @contextmenu.prevent="emit('menu', $event)">
    <!-- ===== cajón izquierdo: ecualizador (detrás de la cabeza) ===== -->
    <div class="ha-cajon" :style="{ left: (izquierdo ? 0 : 207) + 'px', top: '86px', width: '266px', height: '169px' }">
      <svg class="ha-fondo" width="266" height="169" viewBox="0 0 266 169" @pointerdown="arrastrarVentana">
        <Trazo id="ha-izq" :datos="V.izquierdo">
          <Altavoz v-for="(a, k) in ALTAVOCES_IZQ" :key="k" v-bind="a" />
          <rect x="86" y="13" width="162" height="141" fill="#285f03" />
          <rect x="86" y="13" width="162" height="2" fill="#1c4700" />
          <!-- rieles: balance, volumen y 10 bandas -->
          <rect x="96" y="25.5" width="62" height="2" rx="1" fill="#79d420" />
          <rect x="177" y="25.5" width="62" height="2" rx="1" fill="#79d420" />
          <text x="127" y="42" class="ha-rotulo">Balance</text>
          <text x="208" y="42" class="ha-rotulo">Volume</text>
          <rect v-for="i in 10" :key="i" :x="98.5 + (i - 1) * 15" y="58" width="2" height="66" rx="1" fill="#79d420" />
        </Trazo>
      </svg>
      <BotonVector forma="pestana-izq" :abierto="izquierdo" :x="8" :y="66" :w="18" :h="66"
                   :titulo="izquierdo ? 'Cerrar ecualizador' : 'Abrir ecualizador'" @click="izquierdo = !izquierdo" />
      <BotonVector forma="x" :x="71" :y="7" :w="11" :h="11" titulo="Cerrar ecualizador" @click="izquierdo = false" />
      <!-- balance -->
      <span class="ha-tope h" style="left: 92px; top: 21px" @click="motor.balance = -1"></span>
      <div class="ha-zona" style="left: 97px; top: 21px; width: 60px; height: 11px" @pointerdown="balance" @dblclick="motor.balance = 0">
        <div class="ha-perilla" :style="{ left: ((motor.balance + 1) / 2) * 49 + 'px' }"></div>
      </div>
      <span class="ha-tope h" style="left: 156px; top: 21px" @click="motor.balance = 1"></span>
      <!-- volumen -->
      <span class="ha-tope h" style="left: 173px; top: 21px" @click="motor.volumen = 0"></span>
      <div class="ha-zona" style="left: 178px; top: 21px; width: 60px; height: 11px" @pointerdown="volumen">
        <div class="ha-perilla" :style="{ left: motor.volumen * 49 + 'px' }"></div>
      </div>
      <span class="ha-tope h" style="left: 238px; top: 21px" @click="motor.volumen = 1"></span>
      <!-- 10 bandas -->
      <template v-for="(db, i) in motor.bandas" :key="i">
        <span class="ha-tope v" :style="{ left: 94 + i * 15 + 'px', top: '54px' }" @click="motor.bandas[i] = 12"></span>
        <div class="ha-zona" :style="{ left: 94 + i * 15 + 'px', top: '58px', width: '11px', height: '66px' }"
             @pointerdown="banda(i)($event)" @dblclick="motor.bandas[i] = 0">
          <div class="ha-perilla" :style="{ top: ((12 - db) / 24) * 55 + 'px' }"></div>
        </div>
        <span class="ha-tope v" :style="{ left: 94 + i * 15 + 'px', top: '124px' }" @click="motor.bandas[i] = -12"></span>
      </template>
      <BotonVector forma="reset" :x="220" :y="138" :w="26" :h="10" titulo="Restablecer ecualizador"
                   @click="motor.bandas = motor.bandas.map(() => 0); motor.preset = 'Plano'" />
    </div>

    <!-- ===== cajón derecho: lista ===== -->
    <div class="ha-cajon" :style="{ left: (derecho ? 488 : 277) + 'px', top: '86px', width: '271px', height: '170px' }">
      <svg class="ha-fondo" width="271" height="170" viewBox="0 0 271 170" @pointerdown="arrastrarVentana">
        <Trazo id="ha-der" :datos="V.derecho">
          <Altavoz v-for="(a, k) in ALTAVOCES_DER" :key="k" v-bind="a" />
          <rect x="9" y="7" width="180" height="147" fill="#285f03" />
          <rect x="9" y="7" width="180" height="2" fill="#1c4700" />
        </Trazo>
      </svg>
      <BotonVector forma="pestana-der" :abierto="derecho" :x="244" :y="66" :w="18" :h="67"
                   :titulo="derecho ? 'Cerrar lista' : 'Abrir lista'" @click="derecho = !derecho" />
      <BotonVector forma="x" :x="188" :y="7" :w="11" :h="11" titulo="Cerrar lista" @click="derecho = false" />
      <div ref="lista" class="ha-lista" style="left: 12px; top: 10px; width: 172px; height: 140px">
        <div v-for="(p, i) in motor.lista" :key="i" class="ha-fila" :class="{ actual: i === motor.actual }" @dblclick="cargar(i)">
          <span class="ha-nombre">{{ i + 1 }}. {{ p.artista ? p.artista + " - " : "" }}{{ p.titulo }}</span>
          <span>{{ mmss(p.duracion) }}</span>
        </div>
        <div v-if="!motor.lista.length" class="ha-vacia">Lista vacía.<br />
          <a @click="agregarArchivos">Agregar archivos</a><br /><a @click="abrirVentana('biblioteca')">Abrir la biblioteca</a><br />
          o arrastra música aquí</div>
      </div>
    </div>

    <!-- ===== la cabeza ===== -->
    <svg class="ha-cabeza" width="234" height="394" viewBox="0 0 234 394" :style="{ left: P + 54 + 'px', top: 0 }" @pointerdown="arrastrarVentana">
      <defs>
        <linearGradient id="ha-borde-pantalla" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#2e7d00" /><stop offset="1" stop-color="#9df03a" />
        </linearGradient>
        <linearGradient id="ha-barra" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#4a1d58" /><stop offset=".45" stop-color="#d9a2e8" /><stop offset="1" stop-color="#5a2a6a" />
        </linearGradient>
      </defs>
      <Trazo id="ha-cab" :datos="V.cabeza" :suave="1.4">
        <!-- pantalla -->
        <path d="M26 57.5Q117 53 208 57.5Q225 58.5 225.5 76L225.5 200Q225.5 225.5 200 225.5L34 225.5Q8 225.5 8 200L8 76Q8.5 58.5 26 57.5Z"
              fill="url(#ha-borde-pantalla)" />
        <path d="M27 60Q117 56 207 60Q222.5 61 223 77L223 199Q223 223 199 223L35 223Q10.5 223 10.5 199L10.5 77Q11 61 27 60Z" fill="#000" />
        <!-- barra de posición -->
        <rect x="38" y="223.5" width="164" height="9" rx="4.5" fill="#2a5a00" opacity=".55" />
        <rect x="39" y="224.5" width="162" height="7" rx="3.5" fill="url(#ha-barra)" />
        <path v-for="k in 6" :key="k" :d="`M${39 + k * 23.1} 225v6`" stroke="#4a1d58" stroke-width=".8" opacity=".7" />
        <!-- emblema: un rayo dentro de un rombo -->
        <g transform="translate(119 249)" fill="none" stroke="#1f5200" stroke-width="1.6" stroke-linejoin="round">
          <path d="M-9 -9H5L9 -5V9H-5L-9 5Z" fill="#b6f53a" />
          <path d="M2 -7L-4 1H1L-2 7L5 -1H0Z" fill="#e9ff8a" stroke-width="1" />
        </g>
      </Trazo>
    </svg>
    <canvas ref="lienzo" class="ha-vis" width="382" height="276" :style="{ left: P + 77 + 'px', top: '63px' }"
            title="Clic: cambiar visualización" @click="modoVis = (modoVis + 1) % 3"></canvas>
    <div v-if="aviso" class="ha-aviso" :style="{ left: P + 84 + 'px', top: '70px' }">{{ aviso }}</div>
    <div v-if="motor.estado !== 'detenido'" class="ha-tiempo" :style="{ left: P + 84 + 'px', top: '186px' }"
         @click="motor.restante = !motor.restante">{{ motor.restante ? "-" + mmss(motor.duracion - motor.tiempo) : mmss(motor.tiempo) }}</div>

    <BotonVector forma="minimizar" :x="P + 155" :y="4" :w="14" :h="16" titulo="Minimizar" @click="nativo()?.minimizar()" />
    <BotonVector forma="cerrar" :x="P + 170" :y="4" :w="15" :h="16" titulo="Cerrar" @click="nativo()?.cerrar()" />

    <BotonVector forma="anterior" :x="P + 102" :y="31" :w="25" :h="25" titulo="Anterior" @click="anterior" />
    <BotonVector v-if="!pausaVisible" forma="reproducir" :x="P + 127" :y="31" :w="25" :h="25" titulo="Reproducir" @click="reproducir" />
    <BotonVector v-else forma="pausa" :x="P + 127" :y="31" :w="25" :h="25" titulo="Pausa" @click="pausa" />
    <BotonVector forma="detener" :x="P + 152" :y="31" :w="25" :h="25" titulo="Detener" @click="detener" />
    <BotonVector forma="siguiente" :x="P + 177" :y="31" :w="25" :h="25" titulo="Siguiente" @click="siguiente()" />
    <BotonVector forma="menu" :x="P + 220" :y="31" :w="25" :h="25" titulo="Menú de MigueWamp" @click="emit('menu', $event)" />

    <!-- barra de posición -->
    <div class="ha-zona" :style="{ left: P + 93 + 'px', top: '223px', width: '163px', height: '9px' }" @pointerdown="buscar">
      <div v-if="motor.duracion" class="ha-perilla-pos" :style="{ left: posicion * 145 + 'px' }"></div>
    </div>
    <BotonVector forma="eq" :x="P + 69" :y="214" :w="20" :h="19" titulo="Ecualizador" @click="izquierdo = !izquierdo" />
    <BotonVector forma="lista" :x="P + 258" :y="214" :w="19" :h="20" titulo="Lista" @click="derecho = !derecho" />
  </div>
</template>

<style>
.headamp { position: absolute; left: 0; top: 0; width: 760px; height: 394px; transform-origin: 0 0; }
.headamp svg { user-select: none; }
.ha-cajon { position: absolute; transition: left .35s ease-out; }
.ha-fondo { position: absolute; left: 0; top: 0; overflow: visible; }
.ha-cabeza { position: absolute; overflow: visible; }
.ha-rotulo { font: 8.5px Tahoma, Verdana, sans-serif; fill: #8fe02a; text-anchor: middle; }
.ha-zona { position: absolute; cursor: pointer; }
/* perillas y topes en vectores (degradados CSS): nítidos a cualquier tamaño */
.ha-perilla { position: absolute; left: 0; top: 0; width: 11px; height: 11px; pointer-events: none; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #fff 0, #cfcfcf 22%, #7a7a7a 60%, #2b2b2b 100%);
  box-shadow: 0 .5px 1px rgba(0, 0, 0, .6); }
.ha-tope { position: absolute; cursor: pointer;
  background: radial-gradient(ellipse at 40% 30%, #eee 0, #9a9a9a 45%, #3a3a3a 100%); }
.ha-tope.h { width: 5px; height: 11px; border-radius: 3px; }
.ha-tope.v { width: 11px; height: 5px; border-radius: 3px; }
.ha-perilla-pos { position: absolute; top: 0; width: 18px; height: 9px; pointer-events: none; border-radius: 4.5px;
  background: linear-gradient(#f4d6ff, #b65ad4 55%, #5d1a78); box-shadow: 0 0 0 .6px #2c0b3a, 0 0 4px #e6a6ff; }
.ha-vis { position: absolute; width: 191px; height: 138px; border-radius: 22px 22px 30px 30px; cursor: pointer; }
.ha-aviso { position: absolute; width: 176px; color: #b8ff7a; font: bold 11px Tahoma, Verdana, sans-serif;
  text-shadow: 0 0 4px #000; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; pointer-events: none; }
.ha-tiempo { position: absolute; color: #b8ff7a; font: bold 12px Consolas, monospace; text-shadow: 0 0 4px #000; cursor: pointer; }
.ha-lista { position: absolute; overflow-y: auto; font: bold 10.5px Tahoma, Verdana, sans-serif; color: #fff; line-height: 15px; }
.ha-lista::-webkit-scrollbar { width: 9px; }
.ha-lista::-webkit-scrollbar-track { background: #fff; }
.ha-lista::-webkit-scrollbar-thumb { background: #1f3f10; border: 2px solid #fff; }
.ha-fila { display: flex; gap: 6px; padding: 0 3px; cursor: default; }
.ha-fila.actual { color: #3cff2a; }
.ha-nombre { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ha-vacia { color: #d8ffb0; padding: 26px 6px; text-align: center; font-weight: normal; line-height: 17px; }
.ha-vacia a { color: #fff; text-decoration: underline; cursor: pointer; }
</style>
