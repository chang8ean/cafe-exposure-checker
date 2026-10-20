"""빈 구글 시트에 [키워드] · [물길] · [_채점사전] 탭을 만든다 (처음 한 번).

    python setup_sheet.py            # 없는 탭만 만든다
    python setup_sheet.py --force    # 세 탭을 지우고 새로 만든다 (데이터 사라짐!)

만드는 것
  · 헤더 · 1행 고정
  · [키워드] 수식 열(카페노출·블로그노출·Total·위치·의도·부정·점수·등급·중복)
  · [_채점사전] 1행 정규식 묶음 수식 + 칸마다 설명 메모
  · [물길] 구분(메인/서브)·노출여부(Y/W/N/D) 드롭다운
  · 수식 열 '경고' 보호 — 실수로 값을 넣으려 하면 경고창이 뜬다
"""
from __future__ import annotations

import argparse

from checker import config
from checker.sheet import KW_HEADERS, MG_HEADERS, TAB_DICT, TAB_KW, TAB_MG, open_sheet

D = TAB_DICT

# [_채점사전] 카테고리 — (이름, 설명). A·C·E… 열에 단어를 한 줄에 하나씩 넣는다.
DICT_CATS = [
    ("HUB", "허브 — 자사 브랜드·제품명. 검색량 50 미만이어도 P3 로 떨어뜨리지 않는다."),
    ("OURCAT", "자사 카테고리 — 브랜드명·우리 제품군. 선택층 + 2점."),
    ("STEAL", "경쟁 제품 — 같은 수요를 두고 다투는 남의 제품명. 선택층."),
    ("FORM", "제형 — 진액·엑기스·스틱·환 등. 선택층."),
    ("HOOK", "선택 훅 — 효능·부작용·비교·차이 등. 선택층에서 OURCAT 이 아니면 +1 (없으면 -3)."),
    ("NEG", "부정어 — 부작용·먹으면안되·피해야 등. 선택층이면 제품부정 +2, 아니면 질환부정 +1."),
    ("ALT", "대안 — 음식·식단·식사·영양식 등. 대안층(기본 3점)."),
    ("BUY", "구매 의도 — 추천·선물·영양제·가격 등. +1."),
    ("WHO", "대상 — 질환·부위·사람(암·간·폐·부모님 등). 선택층이 아니면 +1."),
    ("PHASE", "단계 — 재발·전이·수술후·항암중 등. 선택층이 아니면 +1."),
    ("MISMATCH", "제외어 — 우리와 무관한 단어. 들어 있으면 등급 '제외'."),
]


def _L(name: str) -> str:
    """카테고리 이름 → 정규식이 들어 있는 1행 칸 (예: OURCAT → '_채점사전'!$D$1)."""
    i = [c for c, _ in DICT_CATS].index(name)
    col = chr(65 + i * 2 + 1)
    return f"'{D}'!${col}$1"


def _blog(mg_url_col: str) -> str:
    return f"REGEXMATCH('{TAB_MG}'!{mg_url_col}2:{mg_url_col}&\"\",\"blog\\.naver\\.com\")"


def keyword_formulas() -> dict:
    """[키워드] 2행 수식. 물길 열 위치는 MG_HEADERS 순서에서 계산한다."""
    c = {h: chr(65 + i) for i, h in enumerate(MG_HEADERS)}
    kw, st, url = c["키워드"], c["노출여부"], c["URL"]
    k = 'REGEXREPLACE($D$2:$D&"","\\s","")'
    t = 'IFERROR(VALUE(SUBSTITUTE(TO_TEXT($E$2:$E),",","")),-1)'

    def expo(blog: bool) -> str:
        cond = _blog(url) if blog else f"(1-{_blog(url)})"
        return ("=ARRAYFORMULA(IF(D2:D=\"\",\"\",IFERROR(VLOOKUP(REGEXREPLACE(D2:D&\"\",\"\\s\",\"\"),"
                f"SORT(FILTER({{REGEXREPLACE('{TAB_MG}'!{kw}2:{kw}&\"\",\"\\s\",\"\"),'{TAB_MG}'!{st}2:{st}}},"
                f"'{TAB_MG}'!{kw}2:{kw}<>\"\",{cond}),2,FALSE),2,FALSE),\"미작업\")))")

    return {
        "B": expo(False),
        "C": expo(True),
        "E": '=ARRAYFORMULA(IF(D2:D="","",IFERROR(F2:F+G2:G,"검색량확인")))',
        "H": (f'=ARRAYFORMULA(IF($D$2:$D="","",LET(k,{k},'
              f'IF(REGEXMATCH(k,{_L("OURCAT")}&"|"&{_L("STEAL")}&"|"&{_L("FORM")}),"선택",'
              f'IF(REGEXMATCH(k,{_L("ALT")}),"대안","결핍")))))'),
        "I": (f'=ARRAYFORMULA(IF($D$2:$D="","",LET(k,{k},'
              f'IF(REGEXMATCH(k,{_L("BUY")}),"구매","정보"))))'),
        "J": (f'=ARRAYFORMULA(IF($D$2:$D="","",LET(k,{k},'
              f'IF(REGEXMATCH(k,{_L("NEG")}),IF($H$2:$H="선택","제품부정","질환부정"),""))))'),
        "K": (f'=ARRAYFORMULA(IF($D$2:$D="","",LET(k,{k},t,{t},'
              'IF($H$2:$H="선택",5,IF($H$2:$H="대안",3,1))'
              '+($I$2:$I="구매")'
              '+IF($J$2:$J="제품부정",2,IF($J$2:$J="질환부정",1,0))'
              f'+IF($H$2:$H="선택",IF(REGEXMATCH(k,{_L("OURCAT")}),2,IF(REGEXMATCH(k,{_L("HOOK")}),1,-3)),'
              f'REGEXMATCH(k,{_L("WHO")})+REGEXMATCH(k,{_L("PHASE")}))'
              '+(t>=50)*(t<=999)-(t>=10000))))'),
        "L": (f'=ARRAYFORMULA(IF($D$2:$D="","",LET(k,{k},t,{t},'
              f'IF(REGEXMATCH(k,{_L("MISMATCH")}),"제외",'
              f'IF((t>=0)*(t<50)*(1-REGEXMATCH(k,{_L("HUB")})),"P3",'
              'IF($K$2:$K>=7,"P1",IF($K$2:$K>=4,"P2","P3")))))))'),
        "M": (f'=ARRAYFORMULA(IF($D$2:$D="","",IF(COUNTIF({k},{k})>1,"중복","")))'),
    }


def _get_or_make(sh, title: str, rows: int, cols: int, force: bool):
    try:
        ws = sh.worksheet(title)
    except Exception:  # noqa: BLE001  (WorksheetNotFound)
        return sh.add_worksheet(title, rows, cols), True
    if not force:
        if len(ws.get_all_values()) > 1:
            print(f"  [{title}] 이미 있고 데이터가 있어 건너뜀 (--force 로 새로 만들 수 있음)")
            return ws, False
    sh.del_worksheet(ws)
    return sh.add_worksheet(title, rows, cols), True


def _protect(sh, ws, c0: int, c1: int, desc: str, r0: int = 1):
    """수식 칸 경고 보호(편집은 되지만 경고창이 뜬다)."""
    return {"addProtectedRange": {"protectedRange": {
        "range": {"sheetId": ws.id, "startRowIndex": r0, "startColumnIndex": c0, "endColumnIndex": c1},
        "description": desc, "warningOnly": True}}}


def _dropdown(ws, col: int, values: list):
    return {"setDataValidation": {
        "range": {"sheetId": ws.id, "startRowIndex": 1, "startColumnIndex": col, "endColumnIndex": col + 1},
        "rule": {"condition": {"type": "ONE_OF_LIST",
                               "values": [{"userEnteredValue": v} for v in values]},
                 "strict": False, "showCustomUi": True}}}


def _widths(ws, px: dict):
    """열 너비(픽셀). 기본 100px 이면 키워드·비고가 잘려 보인다."""
    return [{"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
        "properties": {"pixelSize": w}, "fields": "pixelSize"}} for i, w in px.items()]


def _is_blank(ws) -> bool:
    return not any(c for r in ws.get_all_values() for c in r)     # 빈 탭도 [[]] 로 읽힌다


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    sh = open_sheet(config.load())
    reqs = []

    # _채점사전 — 다른 탭 수식이 이 탭을 참조하므로 먼저 만든다
    ws, made = _get_or_make(sh, D, 200, len(DICT_CATS) * 2, a.force)
    if made:
        row1 = []
        for i, (name, _) in enumerate(DICT_CATS):
            col = chr(65 + i * 2)
            # 단어가 하나도 없으면 아무것도 안 걸리는 정규식(^$)을 둔다 — 빈 패턴은 전부에 걸린다
            row1 += [name, f'=IF(COUNTA({col}2:{col})=0,"^$",TEXTJOIN("|",TRUE,{col}2:{col}))']
        ws.update(range_name="A1", values=[row1], value_input_option="USER_ENTERED")
        for i, (name, desc) in enumerate(DICT_CATS):
            ws.insert_note(f"{chr(65 + i * 2)}1", desc)
        ws.freeze(rows=1)
        reqs.append(_protect(sh, ws, 0, len(DICT_CATS) * 2, "채점사전 1행 — 수식", r0=0))
        reqs[-1]["addProtectedRange"]["protectedRange"]["range"]["endRowIndex"] = 1
        print(f"  [{D}] 생성")

    ws, made = _get_or_make(sh, TAB_MG, 2000, len(MG_HEADERS), a.force)
    if made:
        ws.update(range_name="A1", values=[MG_HEADERS])
        ws.freeze(rows=1)
        reqs.append(_dropdown(ws, MG_HEADERS.index("구분"), ["메인", "서브"]))
        reqs.append(_dropdown(ws, MG_HEADERS.index("노출여부"), ["Y", "W", "N", "D"]))
        reqs += _widths(ws, {MG_HEADERS.index(h): w for h, w in
                             (("날짜", 100), ("카페/블로그", 120), ("키워드", 190),
                              ("비고", 380), ("URL", 300))})
        print(f"  [{TAB_MG}] 생성")

    ws, made = _get_or_make(sh, TAB_KW, 2000, len(KW_HEADERS), a.force)
    if made:
        ws.update(range_name="A1", values=[KW_HEADERS])
        f = keyword_formulas()
        ws.batch_update([{"range": f"{c}2", "values": [[v]]} for c, v in f.items()],
                        value_input_option="USER_ENTERED")
        ws.freeze(rows=1)
        reqs += _widths(ws, {0: 70, 1: 80, 2: 80, 3: 200, 4: 70, 5: 70, 6: 70,
                             7: 60, 8: 60, 9: 70, 10: 50, 11: 50, 12: 50})
        for c0, c1 in ((1, 3), (4, 5), (7, 13)):          # B:C · E · H:M
            reqs.append(_protect(sh, ws, c0, c1, "수식 열 — 값을 쓰지 마세요"))
        print(f"  [{TAB_KW}] 생성")

    if reqs:
        sh.batch_update({"requests": reqs})
    # 탭 순서: 사람이 자주 보는 것부터
    order = {TAB_KW: 0, TAB_MG: 1, D: 2}
    sh.reorder_worksheets(sorted(sh.worksheets(), key=lambda w: order.get(w.title, 9)))
    # 새 시트에 딸려 오는 빈 기본 탭 정리
    for w in sh.worksheets():
        if w.title in ("Sheet1", "시트1") and len(sh.worksheets()) > 1 and _is_blank(w):
            sh.del_worksheet(w)
    print("완료")


if __name__ == "__main__":
    main()
