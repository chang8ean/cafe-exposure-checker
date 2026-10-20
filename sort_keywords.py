"""[키워드] 탭만 정렬한다 — 키워드를 많이 붙여 넣은 뒤 바로 순서를 보고 싶을 때.

    python sort_keywords.py
"""
from checker import config, keyword_sort
from checker.sheet import open_sheet

if __name__ == "__main__":
    r = keyword_sort.sort(open_sheet(config.load()))
    print(f"{r['rows']}행 · 어긋남 {r['violations']} · {'재정렬함' if r['written'] else '이미 정렬됨'}")
