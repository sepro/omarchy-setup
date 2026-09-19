"""Build a one page A4 landscape cheat sheet for Omarchy and Herdr."""
from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Sans", FONT_DIR + "DejaVuSansCondensed.ttf"))
pdfmetrics.registerFont(TTFont("SansBold", FONT_DIR + "DejaVuSansCondensed-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Mono", FONT_DIR + "DejaVuSansMono.ttf"))

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
MARGIN = 22
HEADER_HEIGHT = 180
COLUMN_GAP = 16

# Colors sampled from the koi image so the page feels like one piece
TEAL = HexColor("#1f5c66")
DEEP_TEAL = HexColor("#153f47")
PEACH = HexColor("#f2b48a")
PEACH_LIGHT = HexColor("#fdf0e6")
KEYCAP_FILL = HexColor("#eef4f4")
KEYCAP_BORDER = HexColor("#b9cfd1")
TEXT = HexColor("#2b2f33")
MUTED = HexColor("#6b7a7d")

ROW_HEIGHT = 12.1
SECTION_TITLE_HEIGHT = 17
SECTION_SPACING = 9


# ---------- content ----------
# Each section: (title, [(keys, description), ...]).
# Keys use " + " between modifiers so we can draw each part as its own keycap.

CUSTOM_SHORTCUTS = [
    ("Super + M", "Recent media panel"),
    ("Super + D", "Downloads panel"),
]

OMARCHY_COLUMN_1 = [
    ("Essentials", [
        ("Super + Space", "Omarchy menu"),
        ("Super + Alt + Space", "Apps menu"),
        ("Super + Esc", "System menu (suspend, restart)"),
        ("Super + K", "Show all hotkeys"),
        ("Super + Ctrl + L", "Lock computer"),
        ("Super + W", "Close window"),
    ]),
    ("Windows", [
        ("Super + Arrow", "Focus window in direction"),
        ("Super + Shift + Arrow", "Swap window in direction"),
        ("Super + T", "Toggle tiling / floating"),
        ("Super + F", "Full screen"),
        ("Super + Alt + F", "Full width"),
        ("Super + J", "Toggle split direction"),
        ("Super + L", "Dwindle / scrolling layout"),
        ("Super + - / =", "Resize window"),
        ("Super + G", "Toggle window grouping"),
    ]),
    ("Workspaces", [
        ("Super + 1-4", "Jump to workspace"),
        ("Super + Shift + 1-4", "Move window to workspace"),
        ("Super + Tab", "Next workspace"),
        ("Super + S", "Toggle scratchpad"),
    ]),
]

OMARCHY_COLUMN_2 = [
    ("Launch apps", [
        ("Super + Return", "Terminal"),
        ("Super + Ctrl + Return", "Herdr (agent manager)"),
        ("Super + Shift + Return", "Browser"),
        ("Super + Shift + F", "File manager"),
        ("Super + Shift + N", "Neovim"),
        ("Super + Shift + /", "Password manager"),
    ]),
    ("Clipboard", [
        ("Super + C / X / V", "Copy / cut / paste, everywhere"),
        ("Super + Ctrl + V", "Clipboard history"),
    ]),
    ("Capture", [
        ("Print", "Screenshot"),
        ("Alt + Print", "Screen recording (again to stop)"),
        ("Super + Print", "Color picker"),
        ("Super + Ctrl + Print", "Extract text to clipboard"),
    ]),
    ("System panels", [
        ("Super + Ctrl + A", "Audio"),
        ("Super + Ctrl + W", "Wifi / network"),
        ("Super + Ctrl + B", "Bluetooth"),
        ("Super + Ctrl + T", "Activity (btop)"),
        ("Super + Ctrl + E", "Emoji picker"),
    ]),
    ("Notifications & style", [
        ("Super + ,", "Dismiss notification"),
        ("Super + Shift + ,", "Dismiss all"),
        ("Super + Ctrl + N", "Toggle nightlight"),
        ("Super + Ctrl + Shift + Space", "Pick a theme"),
    ]),
]

HERDR_COLUMN = [
    ("Start here", [
        ("Prefix + c", "New tab"),
        ("Prefix + v / -", "Split right / down"),
        ("Prefix + h j k l", "Move between panes"),
        ("Prefix + w", "Workspace navigation"),
        ("Prefix + q", "Detach (keeps running)"),
        ("Prefix + ?", "Show all bindings"),
    ]),
    ("Panes", [
        ("Prefix + z", "Zoom pane"),
        ("Prefix + x", "Close pane"),
        ("Prefix + Shift + hjkl", "Swap panes"),
        ("Prefix + r", "Resize mode"),
    ]),
    ("Tabs", [
        ("Prefix + n / p", "Next / previous tab"),
        ("Prefix + 1-9", "Jump to tab"),
        ("Prefix + Shift + t", "Rename tab"),
        ("Prefix + Shift + x", "Close tab"),
    ]),
    ("Workspaces", [
        ("Prefix + Shift + n", "New workspace"),
        ("Prefix + Shift + w", "Rename workspace"),
        ("Prefix + Shift + d", "Close workspace"),
        ("Prefix + g", "Goto picker"),
        ("Prefix + b", "Toggle sidebar"),
    ]),
    ("Copy mode (Prefix + [)", [
        ("v", "Start selection"),
        ("y", "Copy selection"),
        ("/", "Search"),
        ("q", "Leave copy mode"),
    ]),
]


# ---------- header ----------

def build_faded_header_image(source_path, output_path, width_pt, height_pt):
    """Crop the artwork to the header shape and fade it to white.

    Fading to white (instead of real transparency) keeps the PDF simple
    and looks identical on paper, since the page itself is white.
    """
    image = Image.open(source_path).convert("RGB")
    target_ratio = width_pt / height_pt
    source_width, source_height = image.size
    crop_height = int(source_width / target_ratio)
    # Keep the two koi in frame: they sit around the vertical middle
    crop_top = (source_height - crop_height) // 2
    image = image.crop((0, crop_top, source_width, crop_top + crop_height))

    fade_mask = Image.new("L", (1, image.height))
    for y in range(image.height):
        progress = y / (image.height - 1)
        # Ease-in curve so the top stays rich and only the lower part melts away
        opacity = 1 - progress ** 1.8
        fade_mask.putpixel((0, y), int(255 * opacity))
    fade_mask = fade_mask.resize(image.size)

    white_background = Image.new("RGB", image.size, "white")
    faded = Image.composite(image, white_background, fade_mask)
    faded.save(output_path, quality=90)


def draw_header(pdf, header_image_path, subtitle="Keyboard cheat sheet  ·  essentials"):
    header_bottom = PAGE_HEIGHT - HEADER_HEIGHT
    pdf.drawImage(ImageReader(header_image_path), 0, header_bottom,
                  width=PAGE_WIDTH, height=HEADER_HEIGHT)

    # A soft dark band behind the title keeps it legible on the busy artwork
    pdf.setFillColor(DEEP_TEAL)
    pdf.setFillAlpha(0.55)
    pdf.roundRect(MARGIN - 8, PAGE_HEIGHT - 66, 330, 50, 8, stroke=0, fill=1)
    pdf.setFillAlpha(1)

    pdf.setFillColor(white)
    pdf.setFont("SansBold", 24)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 44, "Omarchy  &  Herdr")
    pdf.setFont("Sans", 9.5)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 58, subtitle)


# ---------- keycaps and rows ----------

def split_into_keys(key_combo):
    return [part.strip() for part in key_combo.split(" + ")]


def keycap_width(label, font_size):
    return pdfmetrics.stringWidth(label, "Mono", font_size) + 6


def draw_key_combo(pdf, x, y, key_combo, font_size=6.6):
    """Draw keys as little keycaps joined by '+', return the width used."""
    start_x = x
    keys = split_into_keys(key_combo)
    for index, key in enumerate(keys):
        width = keycap_width(key, font_size)
        pdf.setFillColor(KEYCAP_FILL)
        pdf.setStrokeColor(KEYCAP_BORDER)
        pdf.setLineWidth(0.5)
        pdf.roundRect(x, y - 2.4, width, 9.4, 2, stroke=1, fill=1)
        pdf.setFillColor(DEEP_TEAL)
        pdf.setFont("Mono", font_size)
        pdf.drawString(x + 3, y, key)
        x += width
        if index < len(keys) - 1:
            pdf.setFillColor(MUTED)
            pdf.setFont("Sans", 6)
            pdf.drawCentredString(x + 3.5, y + 0.3, "+")
            x += 7
    return x - start_x


def draw_section(pdf, x, y, column_width, title, shortcuts, key_area_width):
    pdf.setFillColor(TEAL)
    pdf.setFont("SansBold", 9)
    pdf.drawString(x, y, title.upper())
    pdf.setStrokeColor(PEACH)
    pdf.setLineWidth(1.2)
    title_width = pdfmetrics.stringWidth(title.upper(), "SansBold", 9)
    pdf.line(x + title_width + 5, y + 3, x + column_width, y + 3)
    y -= SECTION_TITLE_HEIGHT - 4

    for key_combo, description in shortcuts:
        draw_key_combo(pdf, x, y, key_combo)
        pdf.setFillColor(TEXT)
        pdf.setFont("Sans", 7.6)
        pdf.drawString(x + key_area_width, y, description)
        y -= ROW_HEIGHT
    return y - SECTION_SPACING


def widest_key_combo(sections):
    widths = []
    for _, shortcuts in sections:
        for key_combo, _ in shortcuts:
            keys = split_into_keys(key_combo)
            widths.append(sum(keycap_width(k, 6.6) for k in keys) + 7 * (len(keys) - 1))
    return max(widths)


def draw_column(pdf, x, y, column_width, sections):
    # Align descriptions per column so each column reads like a clean table
    key_area_width = widest_key_combo(sections) + 8
    for title, shortcuts in sections:
        y = draw_section(pdf, x, y, column_width, title, shortcuts, key_area_width)
    return y


def draw_custom_section(pdf, x, y, column_width):
    """Custom bindings render like any other section, marked only by a small star."""
    key_area_width = widest_key_combo(OMARCHY_COLUMN_1) + 8
    return draw_section(pdf, x, y, column_width, "Custom ★", CUSTOM_SHORTCUTS, key_area_width)


def draw_column_heading(pdf, x, y, column_width, label, note):
    pdf.setFillColor(DEEP_TEAL)
    pdf.setFont("SansBold", 12)
    pdf.drawString(x, y, label)
    pdf.setFillColor(MUTED)
    pdf.setFont("Sans", 7)
    pdf.drawRightString(x + column_width, y + 0.5, note)
    return y - 17


def build_cheat_sheet(image_path, output_path):
    header_image_path = "/home/claude/header_faded.jpg"
    # Render at ~3x point size so the artwork stays crisp when printed
    build_faded_header_image(image_path, header_image_path, PAGE_WIDTH * 3, HEADER_HEIGHT * 3)

    pdf = canvas.Canvas(output_path, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    pdf.setTitle("Omarchy & Herdr cheat sheet")
    draw_header(pdf, header_image_path)

    column_width = (PAGE_WIDTH - 2 * MARGIN - 2 * COLUMN_GAP) / 3
    column_x = [MARGIN + i * (column_width + COLUMN_GAP) for i in range(3)]
    content_top = PAGE_HEIGHT - HEADER_HEIGHT + 22

    y = draw_column_heading(pdf, column_x[0], content_top, column_width, "Omarchy", "Super + K shows all")
    y = draw_custom_section(pdf, column_x[0], y, column_width)
    lowest_y = [draw_column(pdf, column_x[0], y, column_width, OMARCHY_COLUMN_1)]

    y = draw_column_heading(pdf, column_x[1], content_top, column_width, "Omarchy", "continued")
    lowest_y.append(draw_column(pdf, column_x[1], y, column_width, OMARCHY_COLUMN_2))

    y = draw_column_heading(pdf, column_x[2], content_top, column_width,
                            "Herdr", "Prefix = Ctrl + Space  ·  Super + Ctrl + K shows all")
    lowest_y.append(draw_column(pdf, column_x[2], y, column_width, HERDR_COLUMN))

    # Thin dividers between columns
    pdf.setStrokeColor(KEYCAP_BORDER)
    pdf.setLineWidth(0.4)
    for x in column_x[1:]:
        divider_x = x - COLUMN_GAP / 2
        pdf.line(divider_x, content_top + 8, divider_x, MARGIN + 4)

    pdf.setFillColor(MUTED)
    pdf.setFont("Sans", 6.5)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, 12,
                        "Sources: omarchy.org/manual/hotkeys  ·  herdr.dev/docs/keyboard")
    pdf.save()
    return min(lowest_y)


if __name__ == "__main__":
    lowest = build_cheat_sheet("/mnt/user-data/uploads/1000042622.webp",
                               "/mnt/user-data/outputs/omarchy-herdr-cheatsheet-v2.pdf")
    print("lowest content y:", lowest)
