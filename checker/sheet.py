"""구글 시트 읽기/쓰기. 열은 **헤더 이름으로** 찾는다 — 열 순서가 바뀌어도 안 깨진다."""
from __future__ import annotations

import re
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

TAB_KW, TAB_MG, TAB_DICT = "키워드", "물길", "_채점사전"
MAIN, SUB = "메인", "서브"

# [물길] 탭 — 전부 값 열(수식 없음)
MG_HEADERS = ["날짜", "구분", "카페/블로그", "작업ID", "키워드", "검색량", "노출여부", "비고", "URL"]
# [키워드] 탭 — 구분·키워드·PC·M 만 값, 나머지는 수식
KW_HEADERS = ["구분", "카페노출", "블로그노출", "키워드", "Total", "PC", "M",
              "위치", "의도", "부정", "점수", "등급", "중복"]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def open_sheet(cfg: dict):
    creds = Credentials.from_service_account_file(cfg["service_account_file"], scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(cfg["sheet_id"])


def norm(s) -> str:
    """키워드 비교 키 — 띄어쓰기를 지운다. 조인·중복판정은 전부 이걸 거친다."""
    return re.sub(r"\s+", "", str(s or ""))


def to_int(s) -> int:
    m = re.search(r"\d[\d,]*", str(s or ""))
    return int(m.group(0).replace(",", "")) if m else 0


def parse_date(s):
    """'2026. 10. 20' · '2026-10-20' · '2026/10/20' → date. 못 읽으면 None."""
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def a1(row: int, col: int) -> str:
    return gspread.utils.rowcol_to_a1(row, col)


def header_index(hdr: list, required: list, tab: str) -> dict:
    idx = {h.strip(): i for i, h in enumerate(hdr)}
    missing = [h for h in required if h not in idx]
    if missing:
        raise SystemExit(f"[{tab}] 탭에 열이 없습니다: {missing} — 헤더 이름을 바꾸지 마세요.")
    return idx


def parse_mulgil(vals: list) -> tuple:
    """[물길] 값(헤더 포함) → (행 목록, 열 인덱스).

    서브 행의 날짜·URL·카페·작업ID 가 비어 있으면 **바로 위 메인 행**에서 물려받는다.
    구분이 비어 있으면 메인으로 본다(한 행 = 한 글로 써도 된다).
    """
    if not vals:
        return [], {}
    idx = header_index(vals[0], MG_HEADERS, TAB_MG)
    out, main = [], None
    for n, r in enumerate(vals[1:], start=2):
        g = lambda h: (r[idx[h]].strip() if idx[h] < len(r) else "")   # noqa: E731
        kw = g("키워드")
        if not kw:
            continue
        kind = SUB if g("구분") == SUB else MAIN
        row = {"row": n, "kind": kind, "date": g("날짜"), "venue": g("카페/블로그"),
               "uid": g("작업ID"), "keyword": kw, "volume": g("검색량"),
               "status": g("노출여부").upper(), "bigo": g("비고"), "url": g("URL")}
        if kind == MAIN:
            main = row
        elif main is not None:
            for k in ("date", "url", "venue", "uid"):
                if not row[k]:
                    row[k] = main[k]
        out.append(row)
    return out, idx


def read_mulgil(ws) -> tuple:
    return parse_mulgil(ws.get_all_values())


def read_volumes(sh) -> dict:
    """[키워드] 탭 → {띄어쓰기 지운 키워드: Total}."""
    vals = sh.worksheet(TAB_KW).get_all_values()
    if not vals:
        return {}
    idx = header_index(vals[0], ["키워드", "Total"], TAB_KW)
    out = {}
    for r in vals[1:]:
        if idx["키워드"] < len(r) and r[idx["키워드"]].strip():
            out[norm(r[idx["키워드"]])] = to_int(r[idx["Total"]] if idx["Total"] < len(r) else "")
    return out


def write_column(ws, col_idx: int, updates: list) -> int:
    """updates=[(행번호, 값)] 을 한 열에 일괄 기록. col_idx 는 0부터."""
    if not updates:
        return 0
    ws.batch_update([{"range": a1(r, col_idx + 1), "values": [[v]]} for r, v in updates],
                    value_input_option="USER_ENTERED")
    return len(updates)
