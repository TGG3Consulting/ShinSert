# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — графический интерфейс (Tkinter).

Два режима вывода: Excel (по шаблону) и PDF (по бланку).
Шесть образцов, индивидуальная заявленная W для каждого.
"""
import math
import traceback
from datetime import datetime
from pathlib import Path
from decimal import Decimal
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from calc import (
    VOLUMES, DEFAULT_PRESSURE, VALID_W_GRADES,
    parse_positive, normalize_w, compute_series, compare_w,
)
from excel_export import export_excel
from pdf_export import export_pdf

# Пути к ассетам (рядом с исполняемым файлом)
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
TEMPLATE_XLSX = ASSETS / 'template.xlsx'
BACKGROUND_PDF = ASSETS / 'report_background.pdf'
SIGNATURE_PNG = ASSETS / 'demo_signature.png'
STAMP_PNG = ASSETS / 'demo_stamp.png'

APP_TITLE = 'ՇINCERTIFICATE | Водонепроницаемость бетона | №3407'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry('1100x720')
        self.minsize(1050, 680)
        self.configure(bg='#f2f5f9')

        self._apply_styles()
        self._build_header()
        self._build_info_card()
        self._build_meta()
        self._build_table()
        self._build_bottom()

    # ─── Стили ───────────────────────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use('clam')
        except tk.TclError:
            pass
        s.configure('TFrame', background='#f2f5f9')
        s.configure('Card.TFrame', background='white')
        s.configure('TLabel', background='#f2f5f9', foreground='#1e293b',
                     font=('Segoe UI', 10))
        s.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'),
                     foreground='#12345a', background='#f2f5f9')
        s.configure('CardTitle.TLabel', font=('Segoe UI', 11, 'bold'),
                     background='white', foreground='#12345a')

    # ─── Компоненты ──────────────────────────────────────────────

    def _build_header(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill='both', expand=True)
        self._outer = outer

        ttk.Label(
            outer,
            text='Экспертиза водонепроницаемости бетона',
            style='Title.TLabel',
        ).pack(anchor='w')
        ttk.Label(
            outer,
            text='Автоматизированный расчёт серии из 6 образцов · '
                 'лаборатория ՇINCERTIFICATE',
        ).pack(anchor='w', pady=(2, 12))

    def _build_info_card(self):
        card = ttk.Frame(self._outer, style='Card.TFrame', padding=14)
        card.pack(fill='x', pady=(0, 12))

        ttk.Label(card, text='Справка по испытанию',
                  style='CardTitle.TLabel').pack(anchor='w')
        ttk.Label(
            card,
            text='ГОСТ 12730.5—2018 · Метод по воздухопроницаемости · '
                 '6 бетонных кубов 150×150×150 мм · прибор №3407',
        ).pack(anchor='w', pady=(5, 2))
        ttk.Label(
            card,
            text='Начальное давление J = 0,064 МПа. '
                 'Введите время восстановления вакуума t (секунды) '
                 'и выберите заявленную W для каждого образца.',
        ).pack(anchor='w')

    def _build_meta(self):
        meta = ttk.Frame(self._outer)
        meta.pack(fill='x', pady=(0, 10))

        ttk.Label(meta, text='Заказчик / объект:').pack(side='left')
        self.meta_entry = ttk.Entry(meta, width=50)
        self.meta_entry.pack(side='left', padx=8)

        ttk.Label(meta, text='Дата:').pack(side='left', padx=(12, 4))
        self.date_entry = ttk.Entry(meta, width=12)
        self.date_entry.insert(0, datetime.now().strftime('%d.%m.%Y'))
        self.date_entry.pack(side='left')

        ttk.Label(meta, text='Тип:').pack(side='left', padx=(12, 4))
        self.shape_var = tk.StringVar(value='cube')
        ttk.Radiobutton(meta, text='Куб', variable=self.shape_var,
                        value='cube').pack(side='left')
        ttk.Radiobutton(meta, text='Цилиндр', variable=self.shape_var,
                        value='cylinder').pack(side='left')

    def _build_table(self):
        frame = ttk.LabelFrame(
            self._outer,
            text=' Ввод данных · 6 образцов ',
            padding=10,
        )
        frame.pack(fill='both', expand=True, pady=(0, 8))

        headers = ['№', 'Камера', 'V, см³', 'Заявленная W',
                   'Время t, сек', 'Расчётная W', 'Результат']
        for col, text in enumerate(headers):
            lbl = tk.Label(frame, text=text, font=('Segoe UI', 9, 'bold'),
                           bg='#dce7f3', fg='#12345a', bd=1, relief='solid',
                           height=2, width=14)
            lbl.grid(row=0, column=col, sticky='nsew')

        self.time_entries = []
        self.declared_combos = []
        self.calc_w_labels = []
        self.verdict_labels = []

        for i in range(6):
            row = i + 1
            vol = VOLUMES[i]

            # №
            tk.Label(frame, text=str(i + 1), font=('Segoe UI', 10),
                     bg='white', bd=1, relief='solid').grid(
                row=row, column=0, sticky='nsew')
            # Камера
            tk.Label(frame, text=str(i + 1), font=('Segoe UI', 10),
                     bg='white', bd=1, relief='solid').grid(
                row=row, column=1, sticky='nsew')
            # Объём
            tk.Label(frame, text=str(vol), font=('Segoe UI', 10),
                     bg='white', bd=1, relief='solid').grid(
                row=row, column=2, sticky='nsew')

            # Заявленная W (комбобокс)
            dw = tk.StringVar(value='')
            combo = ttk.Combobox(frame, textvariable=dw,
                                 values=VALID_W_GRADES, width=10,
                                 state='readonly')
            combo.grid(row=row, column=3, padx=4, pady=4, sticky='nsew')
            self.declared_combos.append(dw)

            # Время t (ввод)
            ent = ttk.Entry(frame, font=('Segoe UI', 10),
                            justify='center', width=14)
            ent.grid(row=row, column=4, padx=4, pady=4, sticky='nsew')
            self.time_entries.append(ent)

            # Расчётная W (авто)
            w_var = tk.StringVar(value='—')
            tk.Label(frame, textvariable=w_var, font=('Segoe UI', 11, 'bold'),
                     bg='white', bd=1, relief='solid').grid(
                row=row, column=5, sticky='nsew')
            self.calc_w_labels.append(w_var)

            # Результат (авто)
            v_var = tk.StringVar(value='—')
            tk.Label(frame, textvariable=v_var, font=('Segoe UI', 10),
                     bg='white', bd=1, relief='solid').grid(
                row=row, column=6, sticky='nsew')
            self.verdict_labels.append(v_var)

        for c in range(7):
            frame.grid_columnconfigure(c, weight=1)

    def _build_bottom(self):
        bottom = ttk.Frame(self._outer)
        bottom.pack(fill='x', pady=(4, 0))

        self.status_label = ttk.Label(
            bottom,
            text='Заполните все поля и нажмите одну из кнопок.',
            font=('Segoe UI', 10),
        )
        self.status_label.pack(side='left', fill='x', expand=True)

        ttk.Button(
            bottom, text='Выгрузить Excel',
            command=self._export_excel,
        ).pack(side='right', padx=(8, 0))

        ttk.Button(
            bottom, text='Заключение — PDF',
            command=self._export_pdf,
        ).pack(side='right')

    # ─── Логика ──────────────────────────────────────────────────

    def _collect(self) -> dict:
        """Собирает данные из формы и считает серию."""
        times = []
        declared = []
        for i in range(6):
            t_text = self.time_entries[i].get().strip()
            if not t_text:
                raise ValueError(f'Образец {i+1}: не заполнено время t')
            times.append(parse_positive(t_text, f'Образец {i+1}, время t'))

            dw = self.declared_combos[i].get()
            if not dw:
                raise ValueError(f'Образец {i+1}: не выбрана заявленная W')
            declared.append(dw)

        series = compute_series(times, declared=declared)

        # Обновляем GUI
        for i, spec in enumerate(series['specimens']):
            self.calc_w_labels[i].set(spec['W'])
            if spec['conforms']:
                self.verdict_labels[i].set('✓ Соответствует')
            else:
                self.verdict_labels[i].set('✗ Не соответствует')

        return series

    def _get_meta(self) -> dict:
        return {
            'customer': self.meta_entry.get().strip(),
            'test_date': self.date_entry.get().strip(),
        }

    def _export_excel(self):
        try:
            series = self._collect()
            path = filedialog.asksaveasfilename(
                title='Сохранить Excel',
                defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx')],
                initialfile=f'Протокол_W_{datetime.now():%Y%m%d_%H%M%S}.xlsx',
            )
            if not path:
                return
            export_excel(
                TEMPLATE_XLSX, Path(path), series,
                meta=self._get_meta(),
                shape=self.shape_var.get(),
            )
            self.status_label.configure(text=f'Excel сохранён: {path}')
            messagebox.showinfo('Готово', f'Excel сохранён:\n{path}')
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))

    def _export_pdf(self):
        try:
            series = self._collect()
            path = filedialog.asksaveasfilename(
                title='Сохранить PDF',
                defaultextension='.pdf',
                filetypes=[('PDF', '*.pdf')],
                initialfile=f'Протокол_W_{datetime.now():%Y%m%d_%H%M%S}.pdf',
            )
            if not path:
                return
            export_pdf(
                BACKGROUND_PDF, Path(path), series,
                meta=self._get_meta(),
                shape=self.shape_var.get(),
                signature_path=SIGNATURE_PNG,
                stamp_path=STAMP_PNG,
                demo_mark=True,
            )
            self.status_label.configure(text=f'PDF сохранён: {path}')
            messagebox.showinfo(
                'Готово — DEMO',
                f'PDF сохранён:\n{path}\n\n'
                'Документ помечен ОБРАЗЕЦ / DEMO.',
            )
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))
