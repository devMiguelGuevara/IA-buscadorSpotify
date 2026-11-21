// Punto de entrada de la interfaz. Cada ventana del escritorio carga esta misma página:
// sin nada, el reproductor; con #ventana=<nombre>, una ventana suelta.
import { createApp, h } from "vue";
import "./estilos.css";
import Reproductor from "./reproductor/Reproductor.vue";
import VentanaSuelta from "./ventanas/VentanaSuelta.vue";

const ventana = new URLSearchParams(location.hash.slice(1)).get("ventana");
document.documentElement.dataset.vista = ventana ? "ventana" : "reproductor";

createApp(ventana ? { render: () => h(VentanaSuelta, { nombre: ventana }) } : Reproductor).mount("#app");
