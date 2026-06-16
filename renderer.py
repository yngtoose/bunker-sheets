# -*- coding: utf-8 -*-
"""
Рендер листа персонажа в PNG через Pillow.

Стиль: тёмный «бункерный» постер с радиационным акцентом, формат A4 (портрет).
Главная функция — render(char) -> PIL.Image. Её зовёт и кнопка экспорта,
и предпросмотр в приложении.
"""

import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import system as S
import model as M

# --- Размеры холста -------------------------------------------------------
W, H = 1240, 1700
MARGIN = 48

# --- Цвета ----------------------------------------------------------------
BG       = (18, 20, 18)       # почти чёрный с зеленцой
PANEL    = (28, 31, 28)       # панель
PANEL_HI = (36, 40, 35)
LINE     = (60, 66, 58)
TEXT     = (220, 224, 214)
MUTED    = (140, 148, 134)
ACCENT   = (170, 214, 64)     # радиационный жёлто-зелёный
ACCENT_D = (108, 140, 38)
DANGER   = (210, 92, 70)      # тревожный оранжево-красный
GOOD     = (120, 180, 90)


# --- Шрифты ---------------------------------------------------------------
def _find_font(candidates):
    win_fonts = r"C:\Windows\Fonts"
    for name in candidates:
        p = os.path.join(win_fonts, name)
        if os.path.exists(p):
            return p
    # запасной вариант — шрифт из самого Pillow (есть кириллица)
    try:
        import PIL
        base = os.path.join(os.path.dirname(PIL.__file__), "fonts")
        for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    except Exception:
        pass
    return None


_REG_PATH = _find_font(["arial.ttf", "segoeui.ttf"])
_BOLD_PATH = _find_font(["arialbd.ttf", "seguisb.ttf", "segoeuib.ttf"])
_MONO_PATH = _find_font(["consola.ttf", "cour.ttf"]) or _BOLD_PATH
# Промышленный узкий шрифт для заголовков (с кириллицей)
_DISP_PATH = _find_font(["bahnschrift.ttf", "seguisb.ttf"]) or _BOLD_PATH

_font_cache = {}


def font(size, bold=False, mono=False, disp=False):
    key = (size, bold, mono, disp)
    if key not in _font_cache:
        if disp:
            path = _DISP_PATH
        elif mono:
            path = _MONO_PATH
        elif bold:
            path = _BOLD_PATH
        else:
            path = _REG_PATH
        try:
            _font_cache[key] = ImageFont.truetype(path, size)
        except Exception:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


# --- Примитивы рисования --------------------------------------------------
def _text(d, xy, s, f, fill=TEXT, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def _text_w(d, s, f):
    return d.textlength(s, font=f)


def _rivet(d, cx, cy, r=4):
    """Заклёпка: тёмная лунка со светлым бликом."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(20, 22, 19), outline=(70, 76, 66), width=1)
    d.ellipse([cx - r + 1, cy - r + 1, cx - 1, cy - 1], fill=(96, 104, 88))


def panel(d, x, y, w, h, title=None, fill=PANEL, radius=10, rivets=True):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=LINE, width=2)
    # тонкая верхняя подсветка — будто металл ловит свет
    d.line([x + radius, y + 2, x + w - radius, y + 2], fill=(48, 53, 46), width=1)
    if rivets and w > 80 and h > 60:
        inset = 14
        for cx in (x + inset, x + w - inset):
            for cy in (y + inset, y + h - inset):
                _rivet(d, cx, cy)
    if title:
        # акцентная риска слева от заголовка
        d.rectangle([x + 16, y + 16, x + 21, y + 36], fill=ACCENT)
        d.text((x + 32, y + 12), title.upper(), font=font(22, disp=True), fill=ACCENT)
    return y + (48 if title else 14)


def hazard_stripes(d, x, y, w, h, c1=(214, 184, 40), c2=(20, 22, 19), step=26):
    """Диагональные предупреждающие полосы (жёлто-чёрные)."""
    # подложка
    d.rectangle([x, y, x + w, y + h], fill=c1)
    # косые тёмные полосы поверх, обрезанные по полосе
    i = -h
    while i < w + h:
        d.polygon([(x + i, y), (x + i + step, y), (x + i + step - h, y + h), (x + i - h, y + h)],
                  fill=c2)
        i += step * 2


def radiation_icon(d, cx, cy, r, color):
    """Знак радиации (трилистник) — три сектора вокруг центра."""
    import math
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
    for k in range(3):
        a0 = -90 + k * 120 - 30
        a1 = a0 + 60
        d.pieslice([cx - r, cy - r, cx + r, cy + r], a0, a1, fill=color)
    d.ellipse([cx - r * 0.22, cy - r * 0.22, cx + r * 0.22, cy + r * 0.22], fill=color)


def wrap(d, text, f, max_w):
    """Перенос текста по ширине. Возвращает список строк."""
    lines = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split(" ")
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if _text_w(d, trial, f) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def draw_paragraph(d, x, y, text, f, max_w, line_h, fill=TEXT, placeholder="—"):
    if not str(text).strip():
        _text(d, (x, y), placeholder, f, fill=MUTED)
        return y + line_h
    for ln in wrap(d, text, f, max_w):
        _text(d, (x, y), ln, f, fill=fill)
        y += line_h
    return y


# --- Секции ---------------------------------------------------------------
def draw_header(d, char):
    # Верхняя плашка с лёгким вертикальным градиентом
    for i in range(132):
        t = i / 132
        col = (int(40 - 18 * t), int(44 - 20 * t), int(38 - 18 * t))
        d.line([0, i, W, i], fill=col)
    # hazard-полоса снизу шапки
    hazard_stripes(d, 0, 130, W, 10)

    _text(d, (MARGIN, 18), S.SYSTEM_NAME, font(52, disp=True), fill=ACCENT)
    sub_x = MARGIN + d.textlength(S.SYSTEM_NAME, font(52, disp=True)) + 18
    _text(d, (sub_x, 58), S.SYSTEM_SUBTITLE, font(19, disp=True), fill=MUTED)

    # Имя персонажа справа
    name = char.get("char_name") or "Безымянный"
    _text(d, (W - MARGIN, 22), name, font(38, disp=True), fill=TEXT, anchor="ra")
    line2 = char.get("archetype", "")
    _text(d, (W - MARGIN, 70), line2, font(22, disp=True), fill=ACCENT, anchor="ra")
    line3 = f"Игрок: {char.get('player_name') or '—'}    ·    Погружение {char.get('depth_level', 1)}"
    _text(d, (W - MARGIN, 100), line3, font(17), fill=MUTED, anchor="ra")


def draw_abilities(d, x, y, w, char):
    top = panel(d, x, y, w, 96, title=None, fill=BG, radius=0)
    # 6 коробок в ряд
    n = len(S.ABILITIES)
    gap = 12
    bw = (w - gap * (n - 1)) / n
    bh = 132
    for i, ab in enumerate(S.ABILITIES):
        bx = x + i * (bw + gap)
        d.rounded_rectangle([bx, y, bx + bw, y + bh], radius=10, fill=PANEL, outline=LINE, width=2)
        _text(d, (bx + bw / 2, y + 16), ab["name"], font(17, bold=True), fill=ACCENT, anchor="ma")
        score = char["abilities"].get(ab["key"], 10)
        _text(d, (bx + bw / 2, y + 44), str(score), font(40, bold=True), fill=TEXT, anchor="ma")
        mod = S.format_modifier(M.ability_mod(char, ab["key"]))
        # «таблетка» с модификатором
        pill_w, pill_h = 56, 30
        px = bx + bw / 2 - pill_w / 2
        py = y + 92
        d.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=15,
                            fill=ACCENT_D, outline=ACCENT, width=2)
        _text(d, (bx + bw / 2, py + pill_h / 2), mod, font(20, bold=True), fill=(15, 18, 12), anchor="mm")
    return y + bh


def draw_combat(d, x, y, w, char):
    h = 96
    stats = [
        ("ЗАЩИТА", str(char.get("armor_class", 10))),
        ("ИНИЦ.", S.format_modifier(M.init(char))),
        ("СКОР.", f"{char.get('speed', 9)}м"),
        ("МАСТЕР.", S.format_modifier(int(char.get("prof_bonus", 2)))),
        ("ХИТЫ", str(char.get("hit_die", "к8"))),
        ("ПАС.ВНИМ.", str(M.passive_perception(char))),
    ]
    n = len(stats)
    gap = 12
    bw = (w - gap * (n - 1)) / n
    for i, (label, val) in enumerate(stats):
        bx = x + i * (bw + gap)
        d.rounded_rectangle([bx, y, bx + bw, y + h], radius=10, fill=PANEL, outline=LINE, width=2)
        _text(d, (bx + bw / 2, y + 14), label, font(14, bold=True), fill=MUTED, anchor="ma")
        _text(d, (bx + bw / 2, y + 40), val, font(32, bold=True), fill=TEXT, anchor="ma")
    return y + h


def draw_hp(d, x, y, w, char):
    h = 96
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=PANEL, outline=LINE, width=2)
    _text(d, (x + 16, y + 12), "ЗДОРОВЬЕ (ОЗ)", font(16, bold=True), fill=ACCENT)
    cur = char.get("hp_current", 0)
    mx = M.max_hp(char)
    tmp = char.get("hp_temp", 0)
    _text(d, (x + 16, y + 40), f"{cur}", font(44, bold=True), fill=TEXT)
    cur_w = _text_w(d, str(cur), font(44, bold=True))
    _text(d, (x + 24 + cur_w, y + 56), f"/ {mx}", font(26), fill=MUTED)
    if tmp:
        _text(d, (x + 16, y + 96 - 22), f"времен. +{tmp}", font(16), fill=GOOD)
    # полоса здоровья
    bar_x = x + 16
    bar_y = y + h - 16
    bar_w = w - 32
    d.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 8], radius=4, fill=(50, 54, 48))
    frac = 0 if mx <= 0 else max(0.0, min(1.0, cur / mx))
    if frac > 0:
        col = GOOD if frac > 0.5 else (ACCENT if frac > 0.25 else DANGER)
        d.rounded_rectangle([bar_x, bar_y, bar_x + bar_w * frac, bar_y + 8], radius=4, fill=col)
    return y + h


def draw_tracks(d, x, y, w, char):
    body_top = panel(d, x, y, w, 196, title="Шкалы выживания")
    row_h = 36
    for i, t in enumerate(S.SURVIVAL_TRACKS):
        ry = body_top + i * row_h
        if t["key"] == "infection":
            radiation_icon(d, x + 28, ry + 11, 11, DANGER)
            _text(d, (x + 46, ry), t["name"], font(18, bold=True), fill=TEXT)
        else:
            _text(d, (x + 16, ry), t["name"], font(18, bold=True), fill=TEXT)
        val = char["tracks"].get(t["key"], 0)
        mx = t["max"]
        # пипсы
        pip_r = 9
        gap = 6
        start_x = x + 230
        for p in range(mx):
            cx = start_x + p * (pip_r * 2 + gap)
            filled = p < val
            if filled:
                col = DANGER if t["danger"] == "high" else GOOD
            else:
                col = (50, 54, 48)
            d.ellipse([cx, ry + 2, cx + pip_r * 2, ry + 2 + pip_r * 2],
                      fill=col, outline=LINE, width=1)
        _text(d, (x + w - 16, ry + 2), f"{val}/{mx}", font(16), fill=MUTED, anchor="ra")
    return y + 196


def draw_saves(d, x, y, w, char):
    body_top = panel(d, x, y, w, 200, title="Спасброски")
    row_h = 24
    for i, key in enumerate(S.SAVE_ABILITIES):
        ry = body_top + i * row_h
        prof = char["save_prof"].get(key, False)
        # маркер владения
        mx = x + 16
        d.ellipse([mx, ry + 3, mx + 14, ry + 17], outline=ACCENT, width=2,
                  fill=ACCENT if prof else None)
        _text(d, (mx + 26, ry), S.ABILITY_NAME[key], font(17), fill=TEXT)
        bonus = S.format_modifier(M.save_bonus(char, key))
        _text(d, (x + w - 16, ry), bonus, font(18, bold=True), fill=ACCENT, anchor="ra")
    return y + 200


def draw_weapons(d, x, y, w, char):
    weapons = [wp for wp in char.get("weapons", []) if (wp.get("name") or "").strip()]
    rows = max(1, len(weapons))
    body_h = 70 + rows * 30
    body_top = panel(d, x, y, w, body_h, title="Оружие")
    # заголовки
    c1 = x + 16
    c2 = x + w - 220
    c3 = x + w - 100
    _text(d, (c1, body_top), "Название", font(14, bold=True), fill=MUTED)
    _text(d, (c2, body_top), "Попадание", font(14, bold=True), fill=MUTED)
    _text(d, (c3, body_top), "Урон", font(14, bold=True), fill=MUTED)
    yy = body_top + 28
    if not weapons:
        _text(d, (c1, yy), "—", font(16), fill=MUTED)
    for wp in weapons:
        _text(d, (c1, yy), wp.get("name", ""), font(16), fill=TEXT)
        _text(d, (c2, yy), wp.get("attack", "") or "—", font(16), fill=TEXT)
        _text(d, (c3, yy), wp.get("damage", "") or "—", font(16), fill=TEXT)
        yy += 30
    return y + body_h


def draw_gear(d, x, y, w, h, char):
    body_top = panel(d, x, y, w, h, title="Снаряжение")
    yy = body_top
    _text(d, (x + 16, yy), "Броня:", font(15, bold=True), fill=MUTED)
    for ln in wrap(d, char.get("armor") or "—", font(15), w - 116):
        _text(d, (x + 100, yy), ln, font(15), fill=TEXT)
        yy += 22
    yy += 6
    _text(d, (x + 16, yy), "Расходники:", font(15, bold=True), fill=MUTED)
    yy += 26
    for c in S.CONSUMABLES:
        val = char["consumables"].get(c["key"], 0)
        _text(d, (x + 28, yy), c["name"], font(14), fill=TEXT)
        _text(d, (x + w - 16, yy), str(val), font(15, bold=True), fill=ACCENT, anchor="ra")
        yy += 24
    return y + h


def draw_textblock(d, x, y, w, h, title, text, char_key=None):
    body_top = panel(d, x, y, w, h, title=title)
    draw_paragraph(d, x + 16, body_top, text, font(15), w - 32, 22)
    return y + h


def _labeled(d, x, y, w, label, text):
    """Подпись + абзац под ней. Возвращает новый y."""
    _text(d, (x, y), label, font(15, bold=True), fill=MUTED)
    y += 24
    y = draw_paragraph(d, x, y, text, font(15), w, 22)
    return y + 8


def draw_about(d, x, y, w, h, char):
    body_top = panel(d, x, y, w, h, title="О персонаже")
    yy = body_top
    # Рост / Возраст / Вес в одну строку
    col = (w - 32) / 3
    for i, (label, key) in enumerate([("Рост", "height"), ("Возраст", "age"), ("Вес", "weight")]):
        cx = x + 16 + i * col
        _text(d, (cx, yy), f"{label}:", font(15, bold=True), fill=MUTED)
        lw = _text_w(d, f"{label}:", font(15, bold=True))
        _text(d, (cx + lw + 8, yy), char.get(key) or "—", font(15), fill=TEXT)
    yy += 34
    yy = _labeled(d, x + 16, yy, w - 32, "Характер:", char.get("personality", ""))
    yy = _labeled(d, x + 16, yy, w - 32, "Особая черта:", char.get("special_trait", ""))
    yy = _labeled(d, x + 16, yy, w - 32, "Предыстория:", char.get("backstory", ""))
    return y + h


def _postprocess(img):
    """Зерно бетона + виньетка по краям — атмосфера старого документа."""
    noise = Image.effect_noise((W, H), 22).convert("L")
    img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.045)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse(
        [int(-W * 0.25), int(-H * 0.2), int(W * 1.25), int(H * 1.2)], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(260))
    dark = Image.new("RGB", (W, H), (8, 9, 8))
    return Image.composite(img, dark, vig)


# --- Главная сборка -------------------------------------------------------
def render(char):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    draw_header(d, char)

    x = MARGIN
    full_w = W - 2 * MARGIN
    y = 160

    # происхождение строкой
    origin = char.get("origin") or "—"
    _text(d, (x, y), f"Происхождение: {origin}", font(17), fill=MUTED)
    y += 36

    # Характеристики на всю ширину
    y = draw_abilities(d, x, y, full_w, char) + 18

    # Две колонки
    gap = 24
    col_w = (full_w - gap) / 2
    left_x = x
    right_x = x + col_w + gap

    # --- Левая колонка ---
    ly = y
    ly = draw_hp(d, left_x, ly, col_w, char) + 18
    ly = draw_combat(d, left_x, ly, col_w, char) + 18
    ly = draw_tracks(d, left_x, ly, col_w, char) + 18

    # --- Правая колонка ---
    ry = y
    ry = draw_saves(d, right_x, ry, col_w, char) + 18
    ry = draw_weapons(d, right_x, ry, col_w, char) + 18

    # Выравниваем низ колонок — берём максимум
    y2 = max(ly, ry) + 6

    # Полноширинные блоки снизу
    gw = (full_w - gap) / 2

    # О персонаже — на всю ширину
    y2 = draw_about(d, x, y2, full_w, 280, char) + 18

    # Снаряжение | Инвентарь
    gear_h = 230
    draw_gear(d, x, y2, gw, gear_h, char)
    draw_textblock(d, x + gw + gap, y2, gw, gear_h, "Инвентарь", char.get("inventory", ""))
    y2 += gear_h + 18

    # Перки/мутации | Репутация
    h_block = 170
    draw_textblock(d, x, y2, gw, h_block, "Перки / мутации", char.get("perks", ""))
    draw_textblock(d, x + gw + gap, y2, gw, h_block, "Репутация с фракциями", char.get("reputation", ""))
    y2 += h_block + 18

    # Заметки — на всю ширину
    draw_textblock(d, x, y2, full_w, 120, "Заметки / связи", char.get("notes", ""))

    # Подвал
    _text(d, (W / 2, H - 28), f"{S.SYSTEM_NAME} · лист персонажа", font(14), fill=MUTED, anchor="ma")

    return _postprocess(img)


if __name__ == "__main__":
    # Быстрый тест: рендерим пустого персонажа.
    c = M.new_character()
    c["char_name"] = "Тест Тестов"
    c["abilities"]["str"] = 14
    render(c).save("preview_test.png")
    print("saved preview_test.png")
