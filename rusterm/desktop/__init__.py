"""Десктопное окно EquityLab на PySide6 (TASK-C1, ADR-0004/ADR-0023).

Только чтение: данные собирает data.py через ту же модель экранов,
что и TUI (rusterm/tui/model.py); Qt живёт ровно в window.py и
charts.py, ядро о Qt не знает. Пакет импортируется и без PySide6 —
окно честно откажется словами (см. __main__.py).
"""
