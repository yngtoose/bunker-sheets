# -*- coding: utf-8 -*-
"""
Анимированный бросок костей для ГЛУБИНЫ.

- DieWidget   — один кубик, умеет рисовать грань (пипсы для Д6, число для Д12/Д20)
                и «дёргаться» во время броска.
- DiceRoller  — панель: выбор типа кубика (Д6/Д12/Д20), количество, кнопка броска,
                ряд кубиков и итог. Бросок анимирован: грани быстро мелькают и
                плавно замедляются (ease-out), потом застывают.
- DiceDialog  — окно, которое открывает кнопка «🎲 Кости» в приложении.
"""

import math
import random

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QSizePolicy,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QFontDatabase,
)
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal

import renderer as R  # берём оттуда палитру, чтобы совпадало с листом


def qc(rgb):
    return QColor(*rgb)


BG     = qc(R.BG)
PANEL  = qc(R.PANEL)
LINE   = qc(R.LINE)
TEXT   = qc(R.TEXT)
MUTED  = qc(R.MUTED)
ACCENT = qc(R.ACCENT)
DANGER = qc(R.DANGER)

DICE_TYPES = [6, 12, 20]

# Шрифт для цифр на кубиках. Грузим из файла, чтобы глифы были гарантированно
# доступны (промышленный Bahnschrift в тему листа), иначе — системный запасной.
_NUM_FAMILY = None


def num_family():
    global _NUM_FAMILY
    if _NUM_FAMILY is None:
        _NUM_FAMILY = "Segoe UI"
        for path in (r"C:\Windows\Fonts\bahnschrift.ttf",
                     r"C:\Windows\Fonts\seguisb.ttf"):
            fid = QFontDatabase.addApplicationFont(path)
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                _NUM_FAMILY = fams[0]
                break
    return _NUM_FAMILY


class DieWidget(QWidget):
    """Один кубик: объёмное тело с фасетками, тенью, бликом и свечением."""

    def __init__(self, sides=20, parent=None):
        super().__init__(parent)
        self.sides = sides
        self.value = sides
        self.angle = 0.0
        self.is_max = False     # подсветить, если выпал максимум
        self.setMinimumSize(86, 86)
        self.setMaximumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def set_state(self, value, angle=0.0):
        self.value = value
        self.angle = angle
        self.is_max = (value == self.sides) and angle == 0.0
        self.update()

    # --- геометрия ---
    def _poly(self, r, n, rot_deg=-90):
        pts = []
        for i in range(n):
            a = math.radians(rot_deg) + 2 * math.pi * i / n
            pts.append(QPointF(r * math.cos(a), r * math.sin(a)))
        return pts

    def _shape_path(self, r):
        path = QPainterPath()
        if self.sides == 6:
            rad = r * 0.30
            path.addRoundedRect(QRectF(-r, -r, 2 * r, 2 * r), rad, rad)
        else:
            n = 5 if self.sides == 12 else 6   # пентагон для Д12, гексагон-силуэт для Д20
            pts = self._poly(r, n)
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            path.closeSubpath()
        return path

    def _body_gradient(self, r):
        g = QLinearGradient(0, -r, 0, r)
        g.setColorAt(0.0, QColor(58, 64, 54))
        g.setColorAt(0.5, QColor(32, 36, 31))
        g.setColorAt(1.0, QColor(16, 18, 15))
        return g

    # --- содержимое грани ---
    def _draw_pips(self, p, r):
        s, pr = r * 0.92, r * 0.135
        TL, TR = (-0.5, -0.5), (0.5, -0.5)
        ML, MR = (-0.5, 0.0), (0.5, 0.0)
        BL, BR = (-0.5, 0.5), (0.5, 0.5)
        C = (0.0, 0.0)
        layouts = {
            1: [C], 2: [TL, BR], 3: [TL, C, BR],
            4: [TL, TR, BL, BR], 5: [TL, TR, C, BL, BR],
            6: [TL, TR, ML, MR, BL, BR],
        }
        for (dx, dy) in layouts.get(self.value, [C]):
            cx, cy = dx * s, dy * s
            # впадинка-тень
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 130))
            p.drawEllipse(QPointF(cx, cy + 1.6), pr, pr)
            # глянцевая пипса
            g = QRadialGradient(cx - pr * 0.3, cy - pr * 0.3, pr * 1.5)
            g.setColorAt(0.0, QColor(208, 242, 122))
            g.setColorAt(1.0, QColor(120, 150, 40))
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(cx, cy), pr, pr)

    def _facets_d20(self, p, r):
        hexp = self._poly(r, 6)
        tri = [hexp[0], hexp[2], hexp[4]]   # центральный треугольник вершиной вверх
        path = QPainterPath()
        path.moveTo(tri[0])
        path.lineTo(tri[1])
        path.lineTo(tri[2])
        path.closeSubpath()
        p.setBrush(QColor(255, 255, 255, 16))
        p.setPen(QPen(QColor(0, 0, 0, 80), 1.6))
        p.drawPath(path)

    def _facets_pentagon(self, p, r):
        outer = self._poly(r, 5)
        inner = self._poly(r * 0.52, 5, rot_deg=-90 + 36)
        p.setPen(QPen(QColor(0, 0, 0, 60), 1.4))
        for i in range(5):
            p.drawLine(outer[i], inner[i])
            p.drawLine(outer[i], inner[(i - 1) % 5])
        path = QPainterPath()
        path.moveTo(inner[0])
        for pt in inner[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        p.setBrush(QColor(255, 255, 255, 16))
        p.setPen(QPen(QColor(0, 0, 0, 80), 1.4))
        p.drawPath(path)

    def _draw_number(self, p, r, yoff=0.0):
        f = QFont(num_family())
        f.setBold(True)
        f.setPointSizeF(r * 0.58)
        p.setFont(f)
        rect = QRectF(-r, -r + yoff, 2 * r, 2 * r)
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(rect.translated(1.5, 2.0), Qt.AlignCenter, str(self.value))
        p.setPen(TEXT)
        p.drawText(rect, Qt.AlignCenter, str(self.value))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 16
        outline = DANGER if self.is_max else ACCENT

        # свечение при максимуме
        if self.is_max:
            for i, alpha in enumerate((46, 30, 16)):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(outline.red(), outline.green(), outline.blue(), alpha))
                rr = r + 6 + i * 8
                p.drawEllipse(QPointF(cx, cy), rr, rr)

        p.translate(cx, cy)
        if self.angle:
            p.rotate(self.angle)

        path = self._shape_path(r)

        # падающая тень
        p.save()
        p.translate(0, r * 0.16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawPath(path)
        p.restore()

        # тело
        p.setBrush(QBrush(self._body_gradient(r)))
        p.setPen(QPen(outline, 3.4))
        p.drawPath(path)

        # верхний блик (сияние сверху)
        p.save()
        p.setClipPath(path)
        sheen = QLinearGradient(0, -r, 0, r * 0.1)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 42))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(sheen))
        p.drawRect(QRectF(-r, -r, 2 * r, 1.3 * r))
        p.restore()

        # грань
        if self.sides == 6:
            self._draw_pips(p, r)
        elif self.sides == 12:
            self._facets_pentagon(p, r)
            self._draw_number(p, r)
        else:
            self._facets_d20(p, r)
            self._draw_number(p, r, yoff=r * 0.12)


class DiceRoller(QWidget):
    """Панель броска: выбор кубика, количество, анимация, итог."""

    rolled = Signal(list, int)  # (значения, сумма)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sides = 20
        self.count = 1
        self.dice = []          # список DieWidget
        self._rolling = False
        self._ticks = 0
        self._max_ticks = 16

        root = QVBoxLayout(self)
        root.setSpacing(14)

        # --- заголовок ---
        title = QLabel("БРОСОК КОСТЕЙ")
        title.setAlignment(Qt.AlignCenter)
        tlf = QFont()
        tlf.setPointSize(15)
        tlf.setBold(True)
        title.setFont(tlf)
        title.setStyleSheet("color:#aad640; letter-spacing:2px;")
        root.addWidget(title)

        # --- выбор типа кубика ---
        type_row = QHBoxLayout()
        type_row.addStretch(1)
        self.type_buttons = {}
        for s in DICE_TYPES:
            b = QPushButton(f"Д{s}")
            b.setCheckable(True)
            b.setMinimumWidth(72)
            b.setMinimumHeight(40)
            b.clicked.connect(lambda _=False, sides=s: self.set_sides(sides))
            self.type_buttons[s] = b
            type_row.addWidget(b)
        type_row.addSpacing(20)
        type_row.addWidget(QLabel("Кубиков:"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 10)
        self.count_spin.setValue(1)
        self.count_spin.setMinimumHeight(40)
        self.count_spin.valueChanged.connect(self.set_count)
        type_row.addWidget(self.count_spin)
        type_row.addStretch(1)
        root.addLayout(type_row)

        # --- поле кубиков ---
        self.dice_row = QHBoxLayout()
        self.dice_row.setSpacing(14)
        dice_host = QWidget()
        dice_host.setObjectName("diceHost")
        dice_host.setLayout(self.dice_row)
        dice_host.setMinimumHeight(170)
        dice_host.setStyleSheet(
            "#diceHost { background:#15181480; border:1px solid #2a2f28; border-radius:10px; }")
        root.addWidget(dice_host, 1)

        # --- итог ---
        self.total_label = QLabel("—")
        self.total_label.setAlignment(Qt.AlignCenter)
        tf = QFont()
        tf.setPointSize(19)
        self.total_label.setFont(tf)
        self.total_label.setStyleSheet("color:#dce0d6;")
        root.addWidget(self.total_label)

        # --- кнопка броска ---
        self.roll_btn = QPushButton("🎲  Бросить")
        self.roll_btn.setMinimumHeight(52)
        rf = QFont()
        rf.setPointSize(13)
        rf.setBold(True)
        self.roll_btn.setFont(rf)
        self.roll_btn.clicked.connect(self.roll)
        root.addWidget(self.roll_btn)

        self.set_sides(20)
        self._rebuild_dice()

    # --- настройка ---
    def set_sides(self, sides):
        if self._rolling:
            return
        self.sides = sides
        for s, b in self.type_buttons.items():
            b.setChecked(s == sides)
        for d in self.dice:
            d.sides = sides
            d.set_state(sides)
        self.total_label.setText("—")

    def set_count(self, n):
        if self._rolling:
            return
        self.count = n
        self._rebuild_dice()
        self.total_label.setText("—")

    def _rebuild_dice(self):
        while self.dice_row.count():
            item = self.dice_row.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)      # сразу убрать с экрана (без «призрака»)
                w.deleteLater()
        self.dice = []
        self.dice_row.addStretch(1)
        for _ in range(self.count):
            d = DieWidget(self.sides)
            self.dice.append(d)
            self.dice_row.addWidget(d)
        self.dice_row.addStretch(1)

    # --- анимация броска ---
    def roll(self):
        if self._rolling or not self.dice:
            return
        self._rolling = True
        self.roll_btn.setEnabled(False)
        self._ticks = 0
        self._tick()

    def _tick(self):
        for d in self.dice:
            d.set_state(random.randint(1, d.sides), random.uniform(-14, 14))
        self._ticks += 1
        if self._ticks >= self._max_ticks:
            self._finish()
            return
        # ease-out: интервал растёт квадратично — кубики «замедляются»
        interval = 30 + (self._ticks ** 2) * 0.7
        QTimer.singleShot(int(interval), self._tick)

    def _finish(self):
        values = []
        for d in self.dice:
            v = random.randint(1, d.sides)
            d.set_state(v, 0.0)   # angle=0 — застываем ровно
            values.append(v)
        total = sum(values)
        if len(values) > 1:
            self.total_label.setText(
                f"{'  +  '.join(map(str, values))}   =   <b>{total}</b>"
            )
        else:
            self.total_label.setText(f"Выпало:  <b>{total}</b>")
        self._rolling = False
        self.roll_btn.setEnabled(True)
        self.rolled.emit(values, total)


DARK_QSS = """
QDialog { background: #121412; }
QLabel { color: #dce0d6; }
QSpinBox {
    background: #1c1f1c; color: #dce0d6; border: 2px solid #3c423a;
    border-radius: 6px; padding: 4px; min-width: 54px;
}
QPushButton {
    background: #1c1f1c; color: #dce0d6; border: 2px solid #3c423a;
    border-radius: 8px; padding: 6px 10px;
}
QPushButton:hover { border-color: #aad640; }
QPushButton:checked { background: #6c8c26; color: #121412; border-color: #aad640; }
QPushButton:disabled { color: #6a6f64; }
"""


class DiceDialog(QDialog):
    """Окно броска костей."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ГЛУБИНА — кости")
        self.setMinimumSize(500, 480)
        self.setStyleSheet(DARK_QSS)
        lay = QVBoxLayout(self)
        self.roller = DiceRoller()
        lay.addWidget(self.roller)
