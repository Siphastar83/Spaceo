import os
import sys
import shutil
import tempfile
import threading
import queue
import tkinter.font as tkfont
import customtkinter as ctk
from PIL import Image, ImageDraw

# ---------- Apparence ----------
ctk.set_appearance_mode("light")

WIN_W, WIN_H = 860, 760

BG = "#F3F8FF"
CARD = "#FFFFFF"
CARD_BORDER = "#E3ECF8"
BLUE = "#2F80ED"
BLUE_DARK = "#1F66C9"
BLUE_LIGHT = "#DCEBFF"
HOVER_ROW = "#EEF5FF"
TRACK = "#EEF3FA"
TEXT = "#1F2D3D"
GREY = "#6B7A90"
WARN = "#F2994A"
DANGER = "#EB5757"
FONT = "Segoe UI"

TINTS = {BLUE: "#E3EEFF", WARN: "#FDEBD8", DANGER: "#FBE0E0"}

UNSCANNED = ("Non analysé", "#8EA3C0")   # espace utilisé que le programme ne peut pas voir
FREE = ("Libre", "#BFD9F7")

CATEGORIES = {
    "Vidéos": ({".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}, "#2F80ED"),
    "Images": ({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".raw", ".svg", ".ico", ".psd"}, "#56CCF2"),
    "Musique": ({".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"}, "#9B51E0"),
    "Documents": ({".txt", ".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".csv", ".rtf", ".md"}, "#27AE60"),
    "Archives": ({".zip", ".rar", ".7z", ".tar", ".gz", ".iso", ".bz2"}, "#F2994A"),
    "Programmes": ({".exe", ".dll", ".msi", ".sys", ".bat", ".com", ".jar"}, "#EB5757"),
    "Autres": (set(), "#F2C94C"),
}
LEGEND = [(n, c) for n, (_, c) in CATEGORIES.items()] + [UNSCANNED, FREE]
COLOR_OF = dict(LEGEND)


# ---------- Utilitaires ----------
def categorize(ext):
    for name, (exts, _) in CATEGORIES.items():
        if ext in exts:
            return name
    return "Autres"


def fmt_size(n):
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unit == "To":
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024


def list_drives():
    if os.name == "nt":
        return [f"{c}:\\" for c in "CDEFGHIJKLMNOPQRSTUVWXYZAB" if os.path.exists(f"{c}:\\")]
    return ["/"]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fade(color, amount):
    """Mélange une couleur avec du blanc (amount=0 -> inchangée, 1 -> blanc)."""
    r, g, b = hex_to_rgb(color)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def resource_path(rel):
    """Chemin d'un fichier fourni avec le programme (dans le script comme dans l'exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


LOGO_PATH = resource_path(os.path.join("assets", "img", "logo_spaceo.png"))
LOGO_FRACS = [0.52, 0.28, 0.20]


def logo_ring(size, colors=("#FFFFFF", "#BFE3FF", "#F2C94C"), thick=0.2, gap=7):
    """Petit anneau en 3 parts : c'est le logo de Spaceo."""
    k = 4
    S = size * k
    w = int(S * thick)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [0, 0, S - 1, S - 1]
    start = -90.0
    for frac, col in zip(LOGO_FRACS, colors):
        end = start + frac * 360.0
        d.arc(box, start + gap / 2, end - gap / 2, fill=col, width=w)
        start = end
    return img.resize((size, size), Image.LANCZOS)


def logo_icon(size=256):
    """Icône de l'application : carré arrondi bleu avec l'anneau au centre."""
    c1, c2 = hex_to_rgb("#56B4F5"), hex_to_rgb("#1F66C9")
    grad = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / max(size - 1, 1)
        d.line([(0, y), (size, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    k = 4
    mask = Image.new("L", (size * k, size * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size * k - 1, size * k - 1],
                                           radius=int(size * 0.22 * k), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    ring = logo_ring(int(size * 0.64))
    off = (size - ring.width) // 2
    out.alpha_composite(ring, (off, off))
    return out


def load_logo(size):
    """Charge assets/img/logo_spaceo.png (si absent, redessine le logo à la place)."""
    try:
        img = Image.open(LOGO_PATH).convert("RGBA")
    except Exception:
        img = logo_icon(256)
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path):
    load_logo(256).save(path, format="ICO",
                        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def make_banner(width, height, radius=30, logo_x=None, logo_size=58):
    """Bandeau dégradé bleu avec coins du bas arrondis (et le logo à gauche du titre)."""
    c1, c2 = hex_to_rgb("#1F66C9"), hex_to_rgb("#56B4F5")
    grad = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(grad)
    for x in range(width):
        t = x / max(width - 1, 1)
        d.line([(x, 0), (x, height)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    if logo_x is not None:
        logo = load_logo(logo_size)
        grad.paste(logo, (int(logo_x), (height - logo_size) // 2), logo)
    mask = Image.new("L", (width * 3, height * 3), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, -radius * 3, width * 3, height * 3 - 1], radius=radius * 3, fill=255)
    mask = mask.resize((width, height), Image.LANCZOS)
    out = Image.new("RGB", (width, height), hex_to_rgb(BG))
    out.paste(grad, (0, 0), mask)
    return ctk.CTkImage(light_image=out, size=(width, height))


def render_donut(fractions, colors, size=320, thick=36, gap=2.0):
    """Dessine l'anneau en haute résolution puis le réduit (bords lisses)."""
    k = 3
    S = size * k
    w = thick * k
    box = [0, 0, S - 1, S - 1]
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.arc(box, 0, 360, fill=TRACK, width=w)          # piste claire en fond
    start = -90.0
    for frac, col in zip(fractions, colors):
        if frac <= 0:
            continue
        end = start + frac * 360.0
        a, b = start + gap / 2, end - gap / 2
        if b - a > 0.3:
            d.arc(box, a, b, fill=col, width=w)
        start = end
    img = img.resize((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, size=(size, size))


# ---------- Application ----------
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.title("Spaceo")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)

        self.q = queue.Queue()
        self.stop_flag = threading.Event()
        self.scanning = False
        self.sizes = {}
        self.total = self.used = self.free = 0
        self.values = {}
        self.denom = 1
        self.cur = [0.0] * len(LEGEND)
        self.target = [0.0] * len(LEGEND)
        self.hover = None
        self.state_color = BLUE
        self.anim_job = None
        self.legend_rows = {}

        # --- Bandeau ---
        try:
            text_w = tkfont.Font(family=FONT, size=-32, weight="bold").measure("Spaceo")
        except Exception:
            text_w = 140
        logo_size, gap = 58, 14
        logo_x = WIN_W / 2 - text_w / 2 - gap - logo_size
        banner = ctk.CTkLabel(self, text="Spaceo", image=make_banner(WIN_W, 92, logo_x=logo_x, logo_size=logo_size),
                              compound="center", font=(FONT, 32, "bold"), text_color="white",
                              fg_color="transparent")
        banner.pack()
        ctk.CTkLabel(self, text="Découvre ce qui remplit ton ordinateur en un clic",
                     font=(FONT, 14), text_color=GREY).pack(pady=(10, 10))

        # --- Carte principale ---
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=22,
                            border_width=1, border_color=CARD_BORDER)
        card.pack(fill="both", expand=True, padx=28)

        line = ctk.CTkFrame(card, fg_color="transparent")
        line.pack(fill="x", padx=26, pady=(16, 0))
        ctk.CTkLabel(line, text="Disque à analyser", font=(FONT, 14),
                     text_color=GREY).pack(side="left")
        self.drive = ctk.CTkOptionMenu(
            line, values=list_drives(), width=96, height=34, corner_radius=17,
            command=lambda v: self.on_drive_change(),
            fg_color=BLUE_LIGHT, button_color=BLUE, button_hover_color=BLUE_DARK,
            text_color=BLUE_DARK, dropdown_fg_color=CARD, dropdown_text_color=TEXT,
            dropdown_hover_color=BLUE_LIGHT, font=(FONT, 14, "bold"))
        self.drive.pack(side="left", padx=12)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=26, pady=(4, 0))

        # Roue + texte au centre
        wheel = ctk.CTkFrame(body, fg_color="transparent", width=320, height=320)
        wheel.pack(side="left", padx=(0, 30))
        wheel.pack_propagate(False)
        self.wheel_label = ctk.CTkLabel(wheel, text="", fg_color="transparent")
        self.wheel_label.place(relx=0.5, rely=0.5, anchor="center")

        center = ctk.CTkFrame(wheel, fg_color=CARD, corner_radius=0, width=190, height=130)
        center.place(relx=0.5, rely=0.5, anchor="center")
        self.c_top = ctk.CTkLabel(center, text="Espace total", font=(FONT, 13), text_color=GREY)
        self.c_top.place(relx=0.5, rely=0.2, anchor="center")
        self.c_main = ctk.CTkLabel(center, text="–", font=(FONT, 32, "bold"), text_color=TEXT)
        self.c_main.place(relx=0.5, rely=0.5, anchor="center")
        self.c_sub = ctk.CTkLabel(center, text="", font=(FONT, 14, "bold"), text_color=BLUE)
        self.c_sub.place(relx=0.5, rely=0.8, anchor="center")

        # Légende (survol = mise en avant de la part)
        self.legend = ctk.CTkFrame(body, fg_color="transparent")
        self.legend.pack(side="left", fill="both", expand=True, pady=4)
        self.legend.bind("<Leave>", lambda e: self.set_hover(None))
        for name, color in LEGEND:
            row = ctk.CTkFrame(self.legend, fg_color="transparent", corner_radius=10, height=34)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            dot = ctk.CTkFrame(row, width=14, height=14, corner_radius=7, fg_color=color)
            dot.pack(side="left", padx=(10, 10))
            nm = ctk.CTkLabel(row, text=name, font=(FONT, 15, "bold"), text_color=TEXT)
            nm.pack(side="left")
            pct = ctk.CTkLabel(row, text="–", font=(FONT, 15, "bold"), text_color=TEXT, width=70, anchor="e")
            pct.pack(side="right", padx=(0, 8))
            size = ctk.CTkLabel(row, text="", font=(FONT, 13), text_color=GREY, width=80, anchor="e")
            size.pack(side="right")
            for w_ in (row, dot, nm, pct, size):
                w_.bind("<Enter>", lambda e, n=name: self.set_hover(n), add="+")
            self.legend_rows[name] = (row, size, pct)

        self.alert_label = ctk.CTkLabel(card, text="", font=(FONT, 14, "bold"),
                                        corner_radius=16, height=34)
        self.alert_label.pack(pady=(6, 18), ipadx=14)

        # --- Bouton + état ---
        self.btn = ctk.CTkButton(
            self, text="Analyser mon disque", height=56, corner_radius=28,
            font=(FONT, 18, "bold"), fg_color=BLUE, hover_color=BLUE_DARK,
            text_color="white", command=self.toggle)
        self.btn.pack(fill="x", padx=150, pady=(16, 8))

        self.scan_bar = ctk.CTkProgressBar(self, height=6, fg_color=BLUE_LIGHT,
                                           progress_color=BLUE, mode="indeterminate")
        self.status = ctk.CTkLabel(self, text="Clique sur le bouton bleu pour commencer.",
                                   font=(FONT, 13), text_color=GREY)
        self.status.pack(pady=(0, 14))

        self.on_drive_change()
        self.after(150, self.poll)
        self.after(300, self.set_icon)   # après customtkinter, qui pose sa propre icône

    def set_icon(self):
        try:
            path = os.path.join(tempfile.gettempdir(), "spaceo_icon.ico")
            if not os.path.exists(path):
                save_ico(path)
            self.iconbitmap(path)
        except Exception:
            try:
                from PIL import ImageTk
                self._icon = ImageTk.PhotoImage(load_logo(64))
                self.iconphoto(True, self._icon)
            except Exception:
                pass

    # ---------- Disque ----------
    def on_drive_change(self):
        self.sizes = {}
        try:
            self.total, self.used, self.free = shutil.disk_usage(self.drive.get())
        except OSError:
            self.total = self.used = self.free = 0
        ratio = self.used / self.total if self.total else 0
        if ratio > 0.92:
            self.state_color, msg = DANGER, "Disque presque plein : il faut faire de la place !"
        elif ratio > 0.80:
            self.state_color, msg = WARN, "Attention, le disque se remplit."
        else:
            self.state_color, msg = BLUE, "Tout va bien, il reste de la place."
        self.alert_label.configure(text=f"   {msg}   ", text_color=self.state_color,
                                   fg_color=TINTS[self.state_color])
        self.refresh_values()

    def refresh_values(self):
        values = {n: self.sizes.get(n, 0) for n in CATEGORIES}
        scanned = sum(values.values())
        values[UNSCANNED[0]] = max(self.used - scanned, 0)
        values[FREE[0]] = self.free
        self.values = values
        self.denom = sum(values.values()) or 1
        self.target = [values[n] / self.denom for n, _ in LEGEND]

        for n, _ in LEGEND:
            _, size_l, pct_l = self.legend_rows[n]
            size_l.configure(text=fmt_size(values[n]))
            pct_l.configure(text=f"{values[n] / self.denom * 100:.1f} %")
        self.update_center()
        self.animate()

    # ---------- Centre de la roue ----------
    def update_center(self):
        if self.hover is None:
            self.c_top.configure(text="Espace total", text_color=GREY)
            self.c_main.configure(text=fmt_size(self.total) if self.total else "?",
                                  font=(FONT, 32, "bold"), text_color=TEXT)
            self.c_sub.configure(text=f"{fmt_size(self.free)} libres", text_color=self.state_color)
        else:
            n = self.hover
            col = COLOR_OF[n]
            self.c_top.configure(text=n, text_color=col, font=(FONT, 15, "bold"))
            self.c_main.configure(text=fmt_size(self.values.get(n, 0)),
                                  font=(FONT, 28, "bold"), text_color=TEXT)
            self.c_sub.configure(text=f"{self.values.get(n, 0) / self.denom * 100:.1f} % du disque",
                                 text_color=GREY)

    def set_hover(self, name):
        if name == self.hover:
            return
        self.hover = name
        for n, (row, _, _) in self.legend_rows.items():
            row.configure(fg_color=HOVER_ROW if n == name else "transparent")
        if name is None:
            self.c_top.configure(font=(FONT, 13))
        self.update_center()
        self.draw()

    # ---------- Dessin / animation ----------
    def draw(self):
        colors = []
        for n, c in LEGEND:
            colors.append(fade(c, 0.7) if (self.hover and n != self.hover) else c)
        img = render_donut(self.cur, colors)
        self.wheel_label.configure(image=img)
        self.wheel_label.image = img

    def animate(self):
        if self.anim_job is None:
            self.step()

    def step(self):
        self.anim_job = None
        done = True
        for i, t in enumerate(self.target):
            d = t - self.cur[i]
            if abs(d) > 0.002:
                self.cur[i] += d * 0.28
                done = False
            else:
                self.cur[i] = t
        self.draw()
        if not done:
            self.anim_job = self.after(30, self.step)

    # ---------- Scan ----------
    def toggle(self):
        if self.scanning:
            self.stop_flag.set()
            return
        self.stop_flag.clear()
        self.scanning = True
        self.sizes = {}
        self.btn.configure(text="Arrêter", fg_color=DANGER, hover_color="#C94545")
        self.scan_bar.pack(fill="x", padx=150, pady=(0, 6), before=self.status)
        self.scan_bar.start()
        threading.Thread(target=self.scan, args=(self.drive.get(),), daemon=True).start()

    def scan(self, root):
        sizes, count, stack = {}, 0, [root]
        while stack and not self.stop_flag.is_set():
            path = stack.pop()
            try:
                with os.scandir(path) as it:
                    for e in it:
                        try:
                            if e.is_symlink():
                                continue
                            if e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                            elif e.is_file(follow_symlinks=False):
                                cat = categorize(os.path.splitext(e.name)[1].lower())
                                sizes[cat] = sizes.get(cat, 0) + e.stat(follow_symlinks=False).st_size
                                count += 1
                                if count % 3000 == 0:
                                    self.q.put(("progress", count, dict(sizes)))
                        except OSError:
                            pass
            except OSError:
                pass
        self.q.put(("done", count, sizes))

    def poll(self):
        last = None
        try:
            while True:
                last = self.q.get_nowait()
                if last[0] == "done":
                    break
        except queue.Empty:
            pass
        if last:
            kind, count, sizes = last
            self.sizes = sizes
            self.refresh_values()
            n = f"{count:,}".replace(",", " ")
            if kind == "progress":
                self.status.configure(text=f"Analyse en cours…  {n} fichiers vus")
            else:
                self.scanning = False
                self.scan_bar.stop()
                self.scan_bar.pack_forget()
                self.btn.configure(text="Analyser mon disque", fg_color=BLUE, hover_color=BLUE_DARK)
                self.status.configure(text=f"Terminé !  {n} fichiers analysés.")
        self.after(200, self.poll)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--make-icon":
        save_ico(sys.argv[2])          # utilisé par GitHub pour fabriquer l'icône de l'exe
    else:
        App().mainloop()