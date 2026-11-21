// Datos del visualizador: barras de espectro en escala logarítmica con picos que caen,
// u osciloscopio. Lo usan la skin clásica, la moderna y la cabeza.
import { analizadorActual, motor } from "./motor.js";

export function crearVisualizador(nBarras) {
  let alturas = new Array(nBarras).fill(0), cimas = new Array(nBarras).fill(0), datos = null;
  return {
    // Devuelve { barras: [0..1], cimas: [0..1], onda: [0..1] | null }
    leer(dt, osciloscopio = false) {
      const a = analizadorActual();
      const sonando = a && motor.estado === "sonando";
      if (osciloscopio && sonando) {
        datos = datos?.length === a.fftSize ? datos : new Uint8Array(a.fftSize);
        a.getByteTimeDomainData(datos);
        return { barras: [], cimas: [], onda: Array.from({ length: 76 }, (_, i) => datos[Math.floor((i / 76) * datos.length)] / 255) };
      }
      if (sonando) {
        datos = datos?.length === a.frequencyBinCount ? datos : new Uint8Array(a.frequencyBinCount);
        a.getByteFrequencyData(datos);
        const nyquist = a.context.sampleRate / 2;
        for (let i = 0; i < nBarras; i++) {
          const f0 = 40 * Math.pow(400, i / nBarras), f1 = 40 * Math.pow(400, (i + 1) / nBarras);
          const b0 = Math.floor((f0 / nyquist) * datos.length);
          const b1 = Math.max(b0 + 1, Math.ceil((f1 / nyquist) * datos.length));
          let m = 0;
          for (let b = b0; b < b1; b++) m = Math.max(m, datos[b] || 0);
          const h = m / 255;
          alturas[i] = h > alturas[i] ? h : Math.max(h, alturas[i] - dt * 2.5);
          cimas[i] = alturas[i] > cimas[i] ? alturas[i] : Math.max(0, cimas[i] - dt * 0.6);
        }
      } else {
        alturas = alturas.map((h) => Math.max(0, h - dt * 2.5));
        cimas = cimas.map((h) => Math.max(0, h - dt * 0.6));
      }
      return { barras: alturas, cimas, onda: null };
    },
  };
}
