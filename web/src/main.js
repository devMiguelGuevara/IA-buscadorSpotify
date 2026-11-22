// Punto de entrada de la interfaz. Cada ventana del escritorio carga esta misma página:
// sin nada, el reproductor; con #ventana=<nombre>, una ventana suelta.
import { createApp, h } from "vue";
import "./estilos.css";
import Reproductor from "./reproductor/Reproductor.vue";
import VentanaSuelta from "./ventanas/VentanaSuelta.vue";

import Compacta from "./reproductor/Compacta.vue";
import { vistaCompacta } from "./plataforma.js";

const parametros = new URLSearchParams(location.search + "&" + location.hash.slice(1));
const ventana = parametros.get("ventana");
// La vista compacta va sola en pantallas táctiles angostas (o pidiéndola con ?vista=compacta).
const tactilAngosta = matchMedia("(pointer: coarse)").matches && Math.min(screen.width, innerWidth) < 700;
const compacta = !ventana && (vistaCompacta || parametros.get("vista") === "compacta" || tactilAngosta);
document.documentElement.dataset.vista = ventana ? "ventana" : compacta ? "compacta" : "reproductor";

const raiz = ventana ? { render: () => h(VentanaSuelta, { nombre: ventana }) }
  : compacta ? { render: () => h(Compacta, { sola: true, base: parametros.get("skin") === "moderna" ? "moderna" : "clasica" }) }
  : Reproductor;
createApp(raiz).mount("#app");
