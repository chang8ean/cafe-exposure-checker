# 카페 외부노출 자동체커

네이버 카페·블로그 글이 키워드 **모바일 통합검색 1페이지**에 떠 있는지 매일 확인해 구글 시트에 기록합니다.
키워드 탭에는 자동 점수·등급이 붙습니다.

- 📖 **사용 설명서(사람용)**: 노션 — 전달받은 링크를 여세요
- 🤖 **구축 지시서(Claude Code 용)**: [`CLAUDE.md`](CLAUDE.md)

## 시작하기
1. 이 저장소를 내려받습니다(맥은 홈 폴더 바로 아래 권장).
   ```bash
   git clone https://github.com/chang8ean/cafe-exposure-checker.git ~/cafe-exposure-checker
   ```
2. 그 폴더를 Claude Code 로 열고 **"세팅해줘"** 라고 입력합니다.
   구글 서비스계정 만들기·시트 공유처럼 사람이 눌러야 하는 단계에서는 Claude 가 멈추고 안내합니다.

## 구성
| 파일 | |
|---|---|
| `setup_sheet.py` | 빈 시트에 `키워드` · `물길` · `_채점사전` 탭 생성(처음 한 번) |
| `run.py` | 노출 판정 → 시트 반영 (`--resume` · `--dry-run`) |
| `sort_keywords.py` | `키워드` 탭 정렬 |
| `checker/` | 판정·상태 규칙·자동 서브·정렬 |
| `scripts/` | 매일 자동 실행 등록(맥 launchd · 윈도우 작업 스케줄러) |
| `tests/` | `python -m unittest discover tests` |

## 업데이트 받기
```bash
git pull
```
`config.json` · `service_account.json` 은 저장소에 올라가지 않으므로 업데이트해도 그대로입니다.
