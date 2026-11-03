# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — генерация PDF протокола.

Рендерит данные поверх встроенного бланка report_background.pdf
через PyMuPDF. Не требует установленного Microsoft Office.
"""
from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF

from calc import compare_w


def _find_font(page) -> str:
    """Пытается подключить Sylfaen или Arial для армянского текста."""
    for candidate in (
        Path('C:/Windows/Fonts/sylfaen.ttf'),
        Path('C:/Windows/Fonts/arial.ttf'),
    ):
        if candidate.exists():
            try:
                page.insert_font(fontname='labfont', fontfile=str(candidate))
                return 'labfont'
            except Exception:
                continue
    return 'helv'


def _put(page, x: float, y: float, value: str, fontname: str,
         size: float = 7, max_width: float = None):
    """Печатает текст в указанных координатах PDF."""
    value = str(value)
    sz = size
    if max_width:
        while sz > 4.3 and fitz.get_text_length(value, fontname='helv', fontsize=sz) > max_width:
            sz -= 0.3
    page.insert_text(
        (x, y), value,
        fontname=fontname, fontsize=sz,
        color=(0, 0, 0), overlay=True,
    )


def export_pdf(background_path: Path, output_path: Path,
               series: dict, meta: dict = None, shape: str = 'cube',
               signature_path: Path = None, stamp_path: Path = None,
               demo_mark: bool = True):
    """Генерирует одностраничный PDF протокол.

    Args:
        background_path: report_background.pdf
        output_path: куда сохранить PDF
        series: результат calc.compute_series()
        meta: {customer, object, producer, ...}
        shape: 'cube' или 'cylinder'
        signature_path: путь к demo_signature.png
        stamp_path: путь к demo_stamp.png
        demo_mark: ставить ли метку ОБРАЗЕЦ / DEMO
    """
    meta = meta or {}
    specimens = series['specimens']

    if not background_path.exists():
        raise FileNotFoundError(f'Бланк не найден: {background_path}')

    doc = fitz.open(background_path)
    if len(doc) != 1:
        doc.close()
        raise RuntimeError('Бланк повреждён: ожидается ровно 1 страница')

    page = doc[0]
    fontname = _find_font(page)

    # --- Данные образцов (строки таблицы) ---
    # Координаты откалиброваны по оригинальному армянскому бланку
    for idx, spec in enumerate(specimens):
        y = 428.1 + 11.55 * idx

        _put(page, 174, y, spec.get('declared_W', ''), fontname, 6.2)
        _put(page, 395, y, '15x15x15' if shape == 'cube' else 'D15x10', fontname, 5.2)
        _put(page, 431, y, str(Decimal(str(spec['pressure']))), fontname, 6.2)
        _put(page, 513, y, str(int(spec['M'])), fontname, 6.2)
        _put(page, 543, y, format(spec['t'], 'f'), fontname, 6.2)
        _put(page, 583, y, f"{spec['a']:.3f}", fontname, 6.2)
        _put(page, 625, y, f"{spec['m']:.1f}", fontname, 6.2)

        verdict = 'OK' if spec.get('conforms') else 'NO'
        _put(page, 660, y, f"{spec['W']} {verdict}", fontname, 5.5)

    # --- Мета-поля ---
    for key, y in [('customer', 241.0), ('object', 253.6), ('producer', 266.1)]:
        if meta.get(key):
            _put(page, 125, y, meta[key][:68], fontname, 7, max_width=480)

    # --- Подпись и печать (DEMO) ---
    if signature_path and signature_path.exists():
        page.insert_image(
            fitz.Rect(451, 514, 540, 543),
            filename=str(signature_path),
            keep_proportion=True, overlay=True,
        )
    if stamp_path and stamp_path.exists():
        page.insert_image(
            fitz.Rect(552, 506, 626, 562),
            filename=str(stamp_path),
            keep_proportion=True, overlay=True,
        )

    # --- Метка DEMO ---
    if demo_mark:
        page.insert_text(
            (225, 595), 'ОБРАЗЕЦ / DEMO',
            fontsize=14, fontname='helv',
            color=(0.7, 0.1, 0.1), overlay=True,
        )

    # --- Сохранение ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.set_metadata({'title': 'SHINCERTIFICATE — Протокол водонепроницаемости'})
    doc.save(str(output_path), garbage=3, deflate=True)
    doc.close()

    return output_path
