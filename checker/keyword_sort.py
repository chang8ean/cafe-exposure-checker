"""[키워드] 탭 정렬 — 등급 → 점수 → 검색량 순.

**시트 화면에서 직접 정렬하지 마세요.** 수식 열(ARRAYFORMULA)이 섞여 있어서
2행이 같이 움직이면 수식이 값으로 덮이거나 #REF! 가 나서 열 전체가 깨집니다.
실제로 같은 사고가 세 번 났다(등급 열을 고정 위치로 읽다 터짐 · 정렬이 2행 수식을
값으로 덮어 노출 표시 전멸 · 같은 정렬이 Total 수식도 덮을 뻔함).

그래서 열을 이름으로 정하지 않고 **2행이 수식인지 실제로 읽어 보고** 값 열만
재배열한다. 수식 열은 쓰지 않으므로 알아서 다시 계산된다.
"""
from __future__ import annotations

import re

from checker.sheet import TAB_KW

GRADE_ORDER = {"P1": 0, "P2": 1, "P3": 2}


def _num(v) -> int:
    s = re.sub(r"[^\d]", "", str(v or ""))
    return int(s) if s else 0


def _col(i: int) -> str:
    return chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)


def sort_key(row: list, col: dict):
    g = lambda h: row[col[h]].strip() if h in col and col[h] < len(row) else ""   # noqa: E731
    return (GRADE_ORDER.get(g("등급"), 9), -_num(g("점수")), -_num(g("Total")))


def violations(body: list, col: dict) -> int:
    """정렬이 깨진 지점의 수. 0 이면 이미 정렬돼 있어 쓰지 않는다."""
    bad, prev = 0, None
    for r in body:
        k = sort_key(r, col)
        if prev is not None and k < prev:
            bad += 1
        prev = k
    return bad


def sort(sh, dry_run: bool = False) -> dict:
    ws = sh.worksheet(TAB_KW)
    vals = ws.get_all_values()
    if len(vals) < 3:
        return {"rows": max(len(vals) - 1, 0), "violations": 0, "written": False}
    hdr = [h.strip() for h in vals[0]]
    col = {h: i for i, h in enumerate(hdr)}
    if "키워드" not in col:
        raise SystemExit("[키워드] 탭에 '키워드' 열이 없습니다 — 정렬 중단")
    row2 = ws.get(f"A2:{_col(len(hdr) - 1)}2", value_render_option="FORMULA")
    row2 = row2[0] if row2 else []
    formula = {i for i in range(len(hdr)) if str(row2[i] if i < len(row2) else "").startswith("=")}
    if col["키워드"] in formula:
        raise SystemExit("'키워드' 열이 수식입니다 — 정렬 중단")
    value_cols = [i for i in range(len(hdr)) if i not in formula]
    iKW = col["키워드"]
    body = [r for r in vals[1:] if len(r) > iKW and r[iKW].strip()]
    bad = violations(body, col)
    out = {"rows": len(body), "violations": bad, "written": False}
    if bad == 0 or dry_run:
        return out
    ordered = sorted(body, key=lambda r: sort_key(r, col))
    # 중간에 빈 행이 있었다면 아래쪽에 옛 값이 남지 않게 빈칸으로 채운다
    ordered += [[]] * (len(vals) - 1 - len(ordered))
    g = lambda r, i: r[i] if i < len(r) else ""   # noqa: E731
    ws.batch_update([{"range": f"{_col(i)}2:{_col(i)}{len(ordered) + 1}",
                      "values": [[g(r, i)] for r in ordered]} for i in value_cols],
                    value_input_option="USER_ENTERED")
    out["written"] = True
    return out
