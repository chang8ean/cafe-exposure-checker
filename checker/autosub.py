"""중복 노출 처리 — 비고 기록 + 자동 서브 행 추가.

노출체크는 행마다 '이 행의 글이 이 키워드로 뜨나'만 본다. 그런데 내 글은 안 떠도
**우리 다른 글**이 그 키워드로 떠 있는 경우가 매일 수백 건 나온다. 그 키워드는
이미 우리 자리라서 재작업하면 우리 글끼리 경쟁한다.

  1) 안 뜬 행의 비고에 '다른 글로 노출중(MM/DD): 날짜 카페 「키워드」' 를 적는다.
  2) 그 키워드를 잡고 있는 글 묶음(메인+서브) 맨 아래에 서브 행을 Y 로 끼운다.
     비고에는 '자동추가 MM-DD · 다른 키워드로 노출' 이 붙는다.

행을 끼우면 아래 행번호가 밀린다. 그래서 상태·비고 기록을 **먼저** 끝내고,
끼우기는 **아래쪽부터** 한다(위쪽 끼울 자리가 밀리지 않게).
"""
from __future__ import annotations

import re
import time
from datetime import date

from checker.sheet import MAIN, SUB, norm

MARK = "자동추가"
NOTE = "다른 글로 노출중"
_NOTE_RE = re.compile(NOTE + r"\(\d\d/\d\d\)[^|]*")


def groups(rows: list) -> dict:
    """글 주소 → {"main": 메인 행, "last": 묶음 마지막 행번호, "kws": 묶음 키워드}."""
    out, cur = {}, None
    for r in rows:
        u = r["url"].strip()
        if r["kind"] == MAIN:
            cur = {"main": r, "last": r["row"], "kws": {norm(r["keyword"])}} if u else None
            if cur and u not in out:
                out[u] = cur
        elif cur is not None and u == cur["main"]["url"].strip():
            cur["last"] = r["row"]
            cur["kws"].add(norm(r["keyword"]))
        else:
            cur = None        # 주소가 다른 서브를 만나면 묶음이 끝난 것으로 본다
    return out


def bigo_with_note(old: str, note: str) -> str:
    """기존 비고는 살리고 자동 메모만 갈아 끼운다."""
    old = (old or "").strip()
    if NOTE in old:
        return _NOTE_RE.sub(note, old).strip()
    return f"{old} | {note}" if old else note


def bigo_updates(covered: list, today: date) -> list:
    """covered=[{"row", "bigo", "holder"}] → [(행번호, 새 비고)]. 같은 행은 첫 holder 하나만."""
    out, seen = [], set()
    for c in covered:
        if c["row"] in seen:
            continue
        seen.add(c["row"])
        h = c["holder"]
        note = f"{NOTE}({today:%m/%d}): {h['date']} {h['venue']} 「{h['keyword']}」"
        new = bigo_with_note(c["bigo"], note)
        if new != c["bigo"]:
            out.append((c["row"], new))
    return out


def plan(rows: list, covered: list, vol: dict, today: date, min_vol: int, idx: dict) -> list:
    """끼울 행 목록(아래쪽부터). covered=[{"keyword", "holder"}] — holder 는 떠 있는 우리 글의 행."""
    g = groups(rows)
    seen, out = set(), []
    for c in covered:
        u, kw = c["holder"]["url"].strip(), c["keyword"].strip()
        grp = g.get(u)
        if not grp or not kw or norm(kw) in grp["kws"] or (u, norm(kw)) in seen:
            continue
        if vol.get(norm(kw), 0) <= min_vol:
            continue        # 검색량을 모르거나 작은 키워드는 노이즈로 쌓인다
        seen.add((u, norm(kw)))
        m = grp["main"]
        vals = [""] * (max(idx.values()) + 1)
        for h, v in (("날짜", m["date"]), ("구분", SUB), ("카페/블로그", m["venue"]),
                     ("작업ID", m["uid"]), ("키워드", kw), ("검색량", vol.get(norm(kw), "")),
                     ("노출여부", "Y"), ("비고", f"{MARK} {today:%m-%d} · 다른 키워드로 노출"),
                     ("URL", u)):
            vals[idx[h]] = v
        out.append({"after": grp["last"], "values": vals, "keyword": kw,
                    "holder": m["keyword"]})
    out.sort(key=lambda p: -p["after"])
    return out


def apply(ws, plan_rows: list) -> int:
    for p in plan_rows:
        ws.insert_rows([p["values"]], row=p["after"] + 1,
                       value_input_option="USER_ENTERED", inherit_from_before=True)
        time.sleep(1.1)       # 시트 쓰기 한도(분당 60회)
    return len(plan_rows)

