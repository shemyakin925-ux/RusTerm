#!/usr/bin/env python3
"""
Архиватор сырых документов раскрытия — Фаза 0a.

Ничего не парсит. Скачивает заданные адреса и складывает тела в хранилище
с адресацией по sha256, а каждый запрос описывает строкой в манифесте.
Смысл: содержимое страниц эмитентов перезаписывается без следа, и историю
версий нельзя восстановить задним числом. Сохранённые байты разбираем потом.

Дедупликация по хешу даёт версионирование бесплатно: неизменившаяся страница
не занимает места повторно, а изменившаяся появляется как новый объект,
и по манифесту видно, когда именно она изменилась.

Только стандартная библиотека. Python 3.9+.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

UA = "RusTermArchiver/0.1 (personal research; +shemyakin925@gmail.com)"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_targets(path):
    """Файл целей: 'метка<TAB>url', либо просто url. # — комментарий."""
    targets = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t") if "\t" in line else line.split(None, 1)
            if len(parts) == 2:
                label, url = parts[0].strip(), parts[1].strip()
            else:
                url = parts[0].strip()
                label = url.split("//", 1)[-1].split("/", 1)[0]
            if not url.startswith(("http://", "https://")):
                print(f"  ! {path}:{lineno}: пропущено, не URL: {line}", file=sys.stderr)
                continue
            targets.append((label, url))
    return targets


def fetch(url, timeout):
    """Возвращает (status, body, ctype, error). Исключений не бросает."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, body, resp.headers.get("Content-Type", ""), None
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        return e.code, body, e.headers.get("Content-Type", "") if e.headers else "", None
    except Exception as e:                      # URLError, timeout, TLS, сокет
        return 0, b"", "", f"{type(e).__name__}: {e}"


def store_body(root, body):
    """Кладёт тело в store/<2 знака>/<sha256>. Возвращает (sha, is_new)."""
    sha = hashlib.sha256(body).hexdigest()
    d = os.path.join(root, "store", sha[:2])
    p = os.path.join(d, sha)
    if os.path.exists(p):
        return sha, False
    os.makedirs(d, exist_ok=True)
    tmp = p + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, p)
    return sha, True


def main():
    ap = argparse.ArgumentParser(description="Архиватор раскрытия, Фаза 0a")
    ap.add_argument("--targets", action="append", required=True,
                    help="файл со списком адресов; можно указать несколько раз")
    ap.add_argument("--root", required=True, help="корень хранилища (data/raw)")
    ap.add_argument("--delay", type=float, default=3.0, help="пауза между запросами, с")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--retries", type=int, default=1, help="повторов при сетевой ошибке")
    ap.add_argument("--limit", type=int, default=0, help="взять только первые N целей")
    ap.add_argument("--dry-run", action="store_true", help="показать цели и выйти")
    args = ap.parse_args()

    targets = []
    for t in args.targets:
        targets.extend(read_targets(t))
    if args.limit:
        targets = targets[:args.limit]
    if not targets:
        print("Целей нет — проверьте файлы --targets", file=sys.stderr)
        return 1

    if args.dry_run:
        for label, url in targets:
            print(f"{label}\t{url}")
        print(f"\nвсего целей: {len(targets)}")
        return 0

    root = os.path.abspath(args.root)
    os.makedirs(os.path.join(root, "manifest"), exist_ok=True)
    manifest = os.path.join(root, "manifest",
                            datetime.now(timezone.utc).strftime("%Y-%m") + ".jsonl")

    n_ok = n_new = n_err = 0
    started = time.time()
    with open(manifest, "a", encoding="utf-8") as mf:
        for i, (label, url) in enumerate(targets, 1):
            status = 0
            body = b""
            ctype = ""
            err = None
            for attempt in range(args.retries + 1):
                status, body, ctype, err = fetch(url, args.timeout)
                if err is None:
                    break
                if attempt < args.retries:
                    time.sleep(min(10.0, args.delay * 2))

            rec = {
                "ts": now_iso(), "label": label, "url": url,
                "status": status, "bytes": len(body),
                "ctype": ctype.split(";")[0].strip(), "error": err,
                "sha256": None, "new": False,
            }
            # тело сохраняем только у осмысленных ответов
            if status == 200 and body:
                sha, is_new = store_body(root, body)
                rec["sha256"], rec["new"] = sha, is_new
                n_ok += 1
                n_new += int(is_new)
                mark = "НОВОЕ" if is_new else "без изменений"
            elif err:
                n_err += 1
                mark = f"ошибка: {err}"
            else:
                n_err += 1
                mark = f"HTTP {status}"

            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            mf.flush()
            print(f"  [{i}/{len(targets)}] {label}: {mark}")

            if i < len(targets):
                time.sleep(args.delay)

    dt = time.time() - started
    print(f"\nитог: успешно {n_ok}, из них изменилось {n_new}, ошибок {n_err}, "
          f"за {dt:.0f} с")
    print(f"манифест: {manifest}")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
