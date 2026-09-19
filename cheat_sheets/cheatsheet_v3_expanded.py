"""Expanded four column version of the Omarchy & Herdr cheat sheet.

Reuses the header, keycap drawing and palette from v2 so both versions
stay visually consistent; only content and layout density differ here.
"""
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from cheatsheet_v2 import (
    PAGE_WIDTH, PAGE_HEIGHT, MARGIN, HEADER_HEIGHT,
    TEAL, DEEP_TEAL, PEACH, KEYCAP_BORDER, TEXT, MUTED,
    build_faded_header_image, draw_header, draw_key_combo,
    split_into_keys, keycap_width,
)

COLUMN_COUNT = 4
COLUMN_GAP = 14
KEY_FONT_SIZE = 6.2
DESCRIPTION_FONT_SIZE = 7.1
ROW_HEIGHT = 10.3
SECTION_TITLE_HEIGHT = 15
SECTION_SPACING = 7
# Beyond this width a combo pushes its own description right, instead of
# pushing every row in the column and squeezing the descriptions
MAX_ALIGNED_KEY_WIDTH = 92


# ---------- content ----------

OMARCHY_COLUMN_1 = [
    ("Custom ★", [
        ("Super + M", "Recent media panel"),
        ("Super + D", "Downloads panel"),
    ]),
    ("Essentials", [
        ("Super + Space", "Omarchy menu"),
        ("Super + Alt + Space", "Apps menu"),
        ("Super + Esc", "System menu"),
        ("Super + K", "Show all hotkeys"),
        ("Super + Ctrl + L", "Lock computer"),
        ("Super + W", "Close window"),
        ("Ctrl + Alt + Del", "Close all windows"),
    ]),
    ("Windows", [
        ("Super + Arrow", "Focus in direction"),
        ("Super + Shift + Arrow", "Swap in direction"),
        ("Super + T", "Tiling / floating"),
        ("Super + O", "Sticky and floating"),
        ("Super + P", "Pseudo (natural size)"),
        ("Super + J", "Toggle split direction"),
        ("Super + L", "Dwindle / scrolling layout"),
        ("Super + F", "Full screen"),
        ("Super + Alt + F", "Full width"),
        ("Super + Ctrl + F", "Full screen in window"),
        ("Super + - / =", "Resize left"),
        ("Super + Shift + - / =", "Resize up / down"),
        ("Super + Alt + Home", "Save window width"),
        ("Super + Home", "Restore saved width"),
    ]),
    ("Reminders", [
        ("Super + Ctrl + R", "Set a reminder"),
        ("Super + Ctrl + Alt + R", "See all reminders"),
    ]),
]

OMARCHY_COLUMN_2 = [
    ("Workspaces", [
        ("Super + 1-4", "Jump to workspace"),
        ("Super + Shift + 1-4", "Move window there"),
        ("Super + Shift + Alt + 1-4", "Move, stay here"),
        ("Super + Tab", "Next workspace"),
        ("Super + Shift + Tab", "Previous workspace"),
        ("Super + Ctrl + Tab", "Former workspace"),
        ("Super + S", "Toggle scratchpad"),
        ("Super + Alt + S", "Send to scratchpad"),
    ]),
    ("Groups", [
        ("Super + G", "Toggle grouping"),
        ("Super + Alt + G", "Move out of group"),
        ("Super + Alt + Tab", "Cycle in group"),
        ("Super + Alt + 1-5", "Jump to window in group"),
        ("Super + Alt + Arrow", "Move into group"),
    ]),
    ("Focus, zoom & monitors", [
        ("Alt + Tab", "Cycle windows"),
        ("Ctrl + Alt + Tab", "Cycle monitors"),
        ("Super + Ctrl + Z", "Zoom in (repeat)"),
        ("Super + Ctrl + Alt + Z", "Zoom fully out"),
        ("Super + /", "Next monitor scaling"),
    ]),
    ("Notifications", [
        ("Super + ,", "Dismiss latest"),
        ("Super + Shift + ,", "Dismiss all"),
        ("Super + Ctrl + ,", "Silence on / off"),
        ("Super + Shift + Alt + ,", "History"),
    ]),
    ("Mouse", [
        ("Super + Left drag", "Move window"),
        ("Super + Right drag", "Resize window"),
        ("Super + Scroll", "Scroll workspaces"),
    ]),
]

OMARCHY_COLUMN_3 = [
    ("Launch apps", [
        ("Super + Return", "Terminal"),
        ("Super + Alt + Return", "Tmux terminal"),
        ("Super + Ctrl + Return", "Herdr"),
        ("Super + Shift + Return", "Browser"),
        ("Super + Shift + F", "File manager"),
        ("Super + Shift + N", "Neovim"),
        ("Super + Shift + /", "Password manager"),
    ]),
    ("Clipboard", [
        ("Super + C / X / V", "Copy / cut / paste"),
        ("Super + Ctrl + V", "Clipboard history"),
    ]),
    ("Capture", [
        ("Print", "Screenshot"),
        ("Alt + Print", "Screen recording"),
        ("Super + Print", "Color picker"),
        ("Super + Ctrl + Print", "Text to clipboard"),
        ("Super + Ctrl + C", "Capture menu"),
        ("Super + Ctrl + X", "Dictation on / off"),
        ("Alt + Shift + L", "Copy current URL"),
    ]),
    ("System panels", [
        ("Super + Ctrl + A", "Audio"),
        ("Super + Ctrl + W", "Wifi / network"),
        ("Super + Ctrl + B", "Bluetooth"),
        ("Super + Ctrl + D", "Display"),
        ("Super + Ctrl + P", "Power"),
        ("Super + Ctrl + T", "Activity (btop)"),
        ("Super + Ctrl + E", "Emoji picker"),
    ]),
    ("Style & toggles", [
        ("Super + Ctrl + Shift + Space", "Theme"),
        ("Super + Ctrl + Space", "Background"),
        ("Super + Backspace", "Transparency"),
        ("Super + Shift + Space", "Top bar"),
        ("Super + Ctrl + N", "Nightlight"),
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
        ("Prefix + r", "Resize mode (Esc exits)"),
        ("Prefix + [", "Copy mode"),
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
    ("Copy mode", [
        ("v", "Start selection"),
        ("y", "Copy selection"),
        ("/ ?", "Search forward / back"),
        ("n / N", "Next / previous match"),
        ("q", "Leave copy mode"),
    ]),
    ("Command line", [
        ("herdr", "Start or reattach"),
        ("herdr --remote host", "Attach over SSH"),
    ]),
]


# ---------- layout ----------

def key_combo_width(key_combo):
    keys = split_into_keys(key_combo)
    return sum(keycap_width(key, KEY_FONT_SIZE) for key in keys) + 7 * (len(keys) - 1)


def aligned_key_area(sections):
    widest = max(key_combo_width(combo) for _, rows in sections for combo, _ in rows)
    return min(widest, MAX_ALIGNED_KEY_WIDTH) + 7


def draw_section(pdf, x, y, column_width, title, shortcuts, key_area_width):
    pdf.setFillColor(TEAL)
    pdf.setFont("SansBold", 8.4)
    pdf.drawString(x, y, title.upper())
    title_width = pdfmetrics.stringWidth(title.upper(), "SansBold", 8.4)
    pdf.setStrokeColor(PEACH)
    pdf.setLineWidth(1.1)
    pdf.line(x + title_width + 5, y + 3, x + column_width, y + 3)
    y -= SECTION_TITLE_HEIGHT - 3

    for key_combo, description in shortcuts:
        used_width = draw_key_combo(pdf, x, y, key_combo, font_size=KEY_FONT_SIZE)
        description_x = x + max(key_area_width, used_width + 6)
        pdf.setFillColor(TEXT)
        pdf.setFont("Sans", DESCRIPTION_FONT_SIZE)
        pdf.drawString(description_x, y, description)
        y -= ROW_HEIGHT
    return y - SECTION_SPACING


def draw_sections(pdf, x, y, column_width, sections):
    key_area_width = aligned_key_area(sections)
    for title, shortcuts in sections:
        y = draw_section(pdf, x, y, column_width, title, shortcuts, key_area_width)
    return y


def draw_column_heading(pdf, x, y, column_width, label, note):
    pdf.setFillColor(DEEP_TEAL)
    pdf.setFont("SansBold", 11.5)
    pdf.drawString(x, y, label)
    pdf.setFillColor(MUTED)
    pdf.setFont("Sans", 6.5)
    pdf.drawRightString(x + column_width, y + 0.5, note)
    return y - 16


def build_expanded_cheat_sheet(image_path, output_path):
    header_image_path = "/home/claude/header_faded_expanded.jpg"
    build_faded_header_image(image_path, header_image_path, PAGE_WIDTH * 3, HEADER_HEIGHT * 3)

    pdf = canvas.Canvas(output_path, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    pdf.setTitle("Omarchy & Herdr cheat sheet (expanded)")
    draw_header(pdf, header_image_path, subtitle="Keyboard cheat sheet  ·  expanded")

    column_width = (PAGE_WIDTH - 2 * MARGIN - (COLUMN_COUNT - 1) * COLUMN_GAP) / COLUMN_COUNT
    column_x = [MARGIN + i * (column_width + COLUMN_GAP) for i in range(COLUMN_COUNT)]
    content_top = PAGE_HEIGHT - HEADER_HEIGHT + 22
    lowest_y = []

    omarchy_columns = [
        ("Omarchy", "Super + K shows all", OMARCHY_COLUMN_1),
        ("Omarchy", "continued", OMARCHY_COLUMN_2),
        ("Omarchy", "continued", OMARCHY_COLUMN_3),
    ]
    for x, (label, note, sections) in zip(column_x, omarchy_columns):
        y = draw_column_heading(pdf, x, content_top, column_width, label, note)
        lowest_y.append(draw_sections(pdf, x, y, column_width, sections))

    y = draw_column_heading(pdf, column_x[3], content_top, column_width,
                            "Herdr", "Prefix = Ctrl + Space")
    lowest_y.append(draw_sections(pdf, column_x[3], y, column_width, HERDR_COLUMN))

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
    lowest = build_expanded_cheat_sheet("/mnt/user-data/uploads/1000042622.webp",
                                        "/mnt/user-data/outputs/omarchy-herdr-cheatsheet-expanded.pdf")
    print("lowest content y:", lowest)
