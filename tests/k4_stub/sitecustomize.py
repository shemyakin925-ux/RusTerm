"""Пауза демо-индекса для теста K4 (ТЗ-84: два процесса на одной базе).

Подключается автоматически, когда PYTHONPATH дочернего процесса указывает
на этот каталог, и действует только при заданной RUSTERM_K4_POLL_PAUSE:
без переменной файл не меняет ничего.

Зачем она нужна (измерено): `source_cursor` синтетического источника
общий на всю базу, поэтому второй процесс инжеста приходит на уже
записанный курсор, не находит новых записей индекса и не делает ни одной
записи в базу. В таком виде тест не краснеет ни от «busy timeout
0.001 с вместо 30», ни от выключенной дедупликации заданий — то есть не
проверяет замок вообще. Пауза стоит после того, как источник вернул
индекс, но до записи курсора: оба процесса видят устаревший курсор и
пишут одновременно. Путь продукта при этом не подменён — ни один шаг
конвейера не пропущен, изменён только темп одного обращения к источнику.
"""
import os
import time

_PAUSE = float(os.environ.get("RUSTERM_K4_POLL_PAUSE") or 0)

if _PAUSE > 0:
    import rusterm.providers.disclosures as _disclosures

    _real_poll = _disclosures.SyntheticDisclosuresProvider.poll_index

    def _poll_then_pause(self, cursor):
        outcome = _real_poll(self, cursor)
        time.sleep(_PAUSE)
        return outcome

    _disclosures.SyntheticDisclosuresProvider.poll_index = _poll_then_pause
