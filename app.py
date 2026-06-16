# -*- coding: utf-8 -*-
"""
ГЛУБИНА — конструктор листов персонажа (PySide6).

Слева — форма со всеми полями. Справа — живой предпросмотр картинки и кнопки:
Новый / Открыть / Сохранить / Экспорт PNG.

Запуск:  py -3.12 app.py
"""

import sys
import io

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QSpinBox, QComboBox,
    QCheckBox, QPlainTextEdit, QPushButton, QScrollArea, QGridLayout, QVBoxLayout,
    QHBoxLayout, QGroupBox, QFileDialog, QMessageBox, QFrame, QSizePolicy,
)
from PySide6.QtGui import QPixmap, QImage, QFont
from PySide6.QtCore import Qt, QTimer

from PIL.ImageQt import ImageQt

import system as S
import model as M
import renderer as R
import dice as D


class SheetApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.char = M.new_character()
        self.widgets = {}          # простые поля: key -> widget
        self.ability_w = {}        # key -> QSpinBox
        self.save_w = {}           # key -> QCheckBox
        self.skill_w = {}          # key -> QCheckBox
        self.track_w = {}          # key -> QSpinBox
        self.cons_w = {}           # key -> QSpinBox
        self.weapon_w = []         # список (name, attack, damage) QLineEdit
        self.current_path = None
        self.dice_dialog = None

        self.setWindowTitle(f"{S.SYSTEM_NAME} — конструктор листов персонажа")
        self.resize(1500, 950)

        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.update_preview)
        self.update_preview()

    # --- Построение интерфейса -------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # Левая часть: прокручиваемая форма
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_host = QWidget()
        self.form = QVBoxLayout(form_host)
        self.form.setSpacing(12)
        scroll.setWidget(form_host)
        scroll.setMinimumWidth(720)
        root.addWidget(scroll, 3)

        self._build_header_section()
        self._build_abilities_section()
        self._build_combat_section()
        self._build_tracks_section()
        self._build_saves_section()
        self._build_skills_section()
        self._build_weapons_section()
        self._build_gear_section()
        self._build_inventory_section()
        self._build_about_section()
        self._build_text_sections()
        self.form.addStretch(1)

        # Правая часть: предпросмотр + кнопки
        right = QVBoxLayout()
        btn_row = QHBoxLayout()
        for text, slot in [
            ("Новый", self.on_new),
            ("Открыть…", self.on_open),
            ("Сохранить…", self.on_save),
            ("Экспорт PNG…", self.on_export),
            ("🎲 Кости", self.on_dice),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        right.addLayout(btn_row)

        self.preview = QLabel("Предпросмотр")
        self.preview.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.preview.setMinimumWidth(520)
        prev_scroll = QScrollArea()
        prev_scroll.setWidgetResizable(True)
        prev_scroll.setWidget(self.preview)
        right.addWidget(prev_scroll, 1)
        root.addLayout(right, 2)

    def _group(self, title):
        box = QGroupBox(title)
        self.form.addWidget(box)
        return box

    def _line(self, key, value=""):
        w = QLineEdit(str(value))
        w.textChanged.connect(self.schedule_refresh)
        self.widgets[key] = w
        return w

    def _spin(self, key, value, lo, hi, store):
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(int(value))
        w.valueChanged.connect(self.schedule_refresh)
        store[key] = w
        return w

    def _build_header_section(self):
        box = self._group("Шапка")
        g = QGridLayout(box)
        g.addWidget(QLabel("Имя персонажа"), 0, 0)
        g.addWidget(self._line("char_name", self.char["char_name"]), 0, 1)
        g.addWidget(QLabel("Игрок"), 0, 2)
        g.addWidget(self._line("player_name", self.char["player_name"]), 0, 3)

        g.addWidget(QLabel("Архетип"), 1, 0)
        arch = QComboBox()
        arch.addItems(S.ARCHETYPES)
        arch.setCurrentText(self.char["archetype"])
        arch.currentTextChanged.connect(self.schedule_refresh)
        self.widgets["archetype"] = arch
        g.addWidget(arch, 1, 1)

        g.addWidget(QLabel("Происхождение"), 1, 2)
        g.addWidget(self._line("origin", self.char["origin"]), 1, 3)

        g.addWidget(QLabel("Погружение (ур.)"), 2, 0)
        g.addWidget(self._spin("depth_level", self.char["depth_level"], 1, 20, self.widgets), 2, 1)
        g.addWidget(QLabel("Бонус мастерства"), 2, 2)
        g.addWidget(self._spin("prof_bonus", self.char["prof_bonus"], 1, 10, self.widgets), 2, 3)

    def _build_abilities_section(self):
        box = self._group("Характеристики")
        g = QGridLayout(box)
        for i, ab in enumerate(S.ABILITIES):
            col = i % 3
            row = (i // 3) * 2
            lbl = QLabel(ab["name"])
            lbl.setToolTip(ab["hint"])
            g.addWidget(lbl, row, col)
            sp = self._spin(ab["key"], self.char["abilities"][ab["key"]], 1, 30, self.ability_w)
            sp.setToolTip(ab["hint"])
            g.addWidget(sp, row + 1, col)

    def _build_combat_section(self):
        box = self._group("Бой и здоровье")
        g = QGridLayout(box)
        fields = [
            ("ОЗ макс", "hp_max", 0, 999),
            ("ОЗ текущ", "hp_current", -99, 999),
            ("ОЗ времен", "hp_temp", 0, 999),
            ("Защита (КЗ)", "armor_class", 0, 40),
            ("Скорость, м", "speed", 0, 60),
        ]
        for i, (label, key, lo, hi) in enumerate(fields):
            col = i % 3
            row = (i // 3) * 2
            g.addWidget(QLabel(label), row, col)
            g.addWidget(self._spin(key, self.char[key], lo, hi, self.widgets), row + 1, col)
        # Кубик хитов — строка
        r = (len(fields) // 3) * 2
        g.addWidget(QLabel("Кубик хитов"), r, 2)
        g.addWidget(self._line("hit_die", self.char["hit_die"]), r + 1, 2)

    def _build_tracks_section(self):
        box = self._group("Шкалы выживания")
        g = QGridLayout(box)
        for i, t in enumerate(S.SURVIVAL_TRACKS):
            lbl = QLabel(f'{t["name"]} (0–{t["max"]})')
            lbl.setToolTip(t["hint"])
            g.addWidget(lbl, i, 0)
            g.addWidget(self._spin(t["key"], self.char["tracks"][t["key"]], 0, t["max"], self.track_w), i, 1)
            hint = QLabel(t["hint"])
            hint.setStyleSheet("color:#888;")
            g.addWidget(hint, i, 2)

    def _build_saves_section(self):
        box = self._group("Спасброски (отметь владение)")
        g = QGridLayout(box)
        for i, key in enumerate(S.SAVE_ABILITIES):
            cb = QCheckBox(S.ABILITY_NAME[key])
            cb.setChecked(self.char["save_prof"][key])
            cb.stateChanged.connect(self.schedule_refresh)
            self.save_w[key] = cb
            g.addWidget(cb, i % 3, i // 3)

    def _build_skills_section(self):
        box = self._group("Навыки (отметь владение)")
        g = QGridLayout(box)
        half = (len(S.SKILLS) + 1) // 2
        for i, sk in enumerate(S.SKILLS):
            cb = QCheckBox(f'{sk["name"]}  ({S.ABILITY_NAME[sk["ability"]]})')
            cb.setChecked(self.char["skill_prof"][sk["key"]])
            cb.stateChanged.connect(self.schedule_refresh)
            self.skill_w[sk["key"]] = cb
            col = 0 if i < half else 1
            row = i if i < half else i - half
            g.addWidget(cb, row, col)

    def _build_weapons_section(self):
        box = self._group("Оружие (до 3)")
        g = QGridLayout(box)
        g.addWidget(QLabel("Название"), 0, 0)
        g.addWidget(QLabel("Попадание"), 0, 1)
        g.addWidget(QLabel("Урон"), 0, 2)
        for i, wp in enumerate(self.char["weapons"]):
            name = QLineEdit(wp.get("name", ""))
            attack = QLineEdit(wp.get("attack", ""))
            damage = QLineEdit(wp.get("damage", ""))
            for w in (name, attack, damage):
                w.textChanged.connect(self.schedule_refresh)
            self.weapon_w.append((name, attack, damage))
            g.addWidget(name, i + 1, 0)
            g.addWidget(attack, i + 1, 1)
            g.addWidget(damage, i + 1, 2)

    def _build_gear_section(self):
        box = self._group("Снаряжение")
        g = QGridLayout(box)
        g.addWidget(QLabel("Броня"), 0, 0)
        g.addWidget(self._line("armor", self.char["armor"]), 0, 1, 1, 3)
        for i, c in enumerate(S.CONSUMABLES):
            g.addWidget(QLabel(c["name"]), 1 + i % 3, (i // 3) * 2)
            g.addWidget(self._spin(c["key"], self.char["consumables"][c["key"]], 0, 999, self.cons_w),
                        1 + i % 3, (i // 3) * 2 + 1)

    def _text_block(self, key, value, height=90):
        w = QPlainTextEdit(value)
        w.setMaximumHeight(height)
        w.textChanged.connect(self.schedule_refresh)
        self.widgets[key] = w
        return w

    def _build_inventory_section(self):
        box = self._group("Инвентарь")
        v = QVBoxLayout(box)
        v.addWidget(self._text_block("inventory", self.char["inventory"]))

    def _build_about_section(self):
        box = self._group("О персонаже")
        g = QGridLayout(box)
        g.addWidget(QLabel("Рост"), 0, 0)
        g.addWidget(self._line("height", self.char["height"]), 0, 1)
        g.addWidget(QLabel("Возраст"), 0, 2)
        g.addWidget(self._line("age", self.char["age"]), 0, 3)
        g.addWidget(QLabel("Вес"), 0, 4)
        g.addWidget(self._line("weight", self.char["weight"]), 0, 5)
        g.addWidget(QLabel("Характер"), 1, 0)
        g.addWidget(self._line("personality", self.char["personality"]), 1, 1, 1, 5)
        g.addWidget(QLabel("Особая черта"), 2, 0)
        g.addWidget(self._text_block("special_trait", self.char["special_trait"], 60), 2, 1, 1, 5)
        g.addWidget(QLabel("Предыстория"), 3, 0)
        g.addWidget(self._text_block("backstory", self.char["backstory"], 80), 3, 1, 1, 5)

    def _build_text_sections(self):
        for title, key in [
            ("Перки / мутации", "perks"),
            ("Репутация с фракциями", "reputation"),
            ("Заметки / связи", "notes"),
        ]:
            box = self._group(title)
            v = QVBoxLayout(box)
            v.addWidget(self._text_block(key, self.char[key]))

    # --- Сбор/раздача данных ---------------------------------------------
    def collect(self):
        c = self.char
        c["char_name"] = self.widgets["char_name"].text()
        c["player_name"] = self.widgets["player_name"].text()
        c["archetype"] = self.widgets["archetype"].currentText()
        c["origin"] = self.widgets["origin"].text()
        c["depth_level"] = self.widgets["depth_level"].value()
        c["prof_bonus"] = self.widgets["prof_bonus"].value()
        c["hit_die"] = self.widgets["hit_die"].text()
        for key in ("hp_max", "hp_current", "hp_temp", "armor_class", "speed"):
            c[key] = self.widgets[key].value()
        c["armor"] = self.widgets["armor"].text()
        for key in ("height", "age", "weight", "personality"):
            c[key] = self.widgets[key].text()
        for key in ("perks", "reputation", "notes", "inventory", "special_trait", "backstory"):
            c[key] = self.widgets[key].toPlainText()

        for key, w in self.ability_w.items():
            c["abilities"][key] = w.value()
        for key, w in self.save_w.items():
            c["save_prof"][key] = w.isChecked()
        for key, w in self.skill_w.items():
            c["skill_prof"][key] = w.isChecked()
        for key, w in self.track_w.items():
            c["tracks"][key] = w.value()
        for key, w in self.cons_w.items():
            c["consumables"][key] = w.value()
        c["weapons"] = [
            {"name": n.text(), "attack": a.text(), "damage": d.text()}
            for (n, a, d) in self.weapon_w
        ]
        return c

    def populate(self):
        """Заполнить все виджеты из self.char (после открытия файла)."""
        c = self.char
        self.widgets["char_name"].setText(c["char_name"])
        self.widgets["player_name"].setText(c["player_name"])
        self.widgets["archetype"].setCurrentText(c["archetype"])
        self.widgets["origin"].setText(c["origin"])
        self.widgets["depth_level"].setValue(int(c["depth_level"]))
        self.widgets["prof_bonus"].setValue(int(c["prof_bonus"]))
        self.widgets["hit_die"].setText(c["hit_die"])
        for key in ("hp_max", "hp_current", "hp_temp", "armor_class", "speed"):
            self.widgets[key].setValue(int(c[key]))
        self.widgets["armor"].setText(c["armor"])
        for key in ("height", "age", "weight", "personality"):
            self.widgets[key].setText(c.get(key, ""))
        for key in ("perks", "reputation", "notes", "inventory", "special_trait", "backstory"):
            self.widgets[key].setPlainText(c.get(key, ""))
        for key, w in self.ability_w.items():
            w.setValue(int(c["abilities"][key]))
        for key, w in self.save_w.items():
            w.setChecked(bool(c["save_prof"][key]))
        for key, w in self.skill_w.items():
            w.setChecked(bool(c["skill_prof"][key]))
        for key, w in self.track_w.items():
            w.setValue(int(c["tracks"][key]))
        for key, w in self.cons_w.items():
            w.setValue(int(c["consumables"][key]))
        for i, (n, a, d) in enumerate(self.weapon_w):
            wp = c["weapons"][i] if i < len(c["weapons"]) else {"name": "", "attack": "", "damage": ""}
            n.setText(wp.get("name", ""))
            a.setText(wp.get("attack", ""))
            d.setText(wp.get("damage", ""))

    # --- Предпросмотр -----------------------------------------------------
    def schedule_refresh(self, *args):
        self._refresh_timer.start(250)

    def update_preview(self):
        char = self.collect()
        img = R.render(char)
        qimg = ImageQt(img)
        pix = QPixmap.fromImage(QImage(qimg))
        # масштаб под ширину панели
        target_w = max(400, self.preview.width() - 8)
        pix = pix.scaledToWidth(target_w, Qt.SmoothTransformation)
        self.preview.setPixmap(pix)

    # --- Кнопки -----------------------------------------------------------
    def on_new(self):
        if QMessageBox.question(self, "Новый лист",
                                "Создать новый лист? Несохранённые изменения пропадут.") \
                != QMessageBox.Yes:
            return
        self.char = M.new_character()
        self.current_path = None
        self.populate()
        self.update_preview()

    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть лист", "", "Лист персонажа (*.json)")
        if not path:
            return
        try:
            self.char = M.load_from_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл:\n{e}")
            return
        self.current_path = path
        self.populate()
        self.update_preview()

    def on_save(self):
        self.collect()
        default = (self.char.get("char_name") or "персонаж") + ".json"
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить лист", default,
                                              "Лист персонажа (*.json)")
        if not path:
            return
        try:
            M.save_to_file(self.char, path)
            self.current_path = path
            QMessageBox.information(self, "Готово", "Лист сохранён.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")

    def on_export(self):
        char = self.collect()
        default = (char.get("char_name") or "персонаж") + ".png"
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт картинки", default,
                                              "Изображение PNG (*.png)")
        if not path:
            return
        try:
            R.render(char).save(path)
            QMessageBox.information(self, "Готово", f"Картинка сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить картинку:\n{e}")

    def on_dice(self):
        # Окно броска создаём один раз и переоткрываем (не модальное).
        if self.dice_dialog is None:
            self.dice_dialog = D.DiceDialog(self)
        self.dice_dialog.show()
        self.dice_dialog.raise_()
        self.dice_dialog.activateWindow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_refresh()


APP_QSS = """
QWidget { background: #121412; color: #dce0d6; font-size: 13px; }
QScrollArea { border: none; background: #121412; }
QGroupBox {
    border: 1px solid #3c423a; border-radius: 8px; margin-top: 16px;
    padding: 10px 6px 6px 6px; font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 2px 8px; color: #aad640;
}
QLabel { background: transparent; }
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
    background: #1c1f1c; color: #dce0d6; border: 1px solid #3c423a;
    border-radius: 6px; padding: 4px 6px; selection-background-color: #6c8c26;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #aad640;
}
QComboBox QAbstractItemView {
    background: #1c1f1c; color: #dce0d6; selection-background-color: #6c8c26;
}
QCheckBox { background: transparent; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 2px solid #6a6f64;
    border-radius: 4px; background: #1c1f1c;
}
QCheckBox::indicator:checked { background: #aad640; border-color: #aad640; }
QPushButton {
    background: #1c1f1c; border: 2px solid #3c423a; border-radius: 8px;
    padding: 8px 12px; color: #dce0d6; font-weight: bold;
}
QPushButton:hover { border-color: #aad640; }
QPushButton:pressed { background: #2a2f28; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #3c423a; border-radius: 6px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #6c8c26; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QMessageBox { background: #1c1f1c; }
"""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))   # гарантированно с кириллицей
    app.setStyleSheet(APP_QSS)
    win = SheetApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
