#!/usr/bin/env python3
"""Download ASX annual reports (PDF) for all listed companies.

Free public sources only (ADR-0018):
  company list  https://www.asx.com.au/asx/research/ASXListedCompanies.csv
  yearly index  https://www.asx.com.au/asx/v2/statistics/announcements.do
  PDF           https://announcements.asx.com.au/asxpdf/...

Resumable: done items are logged in <out>/_done.txt; rerun continues.
Stdlib only. Run at low priority:

  nice -n 19 python3 tools/asx_annual_reports.py \
      --out "/Volumes/KINGSTON/LLM adaptation/AU" --from 2016 --to 2026
"""
import argparse, csv, html, io, os, re, sys, time, urllib.request

BASE = "https://www.asx.com.au"
UA = {"User-Agent": "Mozilla/5.0 (research; personal archive)"}
KEEP = re.compile(r"annual (financial )?report", re.I)
DROP = re.compile(r"notice|letter|proxy|governance|lodg|sustainab|"
                  r"availability|online|access|cleansing|reminder", re.I)


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))


def companies():
    text = get(BASE + "/asx/research/ASXListedCompanies.csv").decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    return [r[1] for r in rows if len(r) >= 2 and re.fullmatch(r"[A-Z0-9]{3,6}", r[1])]


def reports(code, year):
    url = (f"{BASE}/asx/v2/statistics/announcements.do?by=asxCode"
           f"&asxCode={code}&timeframe=Y&year={year}")
    page = get(url).decode("utf-8", "replace")
    for row in re.findall(r"<tr.*?</tr>", page, re.S):
        ids = re.search(r"idsId=(\d+)", row)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", row))).strip()
        if ids and KEEP.search(text) and not DROP.search(text):
            date = re.search(r"(\d\d)/(\d\d)/(\d{4})", text)
            d = f"{date[3]}-{date[2]}-{date[1]}" if date else str(year)
            title = re.sub(r"^\S+ \S+ [ap]m |\s*\d+ pages?.*$", "", text)
            yield ids[1], d, title


def pdf_url(ids):
    page = get(f"{BASE}/asx/v2/statistics/displayAnnouncement.do?display=pdf&idsId={ids}")
    if page[:4] == b"%PDF":
        return None, page
    m = re.search(rb'name="pdfURL" value="([^"]+)"', page)
    return (m[1].decode() if m else None), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--from", dest="y0", type=int, default=2016)
    ap.add_argument("--to", dest="y1", type=int, default=2026)
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--codes", help="comma list, e.g. BHP,CBA (default: all)")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    done_path = os.path.join(a.out, "_done.txt")
    done = set(open(done_path).read().split()) if os.path.exists(done_path) else set()
    log = open(done_path, "a")
    codes = a.codes.split(",") if a.codes else companies()
    print(f"{len(codes)} companies, years {a.y0}-{a.y1}", flush=True)

    for n, code in enumerate(codes, 1):
        for year in range(a.y0, a.y1 + 1):
            key = f"{code}:{year}"
            if key in done:
                continue
            try:
                for ids, d, title in reports(code, year):
                    if ids in done:
                        continue
                    time.sleep(a.pause)
                    url, data = pdf_url(ids)
                    if url:
                        time.sleep(a.pause)
                        data = get(url)
                    if not data or data[:4] != b"%PDF":
                        print(f"  skip {code} {ids}: not a PDF", flush=True)
                        continue
                    folder = os.path.join(a.out, code)
                    os.makedirs(folder, exist_ok=True)
                    name = re.sub(r"[^\w\-]+", "_", title[:80]).strip("_")
                    with open(os.path.join(folder, f"{d}_{ids}_{name}.pdf"), "wb") as f:
                        f.write(data)
                    log.write(ids + "\n"); log.flush(); done.add(ids)
                    print(f"  {code} {d} {len(data)//1024}KB", flush=True)
                log.write(key + "\n"); log.flush(); done.add(key)
            except Exception as e:
                print(f"  error {key}: {e}", file=sys.stderr, flush=True)
            time.sleep(a.pause)
        print(f"[{n}/{len(codes)}] {code}", flush=True)


if __name__ == "__main__":
    main()
