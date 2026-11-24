<script setup>
// Presentación de MigueWamp (doble clic en el rayo dorado del reproductor). Todo pasa en una moneda
// dorada, al centro y sobre negro; cada cambio de escena es la moneda que se voltea:
//  1. La moneda entra girando y se asienta mostrando su sello: el rayo, laureles y la inscripción.
//  2. Se voltea: en el reverso, la mano y la luna (public/presentacion/universo.jpg) con la frase.
//  3. Se voltea otra vez: el retrato (public/presentacion/retrato.webp), y ahí queda.
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";

const emit = defineEmits(["fin"]);
const UNIVERSO = "./presentacion/universo.jpg";
const RETRATO = "./presentacion/retrato.webp";
// Zona de la imagen del universo donde se busca la luna (fracciones del ancho y del alto).
const CAJA_LUNA = { x0: 0.33, x1: 0.70, y0: 0.09, y1: 0.40 };
// El retrato ocupa el ancho de la moneda y este punto suyo (fracciones) cae en el centro.
const CENTRO_RETRATO = { x: 0.5, y: 0.47 };
const ANCHO_RETRATO = 0.9; // fracción del diámetro: deja aire entre el pelo y el borde
// Diámetro de la moneda: una parte del alto, sin pasar de casi todo el ancho en pantallas angostas.
const TAMANO = { alto: 0.42, ancho: 0.82 };
// Línea de tiempo, en segundos.
const T = { giro: 2.8, brillo1: 2.6, vuelta1: 4.6, texto: 6.4, textoFin: 11.4, vuelta2: 12.4, dura: 1.3,
  brillo2: 13.9, final: 14.2, quieto: 15.4, auto: 40 };
const VUELTAS = 1440; // al entrar: 4 vueltas y queda de frente

// El sello: laureles a cada lado (dos ramas que nacen de la estrella), estrías y arcos para el texto.
const SELLO = (() => {
  const rad = (g) => (g * Math.PI) / 180, R = 63;
  const punto = (g) => [R * Math.cos(rad(g)), R * Math.sin(rad(g))];
  const tallos = [], hojas = [];
  for (const [a, b] of [[186, 262], [174, 98], [-6, -82], [6, 82]]) {
    const [x0, y0] = punto(a), [x1, y1] = punto(b), dir = Math.sign(b - a);
    tallos.push(`M${x0.toFixed(2)} ${y0.toFixed(2)}A${R} ${R} 0 0 ${dir > 0 ? 1 : 0} ${x1.toFixed(2)} ${y1.toFixed(2)}`);
    for (let i = 0; i < 7; i++) {
      const u = (i + 0.6) / 7, g = a + (b - a) * u, [x, y] = punto(g), escala = 1 - 0.32 * u;
      for (const lado of [-1, 1]) {
        hojas.push(`translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${(g + 90 * dir + lado * 36).toFixed(1)}) scale(${escala.toFixed(2)})`);
      }
    }
  }
  let estrias = "";
  for (let i = 0; i < 96; i++) {
    const c = Math.cos(rad(i * 3.75)), s = Math.sin(rad(i * 3.75));
    estrias += `M${(46.8 * c).toFixed(2)} ${(46.8 * s).toFixed(2)}L${(51.2 * c).toFixed(2)} ${(51.2 * s).toFixed(2)}`;
  }
  return { tallos, hojas, estrias };
})();

const listo = ref(false);
const final = ref(false);
const d = ref(300);
const moneda = reactive({ giro: "", opacidad: 0, frente: true, luz: 1 });
const caraFrente = ref("sello");
const fondoUniverso = reactive({ backgroundImage: `url(${UNIVERSO})` });
const lunaEstilo = reactive({});
const frase = reactive({ visible: false, velo: 0 });
const reflejo = reactive({ opacity: 0 });
const fotoTop = ref("0%");

let uni, centroLuna, cuerpoLuna, radioLuna, t0 = 0, cuadroId = 0, reloj = 0, terminado = false;

const cargar = (src) => new Promise((ok, mal) => {
  const im = new Image();
  im.onload = () => ok(im);
  im.onerror = mal;
  im.src = src;
});
const lim = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const suave = (v) => { v = lim(v); return v * v * (3 - 2 * v); };
const tramo = (t, a, b) => suave((t - a) / (b - a));
const voltear = (t, a) => { const u = lim((t - a) / T.dura); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; };
const enVuelta = (t, a) => { const u = (t - a) / T.dura; return u > 0 && u < 1 ? Math.sin(Math.PI * u) : 0; };

function medir() {
  d.value = Math.round(Math.min(window.innerWidth * TAMANO.ancho, window.innerHeight * TAMANO.alto));
}

// La luna: el rectángulo de sus píxeles dorados, para encuadrarla y darle un latido de luz.
function buscarLuna() {
  const iw = uni.width, ih = uni.height;
  const x0 = Math.round(CAJA_LUNA.x0 * iw), y0 = Math.round(CAJA_LUNA.y0 * ih);
  const bw = Math.round((CAJA_LUNA.x1 - CAJA_LUNA.x0) * iw), bh = Math.round((CAJA_LUNA.y1 - CAJA_LUNA.y0) * ih);
  const c = Object.assign(document.createElement("canvas"), { width: iw, height: ih }).getContext("2d", { willReadFrequently: true });
  c.drawImage(uni, 0, 0);
  const px = c.getImageData(x0, y0, bw, bh).data;
  let minX = bw, maxX = -1, minY = bh, maxY = -1, sx = 0, sy = 0, n = 0;
  for (let y = 0; y < bh; y++) for (let x = 0; x < bw; x++) {
    const i = (y * bw + x) * 4, r = px[i], g = px[i + 1], b = px[i + 2];
    if (r > 170 && g > 110 && r > b + 60) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
      sx += x; sy += y; n++;
    }
  }
  const hay = maxX >= 0;
  centroLuna = hay ? { x: x0 + (minX + maxX) / 2, y: y0 + (minY + maxY) / 2 } : { x: x0 + bw / 2, y: y0 + bh / 2 };
  cuerpoLuna = hay ? { x: x0 + sx / n, y: y0 + sy / n } : centroLuna; // en una media luna, el brillo va en su cuerpo
  radioLuna = hay ? Math.max(maxX - minX, maxY - minY) / 2 : Math.max(bw, bh) / 2;
}

// El reverso: la imagen cubre la moneda a lo ancho y se acerca despacio; la luna late suave.
function encuadrarUniverso(t) {
  const iw = uni.width, ih = uni.height, D = d.value;
  const zoom = 1 + 0.07 * tramo(t, T.vuelta1, T.vuelta2 + T.dura);
  const radio = Math.min(iw, ih) / 2 / zoom;
  const cx = lim(iw / 2 + (centroLuna.x - iw / 2) * (zoom - 1) * 4, radio, iw - radio);
  const cy = lim(ih * 0.42, radio, ih - radio);
  const k = D / 2 / radio;
  fondoUniverso.backgroundSize = `${iw * k}px ${ih * k}px`;
  fondoUniverso.backgroundPosition = `${D / 2 - cx * k}px ${D / 2 - cy * k}px`;
  const lr = radioLuna * k * 1.25;
  const latido = 0.5 + 0.5 * Math.sin((t - T.vuelta1) * Math.PI * 1.1);
  Object.assign(lunaEstilo, {
    left: `${D / 2 + (cuerpoLuna.x - cx) * k - lr}px`, top: `${D / 2 + (cuerpoLuna.y - cy) * k - lr}px`,
    width: `${2 * lr}px`, height: `${2 * lr}px`,
    opacity: (0.16 + 0.22 * latido) * tramo(t, T.vuelta1 + T.dura, T.vuelta1 + T.dura + 1.5),
  });
}

function cuadro(ahora) {
  if (terminado) return;
  const t = (ahora - t0) / 1000;
  let angulo, inclinacion, escala;
  if (t < T.giro) {
    const e = 1 - Math.pow(1 - t / T.giro, 3);
    angulo = VUELTAS * e;
    inclinacion = 20 * (1 - e);
    escala = 0.15 + 0.85 * e;
  } else {
    const v = Math.max(enVuelta(t, T.vuelta1), enVuelta(t, T.vuelta2)); // la moneda se levanta un poco al voltearse
    angulo = VUELTAS + 180 * (voltear(t, T.vuelta1) + voltear(t, T.vuelta2));
    inclinacion = 7 * v;
    escala = 1 - 0.07 * v;
  }
  const c = Math.cos((angulo * Math.PI) / 180);
  moneda.giro = `rotateX(${inclinacion}deg) rotateY(${angulo}deg) scale(${escala})`;
  moneda.opacidad = lim(t / 0.35);
  moneda.frente = c > 0;
  moneda.luz = 0.6 + 0.4 * Math.abs(c); // de canto se ve más oscura
  // Mientras se ve el reverso, el frente cambia el sello por el retrato.
  if (t >= T.vuelta1 + T.dura / 2 + 0.1) caraFrente.value = "retrato";
  if (t >= T.vuelta1 && t < T.vuelta2 + T.dura) encuadrarUniverso(t);

  frase.visible = t >= T.texto && t < T.textoFin;
  frase.velo = tramo(t, T.texto - 0.4, T.texto + 0.8) * (1 - tramo(t, T.textoFin, T.textoFin + 1.2));
  // Un reflejo cruza el oro al asentarse y al final.
  let b = (t - T.brillo1) / 1.1;
  if (b < 0 || b > 1) b = (t - T.brillo2) / 1.1;
  if (b >= 0 && b <= 1) {
    reflejo.opacity = Math.sin(Math.PI * b);
    reflejo.backgroundPosition = `${150 - 250 * b}% 0`;
  } else reflejo.opacity = 0;

  if (t >= T.final) final.value = true;
  if (t < T.quieto) cuadroId = requestAnimationFrame(cuadro);
}

function cerrar() {
  if (terminado) return;
  terminado = true;
  cancelAnimationFrame(cuadroId);
  emit("fin");
}
function tecla(e) {
  if (e.key === "Escape") cerrar();
}
function clic() {
  if (final.value) cerrar(); // durante la secuencia los clics no hacen nada
}

onMounted(async () => {
  window.addEventListener("keydown", tecla);
  window.addEventListener("resize", medir);
  reloj = setTimeout(cerrar, T.auto * 1000);
  let ret;
  try {
    [uni, ret] = await Promise.all([cargar(UNIVERSO), cargar(RETRATO)]);
  } catch {
    return cerrar();
  }
  buscarLuna();
  medir();
  encuadrarUniverso(T.vuelta1);
  fotoTop.value = `${50 - CENTRO_RETRATO.y * ANCHO_RETRATO * (ret.height / ret.width) * 100}%`;
  listo.value = true;
  t0 = performance.now();
  cuadroId = requestAnimationFrame(cuadro);
});
onBeforeUnmount(() => {
  terminado = true;
  cancelAnimationFrame(cuadroId);
  clearTimeout(reloj);
  window.removeEventListener("keydown", tecla);
  window.removeEventListener("resize", medir);
});
</script>

<template>
  <div class="pr" :class="{ final }" @click="clic" @contextmenu.prevent>
    <div v-if="listo" class="pr-escena">
      <div class="pr-moneda" :style="{ width: d + 'px', height: d + 'px', transform: moneda.giro, opacity: moneda.opacidad }">
        <div v-for="i in 14" :key="i" class="pr-canto" :style="{ transform: `translateZ(${((i - 7.5) / 14) * d * 0.075}px)` }"></div>

        <!-- Frente: el sello y, desde la primera vuelta, el retrato -->
        <div class="pr-cara pr-frente" :class="caraFrente"
             :style="{ transform: `translateZ(${d * 0.0375}px)`, visibility: moneda.frente ? 'visible' : 'hidden', filter: `brightness(${moneda.luz})` }">
          <svg v-if="caraFrente === 'sello'" class="pr-sello" viewBox="-100 -100 200 200">
            <defs>
              <linearGradient id="pr-oro" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#fff1b8" /><stop offset=".45" stop-color="#f0be3a" /><stop offset="1" stop-color="#9c6a08" />
              </linearGradient>
              <radialGradient id="pr-centro" cx=".4" cy=".35" r=".75">
                <stop offset="0" stop-color="#f7d77a" /><stop offset=".6" stop-color="#c8901c" /><stop offset="1" stop-color="#8a5c08" />
              </radialGradient>
              <path id="pr-arco-arriba" d="M-69.28 40A80 80 0 1 1 69.28 40" />
              <path id="pr-arco-abajo" d="M-86 0A86 86 0 0 0 86 0" />
              <g id="pr-grabado" fill="none" stroke="currentColor">
                <circle r="95" stroke-width="3.2" />
                <circle r="74" stroke-width="1.2" />
                <circle r="52" stroke-width="1" />
                <circle r="46" stroke-width="1" />
                <path :d="SELLO.estrias" stroke-width=".9" />
                <path v-for="(p, i) in SELLO.tallos" :key="'t' + i" :d="p" stroke-width=".9" stroke-linecap="round" />
                <path v-for="(h, i) in SELLO.hojas" :key="'h' + i" :transform="h" d="M0 0Q5.5-3.4 12 0Q5.5 3.4 0 0ZM1.6 0H9.5"
                      stroke-width=".75" stroke-linejoin="round" />
                <path v-for="x in [-63, 63]" :key="'e' + x" :transform="`translate(${x} 0)`" d="M0-5Q0 0 5 0Q0 0 0 5Q0 0-5 0Q0 0 0-5Z"
                      fill="currentColor" stroke="none" />
                <text class="pr-inscripcion" fill="currentColor" stroke="none" font-size="9" letter-spacing="1.8">
                  <textPath href="#pr-arco-arriba" startOffset="50%" text-anchor="middle">THE WHOLE UNIVERSE IS HERE TO HELP YOU</textPath>
                </text>
                <text class="pr-inscripcion" fill="currentColor" stroke="none" font-size="9" letter-spacing="3.2">
                  <textPath href="#pr-arco-abajo" startOffset="50%" text-anchor="middle">MIGUEWAMP</textPath>
                </text>
              </g>
            </defs>
            <circle r="46" fill="url(#pr-centro)" />
            <!-- relieve: un filo de luz arriba a la izquierda y el trazo oscuro encima -->
            <use href="#pr-grabado" transform="translate(-.5 -.5)" style="color: rgba(255, 244, 200, .75)" />
            <use href="#pr-grabado" style="color: #5b3d04" />
            <path d="M260 88.5l-7 9h5l-3 8.5 9-11h-5l3-6.5z" transform="scale(3.1) translate(-258.5 -97.25)"
                  fill="url(#pr-oro)" stroke="#4a3200" stroke-width=".35" stroke-linejoin="round" class="pr-rayo" />
          </svg>
          <img v-else class="pr-foto" :src="RETRATO" :style="{ top: fotoTop, width: ANCHO_RETRATO * 100 + '%', left: (1 - ANCHO_RETRATO) * 50 + '%' }"
               alt="" draggable="false" />
          <div class="pr-reflejo" :style="reflejo"></div>
        </div>

        <!-- Reverso: la mano y la luna, con la frase -->
        <div class="pr-cara pr-atras"
             :style="{ ...fondoUniverso, transform: `rotateY(180deg) translateZ(${d * 0.0375}px)`, visibility: moneda.frente ? 'hidden' : 'visible', filter: `brightness(${moneda.luz})` }">
          <div class="pr-luna" :style="lunaEstilo"></div>
          <div class="pr-velo" :style="{ opacity: frase.velo }"></div>
          <p class="pr-frase" :class="{ visible: frase.visible }" :style="{ fontSize: d * 0.043 + 'px' }">
            <span>This software is brought to you by</span><br /><b>Miguel Guevara.</b>
          </p>
          <div class="pr-reflejo" :style="reflejo"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pr { position: fixed; inset: 0; z-index: 10000; overflow: hidden; cursor: default; user-select: none;
  background: radial-gradient(ellipse at center, #0e0e10 0%, #000 72%); animation: pr-entrar .6s ease-out both; }
.pr.final { cursor: pointer; }
@keyframes pr-entrar { from { opacity: 0; } }

.pr-escena { position: absolute; inset: 0; display: grid; place-items: center; perspective: 1100px; }
.pr-moneda { position: relative; transform-style: preserve-3d; }
.pr-canto, .pr-cara { position: absolute; inset: 0; border-radius: 50%; }
.pr-canto { background: radial-gradient(circle at 35% 30%, #e8b440, #8a5c08 70%, #5a3a00); }
.pr-cara { overflow: hidden; }
.pr-frente.sello { background: radial-gradient(circle at 34% 28%, #fff1c0 0%, #f3cb58 20%, #dca52a 45%, #b07a12 72%, #7a5206 100%); }
.pr-frente.retrato { background: #fff; }
.pr-atras::before, .pr-frente.retrato::before { content: ""; position: absolute; inset: 0; border-radius: 50%; z-index: 5;
  pointer-events: none; box-shadow: inset 0 0 0 5px #d9a93a, inset 0 0 0 7px rgba(90, 60, 0, .55), inset 0 0 14px rgba(0, 0, 0, .25); }
.pr-sello { position: absolute; inset: 0; width: 100%; height: 100%; }
.pr-inscripcion { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-weight: 700; }
.pr-rayo { filter: drop-shadow(0 .6px .5px rgba(60, 35, 0, .8)) drop-shadow(0 -.4px .4px rgba(255, 245, 200, .8)); }
.pr-reflejo { position: absolute; inset: 0; border-radius: 50%; pointer-events: none; z-index: 4; mix-blend-mode: screen;
  background: linear-gradient(115deg, transparent 35%, rgba(255, 255, 255, .5) 48%, transparent 60%); background-size: 250% 100%; }

.pr-foto { position: absolute; height: auto; mix-blend-mode: multiply; }
.pr-frente.retrato::after { content: ""; position: absolute; inset: 0; border-radius: 50%; pointer-events: none; z-index: 2;
  background: radial-gradient(circle at 50% 45%, transparent 62%, rgba(0, 0, 0, .14) 100%); }

.pr-atras { background-color: #0a2a8a; background-repeat: no-repeat; }
.pr-luna { position: absolute; border-radius: 50%; pointer-events: none; mix-blend-mode: screen;
  background: radial-gradient(circle, rgba(255, 200, 110, .9) 0%, rgba(255, 180, 80, .35) 38%, rgba(255, 170, 60, 0) 70%); }
.pr-velo { position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(to bottom, transparent 45%, rgba(0, 0, 0, .55) 100%); }
.pr-frase { position: absolute; left: 50%; top: 74%; width: 80%; margin: 0; transform: translate(-50%, -50%); text-align: center;
  color: #fff4e0; font-family: "Playfair Display", "Garamond", "Georgia", "Times New Roman", serif; line-height: 1.3;
  text-shadow: 0 0 12px rgba(255, 200, 130, .45), 0 1px 4px rgba(0, 0, 0, .6);
  opacity: 0; filter: blur(4px); transition: opacity 1.2s ease, filter 1.2s ease; pointer-events: none; }
.pr-frase span { font-style: italic; font-weight: 400; }
.pr-frase b { font-weight: 700; letter-spacing: .02em; }
.pr-frase.visible { opacity: 1; filter: blur(0); }
</style>
