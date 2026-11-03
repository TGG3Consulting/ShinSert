# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — точка входа.

Запуск:
    python main.py           — GUI (логин → каталог → экспертиза)
    python main.py --test    — автотест расчётов и БД
    python main.py --initdb  — создать/инициализировать БД
"""
import argparse


def run_gui():
    from gui import App
    App().mainloop()


def run_initdb():
    from db import init_db, get_connection
    conn = get_connection()
    init_db(conn)
    conn.close()
    print('БД инициализирована. Пользователь: test / test')


def run_test():
    from decimal import Decimal
    from calc import compute_series, classify_w, compare_w, normalize_w

    print('=== SHINCERTIFICATE self-test ===')

    times = [Decimal(t) for t in ('10000', '12000', '14000', '16000', '18000', '20000')]
    series = compute_series(times, declared=['W8'] * 6)
    for spec in series['specimens']:
        status = 'OK' if spec['conforms'] else 'FAIL'
        print(f"  Образец {spec['sample']}: t={spec['t']} → W={spec['W']} vs {spec['declared_W']} → {status}")

    assert classify_w(Decimal('5.0')) == 'W4'
    assert classify_w(Decimal('7.0')) == 'W6'
    assert classify_w(Decimal('10.0')) == 'W8'
    print('  classify_w: OK')

    assert compare_w('W10', 'W8') is True
    assert compare_w('W6', 'W8') is False
    assert compare_w('W8', 'W8') is True
    print('  compare_w: OK')

    assert normalize_w('w8') == 'W8'
    assert normalize_w('В6') == 'W6'
    print('  normalize_w: OK')

    # Тест БД
    import tempfile, os
    from db import get_connection, init_db, authenticate, get_expertise_tree
    from db import create_expertise, save_expertise_data, confirm_expertise, get_expertise

    db_path = os.path.join(tempfile.gettempdir(), 'shincert_test.db')
    conn = get_connection(db_path)
    init_db(conn)

    user = authenticate(conn, 'test', 'test')
    assert user is not None and user['role'] == 'admin'
    print('  auth: OK')

    tree = get_expertise_tree(conn)
    assert len(tree) >= 3  # Бетон, Грунты, Металлоконструкции
    print(f'  catalog: {len(tree)} root groups OK')

    # Создаём экспертизу
    leaf = conn.execute("SELECT id FROM expertise_types WHERE code='W-3407'").fetchone()
    exp_id = create_expertise(conn, leaf['id'], user['id'], customer='Тест', test_date='01.01.2025')
    save_expertise_data(conn, exp_id, [('time_0', '10000'), ('declared_0', 'W8')])
    exp = get_expertise(conn, exp_id)
    assert exp['status'] == 'draft'
    print(f'  create expertise #{exp_id}: OK')

    confirm_expertise(conn, exp_id, user['id'])
    exp = get_expertise(conn, exp_id)
    assert exp['status'] == 'confirmed'
    print(f'  confirm expertise: OK')

    try:
        save_expertise_data(conn, exp_id, [('time_0', '99999')])
        assert False, 'Should have raised PermissionError'
    except PermissionError:
        print('  lock after confirm: OK')

    conn.close()
    os.unlink(db_path)

    print('\n✓ Все тесты пройдены.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SHINCERTIFICATE — лабораторная платформа')
    parser.add_argument('--test', action='store_true', help='автотест')
    parser.add_argument('--initdb', action='store_true', help='инициализировать БД')
    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.initdb:
        run_initdb()
    else:
        run_gui()
