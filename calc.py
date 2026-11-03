# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — расчётный модуль.

Формулы по ГОСТ 12730.5-2018 (метод воздухопроницаемости).
Все числа — Decimal для точности лабораторных вычислений.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Объёмы камер прибора №3407 (из шаблона Excel лаборатории)
VOLUMES = [
    Decimal('1720'),  # камера 1
    Decimal('1620'),  # камера 2
    Decimal('1632'),  # камера 3
    Decimal('1620'),  # камера 4
    Decimal('1620'),  # камера 5
    Decimal('1638'),  # камера 6
]

# Начальное вакуумметрическое давление, МПа
DEFAULT_PRESSURE = Decimal('0.064')

# Таблица определения марки W по mc (ГОСТ 12730.5-2018, из методики)
W_RANGES = [
    (Decimal('3.1'),  Decimal('4.5'),   'W2'),
    (Decimal('4.6'),  Decimal('6.5'),   'W4'),
    (Decimal('6.6'),  Decimal('9.4'),   'W6'),
    (Decimal('9.5'),  Decimal('13.7'),  'W8'),
    (Decimal('13.8'), Decimal('19.6'),  'W10'),
    (Decimal('19.7'), Decimal('29.0'),  'W12'),
    (Decimal('29.1'), Decimal('42.0'),  'W14'),
    (Decimal('42.1'), Decimal('60.9'),  'W16'),
    (Decimal('61.0'), Decimal('88.5'),  'W18'),
    (Decimal('88.6'), Decimal('130.2'), 'W20'),
]

VALID_W_GRADES = [f'W{i}' for i in range(2, 22, 2)]


def parse_positive(value: str, name: str = 'значение') -> Decimal:
    """Парсит строку в положительный Decimal."""
    try:
        v = Decimal(str(value).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{name}: введите положительное число')
    if not v.is_finite() or v <= 0:
        raise ValueError(f'{name}: должно быть больше нуля')
    return v


def normalize_w(value: str) -> str:
    """Нормализует введённую марку W → 'W2'...'W20'."""
    raw = str(value).strip().upper().replace(' ', '').replace('В', 'W')
    if raw.startswith('W'):
        raw = raw[1:]
    if raw not in {str(i) for i in range(2, 22, 2)}:
        raise ValueError(f'Марка W должна быть одной из: {", ".join(VALID_W_GRADES)}')
    return 'W' + raw


def classify_w(m: Decimal) -> str:
    """Определяет марку W по сопротивлению воздухопроницанию m.

    Округляет до 0.1 с/см³ (как в таблице ГОСТ).
    """
    x = m.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    if x < Decimal('3.1'):
        return '<W2'
    if x > Decimal('130.2'):
        return '>W20'
    for lo, hi, grade in W_RANGES:
        if lo <= x <= hi:
            return grade
    # Попадание между интервалами таблицы — теоретически невозможно
    raise ValueError(f'Показатель {x} не входит в табличные интервалы')


def w_to_int(grade: str) -> int | None:
    """'W8' → 8, '<W2' → None, '>W20' → None."""
    if grade.startswith(('<', '>')):
        return None
    return int(grade[1:])


def compare_w(actual: str, declared: str) -> bool:
    """Фактическая W ≥ заявленной → True (соответствует)."""
    declared = normalize_w(declared)
    if actual.startswith('<'):
        return False
    if actual.startswith('>'):
        return True
    return int(actual[1:]) >= int(declared[1:])


def compute_specimen(time_sec: Decimal, volume: Decimal,
                     pressure: Decimal = DEFAULT_PRESSURE) -> dict:
    """Рассчитывает один образец.

    Возвращает dict с ключами: volume, pressure, M, t, a, m, W
    """
    M = volume * 10 * pressure       # Vвозд, см³
    a = M / time_sec                  # воздухопроницаемость, см³/с
    m = time_sec / M                  # сопротивление, с/см³
    W = classify_w(m)

    return {
        'volume': volume,
        'pressure': pressure,
        'M': M,
        't': time_sec,
        'a': a,
        'm': m,
        'W': W,
    }


def compute_series(times: list[Decimal],
                   volumes: list[Decimal] = None,
                   pressure: Decimal = DEFAULT_PRESSURE,
                   declared: list[str] = None) -> dict:
    """Рассчитывает серию из 6 образцов.

    Args:
        times: 6 значений времени t в секундах
        volumes: 6 объёмов камер (по умолчанию — прибор №3407)
        pressure: начальное давление, МПа
        declared: 6 заявленных марок W (опционально)

    Returns:
        dict с ключами:
        - specimens: list из 6 dict (результат compute_specimen + declared_W, conforms)
        - sorted_indices: индексы вариационного ряда по m (по возрастанию)
    """
    if volumes is None:
        volumes = VOLUMES
    if len(times) != 6 or len(volumes) != 6:
        raise ValueError('Требуется ровно 6 образцов')
    if declared is not None:
        if len(declared) != 6:
            raise ValueError('Требуется 6 заявленных марок W')
        declared = [normalize_w(w) for w in declared]

    specimens = []
    for i, (t, v) in enumerate(zip(times, volumes)):
        spec = compute_specimen(t, v, pressure)
        spec['sample'] = i + 1
        spec['chamber'] = i + 1
        if declared:
            spec['declared_W'] = declared[i]
            spec['conforms'] = compare_w(spec['W'], declared[i])
        specimens.append(spec)

    # Вариационный ряд по m (по возрастанию)
    sorted_specs = sorted(range(6), key=lambda i: specimens[i]['m'])

    return {
        'specimens': specimens,
        'sorted_indices': sorted_specs,
    }
