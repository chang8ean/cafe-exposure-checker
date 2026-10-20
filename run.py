"""물길 노출 자동체크 — 하루 두 번 돌린다.

    python run.py              # 아침: 우선순위대로 판정 → 시트 반영
    python run.py --resume     # 오후: 아침에 차단으로 못 본 행만 이어서
    python run.py --dry-run    # 판정만 하고 시트에 아무것도 쓰지 않는다

한 번 실행에 하는 일 (순서가 중요하다 — 행 끼우기는 반드시 마지막)
  1. [물길] 읽기 → 조회할 행 고르기(우선순위)
  2. 네이버 모바일 통합검색으로 판정
  3. 노출여부(Y/W/N/D) 바뀐 것만 기록
  4. 내 글은 안 뜨는데 우리 다른 글이 떠 있으면 → 비고 기록
  5. 그 키워드를 잡은 글 묶음 아래에 서브 행 자동 추가
  6. [키워드] 탭 정렬(등급 → 점수 → 검색량)
차단으로 못 본 행은 state/날짜.json 에 (키워드, URL) 로 남겨 --resume 이 잇는다.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime

from checker import autosub, config, exposure, keyword_sort, rules
from checker.sheet import TAB_MG, norm, open_sheet, parse_date, read_mulgil, read_volumes, write_column

STATE_DIR = os.path.join(config.ROOT, "state")


def _state_path(d: date) -> str:
    return os.path.join(STATE_DIR, f"{d.isoformat()}.json")


def _load_keys(d: date):
    p = _state_path(d)
    if not os.path.exists(p):
        return set()
    with open(p, encoding="utf-8") as f:
        return {tuple(k) for k in json.load(f).get("unresolved", [])}


def _save_keys(d: date, keys: list):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(_state_path(d), "w", encoding="utf-8") as f:
        json.dump({"unresolved": sorted(set(keys))}, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true", help="아침에 못 본 행만")
    ap.add_argument("--dry-run", action="store_true", help="시트에 쓰지 않는다")
    ap.add_argument("--no-sort", action="store_true", help="[키워드] 정렬 생략")
    a = ap.parse_args()

    cfg = config.load()
    today = date.today()
    print(f"=== {datetime.now():%Y-%m-%d %H:%M} 노출체크 {'(이어서)' if a.resume else ''}"
          f"{' [dry-run]' if a.dry_run else ''}")
    sh = open_sheet(cfg)
    ws = sh.worksheet(TAB_MG)
    rows, idx = read_mulgil(ws)

    only = _load_keys(today) if a.resume else None
    if a.resume and not only:
        print("이어서 볼 행이 없습니다(아침에 다 봤거나 아침 실행 기록이 없음).")
    targets = rules.select_rows(rows, today, cfg, only_keys=only) if (only or not a.resume) else []

    # 우리 글 전체의 글번호 — 시트 위쪽(메인)이 먼저 잡히도록 setdefault
    owned = {}
    for r in rows:
        pid = exposure.extract_id(r["url"])
        if pid and len(pid) >= 6:
            owned.setdefault(pid, r)

    print(f"대상 {len(targets)}행 (고유 키워드 {len({norm(r['keyword']) for r in targets})}개)")
    checked = exposure.check_rows(targets, delay=cfg["delay_seconds"], owned=owned)

    updates, covered, unresolved = [], [], []
    newly, dropped, expired = [], [], []
    for r in checked:
        if r["exposed"] is None:
            unresolved.append((norm(r["keyword"]), r["url"]))
            continue
        if not r["exposed"]:
            for pid in r["others"]:
                covered.append({"row": r["row"], "bigo": r["bigo"],
                                "keyword": r["keyword"], "holder": owned[pid]})
        d = parse_date(r["date"])
        now = rules.next_status(r["status"], r["exposed"], (today - d).days if d else None,
                                cfg["w_grace_days"])
        if now == r["status"]:
            continue
        updates.append((r["row"], now))
        if now == "Y":
            newly.append(r)
        elif now == "D" and r["status"] == "Y":
            dropped.append(r)
        elif now == "N" and r["status"] in ("", "W"):
            expired.append(r)

    bigo = autosub.bigo_updates(covered, today)
    plan = autosub.plan(rows, covered, read_volumes(sh), today,
                        cfg["autosub_min_volume"], idx) if covered else []

    if not a.dry_run:
        write_column(ws, idx["노출여부"], updates)
        write_column(ws, idx["비고"], bigo)
        autosub.apply(ws, plan)          # 행 끼우기는 맨 마지막
        _save_keys(today, unresolved)
    srt = None if a.no_sort else keyword_sort.sort(sh, dry_run=a.dry_run)

    judged = len(checked) - len(unresolved)
    print(f"판정 {judged}/{len(checked)} · 변경 {len(updates)} · 신규Y {len(newly)} · "
          f"빠짐(Y→D) {len(dropped)} · 유예만료(→N) {len(expired)}")
    print(f"다른 글로 노출 {len({c['row'] for c in covered})}행 · 비고 {len(bigo)} · "
          f"자동 서브 {len(plan)}")
    for p in plan:
        print(f"   + 「{p['keyword']}」 → 「{p['holder']}」 묶음 아래")
    for r in dropped:
        print(f"   ↓ 빠짐: {r['row']}행 「{r['keyword']}」 {r['venue']}")
    if unresolved:
        print(f"판정불가 {len(unresolved)}행 — 차단이면 오후 --resume 이 이어 봅니다.")
    if srt:
        verb = ("재정렬함" if srt["written"] else "정렬 필요(dry-run)" if srt["violations"]
                else "이미 정렬됨")
        print(f"[키워드] 정렬: {verb} "
              f"({srt['rows']}행, 어긋남 {srt['violations']})")


if __name__ == "__main__":
    main()
