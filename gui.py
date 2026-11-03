# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — GUI платформа.

Экраны:
1. Логин
2. Главная (каталог экспертиз + реестр)
3. Экспертиза водонепроницаемости (W-3407)
"""
from datetime import datetime
from pathlib import Path
from decimal import Decimal
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from calc import (
    VOLUMES, VALID_W_GRADES,
    parse_positive, compute_series,
)
from excel_export import export_excel
from pdf_export import export_pdf
from db import (
    get_connection, init_db, authenticate,
    get_expertise_tree, get_type_path,
    create_expertise, save_expertise_data, confirm_expertise,
    get_expertise, list_expertises,
)

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
TEMPLATE_XLSX = ASSETS / 'template.xlsx'
BACKGROUND_PDF = ASSETS / 'report_background.pdf'
SIGNATURE_PNG = ASSETS / 'demo_signature.png'
STAMP_PNG = ASSETS / 'demo_stamp.png'

BG = '#f2f5f9'
NAVY = '#12345a'
WHITE = 'white'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ՇINCERTIFICATE · Лабораторная платформа')
        self.geometry('1200x780')
        self.minsize(1050, 700)
        self.configure(bg=BG)

        self.conn = get_connection()
        init_db(self.conn)

        self.current_user = None

        self._apply_styles()
        self._container = ttk.Frame(self)
        self._container.pack(fill='both', expand=True)

        self._show_login()

    def _apply_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use('clam')
        except tk.TclError:
            pass
        s.configure('TFrame', background=BG)
        s.configure('Card.TFrame', background=WHITE)
        s.configure('TLabel', background=BG, foreground='#1e293b', font=('Segoe UI', 10))
        s.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'), foreground=NAVY, background=BG)
        s.configure('Subtitle.TLabel', font=('Segoe UI', 12), foreground='#475569', background=BG)
        s.configure('CardTitle.TLabel', font=('Segoe UI', 11, 'bold'), background=WHITE, foreground=NAVY)
        s.configure('Nav.TButton', font=('Segoe UI', 10))
        s.configure('Accent.TButton', font=('Segoe UI', 11, 'bold'), padding=(16, 8))
        s.configure('Danger.TButton', font=('Segoe UI', 11, 'bold'), padding=(16, 8))
        s.configure('Treeview', font=('Segoe UI', 10), rowheight=28,
                     background=WHITE, fieldbackground=WHITE)
        s.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'),
                     background='#dce7f3', foreground=NAVY)

    def _clear(self):
        for w in self._container.winfo_children():
            w.destroy()

    # ═══════════════════════════════════════════════════════════════
    #  ЭКРАН 1: ЛОГИН
    # ═══════════════════════════════════════════════════════════════

    def _show_login(self):
        self._clear()
        frame = ttk.Frame(self._container, padding=40)
        frame.place(relx=0.5, rely=0.4, anchor='center')

        ttk.Label(frame, text='ՇINCERTIFICATE', style='Title.TLabel').pack(pady=(0, 4))
        ttk.Label(frame, text='Лабораторная платформа экспертиз',
                  style='Subtitle.TLabel').pack(pady=(0, 30))

        card = ttk.Frame(frame, style='Card.TFrame', padding=30)
        card.pack()

        ttk.Label(card, text='Вход в систему', style='CardTitle.TLabel').pack(anchor='w', pady=(0, 16))

        ttk.Label(card, text='Логин:', background=WHITE).pack(anchor='w')
        self._login_user = ttk.Entry(card, width=30, font=('Segoe UI', 11))
        self._login_user.pack(pady=(2, 10))
        self._login_user.insert(0, 'test')

        ttk.Label(card, text='Пароль:', background=WHITE).pack(anchor='w')
        self._login_pass = ttk.Entry(card, width=30, font=('Segoe UI', 11), show='•')
        self._login_pass.pack(pady=(2, 16))

        ttk.Button(card, text='Войти', style='Accent.TButton',
                   command=self._do_login).pack(fill='x')

        self._login_user.focus_set()
        self._login_pass.bind('<Return>', lambda e: self._do_login())
        self._login_user.bind('<Return>', lambda e: self._login_pass.focus_set())

    def _do_login(self):
        user = authenticate(self.conn, self._login_user.get().strip(),
                            self._login_pass.get())
        if not user:
            messagebox.showerror('Ошибка', 'Неверный логин или пароль')
            return
        self.current_user = dict(user)
        self._show_main()

    # ═══════════════════════════════════════════════════════════════
    #  ЭКРАН 2: ГЛАВНАЯ (каталог + реестр)
    # ═══════════════════════════════════════════════════════════════

    def _show_main(self):
        self._clear()
        outer = ttk.Frame(self._container, padding=16)
        outer.pack(fill='both', expand=True)

        # Верхняя панель
        top = ttk.Frame(outer)
        top.pack(fill='x', pady=(0, 12))

        ttk.Label(top, text='ՇINCERTIFICATE', style='Title.TLabel').pack(side='left')
        user_text = f'{self.current_user["full_name"]} ({self.current_user["role"]})'
        ttk.Label(top, text=user_text, font=('Segoe UI', 10, 'italic')).pack(side='right')
        ttk.Button(top, text='Выход', command=self._show_login).pack(side='right', padx=8)

        # Notebook: Каталог | Реестр
        nb = ttk.Notebook(outer)
        nb.pack(fill='both', expand=True)

        # --- Вкладка: Каталог ---
        cat_frame = ttk.Frame(nb, padding=12)
        nb.add(cat_frame, text='  Каталог экспертиз  ')
        self._build_catalog(cat_frame)

        # --- Вкладка: Реестр ---
        reg_frame = ttk.Frame(nb, padding=12)
        nb.add(reg_frame, text='  Реестр  ')
        self._build_registry(reg_frame)

    def _build_catalog(self, parent):
        ttk.Label(parent, text='Выберите вид экспертизы',
                  font=('Segoe UI', 13, 'bold'), foreground=NAVY).pack(anchor='w', pady=(0, 8))
        ttk.Label(parent, text='Двойной клик по конечному пункту (лист) для создания новой экспертизы.'
                  ).pack(anchor='w', pady=(0, 12))

        tree = ttk.Treeview(parent, show='tree headings', columns=('desc',), height=20)
        tree.heading('#0', text='Название')
        tree.heading('desc', text='Описание')
        tree.column('#0', width=500, stretch=True)
        tree.column('desc', width=400, stretch=True)

        vsb = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        # Заполняем дерево
        catalog = get_expertise_tree(self.conn)
        self._populate_tree(tree, '', catalog)

        tree.bind('<Double-1>', lambda e: self._on_catalog_dblclick(tree))
        self._catalog_tree = tree

    def _populate_tree(self, tree: ttk.Treeview, parent_iid: str, nodes: list):
        for node in nodes:
            icon = '📋' if node['is_leaf'] else ('📂' if not node['parent_id'] else '📁')
            iid = tree.insert(
                parent_iid, 'end',
                text=f' {icon}  {node["name"]}',
                values=(node['description'],),
                open=True,
                tags=('leaf',) if node['is_leaf'] else (),
            )
            # Сохраняем id типа в tags
            tree.item(iid, tags=(f'type_{node["id"]}',) + (('leaf',) if node['is_leaf'] else ()))
            if node['children']:
                self._populate_tree(tree, iid, node['children'])

    def _on_catalog_dblclick(self, tree: ttk.Treeview):
        item = tree.focus()
        if not item:
            return
        tags = tree.item(item, 'tags')
        is_leaf = 'leaf' in tags
        type_id = None
        for t in tags:
            if t.startswith('type_'):
                type_id = int(t.split('_')[1])
        if not is_leaf or not type_id:
            return

        # Определяем код типа
        row = self.conn.execute('SELECT code FROM expertise_types WHERE id=?', (type_id,)).fetchone()
        if not row:
            return

        code = row['code']
        if code == 'W-3407':
            self._show_waterproof_test(type_id)
        else:
            messagebox.showinfo(
                'В разработке',
                f'Экспертиза «{tree.item(item, "text").strip()}» '
                f'пока не реализована.\n\nРеализована только: '
                f'Бетон → Водонепроницаемость → Прибор №3407',
            )

    def _build_registry(self, parent):
        ttk.Label(parent, text='Реестр проведённых экспертиз',
                  font=('Segoe UI', 13, 'bold'), foreground=NAVY).pack(anchor='w', pady=(0, 12))

        cols = ('id', 'date', 'type', 'customer', 'status', 'creator')
        self._reg_tree = ttk.Treeview(parent, columns=cols, show='headings', height=20)

        headings = {
            'id': ('№', 50), 'date': ('Дата', 100), 'type': ('Экспертиза', 300),
            'customer': ('Заказчик', 200), 'status': ('Статус', 100),
            'creator': ('Оператор', 140),
        }
        for c, (text, w) in headings.items():
            self._reg_tree.heading(c, text=text)
            self._reg_tree.column(c, width=w, anchor='center' if w < 120 else 'w')

        vsb = ttk.Scrollbar(parent, orient='vertical', command=self._reg_tree.yview)
        self._reg_tree.configure(yscrollcommand=vsb.set)
        self._reg_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._reg_tree.bind('<Double-1>', self._on_registry_dblclick)

        self._refresh_registry()

    def _refresh_registry(self):
        for item in self._reg_tree.get_children():
            self._reg_tree.delete(item)
        rows = list_expertises(self.conn)
        for r in rows:
            status_text = 'Подтверждена' if r['status'] == 'confirmed' else 'Черновик'
            self._reg_tree.insert('', 'end', iid=str(r['id']), values=(
                r['id'],
                r['test_date'] or r['created_at'][:10],
                r['type_name'],
                r['customer'] or '—',
                status_text,
                r['creator_name'],
            ))

    def _on_registry_dblclick(self, event):
        item = self._reg_tree.focus()
        if not item:
            return
        exp_id = int(item)
        exp = get_expertise(self.conn, exp_id)
        if not exp:
            return
        code = exp['type'].get('code', '')
        if code == 'W-3407':
            self._show_waterproof_test(exp['expertise_type_id'], expertise_id=exp_id)
        else:
            messagebox.showinfo('Просмотр', f'Экспертиза #{exp_id} — просмотр пока не реализован.')

    # ═══════════════════════════════════════════════════════════════
    #  ЭКРАН 3: ЭКСПЕРТИЗА ВОДОНЕПРОНИЦАЕМОСТИ (W-3407)
    # ═══════════════════════════════════════════════════════════════

    def _show_waterproof_test(self, type_id: int, expertise_id: int = None):
        self._clear()
        self._current_type_id = type_id
        self._current_expertise_id = expertise_id
        self._is_confirmed = False

        outer = ttk.Frame(self._container, padding=16)
        outer.pack(fill='both', expand=True)

        # Верхняя панель с навигацией
        top = ttk.Frame(outer)
        top.pack(fill='x', pady=(0, 8))

        ttk.Button(top, text='← Назад', command=self._show_main).pack(side='left')

        # Хлебные крошки
        path = get_type_path(self.conn, type_id)
        crumbs = ' → '.join(p['name'] for p in path)
        ttk.Label(top, text=crumbs, font=('Segoe UI', 9), foreground='#64748b').pack(side='left', padx=12)

        user_text = f'{self.current_user["full_name"]}'
        ttk.Label(top, text=user_text, font=('Segoe UI', 9, 'italic')).pack(side='right')

        # Заголовок
        ttk.Label(outer, text='Водонепроницаемость бетона · Прибор №3407',
                  style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='ГОСТ 12730.5—2018 · Метод воздухопроницаемости · '
                  '6 кубов 150×150×150',
                  style='Subtitle.TLabel').pack(anchor='w', pady=(2, 10))

        # Мета-поля
        meta_frame = ttk.Frame(outer)
        meta_frame.pack(fill='x', pady=(0, 8))

        ttk.Label(meta_frame, text='Заказчик:').grid(row=0, column=0, sticky='w', padx=4)
        self._w_customer = ttk.Entry(meta_frame, width=40)
        self._w_customer.grid(row=0, column=1, sticky='w', padx=4)

        ttk.Label(meta_frame, text='Объект:').grid(row=0, column=2, sticky='w', padx=(16, 4))
        self._w_object = ttk.Entry(meta_frame, width=40)
        self._w_object.grid(row=0, column=3, sticky='w', padx=4)

        ttk.Label(meta_frame, text='Дата:').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self._w_date = ttk.Entry(meta_frame, width=14)
        self._w_date.grid(row=1, column=1, sticky='w', padx=4, pady=4)
        self._w_date.insert(0, datetime.now().strftime('%d.%m.%Y'))

        ttk.Label(meta_frame, text='Тип образца:').grid(row=1, column=2, sticky='w', padx=(16, 4), pady=4)
        self._w_shape = tk.StringVar(value='cube')
        shape_fr = ttk.Frame(meta_frame)
        shape_fr.grid(row=1, column=3, sticky='w', padx=4, pady=4)
        ttk.Radiobutton(shape_fr, text='Куб', variable=self._w_shape, value='cube').pack(side='left')
        ttk.Radiobutton(shape_fr, text='Цилиндр', variable=self._w_shape, value='cylinder').pack(side='left', padx=8)

        # Таблица данных
        table_frame = ttk.LabelFrame(outer, text=' Данные образцов ', padding=8)
        table_frame.pack(fill='both', expand=True, pady=4)

        headers = ['№', 'Камера', 'V, см³', 'Заявленная W', 'Время t, сек',
                   'Расчётная W', 'Результат']
        for col, text in enumerate(headers):
            tk.Label(table_frame, text=text, font=('Segoe UI', 9, 'bold'),
                     bg='#dce7f3', fg=NAVY, bd=1, relief='solid', height=2, width=14
                     ).grid(row=0, column=col, sticky='nsew')

        self._w_times = []
        self._w_declared = []
        self._w_calc = []
        self._w_verdict = []

        for i in range(6):
            r = i + 1
            vol = VOLUMES[i]
            tk.Label(table_frame, text=str(r), bg=WHITE, bd=1, relief='solid',
                     font=('Segoe UI', 10)).grid(row=r, column=0, sticky='nsew')
            tk.Label(table_frame, text=str(r), bg=WHITE, bd=1, relief='solid',
                     font=('Segoe UI', 10)).grid(row=r, column=1, sticky='nsew')
            tk.Label(table_frame, text=str(vol), bg=WHITE, bd=1, relief='solid',
                     font=('Segoe UI', 10)).grid(row=r, column=2, sticky='nsew')

            dw = tk.StringVar()
            combo = ttk.Combobox(table_frame, textvariable=dw, values=VALID_W_GRADES,
                                 width=10, state='readonly')
            combo.grid(row=r, column=3, padx=3, pady=3, sticky='nsew')
            self._w_declared.append(dw)

            ent = ttk.Entry(table_frame, font=('Segoe UI', 10), justify='center', width=14)
            ent.grid(row=r, column=4, padx=3, pady=3, sticky='nsew')
            self._w_times.append(ent)

            wv = tk.StringVar(value='—')
            tk.Label(table_frame, textvariable=wv, bg=WHITE, bd=1, relief='solid',
                     font=('Segoe UI', 11, 'bold')).grid(row=r, column=5, sticky='nsew')
            self._w_calc.append(wv)

            vv = tk.StringVar(value='—')
            tk.Label(table_frame, textvariable=vv, bg=WHITE, bd=1, relief='solid',
                     font=('Segoe UI', 10)).grid(row=r, column=6, sticky='nsew')
            self._w_verdict.append(vv)

        for c in range(7):
            table_frame.grid_columnconfigure(c, weight=1)

        # Кнопки
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill='x', pady=(8, 0))

        self._status_lbl = ttk.Label(btn_frame, text='', font=('Segoe UI', 10))
        self._status_lbl.pack(side='left', fill='x', expand=True)

        self._btn_confirm = ttk.Button(btn_frame, text='✓ Подтвердить',
                                        style='Danger.TButton',
                                        command=self._confirm_current)
        self._btn_confirm.pack(side='right', padx=4)

        self._btn_save = ttk.Button(btn_frame, text='Сохранить', style='Accent.TButton',
                                     command=self._save_current)
        self._btn_save.pack(side='right', padx=4)

        ttk.Button(btn_frame, text='PDF', command=self._export_pdf_w).pack(side='right', padx=4)
        ttk.Button(btn_frame, text='Excel', command=self._export_excel_w).pack(side='right', padx=4)

        # Загрузить существующую экспертизу
        if expertise_id:
            self._load_expertise(expertise_id)

    def _load_expertise(self, exp_id: int):
        """Загружает данные экспертизы в форму."""
        exp = get_expertise(self.conn, exp_id)
        if not exp:
            return

        self._w_customer.delete(0, 'end')
        self._w_customer.insert(0, exp.get('customer', ''))
        self._w_object.delete(0, 'end')
        self._w_object.insert(0, exp.get('object_name', ''))
        self._w_date.delete(0, 'end')
        self._w_date.insert(0, exp.get('test_date', ''))

        # Восстанавливаем данные из key-value
        data_map = {d['key']: d['value'] for d in exp.get('data', [])}
        self._w_shape.set(data_map.get('shape', 'cube'))

        for i in range(6):
            t_val = data_map.get(f'time_{i}', '')
            dw_val = data_map.get(f'declared_{i}', '')
            cw_val = data_map.get(f'calc_w_{i}', '—')
            vv_val = data_map.get(f'verdict_{i}', '—')

            self._w_times[i].delete(0, 'end')
            self._w_times[i].insert(0, t_val)
            if dw_val:
                self._w_declared[i].set(dw_val)
            self._w_calc[i].set(cw_val)
            self._w_verdict[i].set(vv_val)

        # Блокировка если подтверждена
        if exp['status'] == 'confirmed':
            self._lock_form()
            confirmer = exp.get('confirmer', {}).get('full_name', '?')
            self._status_lbl.configure(
                text=f'Подтверждена: {exp["confirmed_at"]} · {confirmer}',
                foreground='#16a34a',
            )

    def _lock_form(self):
        """Блокирует все поля (экспертиза подтверждена)."""
        self._is_confirmed = True
        self._w_customer.configure(state='disabled')
        self._w_object.configure(state='disabled')
        self._w_date.configure(state='disabled')
        for ent in self._w_times:
            ent.configure(state='disabled')
        for combo in self._w_declared:
            # StringVar-based combobox: disable by setting state on widget
            # Find the widget that uses this StringVar
            pass
        self._btn_save.configure(state='disabled')
        self._btn_confirm.configure(state='disabled')
        # Disable comboboxes
        for widget in self._container.winfo_children():
            self._disable_combos_recursive(widget)

    def _disable_combos_recursive(self, widget):
        if isinstance(widget, ttk.Combobox):
            widget.configure(state='disabled')
        for child in widget.winfo_children():
            self._disable_combos_recursive(child)

    def _collect_w(self) -> dict:
        """Собирает данные формы и считает серию."""
        times = []
        declared = []
        for i in range(6):
            t_text = self._w_times[i].get().strip()
            if not t_text:
                raise ValueError(f'Образец {i+1}: не заполнено время t')
            times.append(parse_positive(t_text, f'Образец {i+1}, время'))

            dw = self._w_declared[i].get()
            if not dw:
                raise ValueError(f'Образец {i+1}: не выбрана заявленная W')
            declared.append(dw)

        series = compute_series(times, declared=declared)

        for i, spec in enumerate(series['specimens']):
            self._w_calc[i].set(spec['W'])
            self._w_verdict[i].set('✓ Соотв.' if spec['conforms'] else '✗ Не соотв.')

        return series

    def _build_kv_data(self, series: dict) -> list[tuple[str, str]]:
        """Формирует key-value пары для сохранения в БД."""
        data = [
            ('shape', self._w_shape.get()),
            ('customer', self._w_customer.get().strip()),
            ('object', self._w_object.get().strip()),
            ('test_date', self._w_date.get().strip()),
        ]
        for i, spec in enumerate(series['specimens']):
            data.append((f'time_{i}', str(spec['t'])))
            data.append((f'declared_{i}', spec.get('declared_W', '')))
            data.append((f'calc_w_{i}', spec['W']))
            data.append((f'volume_{i}', str(spec['volume'])))
            data.append((f'M_{i}', str(spec['M'])))
            data.append((f'a_{i}', f'{spec["a"]:.5f}'))
            data.append((f'm_{i}', f'{spec["m"]:.4f}'))
            data.append((f'verdict_{i}', '✓ Соотв.' if spec.get('conforms') else '✗ Не соотв.'))
        return data

    def _save_current(self):
        try:
            series = self._collect_w()

            if not self._current_expertise_id:
                self._current_expertise_id = create_expertise(
                    self.conn, self._current_type_id,
                    self.current_user['id'],
                    customer=self._w_customer.get().strip(),
                    object_name=self._w_object.get().strip(),
                    test_date=self._w_date.get().strip(),
                )

            # Обновляем мета-поля
            self.conn.execute(
                'UPDATE expertises SET customer=?, object_name=?, test_date=? WHERE id=?',
                (self._w_customer.get().strip(), self._w_object.get().strip(),
                 self._w_date.get().strip(), self._current_expertise_id),
            )
            self.conn.commit()

            save_expertise_data(self.conn, self._current_expertise_id,
                                self._build_kv_data(series))

            self._status_lbl.configure(
                text=f'Сохранено · Экспертиза #{self._current_expertise_id}',
                foreground=NAVY,
            )
        except PermissionError as e:
            messagebox.showerror('Запрещено', str(e))
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))

    def _confirm_current(self):
        if not self._current_expertise_id:
            messagebox.showwarning('Внимание', 'Сначала сохраните экспертизу.')
            return
        if self._is_confirmed:
            return

        ok = messagebox.askyesno(
            'Подтверждение',
            'После подтверждения результаты нельзя будет изменить.\n\n'
            'Подтвердить экспертизу?',
        )
        if not ok:
            return

        try:
            # Сохраняем перед подтверждением
            self._save_current()
            confirm_expertise(self.conn, self._current_expertise_id, self.current_user['id'])
            self._lock_form()
            self._status_lbl.configure(
                text=f'Подтверждена · #{self._current_expertise_id}',
                foreground='#16a34a',
            )
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))

    def _get_meta_w(self) -> dict:
        return {
            'customer': self._w_customer.get().strip(),
            'object': self._w_object.get().strip(),
            'test_date': self._w_date.get().strip(),
        }

    def _export_excel_w(self):
        try:
            series = self._collect_w()
            path = filedialog.asksaveasfilename(
                title='Сохранить Excel', defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx')],
                initialfile=f'Протокол_W_{datetime.now():%Y%m%d_%H%M%S}.xlsx',
            )
            if not path:
                return
            export_excel(TEMPLATE_XLSX, Path(path), series,
                         meta=self._get_meta_w(), shape=self._w_shape.get())
            messagebox.showinfo('Готово', f'Excel сохранён:\n{path}')
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))

    def _export_pdf_w(self):
        try:
            series = self._collect_w()
            path = filedialog.asksaveasfilename(
                title='Сохранить PDF', defaultextension='.pdf',
                filetypes=[('PDF', '*.pdf')],
                initialfile=f'Протокол_W_{datetime.now():%Y%m%d_%H%M%S}.pdf',
            )
            if not path:
                return
            export_pdf(BACKGROUND_PDF, Path(path), series,
                       meta=self._get_meta_w(), shape=self._w_shape.get(),
                       signature_path=SIGNATURE_PNG, stamp_path=STAMP_PNG,
                       demo_mark=True)
            messagebox.showinfo('Готово — DEMO', f'PDF сохранён:\n{path}\n\nОБРАЗЕЦ / DEMO')
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))
