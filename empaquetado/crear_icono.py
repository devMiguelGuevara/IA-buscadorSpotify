"""Dibuja el icono de MigueWamp (rayo dorado sobre fondo gris carbón) en varios tamaños."""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).with_name("MigueWamp.ico")


def dibujar(tam: int) -> Image.Image:
    escala = 4  # se dibuja grande y se reduce, para bordes suaves
    t = tam * escala
    img = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([t * .04, t * .04, t * .96, t * .96], radius=t * .2, fill=(40, 40, 52), outline=(112, 112, 126), width=max(1, t // 40))
    rayo = [(.60, .10), (.26, .56), (.48, .56), (.36, .92), (.76, .40), (.53, .40), (.68, .10)]
    d.polygon([(x * t, y * t) for x, y in rayo], fill=(240, 190, 16), outline=(90, 70, 0), width=max(1, t // 64))
    return img.resize((tam, tam), Image.LANCZOS)


if __name__ == "__main__":
    tamanos = [16, 24, 32, 48, 64, 128, 256]
    dibujar(256).save(DESTINO, sizes=[(s, s) for s in tamanos])
    print(f"Icono creado: {DESTINO}")
