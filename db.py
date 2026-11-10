# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — слой базы данных (SQLite, миграция на Postgres позже).

Таблицы:
- users              — пользователи с ролями
- expertise_types    — 3-уровневый каталог экспертиз (дерево)
- expertises         — реестр проведённых экспертиз
- expertise_data     — данные каждой экспертизы (key-value для гибкости)
"""
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'shincert.db'


def _hash_password(password: str) -> str:
    """SHA-256 хеш пароля (для MVP; в проде — bcrypt)."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def get_connection(db_path: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db(conn: sqlite3.Connection = None):
    """Создаёт таблицы и начальные данные."""
    own = conn is None
    if own:
        conn = get_connection()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT    NOT NULL UNIQUE,
        password    TEXT    NOT NULL,
        full_name   TEXT    NOT NULL DEFAULT '',
        role        TEXT    NOT NULL DEFAULT 'operator',
        is_active   INTEGER NOT NULL DEFAULT 1,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS expertise_types (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id   INTEGER REFERENCES expertise_types(id),
        name        TEXT    NOT NULL,
        code        TEXT    NOT NULL DEFAULT '',
        description TEXT    NOT NULL DEFAULT '',
        sort_order  INTEGER NOT NULL DEFAULT 0,
        is_leaf     INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS expertises (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        expertise_type_id INTEGER NOT NULL REFERENCES expertise_types(id),
        created_by      INTEGER NOT NULL REFERENCES users(id),
        confirmed_by    INTEGER REFERENCES users(id),
        customer        TEXT    NOT NULL DEFAULT '',
        object_name     TEXT    NOT NULL DEFAULT '',
        test_date       TEXT    NOT NULL DEFAULT '',
        status          TEXT    NOT NULL DEFAULT 'draft',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        confirmed_at    TEXT,
        notes           TEXT    NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS expertise_data (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        expertise_id    INTEGER NOT NULL REFERENCES expertises(id),
        key             TEXT    NOT NULL,
        value           TEXT    NOT NULL DEFAULT '',
        sort_order      INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS knowledge_base (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        expertise_type_id   INTEGER NOT NULL REFERENCES expertise_types(id),
        title               TEXT    NOT NULL,
        category            TEXT    NOT NULL DEFAULT 'document',
        content             TEXT    NOT NULL DEFAULT '',
        file_path           TEXT    NOT NULL DEFAULT '',
        url                 TEXT    NOT NULL DEFAULT '',
        sort_order          INTEGER NOT NULL DEFAULT 0,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_expertise_data_eid
        ON expertise_data(expertise_id);
    CREATE INDEX IF NOT EXISTS idx_expertises_type
        ON expertises(expertise_type_id);
    CREATE INDEX IF NOT EXISTS idx_expertise_types_parent
        ON expertise_types(parent_id);
    CREATE INDEX IF NOT EXISTS idx_knowledge_base_type
        ON knowledge_base(expertise_type_id);
    """)

    _seed_users(conn)
    _seed_expertise_types(conn)
    _seed_knowledge_base(conn)
    conn.commit()
    if own:
        conn.close()


def _seed_users(conn: sqlite3.Connection):
    """Создаёт пользователя test/test если нет ни одного."""
    row = conn.execute('SELECT COUNT(*) c FROM users').fetchone()
    if row['c'] > 0:
        return
    conn.execute(
        'INSERT INTO users (username, password, full_name, role) VALUES (?,?,?,?)',
        ('test', _hash_password('test'), 'Test Admin', 'admin'),
    )


def _seed_expertise_types(conn: sqlite3.Connection):
    """Заполняет демо-каталог экспертиз (3 уровня)."""
    row = conn.execute('SELECT COUNT(*) c FROM expertise_types').fetchone()
    if row['c'] > 0:
        return

    tree = [
        # Уровень 1: Группы
        ('Бетон', 'CONCRETE', '', [
            # Уровень 2: Подгруппы
            ('Водонепроницаемость бетона', 'WATERPROOF', '', [
                # Уровень 3: Конкретные экспертизы (leaf)
                ('ГОСТ 12730.5-2018 · Метод воздухопроницаемости · Прибор №3407',
                 'W-3407', 'Серия из 6 кубов 150×150×150, прибор №3407'),
                ('ГОСТ 12730.5-2018 · Метод «мокрого пятна»',
                 'W-WET', 'Альтернативный метод определения W'),
            ]),
            ('Прочность бетона', 'STRENGTH', '', [
                ('ГОСТ 10180-2012 · Прочность на сжатие',
                 'STR-COMPRESS', 'Испытание кубов/цилиндров на сжатие'),
                ('ГОСТ 10180-2012 · Прочность на изгиб',
                 'STR-BEND', 'Испытание балок на изгиб'),
            ]),
            ('Морозостойкость бетона', 'FROST', '', [
                ('ГОСТ 10060-2012 · Базовый метод',
                 'FROST-BASE', 'Циклы замораживания-оттаивания'),
            ]),
        ]),
        ('Грунты', 'SOIL', '', [
            ('Физические свойства грунтов', 'SOIL-PHYS', '', [
                ('ГОСТ 5180-2015 · Влажность и плотность',
                 'SOIL-WD', 'Определение влажности и плотности грунта'),
                ('ГОСТ 5180-2015 · Границы пластичности',
                 'SOIL-PLAST', 'Определение пределов текучести и раскатывания'),
            ]),
            ('Механические свойства грунтов', 'SOIL-MECH', '', [
                ('ГОСТ 12248-2010 · Компрессионные испытания',
                 'SOIL-COMPR', 'Определение сжимаемости грунта'),
            ]),
        ]),
        ('Металлоконструкции', 'METAL', '', [
            ('Сварные соединения', 'WELD', '', [
                ('ГОСТ 6996-66 · Механические испытания сварных соединений',
                 'WELD-MECH', 'Испытания на растяжение, изгиб, ударную вязкость'),
            ]),
            ('Прочность металла', 'METAL-STR', '', [
                ('ГОСТ 1497-84 · Испытания на растяжение',
                 'METAL-TENS', 'Определение предела текучести и прочности'),
            ]),
        ]),
    ]

    def insert_node(parent_id, items):
        for item in items:
            if len(item) == 4:
                name, code, desc, children = item
                is_leaf = 0
            else:
                name, code, desc = item
                children = []
                is_leaf = 1

            cur = conn.execute(
                'INSERT INTO expertise_types (parent_id, name, code, description, is_leaf) '
                'VALUES (?,?,?,?,?)',
                (parent_id, name, code, desc, is_leaf),
            )
            node_id = cur.lastrowid
            if children:
                insert_node(node_id, children)

    insert_node(None, tree)


def _seed_knowledge_base(conn: sqlite3.Connection):
    """Заполняет демо-записи базы знаний для каждого уровня каталога."""
    row = conn.execute('SELECT COUNT(*) c FROM knowledge_base').fetchone()
    if row['c'] > 0:
        return

    # Маппинг code → список записей (title, category, content, url)
    # url='' для обычных, url='...' для видео
    kb_entries = {
        'CONCRETE': [
            ('Общие требования к бетонным смесям', 'document',
             'Бетонные смеси должны соответствовать установленным требованиям к составу, однородности и технологическим свойствам. При контроле качества оценивают удобоукладываемость, среднюю плотность, пористость, расслаиваемость, температуру и сохраняемость свойств. Методы определения этих показателей установлены ГОСТ 10181—2014.', ''),
            ('Виды бетона по средней плотности', 'reference',
             'Бетоны классифицируются по средней плотности, которая зависит от состава и структуры материала. Классификация предусмотрена ГОСТ 25192—2012 и учитывается при определении области применения бетона. Выделяют особо лёгкие, лёгкие, тяжёлые и особо тяжёлые бетоны.', ''),
            ('Виды бетона по структуре', 'reference',
             'ГОСТ 25192—2012 предусматривает классификацию бетонов в зависимости от особенностей их внутренней структуры. Структура влияет на плотность, прочность, теплопроводность и другие характеристики материала. Выделяют плотные, поризованные, ячеистые и крупнопористые бетоны.', ''),
            ('Виды бетона по назначению', 'reference',
             'Бетоны классифицируются в зависимости от области применения и предъявляемых к ним требований. ГОСТ 25192—2012 предусматривает классификацию бетонов по назначению: конструкционные и специальные бетоны.', ''),
            ('Виды бетонных смесей по удобоукладываемости', 'reference',
             'ГОСТ 7473—2010 устанавливает классификацию бетонных смесей по удобоукладываемости. Показатели определяют методами ГОСТ 10181—2014. Выделяют жёсткие, подвижные и растекающиеся бетонные смеси.', ''),
            ('Классификация бетонов по назначению', 'reference',
             'Бетоны различаются по назначению, составу и условиям эксплуатации. В зависимости от области применения к ним предъявляются различные требования по прочности, водонепроницаемости, морозостойкости и другим характеристикам. Для каждого вида бетона применяются соответствующие нормативные требования и методы испытаний.', ''),
        ],
        'WATERPROOF': [
            ('ГОСТ 12730.5—2018 — Водонепроницаемость бетона', 'gost',
             'ГОСТ 12730.5—2018 устанавливает методы определения водонепроницаемости бетона по мокрому пятну, коэффициенту фильтрации, глубине проникания воды под давлением и воздухопроницаемости. Документ содержит требования к образцам, оборудованию, условиям испытаний и обработке результатов.', ''),
            ('Методические указания по определению W', 'methodology',
             'Марку бетона по водонепроницаемости W определяют по результатам испытаний установленным методом. При испытании по мокрому пятну на образцы воздействуют ступенчато повышаемым давлением воды и контролируют её проникновение через бетон. Результаты фиксируют и обрабатывают в соответствии с разделом 4 ГОСТ 12730.5—2018.', ''),
            ('Видеоматериалы', 'video', 'Видеоинструкции по работе с оборудованием для определения водонепроницаемости.', ''),
        ],
        'W-3407': [
            ('Паспорт прибора №3407', 'passport',
             'Технические характеристики, объёмы камер (1720, 1620, 1632, 1620, 1620, 1638 см³), допустимые погрешности. Начальное вакуумметрическое давление J = 0,064 МПа.', ''),
            ('Таблица определения марки W по mc', 'reference',
             'mc 3.1–4.5 → W2, 4.6–6.5 → W4, 6.6–9.4 → W6, 9.5–13.7 → W8, 13.8–19.6 → W10, 19.7–29.0 → W12, 29.1–42.0 → W14, 42.1–60.9 → W16, 61.0–88.5 → W18, 88.6–130.2 → W20.', ''),
            ('Инструкция: подготовка кубов 150×150×150', 'methodology',
             'Требования к форме, размерам, выдержке и маркировке образцов перед испытанием. Серия из 6 кубов 150×150×150 мм.', ''),
            ('FAQ: частые ошибки при испытании', 'faq',
             'Недостаточная герметизация камеры, неправильный отсчёт времени, влияние температуры окружающей среды, неверное определение начального разрежения.', ''),
        ],
        'W-WET': [
            ('ГОСТ 12730.5-2018 — Метод «мокрого пятна»', 'gost',
             'Описание альтернативного метода определения водонепроницаемости бетона по появлению мокрого пятна на поверхности образца.', ''),
        ],
        'STRENGTH': [
            ('ГОСТ 10180-2012 — Прочность бетона', 'gost',
             'Методы определения прочности по контрольным образцам.', ''),
            ('Классы бетона по прочности на сжатие', 'reference',
             'Таблица соответствия: B7.5, B10, B15, B20, B25, B30, B35, B40 и выше.', ''),
            ('Определение удобоукладываемости бетонной смеси', 'methodology',
             'Удобоукладываемость характеризует способность бетонной смеси заполнять форму и уплотняться при заданных условиях. По ГОСТ 10181—2014 её оценивают различными методами: подвижность, жёсткость, расплыв и степень уплотняемости.', ''),
            ('Определение пористости и расслаиваемости', 'methodology',
             'Испытания позволяют определять показатели пористости бетонной смеси и оценивать её склонность к расслаиванию. ГОСТ 10181—2014 предусматривает объёмный, компрессионный и расчётный способы определения содержания воздуха или газа.', ''),
            ('Неразрушающий контроль прочности бетона', 'methodology',
             'ГОСТ 22690—2015 предусматривает методы упругого отскока, пластической деформации, ударного импульса, отрыва, отрыва со скалыванием и скалывания ребра. Прочность бетона определяют по результатам измерений с использованием установленных градуировочных зависимостей.', ''),
        ],
        'STR-COMPRESS': [
            ('Методика испытания кубов на сжатие', 'methodology',
             'Подготовка пресса, центрирование образца, скорость нагружения, расчёт Rб.', ''),
        ],
        'STR-BEND': [
            ('Методика испытания балок на изгиб', 'methodology',
             'Схема нагружения, расчёт Rби, требования к размерам балки.', ''),
        ],
        'FROST': [
            ('Морозостойкость бетона', 'gost',
             'ГОСТ 10060—2012 устанавливает два базовых и два ускоренных метода определения морозостойкости бетона. Испытания предусматривают циклическое замораживание и оттаивание образцов с последующей оценкой изменения их характеристик и соответствия установленным требованиям.', ''),
        ],
        'FROST-BASE': [
            ('Базовый метод: циклы замораживания-оттаивания', 'methodology',
             'Режим камеры, контрольные образцы, критерии потери массы и прочности.', ''),
        ],
        'SOIL': [
            ('Классификация грунтов по ГОСТ 25100', 'reference',
             'Скальные, дисперсные, мёрзлые. Подразделение по генезису и составу.', ''),
        ],
        'SOIL-PHYS': [
            ('ГОСТ 5180-2015 — Полный текст', 'gost',
             'Методы лабораторного определения физических характеристик грунтов.', ''),
        ],
        'SOIL-WD': [
            ('Методика определения влажности грунта', 'methodology',
             'Весовой метод, сушка при 105°C, расчёт W.', ''),
        ],
        'SOIL-PLAST': [
            ('Определение границ пластичности', 'methodology',
             'Метод Казагранде и метод раскатывания в шнур.', ''),
        ],
        'SOIL-MECH': [
            ('ГОСТ 12248-2010 — обзор', 'gost',
             'Методы лабораторного определения характеристик прочности и деформируемости.', ''),
        ],
        'SOIL-COMPR': [
            ('Компрессионные испытания: методика', 'methodology',
             'Подготовка образца, схема нагружения, построение компрессионной кривой.', ''),
        ],
        'METAL': [
            ('Общие требования к испытаниям металлоконструкций', 'reference',
             'Нормативная база, виды испытаний, требования к лаборатории.', ''),
            ('Отбор и подготовка образцов для испытаний', 'methodology',
             'ГОСТ 7564—97 устанавливает правила отбора проб, заготовок и образцов металлического проката для проведения механических и технологических испытаний. Документ определяет требования к месту отбора, направлению, форме и подготовке образцов.', ''),
            ('Отбор проб для определения химического состава', 'methodology',
             'ГОСТ 7565—81 регламентирует порядок отбора и подготовки проб чугуна, стали и сплавов для определения химического состава.', ''),
            ('Виды проволоки по назначению', 'reference',
             'Стальная проволока подразделяется по назначению и условиям применения: общего назначения, арматурная, сварочная, пружинная и специальная. Требования к отдельным видам проволоки устанавливаются соответствующими стандартами, в том числе ГОСТ 3282—74.', ''),
            ('Виды арматуры по классам прочности', 'reference',
             'ГОСТ 34028—2016 устанавливает классы арматурного проката: А240, А400, А500, А600, Ап600, А800 и А1000 — в зависимости от уровня предела текучести и назначения.', ''),
        ],
        'WELD': [
            ('ГОСТ 6996-66 — обзор', 'gost',
             'Методы определения механических свойств сварного соединения.', ''),
        ],
        'WELD-MECH': [
            ('Испытание сварных соединений: методика', 'methodology',
             'Вырезка образцов, растяжение, изгиб, ударная вязкость по Шарпи.', ''),
        ],
        'METAL-STR': [
            ('ГОСТ 1497-84 — обзор', 'gost',
             'Методы испытаний на растяжение металлических материалов.', ''),
            ('Испытание проволоки на перегиб', 'methodology',
             'ГОСТ 1579—93 устанавливает метод испытания проволоки путём последовательных перегибов на 90° в противоположных направлениях. В ходе испытания фиксируют количество выдержанных перегибов до установленного критерия завершения или разрушения образца.', ''),
            ('Испытание арматурной стали на растяжение', 'methodology',
             'ГОСТ 12004—81 устанавливает методы испытания арматурной стали на растяжение. Определяют временное сопротивление, предел текучести, относительное удлинение, сужение и другие механические характеристики.', ''),
            ('Испытание металлических материалов на изгиб', 'methodology',
             'ГОСТ 14019—2003 устанавливает метод испытания металлических материалов на изгиб. Предусмотрены испытания до заданного угла, до параллельности сторон образца и до их соприкосновения.', ''),
            ('Определение содержания никеля в стали', 'methodology',
             'ГОСТ 12352—81 устанавливает методы определения массовой доли никеля в легированных и высоколегированных сталях: фотометрический, гравиметрический и атомно-абсорбционный.', ''),
            ('Испытание арматурного проката на выносливость', 'methodology',
             'ГОСТ 34028—2016, приложение Е, устанавливает методику испытания арматурного проката на выносливость. Образцы подвергают повторяющимся растягивающим нагрузкам. Результат оценивают по способности выдержать установленное количество циклов без разрушения.', ''),
        ],
        'METAL-TENS': [
            ('Испытание на растяжение: методика', 'methodology',
             'Подготовка образца, скорость деформирования, определение σ₀.₂ и σв.', ''),
        ],
    }

    # Видео — привязаны к WATERPROOF (видны из W-3407 и ниже через include_parents)
    video_entries = {
        'WATERPROOF': [
            ('Работа с установкой для определения водонепроницаемости', 'video',
             'Демонстрация работы с лабораторной установкой для определения водонепроницаемости бетона.',
             'https://rutube.ru/video/d3e58640c1cc7be18809acf7d2298a13/'),
            ('Работа с измерителем водонепроницаемости ВИП-1', 'video',
             'Подробная видеоинструкция по работе с измерителем ВИП-1.',
             'https://www.youtube.com/watch?v=cEoaSFqyPKs&t=1s'),
        ],
        'STRENGTH': [
            ('Работа с испытательным прессом для бетона', 'video',
             'Демонстрация испытания бетонных кубиков на прессе.',
             'https://sti-tdsk.ru/wp-content/uploads/2022/04/ispytaniya-betonnyh-kubikov.mp4'),
            ('Определение подвижности бетонной смеси', 'video',
             'Определение осадки конуса бетонной смеси.',
             'https://sti-tdsk.ru/wp-content/uploads/2022/03/osadka-konusa.mp4'),
        ],
        'METAL-STR': [
            ('Испытание арматурной стали на растяжение', 'video',
             'Видеодемонстрация испытания арматурной стали.',
             'https://rutube.ru/video/399296e8df896702578041c858ee1810/'),
        ],
    }

    for code, entries in kb_entries.items():
        type_row = conn.execute(
            'SELECT id FROM expertise_types WHERE code=?', (code,)
        ).fetchone()
        if not type_row:
            continue
        for i, (title, category, content, url) in enumerate(entries):
            conn.execute(
                'INSERT INTO knowledge_base (expertise_type_id, title, category, content, url, sort_order) '
                'VALUES (?,?,?,?,?,?)',
                (type_row['id'], title, category, content, url, i),
            )

    for code, entries in video_entries.items():
        type_row = conn.execute(
            'SELECT id FROM expertise_types WHERE code=?', (code,)
        ).fetchone()
        if not type_row:
            continue
        base = conn.execute(
            'SELECT MAX(sort_order) m FROM knowledge_base WHERE expertise_type_id=?',
            (type_row['id'],)
        ).fetchone()
        start = (base['m'] or 0) + 1
        for i, (title, category, content, url) in enumerate(entries):
            conn.execute(
                'INSERT INTO knowledge_base (expertise_type_id, title, category, content, url, sort_order) '
                'VALUES (?,?,?,?,?,?)',
                (type_row['id'], title, category, content, url, start + i),
            )


# ─── CRUD ────────────────────────────────────────────────────────

def authenticate(conn: sqlite3.Connection, username: str, password: str):
    """Возвращает Row пользователя или None."""
    return conn.execute(
        'SELECT * FROM users WHERE username=? AND password=? AND is_active=1',
        (username, _hash_password(password)),
    ).fetchone()


def get_expertise_tree(conn: sqlite3.Connection, parent_id=None) -> list[dict]:
    """Возвращает дерево типов экспертиз."""
    if parent_id is None:
        rows = conn.execute(
            'SELECT * FROM expertise_types WHERE parent_id IS NULL ORDER BY sort_order, name'
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM expertise_types WHERE parent_id=? ORDER BY sort_order, name',
            (parent_id,),
        ).fetchall()

    result = []
    for r in rows:
        node = dict(r)
        node['children'] = get_expertise_tree(conn, r['id'])
        result.append(node)
    return result


def get_type_path(conn: sqlite3.Connection, type_id: int) -> list[dict]:
    """Возвращает путь от корня до type_id (хлебные крошки)."""
    path = []
    current = type_id
    while current:
        row = conn.execute('SELECT * FROM expertise_types WHERE id=?', (current,)).fetchone()
        if not row:
            break
        path.insert(0, dict(row))
        current = row['parent_id']
    return path


def create_expertise(conn: sqlite3.Connection, type_id: int, user_id: int,
                     customer: str = '', object_name: str = '',
                     test_date: str = '', notes: str = '') -> int:
    """Создаёт новую экспертизу (статус draft)."""
    cur = conn.execute(
        'INSERT INTO expertises (expertise_type_id, created_by, customer, object_name, test_date, notes) '
        'VALUES (?,?,?,?,?,?)',
        (type_id, user_id, customer, object_name,
         test_date or datetime.now().strftime('%d.%m.%Y'), notes),
    )
    conn.commit()
    return cur.lastrowid


def save_expertise_data(conn: sqlite3.Connection, expertise_id: int,
                        data: list[tuple[str, str]]):
    """Сохраняет/перезаписывает данные экспертизы (list of (key, value))."""
    # Проверяем, не подтверждена ли
    exp = conn.execute('SELECT status FROM expertises WHERE id=?', (expertise_id,)).fetchone()
    if exp and exp['status'] == 'confirmed':
        raise PermissionError('Экспертиза подтверждена — редактирование запрещено')

    conn.execute('DELETE FROM expertise_data WHERE expertise_id=?', (expertise_id,))
    for i, (key, value) in enumerate(data):
        conn.execute(
            'INSERT INTO expertise_data (expertise_id, key, value, sort_order) VALUES (?,?,?,?)',
            (expertise_id, key, str(value), i),
        )
    conn.commit()


def confirm_expertise(conn: sqlite3.Connection, expertise_id: int, user_id: int):
    """Подтверждает экспертизу — после этого данные нельзя менять."""
    conn.execute(
        "UPDATE expertises SET status='confirmed', confirmed_by=?, confirmed_at=datetime('now') "
        "WHERE id=? AND status='draft'",
        (user_id, expertise_id),
    )
    conn.commit()


def get_expertise(conn: sqlite3.Connection, expertise_id: int) -> dict | None:
    """Возвращает экспертизу со всеми данными."""
    row = conn.execute('SELECT * FROM expertises WHERE id=?', (expertise_id,)).fetchone()
    if not row:
        return None
    exp = dict(row)
    exp['data'] = [
        dict(r) for r in conn.execute(
            'SELECT * FROM expertise_data WHERE expertise_id=? ORDER BY sort_order',
            (expertise_id,),
        ).fetchall()
    ]
    # Тип экспертизы
    t = conn.execute('SELECT * FROM expertise_types WHERE id=?', (exp['expertise_type_id'],)).fetchone()
    exp['type'] = dict(t) if t else {}
    exp['type_path'] = get_type_path(conn, exp['expertise_type_id'])
    # Пользователи
    u = conn.execute('SELECT * FROM users WHERE id=?', (exp['created_by'],)).fetchone()
    exp['creator'] = dict(u) if u else {}
    if exp['confirmed_by']:
        c = conn.execute('SELECT * FROM users WHERE id=?', (exp['confirmed_by'],)).fetchone()
        exp['confirmer'] = dict(c) if c else {}
    return exp


def list_expertises(conn: sqlite3.Connection, type_id: int = None,
                    status: str = None) -> list[dict]:
    """Реестр экспертиз с фильтрами."""
    query = """
        SELECT e.*, t.name as type_name, t.code as type_code,
               u.full_name as creator_name
        FROM expertises e
        JOIN expertise_types t ON e.expertise_type_id = t.id
        JOIN users u ON e.created_by = u.id
        WHERE 1=1
    """
    params = []
    if type_id:
        query += ' AND e.expertise_type_id=?'
        params.append(type_id)
    if status:
        query += ' AND e.status=?'
        params.append(status)
    query += ' ORDER BY e.created_at DESC'

    return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_knowledge_base(conn: sqlite3.Connection, type_id: int,
                       include_parents: bool = True) -> list[dict]:
    """Возвращает записи базы знаний для типа экспертизы.

    Если include_parents=True, включает также записи родительских уровней
    (вид → подвид → подподвид — видишь всё от корня до текущего).
    """
    type_ids = [type_id]
    if include_parents:
        current = type_id
        while True:
            row = conn.execute(
                'SELECT parent_id FROM expertise_types WHERE id=?', (current,)
            ).fetchone()
            if not row or not row['parent_id']:
                break
            type_ids.append(row['parent_id'])
            current = row['parent_id']

    placeholders = ','.join('?' * len(type_ids))
    rows = conn.execute(
        f"""SELECT kb.*, et.name as type_name
            FROM knowledge_base kb
            JOIN expertise_types et ON kb.expertise_type_id = et.id
            WHERE kb.expertise_type_id IN ({placeholders})
            ORDER BY et.id, kb.sort_order""",
        type_ids,
    ).fetchall()
    return [dict(r) for r in rows]
