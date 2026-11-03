# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — экспорт заполненного Excel.

Патчит оригинальный армянский шаблон (Ջრաانтафанцелиутян орошум.xlsx),
сохраняя все рисунки, layout и оформление. Заполняет только ячейки данных.
"""
import re
import zipfile
from pathlib import Path

from lxml import etree

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
M = '{' + NS + '}'


def _cell(root, addr: str):
    """Находит или создаёт ячейку по адресу (например 'D23')."""
    found = root.xpath(
        './/m:sheetData/m:row/m:c[@r=$addr]',
        namespaces={'m': NS}, addr=addr,
    )
    if found:
        return found[0]

    rownum = int(re.search(r'\d+', addr).group())
    sheet = root.find(M + 'sheetData')

    row = next(
        (r for r in sheet if r.tag == M + 'row' and int(r.get('r')) == rownum),
        None,
    )
    if row is None:
        row = etree.Element(M + 'row', r=str(rownum))
        pos = next(
            (i for i, r in enumerate(sheet) if int(r.get('r')) > rownum),
            len(sheet),
        )
        sheet.insert(pos, row)

    c = etree.Element(M + 'c', r=addr)
    col_val = lambda x: sum(
        (ord(k) - 64) * 26 ** i
        for i, k in enumerate(re.match('[A-Z]+', x).group()[::-1])
    )
    pos = next(
        (i for i, x in enumerate(row)
         if x.tag == M + 'c' and col_val(x.get('r')) > col_val(addr)),
        len(row),
    )
    row.insert(pos, c)
    return c


def _write(root, addr: str, value, formula: bool = False):
    """Записывает значение или формулу в ячейку."""
    c = _cell(root, addr)
    for ch in list(c):
        if ch.tag in (M + 'v', M + 'f', M + 'is'):
            c.remove(ch)

    if formula:
        c.attrib.pop('t', None)
        etree.SubElement(c, M + 'f').text = value.lstrip('=')
    elif isinstance(value, (int, float)):
        c.attrib.pop('t', None)
        etree.SubElement(c, M + 'v').text = str(value)
    else:
        from decimal import Decimal
        if isinstance(value, Decimal):
            c.attrib.pop('t', None)
            etree.SubElement(c, M + 'v').text = str(value)
        else:
            c.set('t', 'inlineStr')
            etree.SubElement(etree.SubElement(c, M + 'is'), M + 't').text = str(value)


def export_excel(template_path: Path, output_path: Path, series: dict,
                 meta: dict = None, shape: str = 'cube'):
    """Заполняет шаблон Excel результатами серии.

    Args:
        template_path: путь к исходному .xlsx шаблону
        output_path: куда сохранить заполненный файл
        series: результат calc.compute_series()
        meta: {customer, object, producer, design_class, test_date, ...}
        shape: 'cube' или 'cylinder'
    """
    meta = meta or {}
    specimens = series['specimens']

    if not template_path.exists():
        raise FileNotFoundError(f'Шаблон не найден: {template_path}')

    with zipfile.ZipFile(template_path) as z:
        root = etree.fromstring(z.read('xl/worksheets/sheet1.xml'))

        # Разбиваем merge D23:D28, чтобы каждый образец имел свою заявленную W
        merges = root.find(M + 'mergeCells')
        if merges is not None:
            for merge in list(merges):
                if merge.get('ref') == 'D23:D28':
                    merges.remove(merge)
                    merges.set('count', str(len(merges)))
                    break

        # Заполняем строки 23–28 (6 образцов)
        for i, spec in enumerate(specimens, 23):
            size_text = '15x15x15' if shape == 'cube' else 'Ø15 × 10'
            _write(root, f'I{i}', size_text)
            _write(root, f'J{i}', spec['pressure'])
            _write(root, f'K{i}', i - 22)  # номер камеры
            _write(root, f'M{i}', f'L{i}*10*J{i}', formula=True)
            _write(root, f'N{i}', spec['t'])
            _write(root, f'O{i}', f'IFERROR(M{i}/N{i},"")', formula=True)
            _write(root, f'P{i}', f'IFERROR(N{i}/M{i},"")', formula=True)

            # Класс бетона / заявленная W
            class_text = meta.get('design_class', '').strip()
            declared = spec.get('declared_W', '')
            d_text = f'{class_text} / {declared}'.strip(' /')
            _write(root, f'D{i}', d_text)

            # Расчётная W + вердикт
            verdict = 'Այո' if spec.get('conforms') else 'Ոdelays'
            _write(root, f'Q{i}', f'{spec["W"]} — {verdict}')

        # Заголовок размеров
        _write(root, 'I20', (
            'Խoranaрdazev stuganimushneri chapsereh, sm'
            if shape == 'cube'
            else 'Cilindrazev stuganimushneri chapsereh, sm'
        ))

        # Мета-поля протокола
        fields = {
            'C16': 'customer', 'C17': 'object', 'C18': 'producer',
            'C23': 'sample_id', 'E23': 'receipt_date',
            'F23': 'production_date', 'G23': 'test_date',
        }
        for addr, key in fields.items():
            if meta.get(key):
                _write(root, addr, meta[key])

        # Сериализуем XML
        xml = etree.tostring(root, xml_declaration=True,
                             encoding='UTF-8', standalone=True)

        # Собираем новый xlsx, заменяя только sheet1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, 'w') as dest:
            for info in z.infolist():
                if info.filename == 'xl/worksheets/sheet1.xml':
                    dest.writestr(info, xml)
                else:
                    dest.writestr(info, z.read(info.filename))

    return output_path
