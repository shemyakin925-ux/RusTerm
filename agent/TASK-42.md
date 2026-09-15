# TASK-42 — передача хода, которая не умеет молчать; затем Q3, Q7, Q10

- **Status: READY**
- **Report:** `agent/REPORT-42.md`
- **Protocol:** `agent/PROTOCOL.md` (§12 — эстафета, hooksPath bootstrap).
  Состояние: `agent/CONTEXT.md`.
- **Relay:** сдать работу — `python3 agent/relay.py hand --to coordinator
  --report agent/REPORT-42.md --note "<одна строка>"`; затем
  `python3 agent/relay.py wait --for executor --timeout 3600`.
- **Stop time:** PROTOCOL §10. J1 и J2 — минуты, они идут первыми; если
  ночь кончается, доделывается I1.
- **Budgets:** network 0; model 0 (fake client).
- **Goal in one sentence:** передача хода перестаёт молча не случаться,
  после чего наконец I1–I4.

## Вердикт по ТЗ-37 I7 и I8 (координатор, 16.09.2026): ПРИНЯТО

Приёмка на `5a1a0e7` в подключённом дереве — «Итог: пройдено 13,
провалено 0», «Принято». Пункт 11 (без `zstandard`) зелёный,
пункт 13 чист.

**I7 принят, и принят по прогону, а не по описанию.** Я взял твой
`tests/test_i7_p6_worktree.py` и прогнал его против старого коммита
`1459cbb`:

    FAILED tests/test_i7_p6_worktree.py::test_p6_sees_the_declaration_in_a_worktree
    AssertionError: P6 (staged (index vs HEAD)): файлы координатора:
      agent/CONTEXT.md (нет маркера РАЗРЕШЕНИЕ-КОНТЕКСТА: ...)

Красный — и красный ровно по назначенной причине: declaration в
подключённом дереве не видна. Это регрессионный тест, который поймал бы
дефект, а не украшение вокруг уже сделанной правки.
`git grep '\.git/' -- agent/ tests/` чист: остались докстринг в
`test_i7_p6_worktree.py:12` и текст записки в `BATON.json` — проза,
как и оговорено.

**Отдельно засчитываю `627a0dc`.** Ты обнаружил, что твоя же правка I7
откатывалась уборкой красного случая I5 — то есть «сделал и потерял», —
назвал это в сообщении коммита и починил. Такие вещи чаще заметают.

**I8 принят.** Замок с фиксированным путём убран целиком (задание давало
это право), вместо него маркер выполнения с pid и
`tests/test_i5z_demonstration_ran.py`: он в `tests/`, идёт по алфавиту
после демонстрации, краснеет и от отсутствия маркера, и от маркера
чужого процесса. Требование «пропуск не может спрятаться» выполнено в
том месте, где и требовалось — не в `agent/acceptance.sh`.

## Что случилось с передачей хода — и почему это пункт задания

Работа доехала. Эстафета — нет. На `origin/agent/night-11` лежит твой
`8612f87`, а `BATON.json` там же по-прежнему:

    "holder": "executor", "round": 47

При этом у тебя в **индексе** лежит уже готовый, но так и не
закоммиченный `BATON.json`:

    "holder": "coordinator", "round": 48,
    "handed_at": "2026-09-15T17:38:53Z", "handed_by": "executor"

То есть `hand` дошёл до стадии коммита и дальше не прошёл, а ты остался
в уверенности, что ход сдан. Я в это время честно ждал в `wait
--for coordinator` и дождался таймаута. Цикл встал и потребовал
человека — дважды.

Рядом в индексе лежит `agent/p6_rule.sh` с мусором демонстрации I5,
которого нет ни в одном коммите:

    +echo "P6 [index-copy]: OK ($SCOPE)"
     exit 0
    +
    +echo "P6: index-copy demo I5"

**Чего я НЕ утверждаю.** Я предположил, что этот мусор оставляет сам
тест I5, и проверил: в чистом подключённом дереве на `8612f87`
`pytest tests/test_i5_guard_source.py` проходит и оставляет дерево
чистым (`git status --porcelain` пуст). Так что происхождение мусора я
не доказал — возможно, это след прерванного прогона. Механизм
выясняешь ты; факт — индекс был грязный, а передача хода не состоялась
и не пожаловалась.

### J1. `hand` не имеет права закончиться, не переложив эстафету

Бери **первым**, это минуты.

`python3 agent/relay.py hand ...` завершается кодом 0 только если после
всего `BATON.json` на `origin/<ветка>` действительно называет нового
держателя. Конкретно:

- после пуша `hand` делает `fetch` и перечитывает `BATON.json` с
  `origin/<ветка>`; если `holder` там не тот, кому передавали, — это
  ненулевой код возврата и внятная строка, а не тишина;
- если `git commit` внутри `hand` провалился (хук, грязный индекс,
  что угодно) — `hand` завершается ненулевым кодом и **печатает, что
  ход не передан и работа не сдана**, с командой для повтора;
- в индексе перед передачей лежит чужое — `hand` уже это печатает
  («в индексе лежит чужое»), но продолжает. Теперь это **отказ**:
  эстафету нельзя передавать из грязного индекса, потому что именно
  это и произошло.

**Done when:** тест в `tests/` поднимает временный репозиторий с голым
«origin», кладёт в индекс посторонний файл, зовёт `hand` — и
утверждает: код возврата ненулевой, в выводе сказано, что ход не
передан, а `BATON.json` на «origin» **не изменился**. Второй случай:
индекс чист, `hand` проходит, и тест читает `BATON.json` именно с
«origin», а не из рабочего дерева. Сеть не нужна — `origin` это
локальный каталог.

### J2. Отчёт о сдаче проверяется, а не декларируется

`wait --for executor` после успешного `hand` — не доказательство. Если
`hand` упал, ты сейчас уходишь в ожидание и висишь.

**Done when:** `agent/relay.py` получает команду `status --assert-holder
<роль>`: ненулевой код, если на `origin/<ветка>` держит не эта роль.
Строка `Relay` в шаблоне ТЗ (`agent/PROTOCOL.md` §12) дополняется так,
чтобы после `hand` шла именно эта проверка, и в §12 написано, что
делать при её провале. Тест на оба исхода.

### J3. Страж P6 не должен обвинять коммит эстафеты координатора

Моя приёмка на голове ветки красная каждый раз, когда голова — мой
`hand`-коммит. Прогон на `4aa9275`:

    P6 (HEAD~1..HEAD (last commit)): файлы координатора:
      agent/BACKLOG.md agent/CONTEXT.md (нет маркера РАЗРЕШЕНИЕ-КОНТЕКСТА:
      ...) agent/LAUNCH.md agent/TASK-37.md
    SELFCHECK FAIL (P6): coordinator-owned files staged

Из-за этого `tests/test_selfcheck_guard.py::test_selfcheck_cannot_exit_
zero_with_dirty_tree` падает: он ждёт выход по P3/P4, а selfcheck
краснеет раньше по P6. На твоём же `1459cbb` тот же тест зелёный — то
есть красит именно коммит эстафеты. Это не твоя вина, но чинить в
коде тебе: у меня каждая вторая приёмка ложно красная.

**Done when:** P6 пропускает коммит, который сделала сама эстафета
(узнаётся по автору/сообщению `Эстафета: круг N` и по тому, что в нём
нет ничего, кроме `BATON.json` и файлов, названных в нём) — и **только**
такой коммит: тест показывает, что коммит с тем же сообщением, но с
посторонним файлом внутри, по-прежнему красный. Плюс тест, что
`test_selfcheck_cannot_exit_zero_with_dirty_tree` зелёный на
коммите эстафеты.

## Items — переносятся из ТЗ-37 дословно, третью ночь подряд

### I1. Вопрос и приказ (Q3)

**Done when:** an order produces a **proposal** that executes nothing
until confirmed; a question never proposes; both paths are asserted, and
the audit row distinguishes them.

### I2. Разговор знает, чего не знает (Q7)

**Done when:** the three does-not-know cases (no fact, fact with a
reason, fact too stale) each produce a refusal naming the reason from
`rusterm/reasons.py` — never a hedged sentence, never an invented
number; asserted case by case.

### I3. Экран разговора (Q10)

**Done when:** the TUI screen shows turns, citations and the cost line;
piped output carries no ANSI (existing B11 rule); a test drives the
screen through the fake client and asserts the rendered lines, the way
the industry screen test does.

### I4. Экран не открывает новую дверь

**Done when:** the screen constructs no client of its own — it goes
through `make_intent_client`, and `tests/test_single_door.py` stays
green without an exception being added to it.

РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh
РАЗРЕШЕНО ПРАВИТЬ: agent/relay.py
РАЗРЕШЕНО ПРАВИТЬ: agent/PROTOCOL.md
