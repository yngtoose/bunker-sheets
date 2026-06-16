# -*- coding: utf-8 -*-
"""
Модель данных персонажа + сохранение/загрузка в JSON.

Character — это просто словарь полей. Мы не хардкодим список полей в нескольких
местах: характеристики/шкалы берутся из system.py. Так правки правил
в system.py не ломают модель.
"""

import json
import system as S


def new_character():
    """Пустой персонаж со значениями по умолчанию."""
    char = {
        # Шапка
        "char_name": "",
        "player_name": "",
        "archetype": S.ARCHETYPES[0],
        "origin": "",          # происхождение / откуда родом
        "depth_level": 1,      # уровень погружения (аналог уровня)
        "prof_bonus": 2,       # бонус мастерства

        # Характеристики (значения 1..30)
        "abilities": {k: 10 for k in S.ABILITY_KEYS},

        # Спасброски: владение по характеристикам
        "save_prof": {k: False for k in S.ABILITY_KEYS},

        # Боевые производные (ОЗ макс вычисляется: Телосложение × 5)
        "hp_current": 10,
        "hp_temp": 0,
        "armor_class": 10,
        "speed": 9,            # в метрах (3 клетки)
        "hit_die": "к8",

        # Шкалы выживания (текущее значение)
        "tracks": {t["key"]: (0 if t["danger"] == "high" else t["max"])
                   for t in S.SURVIVAL_TRACKS},

        # Снаряжение
        "weapons": [           # список оружия: {name, caliber, attack, damage}
            {"name": "", "caliber": "", "attack": "", "damage": ""},
            {"name": "", "caliber": "", "attack": "", "damage": ""},
            {"name": "", "caliber": "", "attack": "", "damage": ""},
        ],
        "armor": "",
        "consumables": {c["key"]: 0 for c in S.CONSUMABLES},
        "ammo": {c["key"]: 0 for c in S.CALIBERS},   # патроны по калибрам
        "inventory": "",       # инвентарь, свободный текст

        # О персонаже
        "height": "",          # рост
        "age": "",             # возраст
        "weight": "",          # вес
        "personality": "",     # характер
        "backstory": "",       # предыстория
        "special_trait": "",   # особая черта (заболевание, псих. травма,
                               #               необычная внешность, раса)

        # Текстовые блоки
        "perks": "",           # перки / мутации / особенности архетипа
        "reputation": "",      # репутация с фракциями
        "notes": "",           # заметки / связи
    }
    return char


def init(char):
    """Инициатива персонажа = модификатор ЛОВКОСТИ."""
    return S.ability_modifier(char["abilities"].get("dex", 10))


def max_hp(char):
    """Максимум ОЗ = Телосложение × 5 (характеристика wis)."""
    try:
        return int(char["abilities"].get("wis", 10)) * 5
    except (TypeError, ValueError):
        return 50


def ability_mod(char, key):
    return S.ability_modifier(char["abilities"].get(key, 10))


def save_bonus(char, key):
    """Бонус спасброска = мод характеристики (+ бонус мастерства если владение)."""
    bonus = ability_mod(char, key)
    if char["save_prof"].get(key):
        bonus += int(char.get("prof_bonus", 2))
    return bonus


def passive_perception(char):
    """Пассивная внимательность = 10 + модификатор Интеллекта."""
    return 10 + ability_mod(char, "int")


# --- Сохранение / загрузка ------------------------------------------------

def save_to_file(char, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(char, f, ensure_ascii=False, indent=2)


def load_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Сливаем с дефолтом, чтобы старые файлы не падали при новых полях.
    base = new_character()
    base.update({k: v for k, v in data.items() if k in base})
    # вложенные словари тоже аккуратно сливаем
    for nested in ("abilities", "save_prof", "tracks", "consumables", "ammo"):
        if isinstance(data.get(nested), dict):
            base[nested].update(data[nested])
    if isinstance(data.get("weapons"), list):
        base["weapons"] = data["weapons"]
    return base
