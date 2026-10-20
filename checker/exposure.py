"""네이버 모바일 통합검색(SERP)에서 우리 글이 떠 있는지 판정한다.

방식: 키워드로 m.search.naver.com 을 열고, 결과 HTML 안에 우리 글의 글번호가
**네이버 글 주소 형태로** 들어 있으면 노출로 본다. 사람이 눈으로 검색해 보는 것과 같다.
카페탭·블로그탭은 보지 않는다 — 통합검색 1페이지만.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")


class BlockedError(Exception):
    """네이버가 요청을 막았다(403/429/요청과다 안내 페이지)."""


def query_of(keyword: str) -> str:
    """검색 질의는 **띄어쓰기를 지운 형태**로 통일한다.

    네이버는 '간수치 높은이유'와 '간수치높은이유'를 다른 질의로 처리한다.
    실측 21건에서 붙여서 놓친 경우는 0건, 붙여야만 잡힌 경우가 2건이었다.
    표기만 다른 행들이 검색 1회를 함께 쓰게 되어 요청 수도 준다.
    """
    return re.sub(r"\s+", "", str(keyword or ""))


def extract_id(url: str):
    """글 주소에서 글번호를 뽑는다. 못 뽑으면 None.

    블로그 blog.naver.com/{id}/{글번호} · 카페 cafe.naver.com/{카페}/{글번호}
    신형 카페 .../cafes/{클럽}/articles/{글번호} · 옛 카페 ...articleid={글번호}
    """
    if not url:
        return None
    u = urllib.parse.unquote(urllib.parse.unquote(url))
    for pat in (r'blog\.naver\.com/[^/?#]+/(\d{6,})',
                r'/articles/(\d{4,})',
                r'cafe\.naver\.com/[^/?#]+/(\d{5,})',
                r'articleid=(\d{4,})'):
        m = re.search(pat, u, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def resolve_short(url: str) -> str:
    """naver.me 단축주소 → 실제 주소. 실패하면 원래 주소."""
    if not url or "naver.me" not in url:
        return url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.geturl()
    except Exception:  # noqa: BLE001
        return url


def origin(url: str):
    """(카페 주소이름 또는 블로그ID, 글번호). 주인을 못 뽑으면 (None, 글번호)."""
    u = urllib.parse.unquote(urllib.parse.unquote(url or ""))
    m = re.search(r'(?:cafe|blog)\.naver\.com/([A-Za-z0-9_-]+)/(\d{4,})', u)
    if m:
        return m.group(1), m.group(2)
    return None, extract_id(url)


def fetch_serp(query: str, retries: int = 2, backoff=(6, 20)) -> str:
    """모바일 통합검색 HTML. 막히면 쉬었다 재시도하고, 끝내 막히면 BlockedError."""
    url = ("https://m.search.naver.com/search.naver?where=m&query="
           + urllib.parse.quote(query))
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept-Language": "ko-KR"})
            with urllib.request.urlopen(req, timeout=15) as r:
                html = r.read().decode("utf-8", "ignore")
            # 200 인데 정상 결과가 아닌 '요청과다' 안내 페이지 방어
            if len(html) < 10000 or "search.naver" not in html:
                raise BlockedError(f"소프트블록(len={len(html)})")
            return html
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (403, 429) and e.code < 500:
                raise
        except (urllib.error.URLError, BlockedError) as e:
            last = e
        if attempt < retries:
            time.sleep(backoff[min(attempt, len(backoff) - 1)])
    raise BlockedError(f"차단 지속: {last}")


def serp_ids(html: str, owner: str = None) -> set:
    """결과 HTML 에 실린 네이버 글번호 전부 — **글 주소 문맥 안의 숫자만** 센다.

    결과 HTML 은 700~950KB 라 그냥 `글번호 in html` 로 찾으면 이미지 파일명
    (예: 1766731093373_unnamed.jpg) 같은 엉뚱한 숫자에 걸린다. 실측에서 느슨한
    매칭은 12개 중 7개를 노출로 잘못 읽었다.
    owner 를 주면 그 카페/블로그 글만 센다 — 글번호는 카페마다 따로 매겨져 겹친다.
    """
    u = urllib.parse.unquote(urllib.parse.unquote(html or ""))
    who = re.escape(owner) if owner else r"[A-Za-z0-9_-]+"
    out = set()
    for pat in (rf"cafe\.naver\.com/{who}/(\d{{4,}})",
                rf"blog\.naver\.com/{who}/(\d{{6,}})",
                r"/articles/(\d{4,})",
                r"articleid=?(\d{4,})",
                r"logNo=?(\d{6,})"):
        out.update(re.findall(pat, u, re.I))
    return out


def check(url: str, html: str) -> dict:
    """이 글이 이 검색 결과에 떠 있나. exposed=None 이면 판정불가."""
    owner, pid = origin(resolve_short(url))
    if not pid:
        return {"exposed": None, "id": None, "error": "글번호 추출 실패"}
    return {"exposed": pid in serp_ids(html, owner), "id": pid, "error": None}


def check_rows(rows: list, delay: float = 2.0, owned: dict = None,
               abort_after: int = 6, pause_on_block: float = 300.0,
               progress=None) -> list:
    """행들을 판정한다. 같은 키워드(띄어쓰기 무시)는 검색 1회만 한다.

    연속 abort_after 번 막히면 pause_on_block 초 쉬고 한 번 재개한다. 또 막히면
    남은 행은 '차단중단'으로 두고 끝낸다 — 무리하면 차단이 길어진다.
    실측: 한 번 실행에 고유 키워드 약 500개에서 막힌다. 남은 건 오후 --resume 이 맡는다.

    owned={글번호: 행} 을 주면 그 검색 결과에 떠 있는 **우리 다른 글**을
    '다른우리글' 로 함께 돌려준다(추가 요청 없음). 내 글은 안 떠도 우리 다른 글이
    그 자리를 잡고 있으면 재작업 대상이 아니다.
    """
    cache, out = {}, []
    blocked_streak, paused, aborted = 0, False, False
    for i, r in enumerate(rows):
        q = query_of(r["keyword"])
        if aborted:
            out.append({**r, "exposed": None, "pid": None,
                        "error": "차단중단", "others": []})
            continue
        if q not in cache:
            try:
                cache[q] = (fetch_serp(q), None)
                blocked_streak = 0
            except Exception as e:  # noqa: BLE001
                cache[q] = (None, str(e))
                blocked_streak += 1
            time.sleep(delay)
            if blocked_streak >= abort_after:
                if not paused and pause_on_block > 0:
                    time.sleep(pause_on_block)
                    paused, blocked_streak = True, 0
                else:
                    aborted = True
        html, err = cache[q]
        if html is None:
            out.append({**r, "exposed": None, "pid": None,
                        "error": f"검색실패:{err}", "others": []})
            continue
        res = check(r["url"], html)
        others = []
        if owned:
            ids = cache.get(q + "\0ids")
            if ids is None:
                ids = cache[q + "\0ids"] = serp_ids(html)
            others = sorted((ids & set(owned)) - {res["id"]})
        out.append({**r, "exposed": res["exposed"], "pid": res["id"],
                    "error": res["error"], "others": others})
        if progress:
            progress(i + 1, len(rows), out[-1])
    return out
