"""노출 상태 규칙과 조회 우선순위 — 시트를 건드리지 않는 순수 함수만 둔다(테스트 대상).

상태 4가지
  Y  지금 통합검색에 떠 있다
  W  대기 — 발행 후 w_grace_days(기본 21일) 안이고 아직 안 떴다
  N  유예가 끝날 때까지 한 번도 안 떴다 (실패)
  D  떴다가 빠졌다 — 다시 뜰 때까지 D 를 유지한다 (최우선 재작업 신호)

21일인 이유(실측 47,005건): 한 번도 안 뜬 채 7일이 지난 글의 39%가 그 뒤에 떴다.
7일에 N 을 박으면 열에 넷을 잘못 죽인다. 21일이면 그 뒤에 뜨는 건 5.4%다
(14일 25.9% · 28일 2.4%).
"""
from __future__ import annotations

from datetime import date

from checker.sheet import norm, parse_date


def next_status(cur: str, exposed: bool, age_days, grace: int) -> str:
    cur = (cur or "").strip().upper()
    if exposed:
        return "Y"
    if cur in ("Y", "D"):
        return "D"
    if cur in ("", "W"):
        if age_days is None or age_days < grace:
            return "W"            # 날짜를 못 읽으면 유예를 계속 준다
        return "N"
    return "N"


def is_dead(row: dict, cfg: dict) -> bool:
    """되살아날 수 없는 행 — 폐쇄 카페 또는 글이 전부 지워진 아이디."""
    url, venue = row.get("url", ""), norm(row.get("venue", ""))
    for c in cfg.get("dead_cafes", []):
        if c and (c in url or norm(c) in venue):
            return True
    return row.get("uid", "") in set(cfg.get("dead_ids", []))


def select_rows(rows: list, today: date, cfg: dict, only_keys: set = None) -> list:
    """조회할 행을 우선순위 순으로 고른다.

    네이버는 한 번 실행에 고유 키워드 약 500개에서 막는다. 값이 바뀔 가능성이
    높은 행부터 쓴다.
      1순위: 노출여부 빈칸·W, 또는 발행 fresh_days(30일) 이내
      2순위: 발행 recent_days(60일) 이내, 또는 지금 Y
      3순위: 나머지 N·D — 단 old_days(90일) 넘은 N·D 는 일요일에만
    같은 순위 안에서는 아래(최신) 행부터.
    only_keys={(띄어쓰기 지운 키워드, URL)} 를 주면 그 행만 고른다(--resume).
    행번호가 아니라 키워드+URL 로 찾는다 — 행이 끼워지거나 지워져도 안 어긋난다.
    """
    picked = []
    for r in rows:
        if not r["url"].startswith("http") or is_dead(r, cfg):
            continue
        if only_keys is not None:
            if (norm(r["keyword"]), r["url"]) in only_keys:
                picked.append((0, -r["row"], r))
            continue
        d = parse_date(r["date"])
        age = (today - d).days if d else None
        st = r["status"]
        if st in ("", "W") or (age is not None and age <= cfg["fresh_days"]):
            tier = 0
        elif st == "Y" or (age is not None and age <= cfg["recent_days"]):
            tier = 1
        else:
            if age is not None and age > cfg["old_days"] and today.weekday() != 6:
                continue
            tier = 2
        picked.append((tier, -r["row"], r))
    picked.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in picked]
