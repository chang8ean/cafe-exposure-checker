"""설정 읽기 — 저장소 루트의 config.json (config.example.json 을 복사해 만든다)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "sheet_id": "",
    "service_account_file": "service_account.json",
    "delay_seconds": 2.0,        # 새 키워드 검색 사이 대기(초). 줄이면 차단이 빨리 온다
    "w_grace_days": 21,          # 발행 후 이 기간까지 안 떠도 W(대기) 유지
    "fresh_days": 30,            # 조회 1순위: 이 안에 발행된 글
    "recent_days": 60,           # 조회 2순위: 이 안에 발행된 글
    "old_days": 90,              # 이보다 오래된 N/D 는 일요일에만 조회
    "autosub_min_volume": 100,   # 자동 서브 행은 검색량이 이보다 클 때만
    "dead_cafes": [],            # 폐쇄된 카페 — URL 또는 카페명 일부 (조회 안 함)
    "dead_ids": [],              # 글이 전부 삭제된 작업ID (조회 안 함)
}


def load(path: str = None) -> dict:
    path = path or os.environ.get("CHECKER_CONFIG") or os.path.join(ROOT, "config.json")
    if not os.path.exists(path):
        raise SystemExit(f"설정 파일이 없습니다: {path}\n"
                         "config.example.json 을 config.json 으로 복사해 채우세요.")
    with open(path, encoding="utf-8") as f:
        cfg = {**DEFAULTS, **json.load(f)}
    if not cfg["sheet_id"]:
        raise SystemExit("config.json 의 sheet_id 가 비어 있습니다.")
    key = cfg["service_account_file"]
    if not os.path.isabs(key):
        key = os.path.join(os.path.dirname(os.path.abspath(path)), key)
    if not os.path.exists(key):
        raise SystemExit(f"서비스계정 키 파일이 없습니다: {key}")
    cfg["service_account_file"] = key
    return cfg
