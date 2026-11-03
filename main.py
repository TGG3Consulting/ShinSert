# -*- coding: utf-8 -*-
"""SHINCERTIFICATE — точка входа.

Запуск:
    python main.py           — GUI
    python main.py --test    — автотест расчётов
"""
import argparse
import sys


def run_gui():
    from gui import App
    App().mainloop()


def run_test():
    """Автотест: расчёт серии, классификация W, сравнение."""
    from decimal import Decimal
    from calc import compute_series, classify_w, compare_w, normalize_w

    print('=== SHINCERTIFICATE self-test ===')

    # Тест расчёта серии
    times = [Decimal(t) for t in ('10000', '12000', '14000', '16000', '18000', '20000')]
    declared = ['W8'] * 6
    series = compute_series(times, declared=declared)

    for spec in series['specimens']:
        status = 'OK' if spec['conforms'] else 'FAIL'
        print(f"  Образец {spec['sample']}: "
              f"t={spec['t']} → W={spec['W']} vs {spec['declared_W']} → {status}")

    # Тест классификации
    assert classify_w(Decimal('5.0')) == 'W4'
    assert classify_w(Decimal('7.0')) == 'W6'
    assert classify_w(Decimal('10.0')) == 'W8'
    assert classify_w(Decimal('2.0')) == '<W2'
    assert classify_w(Decimal('140.0')) == '>W20'
    print('  classify_w: OK')

    # Тест сравнения
    assert compare_w('W10', 'W8') is True
    assert compare_w('W6', 'W8') is False
    assert compare_w('W8', 'W8') is True
    assert compare_w('<W2', 'W4') is False
    assert compare_w('>W20', 'W20') is True
    print('  compare_w: OK')

    # Тест нормализации
    assert normalize_w('w8') == 'W8'
    assert normalize_w('W 12') == 'W12'
    assert normalize_w('В6') == 'W6'  # русская В → W
    print('  normalize_w: OK')

    print('\n✓ Все тесты пройдены.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='SHINCERTIFICATE — водонепроницаемость бетона',
    )
    parser.add_argument('--test', action='store_true',
                        help='запустить автотест расчётов')
    args = parser.parse_args()

    if args.test:
        run_test()
    else:
        run_gui()
