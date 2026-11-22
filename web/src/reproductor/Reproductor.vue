<script setup>
// MigueWamp: el reproductor completo con tres skins vectoriales.
// - clásica y moderna: principal, ecualizador y lista apilados como en Winamp;
// - cabeza: una sola figura con alas y altavoces.
// La ventana del sistema mide justo esto y se agranda desde la esquina; todo es vectorial.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import Defs from "./Defs.vue";
import Principal from "./Principal.vue";
import Ecualizador from "./Ecualizador.vue";
import Lista from "./Lista.vue";
import HeadAmp from "./HeadAmp.vue";
import Compacta from "./Compacta.vue";
import MenuContexto from "./MenuContexto.vue";
import { adelantar, agregar, anterior, detener, motor, pausa, programarDormir, reemplazar, reproducir, siguiente } from "./motor.js";
import { abrirVentana, fijarForma, nativo, redimensionarVentana } from "../ventanas/nativo.js";
import { alTerminarDescarga, revisarDescargas } from "../estado.js";
import { soltarArchivos } from "./disco.js";

const SKINS = { clasica: "Clásica", moderna: "Moderna", cabeza: "Cabeza", compacta: "Compacta (vertical)" };
const ANCHO_BASE = 275, ALTO_BASE = 116;
const CABEZA = { ancho: 760, alto: 394 }; // lienzo de la skin "Cabeza"

const v = reactive({
  skin: "clasica", eq: true, pl: true, altoLista: 200, listo: false,
  anchos: { clasica: 412, moderna: 412, cabeza: 1140, compacta: 400 },
  altoCompacta: 760, baseCompacta: "clasica", // la compacta es alta y angosta, con aspecto clásico o moderno
  cabezaElegida: false, // el usuario ya eligió un tamaño para la cabeza
});
const escalaCabeza = computed(() => ancho.value / CABEZA.ancho);
const ancho = computed(() => v.anchos[v.skin]);
const u = computed(() => ancho.value / ANCHO_BASE);
const altoTotal = computed(() => {
  if (v.skin === "compacta") return Math.round(v.altoCompacta);
  if (v.skin === "cabeza") return Math.round((ancho.value * CABEZA.alto) / CABEZA.ancho);
  const separacion = v.skin === "moderna" ? 2 * u.value * ((v.eq ? 1 : 0) + (v.pl ? 1 : 0)) : 0;
  return Math.round(ALTO_BASE * u.value * (v.eq ? 2 : 1) + (v.pl ? v.altoLista * u.value : 0) + separacion);
});

const skinUrl = new URLSearchParams(location.search).get("skin");
if (skinUrl && SKINS[skinUrl]) v.skin = skinUrl;
// La compacta toma los colores de la clásica o de la moderna (las ventanas sueltas también).
const skinVisual = computed(() => (v.skin === "compacta" ? v.baseCompacta : v.skin));
watch(skinVisual, (s) => (document.documentElement.dataset.skin = s), { immediate: true });
function desdeCompacta(cual) {
  if (cual === "completo") v.skin = v.baseCompacta;
  else v.baseCompacta = cual;
}

// --- tamaño de la ventana real
let ultimo = "";
function aplicarTamano() {
  if (!v.listo) return;
  const clave = `${Math.round(ancho.value)}x${altoTotal.value}`;
  if (clave === ultimo) return;
  ultimo = clave;
  nativo()?.tamano(Math.round(ancho.value), altoTotal.value);
}
// Skins rectangulares: la ventana entera es la forma (HeadAmp manda su propia silueta).
watch(() => [v.skin, ancho.value, altoTotal.value], () => {
  if (v.skin !== "cabeza") fijarForma("skin", [0, 0, Math.round(ancho.value) + 2, altoTotal.value + 2]);
}, { immediate: true });
let guardado = 0;
watch(() => [v.skin, ancho.value, v.eq, v.pl, v.altoLista, v.altoCompacta, v.baseCompacta, motor.nivelar, motor.fundido], () => {
  aplicarTamano();
  clearTimeout(guardado);
  guardado = setTimeout(() => nativo()?.guardar_ajustes({
    reproductor: { skin: v.skin, anchos: { ...v.anchos }, eq: v.eq, pl: v.pl, altoLista: v.altoLista, cabezaElegida: v.cabezaElegida,
                   altoCompacta: v.altoCompacta, baseCompacta: v.baseCompacta, nivelar: motor.nivelar, fundido: motor.fundido },
  }), 400);
});

function agrandar(e) {
  redimensionarVentana(e, (w, h) => {
    if (v.skin === "cabeza") {
      v.anchos.cabeza = Math.min(1800, Math.max(420, w));
    } else if (v.skin === "compacta") {
      v.anchos.compacta = Math.min(760, Math.max(320, w));
      v.altoCompacta = Math.min(1600, Math.max(480, h));
    } else {
      v.anchos[v.skin] = Math.min(1600, Math.max(ANCHO_BASE, w));
      const uu = v.anchos[v.skin] / ANCHO_BASE;
      if (v.pl) v.altoLista = Math.max(58, (h - ALTO_BASE * uu * (v.eq ? 2 : 1)) / uu);
    }
    ultimo = `${Math.round(ancho.value)}x${altoTotal.value}`;
    return [ancho.value, altoTotal.value];
  });
}

// --- menú principal
const menu = ref(null);
function abrirMenu(e) {
  const x = e?.clientX ?? 20, y = e?.clientY ?? 20;
  menu.value = {
    x, y,
    items: [
      { texto: "Abrir ubicación…", atajo: "Ctrl+L", accion: () => abrirVentana("ubicacion") },
      { texto: "Biblioteca multimedia…", atajo: "Alt+L", accion: () => abrirVentana("biblioteca") },
      { texto: "Descargas…", atajo: "Alt+D", accion: () => abrirVentana("descargas") },
      { texto: "Laboratorio de mejora…", atajo: "Alt+M", accion: () => abrirVentana("laboratorio") },
      "-",
      { grupo: "Skins" },
      ...Object.entries(SKINS).map(([id, nombre]) => ({ texto: nombre, marcado: v.skin === id, accion: () => (v.skin = id) })),
      "-",
      ...(v.skin === "cabeza" ? [
        { grupo: "Tamaño" },
        ...[1, 1.25, 1.5, 1.75, 2].map((s) => ({
          texto: `${Math.round(s * 100)} %`, marcado: Math.abs(escalaCabeza.value - s) < 0.01,
          accion: () => { v.anchos.cabeza = Math.round(CABEZA.ancho * s); v.cabezaElegida = true; },
        })),
        "-",
      ] : []),
      ...(v.skin === "cabeza" ? [] : [
        { texto: "Ecualizador", atajo: "Alt+G", marcado: v.eq, accion: () => (v.eq = !v.eq) },
        { texto: "Lista de reproducción", atajo: "Alt+E", marcado: v.pl, accion: () => (v.pl = !v.pl) },
        "-",
      ]),
      { grupo: "Reproducción" },
      { texto: "Volumen nivelado", marcado: motor.nivelar, accion: () => (motor.nivelar = !motor.nivelar) },
      { texto: `Fundido entre canciones: ${motor.fundido ? motor.fundido + " s" : "no"}`, accion: () => {
        const pasos = [0, 3, 6, 10];
        motor.fundido = pasos[(pasos.indexOf(motor.fundido) + 1) % pasos.length];
      } },
      { texto: `Dormir: ${textoDormir()}`, accion: () => {
        const pasos = [0, 15, 30, 60, "cancion"];
        programarDormir(pasos[(pasos.indexOf(motor.dormir) + 1) % pasos.length]);
      } },
      "-",
      { texto: "Salir", accion: () => nativo()?.cerrar() },
    ],
  };
}
function textoDormir() {
  if (motor.dormir === "cancion") return "al terminar la canción";
  if (!motor.dormirFin) return "no";
  return `en ${Math.max(1, Math.ceil((motor.dormirFin - Date.now()) / 60000))} min`;
}
function siguienteSkin() {
  const ids = Object.keys(SKINS);
  v.skin = ids[(ids.indexOf(v.skin) + 1) % ids.length];
}

// --- órdenes de otras ventanas (biblioteca: reproducir / encolar)
let ordenes = 0;
async function revisarCola() {
  try {
    const r = await (await fetch(`/api/cola?desde=${ordenes}`)).json();
    for (const o of r.ordenes) o.accion === "reproducir" ? reemplazar(o.pistas) : agregar(o.pistas);
    ordenes = r.n;
  } catch {}
}

// --- atajos de Winamp
function teclas(e) {
  if (e.target.closest?.("input, textarea")) return;
  const k = e.key.toLowerCase();
  const acciones = {
    z: anterior, x: reproducir, c: pausa, v: detener, b: () => siguiente(),
    arrowleft: () => adelantar(-5), arrowright: () => adelantar(5),
    arrowup: () => (motor.volumen = Math.min(1, motor.volumen + 0.05)),
    arrowdown: () => (motor.volumen = Math.max(0, motor.volumen - 0.05)),
    s: () => (motor.aleatorio = !motor.aleatorio), r: () => (motor.repetir = !motor.repetir),
  };
  let accion = null;
  if (e.ctrlKey && k === "l") accion = () => abrirVentana("ubicacion");
  else if (e.altKey && k === "l") accion = () => abrirVentana("biblioteca");
  else if (e.altKey && k === "d") accion = () => abrirVentana("descargas");
  else if (e.altKey && k === "s") accion = siguienteSkin;
  else if (e.altKey && k === "m") accion = () => abrirVentana("laboratorio");
  else if (e.altKey && k === "g") accion = () => (v.eq = !v.eq);
  else if (e.altKey && k === "e") accion = () => (v.pl = !v.pl);
  else if (!e.ctrlKey && !e.altKey) accion = acciones[k];
  if (accion) {
    e.preventDefault();
    accion();
  }
}

// La cabeza original arranca al 150 % hasta que elijas otro tamaño. Se aplica después de
// leer los ajustes y de saber si está el .wal, en el orden en que terminen.
function tamanoCabeza() {
  if (!v.cabezaElegida) v.anchos.cabeza = Math.round(CABEZA.ancho * 1.5);
}

let reloj = 0;
onMounted(() => {
  window.addEventListener("keydown", teclas);
  tamanoCabeza();
  alTerminarDescarga((pistas) => agregar(pistas, motor.estado === "detenido" && motor.actual < 0));
  const iniciar = async () => {
    const r = (await nativo()?.leer_ajustes())?.reproductor || {};
    if (r.ancho && !r.anchos) r.anchos = { ...v.anchos, clasica: r.ancho, moderna: r.ancho };
    delete r.ancho;
    if (typeof r.nivelar === "boolean") motor.nivelar = r.nivelar;
    delete r.nivelar;
    if (typeof r.fundido === "number") motor.fundido = r.fundido;
    delete r.fundido;
    Object.assign(v, r, { anchos: { ...v.anchos, ...(r.anchos || {}) }, listo: true });
    if (!SKINS[v.skin]) v.skin = "clasica";
    tamanoCabeza();
    aplicarTamano();
    try { ordenes = (await (await fetch("/api/cola?desde=999999")).json()).n; } catch {}
  };
  if (nativo()) iniciar();
  else window.addEventListener("pywebviewready", iniciar, { once: true });
  setTimeout(() => !v.listo && ((v.listo = true), aplicarTamano()), 1500);
  reloj = setInterval(() => { revisarCola(); revisarDescargas(); }, 1000);
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", teclas);
  clearInterval(reloj);
});
</script>

<template>
  <div class="reproductor" :data-skin="v.skin" :style="{ '--u': u }" @dragover.prevent @drop.prevent="soltarArchivos">
    <Defs :skin="v.skin" />
    <HeadAmp v-if="v.skin === 'cabeza'" :escala="escalaCabeza" @menu="abrirMenu" />
    <template v-else-if="v.skin === 'compacta'">
      <Compacta :base="v.baseCompacta" @skin="desdeCompacta" />
      <div class="agarradera" title="Arrastra para agrandar" @pointerdown="agrandar"></div>
    </template>
    <template v-else>
      <Principal :eq="v.eq" :pl="v.pl" :skin="v.skin" @alternar-eq="v.eq = !v.eq" @alternar-pl="v.pl = !v.pl" @menu="abrirMenu" />
      <Ecualizador v-if="v.eq" :skin="v.skin" @cerrar="v.eq = false" @menu="abrirMenu" />
      <Lista v-if="v.pl" :style="{ height: v.altoLista * u + 'px' }" @cerrar="v.pl = false" @menu="abrirMenu" />
      <div class="agarradera" title="Arrastra para agrandar" @pointerdown="agrandar"></div>
    </template>
    <MenuContexto v-if="menu" v-bind="menu" @cerrar="menu = null" />
  </div>
</template>
