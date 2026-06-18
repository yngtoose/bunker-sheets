# -*- coding: utf-8 -*-
"""
Эмулятор фонарика для ГЛУБИНЫ.

Окно показывает фонарь с лучом и шкалу заряда. Кнопка включает фонарик —
заряд начинает расходоваться со временем. Когда заряд кончился, кнопка
«Перезарядить» тратит одну батарейку из инвентаря и заряжает фонарик заново.

Батарейки берутся из расходника «Батарейки для фонаря» (consumables.battery)
через колбэки get_batteries / consume_battery, которые передаёт приложение.
"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QSizePolicy, QMessageBox,
)
from PySide6.QtGui import (
    QPainter, QColor, QLinearGradient, QPen, QBrush, QFont, QPolygonF,
)
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF

import renderer as R
from dice import DARK_QSS


def qc(t):
    return QColor(*t)


BG, PANEL, LINE = qc(R.BG), qc(R.PANEL), qc(R.LINE)
TEXT, MUTED, ACCENT = qc(R.TEXT), qc(R.MUTED), qc(R.ACCENT)
DANGER, GOOD = qc(R.DANGER), qc(R.GOOD)
WARN = QColor(214, 184, 40)


class FlashlightWidget(QWidget):
    """Рисует фонарь с лучом (светится при включении) и шкалу заряда."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.on = False
        self.charge = 100.0
        self.setMinimumSize(300, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_state(self, on, charge):
        self.on = on
        self.charge = charge
        self.update()

    @staticmethod
    def _vgrad(y0, y1, top, bot):
        g = QLinearGradient(0, y0, 0, y1)
        g.setColorAt(0.0, QColor(*top))
        g.setColorAt(1.0, QColor(*bot))
        return g

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        lit = self.on and self.charge > 0
        intensity = (self.charge / 100.0) if lit else 0.0

        cy = h * 0.42
        bodyH = h * 0.145          # тонкий и длинный
        headH = h * 0.26

        x0 = w * 0.04              # хвост (закруглён)
        x_body1 = w * 0.58         # конец корпуса / начало головки
        x_head1 = w * 0.66         # перёд головки
        bezelW = max(8.0, w * 0.018)
        x_bezel = x_head1 + bezelW + 2

        # --- ЛУЧ (за корпусом) ---
        if lit:
            spread = headH * 0.6
            beam = QLinearGradient(x_bezel, cy, w, cy)
            beam.setColorAt(0.0, QColor(255, 240, 175, int(210 * intensity)))
            beam.setColorAt(0.5, QColor(255, 238, 165, int(85 * intensity)))
            beam.setColorAt(1.0, QColor(255, 238, 165, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(beam))
            p.drawPolygon(QPolygonF([
                QPointF(x_bezel, cy - headH * 0.18),
                QPointF(x_bezel, cy + headH * 0.18),
                QPointF(w + 30, cy + spread + h * 0.20),
                QPointF(w + 30, cy - spread - h * 0.20),
            ]))
            # лучи-штрихи
            p.setPen(QPen(QColor(255, 246, 205, int(110 * intensity)), 2))
            for t in (-0.7, -0.28, 0.28, 0.7):
                p.drawLine(QPointF(x_bezel + 4, cy + t * headH * 0.14),
                           QPointF(w - 6, cy + t * (spread + h * 0.16)))

        body_len = x_body1 - x0

        # --- корпус: длинная труба с закруглённым хвостом ---
        p.setBrush(QBrush(self._vgrad(cy - bodyH * 0.5, cy + bodyH * 0.5, (112, 118, 104), (36, 40, 34))))
        p.setPen(QPen(LINE, 2))
        p.drawRoundedRect(QRectF(x0, cy - bodyH * 0.5, body_len, bodyH), bodyH * 0.42, bodyH * 0.42)
        # блик сверху
        p.setPen(QPen(QColor(255, 255, 255, 30), 2))
        p.drawLine(QPointF(x0 + bodyH * 0.5, cy - bodyH * 0.40), QPointF(x_body1 - 6, cy - bodyH * 0.40))

        # рифление: группа у хвоста и у головки
        p.setPen(QPen(QColor(30, 34, 30), 2))

        def grip(a, b, n):
            for k in range(n):
                gx = a + k * (b - a) / (n - 1)
                p.drawLine(QPointF(gx, cy - bodyH * 0.42), QPointF(gx, cy + bodyH * 0.42))

        grip(x0 + body_len * 0.10, x0 + body_len * 0.26, 5)
        grip(x0 + body_len * 0.66, x0 + body_len * 0.88, 6)

        # --- боковая кнопка ---
        btn_w = max(8.0, w * 0.028)
        btn_cx = x0 + body_len * 0.48
        btn_top = cy - bodyH * 0.5
        p.setPen(QPen(LINE, 2))
        p.setBrush(QColor(44, 48, 42))
        p.drawRoundedRect(QRectF(btn_cx - btn_w / 2, btn_top - btn_w * 0.55, btn_w, btn_w * 0.95), 3, 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(72, 78, 68))
        p.drawRoundedRect(QRectF(btn_cx - btn_w * 0.30, btn_top - btn_w * 0.40, btn_w * 0.60, btn_w * 0.5), 2, 2)

        # --- головка-раструб ---
        p.setPen(QPen(LINE, 2))
        p.setBrush(QBrush(self._vgrad(cy - headH * 0.5, cy + headH * 0.5, (120, 126, 112), (40, 44, 38))))
        p.drawPolygon(QPolygonF([
            QPointF(x_body1 - bodyH * 0.35, cy - bodyH * 0.5),
            QPointF(x_head1, cy - headH * 0.5),
            QPointF(x_head1, cy + headH * 0.5),
            QPointF(x_body1 - bodyH * 0.35, cy + bodyH * 0.5),
        ]))

        # --- линза-полоса (НЕ круг) ---
        bezel = QRectF(x_head1 - 2, cy - headH * 0.5, bezelW + 4, headH)
        if lit:
            lg = QLinearGradient(0, cy - headH * 0.5, 0, cy + headH * 0.5)
            lg.setColorAt(0.0, QColor(255, 252, 225))
            lg.setColorAt(0.5, QColor(255, 236, 150))
            lg.setColorAt(1.0, QColor(232, 202, 105))
            p.setBrush(QBrush(lg))
            p.setPen(QPen(QColor(255, 240, 170), 2))
        else:
            p.setBrush(QColor(28, 31, 28))
            p.setPen(QPen(LINE, 2))
        p.drawRoundedRect(bezel, 4, 4)

        # --- шкала заряда ---
        bar_x, bar_w = 24, w - 48
        bar_y, bar_h = h - 38, 18
        p.setPen(QPen(LINE, 1))
        p.setBrush(QColor(40, 44, 40))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5, 5)
        frac = max(0.0, min(1.0, self.charge / 100.0))
        col = GOOD if self.charge > 50 else (WARN if self.charge > 20 else DANGER)
        if frac > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * frac, bar_h), 5, 5)
        f = QFont("Segoe UI")
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        p.setPen(TEXT)
        p.drawText(QRectF(bar_x, bar_y - 1, bar_w, bar_h), Qt.AlignCenter, f"{int(self.charge)}%")


class FlashlightDialog(QDialog):
    """Окно фонарика. get_batteries() -> int, consume_battery() тратит 1 батарейку."""

    def __init__(self, get_batteries, consume_battery, parent=None):
        super().__init__(parent)
        self.get_batteries = get_batteries
        self.consume_battery = consume_battery
        self.charge = 100.0
        self.on = False

        self.setWindowTitle("ГЛУБИНА — фонарик")
        self.setMinimumSize(440, 480)
        self.setStyleSheet(DARK_QSS)

        root = QVBoxLayout(self)
        root.setSpacing(12)

        self.view = FlashlightWidget()
        root.addWidget(self.view, 1)

        self.status = QLabel("—")
        self.status.setAlignment(Qt.AlignCenter)
        sf = QFont()
        sf.setPointSize(13)
        sf.setBold(True)
        self.status.setFont(sf)
        root.addWidget(self.status)

        self.batt_label = QLabel("—")
        self.batt_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.batt_label)

        life_row = QHBoxLayout()
        life_row.addStretch(1)
        life_row.addWidget(QLabel("Заряда хватает на"))
        self.life_spin = QSpinBox()
        self.life_spin.setRange(1, 120)
        self.life_spin.setValue(5)
        self.life_spin.setSuffix(" мин")
        life_row.addWidget(self.life_spin)
        life_row.addStretch(1)
        root.addLayout(life_row)

        btn_row = QHBoxLayout()
        self.toggle_btn = QPushButton("🔦  Включить")
        self.toggle_btn.setMinimumHeight(48)
        self.toggle_btn.clicked.connect(self.toggle)
        self.recharge_btn = QPushButton("🔋  Перезарядить (−1 батарейка)")
        self.recharge_btn.setMinimumHeight(48)
        self.recharge_btn.clicked.connect(self.recharge)
        btn_row.addWidget(self.toggle_btn)
        btn_row.addWidget(self.recharge_btn)
        root.addLayout(btn_row)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.refresh()

    # --- логика ---
    def _tick(self):
        if self.on and self.charge > 0:
            self.charge -= 100.0 / (self.life_spin.value() * 60)
            if self.charge <= 0:
                self.charge = 0.0
                self.on = False
        self.refresh()

    def toggle(self):
        if not self.on:
            if self.charge <= 0:
                QMessageBox.information(
                    self, "Фонарик", "Фонарик разряжен — перезарядите (−1 батарейка).")
                return
            self.on = True
        else:
            self.on = False
        self.refresh()

    def recharge(self):
        if self.charge >= 100:
            QMessageBox.information(self, "Фонарик", "Фонарик уже полностью заряжен.")
            return
        if self.get_batteries() <= 0:
            QMessageBox.warning(self, "Нет батареек",
                                "В рюкзаке нет батареек для фонаря.")
            return
        self.consume_battery()
        self.charge = 100.0
        self.refresh()

    def refresh(self):
        self.view.set_state(self.on, self.charge)
        batt = self.get_batteries()
        if self.on and self.charge > 0:
            rem = self.charge / 100.0 * self.life_spin.value()
            self.status.setText(f"🔦 ВКЛ · заряд {int(self.charge)}% · ≈ {rem:.1f} мин")
            self.status.setStyleSheet("color:#e6d27a;")
            self.toggle_btn.setText("Выключить")
        else:
            state = "разряжен" if self.charge <= 0 else "выключен"
            self.status.setText(f"Фонарик {state} · заряд {int(self.charge)}%")
            self.status.setStyleSheet("color:#8c9486;")
            self.toggle_btn.setText("🔦  Включить")
        self.batt_label.setText(f"Батареек в рюкзаке: {batt}")
        self.batt_label.setStyleSheet("color:#aad640;" if batt > 0 else "color:#d25c46;")

    # таймер крутим только когда окно открыто
    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()
