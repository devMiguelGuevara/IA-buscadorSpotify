"""Lector rápido: muestra un PDF o TXT palabra por palabra.

Atajos: Espacio = play/pausa · ←/→ = retroceder/avanzar una línea ·
↑/↓ = más/menos velocidad · Ctrl+O = abrir archivo · Inicio = volver al principio
"""

import re
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pypdf import PdfReader

PALABRAS_POR_LINEA = 10
PPM_INICIAL = 250          # palabras por minuto
PPM_MIN, PPM_MAX, PPM_PASO = 60, 1000, 25
PAUSA_PUNTUACION = {".": 2.2, "!": 2.2, "?": 2.2, ":": 1.6, ";": 1.6, ",": 1.4}

TECNICAS = {
    "normal": "Normal",
    "punto_focal": "Punto focal",
    "negrita_inicio": "Negrita inicio",
    "negrita_final": "Negrita final",
}

COLOR_FONDO = "#fafafa"
COLOR_CONTEXTO = "#9a9a9a"
COLOR_FOCO = "#d62828"


def cargar_texto(ruta: Path) -> str:
    if ruta.suffix.lower() == ".pdf":
        lector = PdfReader(ruta)
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    for codificacion in ("utf-8", "cp1252", "latin-1"):
        try:
            return ruta.read_text(encoding=codificacion)
        except UnicodeDecodeError:
            continue
    return ""


def limpiar_texto(texto: str) -> str:
    # Une tildes "sueltas" que algunos PDF extraen como caracteres combinados (a + ´ -> á).
    texto = unicodedata.normalize("NFC", texto)
    # Une palabras cortadas con guion al final de línea: "pala-\nbra" -> "palabra".
    texto = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", texto)
    # Quita espacios antes de signos de cierre: "hola ," -> "hola,".
    texto = re.sub(r"\s+([,.;:!?)\]}»”])", r"\1", texto)
    # Quita espacios después de signos de apertura: "¿ qué" -> "¿qué".
    texto = re.sub(r"([¿¡(\[{«“])\s+", r"\1", texto)
    return texto


def punto_focal(palabra: str) -> int:
    """Letra donde el ojo reconoce mejor la palabra (un poco antes del centro)."""
    n = len(palabra)
    if n <= 1:
        return 0
    if n <= 5:
        return 1
    if n <= 9:
        return 2
    if n <= 13:
        return 3
    return 4


class LectorRapido:
    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.palabras: list[str] = []
        self.indice = 0
        self.leyendo = False
        self._tarea = None  # id de root.after, para no lanzar dos bucles a la vez

        self.ppm = tk.IntVar(value=PPM_INICIAL)
        self.tecnica = tk.StringVar(value="punto_focal")
        self.pausa_en_puntuacion = tk.BooleanVar(value=True)

        raiz.title("Lectura Rápida")
        raiz.geometry("900x520")
        raiz.minsize(640, 400)
        raiz.configure(bg=COLOR_FONDO)
        self._construir_interfaz()
        self._atajos()
        self._mostrar()

    # ---------------------------------------------------------------- interfaz
    def _construir_interfaz(self) -> None:
        marco = tk.Frame(self.raiz, bg=COLOR_FONDO)
        marco.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)
        marco.columnconfigure(0, weight=1)

        self.lbl_archivo = tk.Label(marco, text="Abre un PDF o TXT para empezar (Ctrl+O)",
                                    bg=COLOR_FONDO, fg="#555", anchor="w")
        self.lbl_archivo.grid(row=0, column=0, sticky="ew")

        self.lbl_anterior = tk.Label(marco, bg=COLOR_FONDO, fg=COLOR_CONTEXTO, anchor="e")
        self.lbl_anterior.grid(row=1, column=0, sticky="ew", pady=(24, 4))

        # Text (y no Label) porque permite resaltar parte de la palabra con etiquetas.
        self.txt_actual = tk.Text(marco, height=1, bd=0, bg="white", fg="black", cursor="arrow",
                                  highlightthickness=1, highlightbackground="#ddd", wrap="none",
                                  takefocus=0, state="disabled")
        self.txt_actual.grid(row=2, column=0, sticky="ew", ipady=12)
        self.txt_actual.tag_configure("centro", justify="center")
        self.txt_actual.tag_configure("foco", foreground=COLOR_FOCO)

        self.lbl_siguiente = tk.Label(marco, bg=COLOR_FONDO, fg=COLOR_CONTEXTO, anchor="w")
        self.lbl_siguiente.grid(row=3, column=0, sticky="ew", pady=(4, 16))

        self.progreso = ttk.Progressbar(marco, mode="determinate")
        self.progreso.grid(row=4, column=0, sticky="ew")
        self.lbl_progreso = tk.Label(marco, bg=COLOR_FONDO, fg="#555")
        self.lbl_progreso.grid(row=5, column=0, sticky="ew", pady=(2, 12))

        # takefocus=False: si un botón tuviera el foco, Espacio lo pulsaría Y dispararía el atajo.
        controles = tk.Frame(marco, bg=COLOR_FONDO)
        controles.grid(row=6, column=0)
        for texto, accion in [
            ("Abrir…", self.abrir),
            ("⏮ Inicio", self.reiniciar),
            ("⏪ Línea", lambda: self.saltar(-PALABRAS_POR_LINEA)),
            ("▶ Leer", self.play_pausa),
            ("Línea ⏩", lambda: self.saltar(PALABRAS_POR_LINEA)),
        ]:
            boton = ttk.Button(controles, text=texto, command=accion, takefocus=False)
            boton.pack(side=tk.LEFT, padx=3)
            if accion == self.play_pausa:
                self.btn_play = boton
                boton.config(width=10)

        ajustes = tk.Frame(marco, bg=COLOR_FONDO)
        ajustes.grid(row=7, column=0, pady=(12, 0))
        tk.Label(ajustes, text="Palabras por minuto:", bg=COLOR_FONDO).pack(side=tk.LEFT)
        ttk.Spinbox(ajustes, from_=PPM_MIN, to=PPM_MAX, increment=PPM_PASO, width=6,
                    textvariable=self.ppm).pack(side=tk.LEFT, padx=(4, 16))
        tk.Label(ajustes, text="Técnica:", bg=COLOR_FONDO).pack(side=tk.LEFT)
        combo = ttk.Combobox(ajustes, state="readonly", width=15, values=list(TECNICAS.values()))
        combo.set(TECNICAS[self.tecnica.get()])
        combo.bind("<<ComboboxSelected>>", lambda e: self._cambiar_tecnica(combo.get()))
        combo.pack(side=tk.LEFT, padx=(4, 16))
        ttk.Checkbutton(ajustes, text="Pausa en puntuación", variable=self.pausa_en_puntuacion,
                        takefocus=False).pack(side=tk.LEFT)

        self.raiz.bind("<Configure>", self._ajustar_fuentes)

    def _atajos(self) -> None:
        def atajo(accion):
            # Si el foco está en un campo editable, la tecla es para el campo, no un atajo.
            return lambda e: None if isinstance(e.widget, (ttk.Spinbox, ttk.Combobox)) else accion()

        self.raiz.bind("<space>", atajo(self.play_pausa))
        self.raiz.bind("<Left>", atajo(lambda: self.saltar(-PALABRAS_POR_LINEA)))
        self.raiz.bind("<Right>", atajo(lambda: self.saltar(PALABRAS_POR_LINEA)))
        self.raiz.bind("<Up>", atajo(lambda: self._cambiar_velocidad(PPM_PASO)))
        self.raiz.bind("<Down>", atajo(lambda: self._cambiar_velocidad(-PPM_PASO)))
        self.raiz.bind("<Home>", atajo(self.reiniciar))
        self.raiz.bind("<Control-o>", lambda e: self.abrir())

    def _ajustar_fuentes(self, evento=None) -> None:
        if evento is not None and evento.widget is not self.raiz:
            return  # <Configure> también se dispara por cada widget hijo
        base = max(10, self.raiz.winfo_width() // 60)
        self.lbl_anterior.config(font=("Helvetica", base), wraplength=self.raiz.winfo_width() - 60)
        self.lbl_siguiente.config(font=("Helvetica", base), wraplength=self.raiz.winfo_width() - 60)
        self.txt_actual.config(font=("Helvetica", base * 3))
        self.txt_actual.tag_configure("negrita", font=("Helvetica", base * 3, "bold"))

    # ------------------------------------------------------------------ acciones
    def abrir(self) -> None:
        ruta = filedialog.askopenfilename(filetypes=[("PDF o texto", "*.pdf *.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            texto = cargar_texto(Path(ruta))
        except Exception as e:
            messagebox.showerror("No se pudo abrir", str(e))
            return
        palabras = limpiar_texto(texto).split()
        if not palabras:
            messagebox.showwarning("Sin texto", "No se encontró texto (¿es un PDF escaneado?).")
            return
        self.pausar()
        self.palabras, self.indice = palabras, 0
        self.lbl_archivo.config(text=f"{Path(ruta).name} — {len(palabras):,} palabras")
        self._mostrar()

    def play_pausa(self) -> None:
        if self.leyendo:
            self.pausar()
        elif self.palabras:
            if self.indice >= len(self.palabras):
                self.indice = 0
            self.leyendo = True
            self.btn_play.config(text="⏸ Pausa")
            self._siguiente_palabra()

    def pausar(self) -> None:
        self.leyendo = False
        self.btn_play.config(text="▶ Leer")
        if self._tarea:
            self.raiz.after_cancel(self._tarea)
            self._tarea = None

    def reiniciar(self) -> None:
        self.pausar()
        self.indice = 0
        self._mostrar()

    def saltar(self, cantidad: int) -> None:
        if self.palabras:
            self.indice = min(max(0, self.indice + cantidad), len(self.palabras) - 1)
            self._mostrar()

    def _cambiar_velocidad(self, delta: int) -> None:
        self.ppm.set(min(PPM_MAX, max(PPM_MIN, self._ppm() + delta)))
        self._mostrar()

    def _cambiar_tecnica(self, nombre: str) -> None:
        self.tecnica.set(next(k for k, v in TECNICAS.items() if v == nombre))
        self._mostrar()

    def _ppm(self) -> int:
        try:
            return min(PPM_MAX, max(PPM_MIN, int(self.ppm.get())))
        except (tk.TclError, ValueError):
            return PPM_INICIAL

    # ------------------------------------------------------------------- lectura
    def _siguiente_palabra(self) -> None:
        if not self.leyendo:
            return
        if self.indice >= len(self.palabras):
            self.pausar()
            return
        self._mostrar()
        palabra = self.palabras[self.indice]
        self.indice += 1

        # La velocidad se lee en cada palabra, así cambiarla no reinicia la lectura.
        espera = 60_000 / self._ppm()
        if self.pausa_en_puntuacion.get() and palabra[-1] in PAUSA_PUNTUACION:
            espera *= PAUSA_PUNTUACION[palabra[-1]]
        elif len(palabra) > 10:
            espera *= 1.3
        self._tarea = self.raiz.after(int(espera), self._siguiente_palabra)

    def _mostrar(self) -> None:
        i = min(self.indice, len(self.palabras) - 1) if self.palabras else 0
        anterior = self.palabras[max(0, i - PALABRAS_POR_LINEA):i]
        siguiente = self.palabras[i + 1:i + 1 + PALABRAS_POR_LINEA]
        self.lbl_anterior.config(text=" ".join(anterior))
        self.lbl_siguiente.config(text=" ".join(siguiente))
        self._pintar_palabra(self.palabras[i] if self.palabras else "")

        total = len(self.palabras)
        self.progreso.config(maximum=max(total, 1), value=i + 1 if total else 0)
        restantes = max(total - i - 1, 0)
        minutos = restantes / self._ppm()
        self.lbl_progreso.config(
            text=f"Palabra {i + 1 if total else 0:,} de {total:,} · {self._ppm()} ppm · "
                 f"quedan ~{int(minutos)} min {int(minutos % 1 * 60)} s"
        )

    def _pintar_palabra(self, palabra: str) -> None:
        t = self.txt_actual
        t.config(state="normal")
        t.delete("1.0", tk.END)
        tecnica = self.tecnica.get()
        mitad = (len(palabra) + 1) // 2

        if tecnica == "punto_focal" and palabra:
            p = punto_focal(palabra)
            t.insert(tk.END, palabra[:p])
            t.insert(tk.END, palabra[p], "foco")
            t.insert(tk.END, palabra[p + 1:])
        elif tecnica == "negrita_inicio":
            t.insert(tk.END, palabra[:mitad], "negrita")
            t.insert(tk.END, palabra[mitad:])
        elif tecnica == "negrita_final":
            t.insert(tk.END, palabra[:mitad])
            t.insert(tk.END, palabra[mitad:], "negrita")
        else:
            t.insert(tk.END, palabra)
        t.tag_add("centro", "1.0", tk.END)
        t.config(state="disabled")


if __name__ == "__main__":
    raiz = tk.Tk()
    LectorRapido(raiz)
    raiz.mainloop()
