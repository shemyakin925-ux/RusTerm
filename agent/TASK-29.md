# TASK-29 — Ключи в окружении: приёмка снова обязана быть зелёной

- **Status: ACCEPTED** 14.09.2026 — journal `agent/ACCEPTANCE-30.txt`; acceptance 13/13 on `agent/night-10`, merged into `main`.
- **Report:** `agent/REPORT-29.md`
- **Protocol:** `agent/PROTOCOL.md` (read once per shift, it outranks
  this file). State of the project: `agent/CONTEXT.md`.
- **Budgets:** network 0, model 0. Nothing here needs either.
- **Goal in one sentence:** the keys arrived on 13.09.2026 and the suite
  went red on the machine that has them — three tests fail, one of them
  by making a **live model call**, and a real key printed itself into
  pytest output; tonight having a key stops being a failure mode.

## 0. What the coordinator measured, so you do not re-measure it

On `main` (`616173c`), with the user's real `~/.rusterm.env` present:

```
FAILED tests/test_llm_api.py::test_build_without_key_is_config_error
FAILED tests/test_llm_real.py::test_m5_real_model_skips_without_key
FAILED tests/test_ops.py::test_d7_d8_ops_command_audit_rows_confirm_and_json_keys
```

With no key file the same tree is green. Causes, in order:

1. `tests/test_llm_real.py`, `tests/test_edgar.py` and
   `tests/test_refresh_live.py` call `env.load_env()`, which **writes
   into the real `os.environ` by contract** and is not restored
   afterwards (only `tests/test_env.py` has the restoring fixture). A
   later test that asserts «no key → ConfigError» then sees a key.
2. `tests/test_ops.py` runs the CLI as a subprocess; with a key present
   `cmd_ops` takes the API path and **actually called OpenRouter**. The
   answer was not JSON and the command exited 1.
3. `tests/test_llm_real.py` is a tripwire from TASK-9 V7: with a key it
   calls `pytest.fail("ключ задан, а живой путь M5 не реализован")`.
4. The failure message of (1) printed the user's real key prefix into
   pytest output. Under CI or in a report that is a leak.

## 1. Items

### A1. Ни один тест не читает настоящий `~/.rusterm.env`

**Zone:** `tests/conftest.py` (new), `tests/test_env.py`.

An autouse fixture points `RUSTERM_ENV_FILE` at an empty file inside
`tmp_path` and clears every name in `env.ENV_NAMES` from `os.environ`
before each test, restoring both afterwards. A test that wants a value
sets it itself (`monkeypatch.setenv`), as most already do. The existing
restoring fixture in `test_env.py` stays — it is not replaced by the
global one, it is covered by it.

**Done when:** with the real key file present, `python3 -m pytest -q` is
green; with `RUSTERM_ENV_FILE` pointed at a file holding a fake key, the
suite is still green; `tests/test_env.py` still proves that `load_env`
writes into the environment (its contract is unchanged).

### A2. Сеть в наборе — только по явному маркеру

**Zone:** `pyproject.toml`, `tests/test_ops.py`, the live tests.

- A `live` marker is registered and `addopts` carry `-m "not live"`, so
  the default run collects no test that can reach the network.
- Every test that can make a request — `test_edgar.py`,
  `test_refresh_live.py`, `test_llm_real.py` and any successor — carries
  it.
- `tests/test_ops.py` stops depending on what is in the environment: it
  drives the rule client explicitly, or injects a fake transport. A
  subprocess test passes an environment it built itself.

**Done when:** with all four keys set, a default run makes **zero**
requests — proven by a counter or a transport that raises on use, not by
inspection; `python3 -m pytest -m live --collect-only -q` lists exactly
the marked tests and their count is stated in the report.

### A3. Растяжка V7 перестаёт падать от наличия ключа

**Zone:** `tests/test_llm_real.py`.

The tripwire was right when a key was impossible; it is wrong now. Two
permitted resolutions, and you pick with a reason in the report:

- the live M5 path is implemented behind the `live` marker (maximum 2
  model calls, every numeric claim cited, a mass operation executes
  nothing) — this is the contract from TASK-7 T16; or
- the test keeps the contract but becomes `live`-marked and skips by
  default, and the debt it guards is written into
  `agent/BACKLOG.md` by name.

**Done when:** neither a present key nor an absent one makes a default
run red, and the report quotes both runs.

### A4. Значение ключа не попадает в вывод

**Zone:** `rusterm/providers/llm_api.py`, `tests/test_secrets_absent.py`.

`LlmApiClient.__repr__` masks `api_key` (`sk-or-***`), and the same rule
covers any dataclass that carries a secret. The existing secret guard
gains a case: the repr of a client built with a fake key contains no
part of it beyond the four-character prefix.

**Done when:** a test constructs the client with
`sk-or-v1-TESTONLY000000` and asserts the fake value is absent from
`repr()`, from a formatted assertion message and from the audit log;
`python3 -m pytest -q 2>&1 | grep -c "sk-or-v1-TESTONLY"` is 0.

### A5. Приёмка с ключами в окружении

**Done when:** `bash agent/acceptance.sh` is 13/13 **while the real key
file is in place**, and the report carries the «Итог» line and the exit
status captured before any pipe.
