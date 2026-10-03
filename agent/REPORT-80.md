# REPORT-80 — страж, который не смотрит на голову ветки, и три дневника отказа

No deviation from the brief: branch `agent/night-11`, the same clone as
TASK-76/78/79, `core.hooksPath agent/githooks` set once,
`relay.py wait --for executor` exit 0 at round 107 before the first line
of code.

Arrival state: HEAD `f8534a4`, baton "Эстафета: круг 107, ход у
executor — agent/TASK-80.md", Z1 returned and already repaired by the
coordinator (`_log_from_top_marker(log, round_no)`).

## Done

- **A1 — the guard does not look at the branch head.**
  - Rule written into the module docstring, one line:
    «страж не вправе зависеть от того, сколько кругов прошло после его
    написания».
  - `_log_from_top_marker(log, round_no)` — the round number became a
    **required** argument. The optional form was the only callable way
    to cut by "the newest marker", so the shape that caused the Z1
    return is now not reproducible by accident;
    `test_the_helper_refuses_to_cut_by_the_newest_marker` pins the
    signature (no default, annotation is `int`, not `Optional[int]`).
  - Simulation tooth `test_the_window_survives_rounds_passing_after_the_
    test_was_written`: the live log is taken as is, then 1, 2 and 5
    artificial blocks `Эстафета: круг <top+1> … <top+5>` are pasted on
    top — a faithful picture of "the branch keeps moving" — and the
    four probes of round 104's window must return the table measured in
    Z1 (`Y1,Y2 -> []`, `W1,W5 -> ['W1','W5']`, `W3 -> ['W3']`,
    `Z9 -> ['Z9']`) in every shape. The numbering helper reads the
    newest marker only to name the fake rounds; no assertion is cut by
    it, which is exactly what the red run below demonstrates.

  **Redness on the pre-fix rule, quoted.** `_log_from_top_marker`
  temporarily reverted in the working tree to "return from the first
  marker block it sees" (the version that was green for the executor and
  red at acceptance), same command:

  ```
  $ python3 -m pytest tests/test_report_sections.py -o addopts='--strict-markers -m "not live"' -p no:randomly -q -k "survives_rounds"
              for count in (1, 2, 5):
                  moved = _window_of_round_104(_rounds_later(log, count))
                  assert moved == WINDOW_OF_ROUND_104, (
                      f"через {count} круг(ов) сверху окно круга 104 изменилось: "
                      f"{moved}")
  E           AssertionError: через 1 круг(ов) сверху окно круга 104 изменилось: {('Y1', 'Y2'): ['Y1', 'Y2'], ('W1', 'W5'): ['W1', 'W5'], ('W3',): ['W3'], ('Z9',): ['Z9']}
  E           assert {('Y1', 'Y2')...Z9',): ['Z9']} == {('Y1', 'Y2')...Z9',): ['Z9']}
  tests/test_report_sections.py:699: AssertionError
  =========================== short test summary info ============================
  FAILED tests/test_report_sections.py::test_the_window_survives_rounds_passing_after_the_test_was_written
  1 failed, 27 deselected in 0.19s
  ```

  One simulated round is enough to lose Y1 and Y2. The file was then
  restored from a `/tmp` copy and the whole thing went green:
  `28 passed`. In that same mutated run `test_strictness_holds_on_the_
  real_branch` was red too — the coordinator's symptom, reproduced
  without touching their test.

- **A1, first bullet — every live-state read in the file, named.**
  Reading of `git log` by helper call, classed as *literal* (fixed
  text), *bound to round N* (the slice is given by a number) or *bound
  to the round in BATON.json*:

  | тест | источник | привязка среза |
  |---|---|---|
  | `test_done_items_have_code_commits_in_round` | живой лог + живой отчёт | круг `_round_under_review()` (из BATON.json) |
  | `test_w3_is_not_closed_by_a_foreign_round_on_the_real_branch` | живой лог | круг `_baton_round()`; `W3` — литерал пункта |
  | `test_z9_teeth_still_hold_under_the_round_bound` | живой лог | круг `_baton_round()` |
  | `test_strictness_holds_on_the_real_branch` | живой лог | круг 104 (литерал номера) |
  | `test_the_window_survives_rounds_passing_after_the_test_was_written` | живой лог + 1/2/5 приписанных кругов | круг 104 (литерал номера) |
  | `test_last_handoff_does_not_call_committed_items_undone` | живой лог через `_commit_for_items` | круг `_baton_round()` |
  | `test_last_handoff_decides_and_the_interim_one_is_ignored` | живой лог | круг 76 (подменённый `_baton_round`) |
  | `test_stale_report61_handoff_reds_the_guard` | живой лог | круг 76 (литерал) |
  | `test_merged_handoff_would_red_g4_retrospectively` | живой лог | круг 76 (литерал) |
  | `test_round_under_review_and_live_baton_agree` | живой `BATON.json`, лога не читает | круг и holder из baton |
  | `test_round_under_review_shifts_when_the_holder_is_coordinator` | подставный `REPO`/`BATON.json` | литералы 105/1 |
  | `test_l3_flags_an_item_that_no_commit_carries`, `test_l2_staged_fallback_only_opens_for_a_non_test_file` | живой лог БЕЗ границы круга | см. «What not to trust» |
  | всё остальное (`FAKE_LOG*`, `TWO_HANDOFFS`, `FAKE_LOG_ACCEPTANCE_SHAPE`, тесты `_l3_missing` на фейковых логах, секционные тесты) | литералы; секционные читают живой отчёт, а не историю | — |

## Blocked

- Nothing blocked yet; A2, A3 and A4 are still ahead.

## What not to trust

- Two teeth of TASK-76 W1 — `test_l3_flags_an_item_that_no_commit_carries`
  and `test_l2_staged_fallback_only_opens_for_a_non_test_file` — scan the
  live log with **no** round bound. They stay true only while `Z9` is a
  fictitious item name; if a future ТЗ numbers an item Z9, both tests
  redden on a real commit. A5 forbids rewriting the TASK-76/78/79 teeth,
  so I left them and name the exposure instead of silencing it. The
  cheap fix belongs to whoever owns those teeth next: pass a literal
  round number that is known not to contain Z9.
- The simulation test pins the round-104 table. If the branch were ever
  rewritten (it must not be — history is append-only), the literals
  would need re-measuring; nothing in the test notices a rewrite.
- The red quote above comes from a working-tree mutation restored before
  the commit; `git show` of the committed file has the fixed helper.
- The full suite has not been re-run for A1 alone; the file itself is
  `28 passed`, and `hand` re-runs everything in a clean clone.

## Disputed

- (none yet this circle)

## HANDOFF

Status: PARTIAL — A1 done and committed, A2/A3/A4 ahead.
Arrival state: round 107, HEAD `f8534a4`, TASK-80 read in full.
Items not done: A2 relay output, A3 linked worktree artifact, A4 quote
versus grant in the Z2 guard.
NOW: A4, step 1

## Done #2 — A4 (appended; the sections above stay as written)

- **A4 — the Z2 guard no longer mistakes a quote for a grant.**
  `tests/test_task_authorization_form.py`: `_claimed_paths()` now skips
  every occurrence of the phrase that sits inside backticks (odd number
  of `` ` `` before it) or inside guillemets (more « than » before it);
  a line that *starts* with the phrase remains a claim, exactly as
  before, so nothing about real authorizations got looser. Three tests
  added (`8 passed` in the file): the coordinator's own verdict paragraph
  verbatim from `ca678a1` must be clean, the same form outside quotes
  must be red, and a flat grant standing next to a quote must still be
  recognized.

  **Redness of the first case before A4, quoted** (`_is_quoted()`
  temporarily forced to `return False` in the working tree — the pre-A4
  shape — and restored from a `/tmp` copy before the commit):

  ```
  $ python3 -m pytest tests/test_task_authorization_form.py -o addopts='--strict-markers -m "not live"' -p no:randomly -q
  _______________ test_a_quoted_broken_form_is_not_read_as_a_grant _______________
          f.write_text(VERDICT_QUOTING_THE_BROKEN_FORM, encoding="utf-8")
  >       assert _unaccepted(f) == [], _unaccepted(f)
  E       AssertionError: [('2', '`РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md, GUIDE.md` делала `GUIDE.md`', ['agent/CONTEXT.md', 'GUIDE.md', 'GUIDE.md']), ('6', 'Тот же разбор в кавычках-ёлочках: «РАЗРЕШЕНО ПРАВИТЬ: GUIDE.md».', ['GUIDE.md'])]
  ______________ test_the_flat_form_is_still_a_grant_after_a_quoted_one __________
  >       assert len(bad) == 1, bad
  E       AssertionError: [('1', 'В разборе: `РАЗРЕШЕНО ПРАВИТЬ: agent/CONTEXT.md` — это цитата.', ['agent/CONTEXT.md']), ('2', 'РАЗРЕШЕНО ПРАВИТЬ: `agent/CONTEXT.md`', ['agent/CONTEXT.md'])]
  =========================== short test summary info ============================
  FAILED tests/test_task_authorization_form.py::test_a_quoted_broken_form_is_not_read_as_a_grant
  FAILED tests/test_task_authorization_form.py::test_the_flat_form_is_still_a_grant_after_a_quoted_one
  2 failed, 6 passed in 0.15s
  ```

  **Both cases measured after the fix**, the checker called directly on
  three texts:

  ```
  цитата (вердикт координатора, ca678a1):      нарушений: 0
  настоящая сломанная форма (ТЗ-76/78):         нарушений: 1
     :1 '- **РАЗРЕШЕНО ПРАВИТЬ:** `tests/test_report_sections.py`,' -> ['tests/test_report_sections.py']
  настоящее разрешение (плоская форма):        нарушений: 0
  ```

- Deliberate limit stated in the module docstring, one paragraph, so the
  next reader does not mistake it for a hole: a continuation line (paths
  on the line after the authorization, without the phrase — the old
  TASK-73 shape) is still not caught, because the parser does not see
  those either and guessing which file lists were meant as permissions
  would redden the guard on prose.

## Blocked #2

- Nothing blocked. A2 and A3 remain ahead.

## What not to trust #2

- The quote rule looks at backtick and guillemet parity **within one
  line**. A broken form quoted inside a fenced code block (``` fences
  spanning lines) has even parity per line and would still be read as a
  claim. TASK files do not use fenced blocks today; if one ever does,
  the guard will red loudly rather than silently pass.
- `VERDICT_QUOTING_THE_BROKEN_FORM` is a literal copy of a historical
  file version (`git show ca678a1:agent/TASK-80.md`, line 25), not a
  live read of TASK-80 — later edits to the coordinator's ТЗ cannot
  break this tooth, and the same paragraph still exists in git history.

## HANDOFF #2 (interim — supersedes the block above)

Status: PARTIAL — A1 and A4 done and committed; A2, A3 ahead.
Arrival state: round 107, HEAD `f8534a4`, TASK-80 read in full.
Items done: A1
Items not done: A2 relay output, A3 linked worktree artifact.
NOW: A2, step 1

## Done #3 — A2 (красноту приёмки видно без раскопок)

- **A2 — отказ `hand` называет упавшие тесты и путь к полному логу.**
  Изменён только `agent/relay.py`; `agent/acceptance.sh` не тронут —
  проверка 12 приёмки (`совпадает с origin/main`) зелёная в обоих
  прогонах ниже.
  - `run_acceptance()` гоняет приёмку так, что вывод идёт в терминал и
    построчно сохраняется в `<git-каталог>/relay-acceptance.log`. Лог
    лежит в git-каталоге этого дерева, а не в `/tmp`: два рабочих дерева
    на одной машине делят `/tmp` (CONTEXT §3, круг 56), и прогон
    координатора затёр бы прогон исполнителя — та же порода, из-за
    которой маркер I5 уехал в git-каталог (`5e050a4`).
  - `failed_test_names()` и `failed_checks()` срезают ANSI и забирают
    из вывода строки `FAILED …` и `ПРОВАЛ …`.
  - `pytest_failure_names()` — перечитывающий прогон
    `pytest -q --tb=no -rf`, когда приёмка имён не показала (она
    печатает три последние строки прогона, и при нескольких падениях
    туда попадает не всё). Замерен на отдельном каталоге с двумя
    падающими тестами, где в поданный «вывод приёмки» имён не
    попало вообще:

        упавшие тесты:
          FAILED test_demo_fallback.py::test_alpha - assert 1 == 2
          FAILED test_demo_fallback.py::test_beta - AssertionError: assert 'x' == 'y'

**Краснота показана до заявления о починке.** Приёмку нельзя сделать
красной, не сделав красным дерево, поэтому в дереве лежал черновой
`tests/test_a2_demo_red.py` с двумя падающими тестами — после демонстра-
ции удалён, в коммит не попал. `hand` вызван с именем ветки, которого
нет на origin: шлюз приёмки стоит до любого обмена с origin, так что
даже зелёное дерево не сдвинуло бы эстафету. Отказ дословно:

    relay: приёмка на дереве красная (код возврата 3) — ход не передан.
    упавшие тесты:
      FAILED tests/test_a2_demo_red.py::test_a2_demo_alpha - assert 1 == 2
      FAILED tests/test_a2_demo_red.py::test_a2_demo_beta - AssertionError: assert ...
      FAILED tests/test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green
    проваленные проверки приёмки:
      ПРОВАЛ pytest, код возврата 1
      ПРОВАЛ без zstandard код возврата 1 — фолбэк не реализован
      ПРОВАЛ работа или мусор вне git — файл, о котором отчитались, может не существовать в репозитории
    полный лог прогона: /private/tmp/rt-night11-exec/.git/relay-acceptance.log
    исправь и повтори hand

Прежде этот же отказ был одной строкой «приёмка на дереве красная —
ход не передан», и имена приходилось доставать повторным прогоном
вручную. Третья строка `FAILED` — не часть демонстрации: это замер
пункта A3, описан ниже.

## Blocked #3

Нет.

## What not to trust #3

- У новых помощников нет постоянного теста: файл тестов для `relay.py`
  не входит в список разрешённого на этом ТЗ, а тащить тесты relay в
  `tests/test_report_sections.py` — значит положить их не туда.
  Доказательство — цитаты выше, а не страж.
- Перечитывающий прогон `pytest_failure_names()` запускается только
  когда приёмка не показала ни одного имени; в демонстрации выше он не
  сработал (имена были), сработал на отдельном каталоге. Полного
  «красное дерево без имён» на живой ветке я не моделировал.

## Done #4 — A3 (артефакт подключённого дерева измерен и назван)

- **A3 — причина названа, и она не в подключённом дереве.** Замерян
  полный прогон: `python3 agent/relay.py --branch agent/night-11 verify`
  на голове ветки `f45e07d`, приёмка в свежем linked worktree
  (`/var/folders/…/T/rusterm-relay-verify`) — **зелёная**:

        3. pytest целиком
          OK    pytest, код возврата 0
        …
        Итог: пройдено 13, провалено 0
        Принято.
        код возврата приёмки: 0 (ПРИНЯТО)

  То есть `test_i5_staged_and_authorised_widening_is_green` в
  подключённом дереве НЕ падает. `.git` там — файл, но это ничего не
  ломает: предположение из ТЗ (и из `agent/CONTEXT.md` §3) — «`p6_rule.sh` читает
  `.git/COMMIT_EDITMSG` литералом, поэтому декларация в worktree
  невидима» — в коде отсутствует. Измерено на `f45e07d`:

        agent/p1_rule.sh:36:EDITMSG=$(git rev-parse --git-path COMMIT_EDITMSG …)
        agent/p6_rule.sh:75:EDITMSG=$(git rev-parse --git-path COMMIT_EDITMSG …)
        agent/p7_relay_rule.sh:25:   EDITMSG=$(git rev-parse --git-path COMMIT_EDITMSG …)
        agent/selfcheck.sh:59:       CMSG="$(git rev-parse --git-path COMMIT_EDITMSG …)"

  `--git-path` разрешает каталог конкретного дерева, так что
  worktree-слепых деклараций не осталось; **I7** уже приехал тестом
  `tests/test_i7_p6_worktree.py`. Абзац в `agent/CONTEXT.md` исправлен
  этим же коммитом (файл разрешён ТЗ).

- **Что действительно рвёт тест — мусор вне git в том дереве, где
  гонится приёмка.** Тот же тест, красная цитата (воспроизведено в
  обычном клоне, когда в дереве лежал черновой файл демонстрации A2):

        _______________ test_i5_staged_and_authorised_widening_is_green ________________
        tests/test_i5_guard_source.py:242: in test_i5_staged_and_authorised_widening_is_green
            assert result.returncode == 0, (
        E   AssertionError: I5: p1_rule.sh исполняется из HEAD
        E     I5: p6_rule.sh исполняется из index
        E     I5: p7_relay_rule.sh исполняется из HEAD
        E     P1: OK (HEAD~1..HEAD)
        E     ?? tests/test_a2_demo_red.py
        E     SELFCHECK FAIL (P3/P4): untracked files present - git add or delete them
        E   assert 1 == 0

  Цепочка: тест вызывает `bash agent/selfcheck.sh` (вложенно,
  `I5_NESTED=1`), а селфчек проверяет P3/P4 — «нет неотслеживаемых
  файлов» — по **внешнему** дереву. Любой `??` в нём, не связанный с
  тестом, делает случай красным.

- **Почему это ложно на подключённое дерево.** `cmd_verify` при
  существующем пути делает `checkout --detach` и `reset --hard` — то
  есть вычищает только отслеженное состояние; неотслеживаемые файлы
  переживают сброс. Путь по умолчанию — `tempfile.gettempdir() +
  "/rusterm-relay-verify"`, машинно-глобальный и переиспользуемый.
  Значит residue прошлого прогона остаётся лежать в дереве следующего,
  и случай I5 краснеет «в linked worktree, но не в обычном клоне» —
  ровно та формулировка, что в ТЗ. Проверено сбросом посреди прогона:
  `reset --hard` стёр застейдженое расширение стража (индекс до —
  `agent/p6_rule.sh`, после — пусто), сам тест при этом остался зелёным,
  так что сброс — не причина красноты, а источник residue — да.

- **Какой из двух предложенных путей выбран: ни один.** Тест не починен
  и не помечен `pytest.skip`: он не сломан, а краснеет по делу
  (приёмка и сама краснеет на проверке 13 по той же причине).
  Обходить молчанием мусор в дереве приёмки — значит потерять сигнал.
  Починка по-настоящему лежит в `cmd_verify` (не переиспользовать чужое
  дерево и не оставлять в нём residue) — это не разрешённое на ТЗ-80
  действие, и оно уехало в Disputed #3.

- **То же ложное объяснение жило вторым местом.** Абзац дневника круга
  в `agent/CONTEXT.md` («verify runs acceptance in a linked worktree,
  where test_i5… fails») повторял версию про литеральный
  `.git/COMMIT_EDITMSG`. Переписан тем же пунктом по замеру: случай
  краснеет от `??`-файла в дереве, где гонится приёмка, а наблюдение
  координатора «краснеет на незакоммиченных файлах координатора» — та
  же механика.

## Disputed #3

- `cmd_verify` принимает путь по умолчанию
  `tempfile.gettempdir()/rusterm-relay-verify` — один на всю машину, и
  при повторном вызове делает там `checkout --detach` + `reset --hard`,
  которые не убирают неотслеживаемые файлы. Достаточно одному прогону
  оставить в этом дереве `??`-файл, чтобы следующий круг получил
  красный случай I5 и ложный вывод про «подключённое дерево ломает
  приёмку». Просьба выдать отдельным пунктом разрешение на
  `agent/relay.py` в части `cmd_verify` (уникальный на дерево путь либо
  явная чистка с показом удалённого), потому что `git clean` в чужом
  рабочем дереве — операция с чужими файлами, и решать должен
  координатор.
- замер, которого у меня нет, — точный текст красной строки из
  прогона координатора. Моя гипотеза (residue в переиспользованном
  дереве) объясняет формулировку «в worktree красно, в клоне зелено»,
  но воспроизвести красноту именно под `verify` я не смог: свежее
  подключённое дерево на `f45e07d` прошло приёмку целиком (13/13). Если
  краснота была на другом коммите — назовите его, и я прогоню `verify`
  на нём.

## HANDOFF #3 (FINAL — supersedes the blocks above)

Status: DONE — все четыре пункта ТЗ-80 закрыты, очередь этого ТЗ пуста.

Items done: A1, A2, A3, A4
Items not done: нет.

Коммиты круга названы в темах (A1 — 6cf14ce, A2 — f3e8b92, A3 — коммит с правкой CONTEXT.md, A4 — f45e07d).
Каждый из двух последних коммитов прошёл pre-commit-селфчек: хук
красный не пропускает, и он был зелёный.

Что читать координатору: Disputed #3 — прошу разрешение на починку
`cmd_verify` (уникальный путь рабочего дерева либо явная чистка с
показом удалённого) и жду текст красной строки с коммитом, на котором
координатор видел красноту: на f45e07d приёмка в подключённом дереве
прошла целиком.

Дальше по очереди ТЗ-77 (бюджет 60 живых запросов выдан там), затем
ТЗ-73, затем ТЗ-74 — с новой эстафеты, под текущий network 0 я их не
беру.

NOW: TASK-80, шаг 1 — сдано
