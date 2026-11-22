// Archivos de audio elegidos con el selector del navegador: se reproducen en su lugar, sin
// copiarlos (útil cuando no hay servicio interno, por ejemplo al abrir la interfaz en el navegador).

export function elegirAudiosLocales() {
  return new Promise((resolver) => {
    const entrada = document.createElement("input");
    entrada.type = "file";
    entrada.accept = "audio/*";
    entrada.multiple = true;
    entrada.style.display = "none";
    entrada.addEventListener("change", () => {
      resolver([...entrada.files]);
      entrada.remove();
    }, { once: true });
    document.body.appendChild(entrada);
    entrada.click();
  });
}

// Título y artista a partir del nombre ("01 - Artista - Título.mp3"); si no trae artista,
// se usa la carpeta (Artista/Álbum/01 Canción.mp3 es lo más común).
export function datosDeNombre(nombre, carpeta = "") {
  const base = nombre.replace(/\.[^.]+$/, "").replace(/^\d{1,3}\s*[-._)]\s*/, "").trim();
  if (base.includes(" - ")) {
    const [artista, titulo] = base.split(/ - (.+)/);
    return { artista: artista.trim(), titulo: (titulo || base).trim() };
  }
  const partes = carpeta.split("/").filter(Boolean);
  return { artista: partes.length > 1 ? partes.at(-2) : partes.at(-1) || "", titulo: base || nombre };
}

// Un archivo elegido, como pista del reproductor.
export function pistaLocal(archivo) {
  return { url: URL.createObjectURL(archivo), ...datosDeNombre(archivo.name), local: true };
}
