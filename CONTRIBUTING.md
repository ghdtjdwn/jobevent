# 함께 개발하기

1. 저장소를 clone하거나 fork합니다. Python 3.11 이상과 [uv](https://docs.astral.sh/uv/)를 사용합니다.
2. `uv sync --locked` → `uv run python deploy/dev.py` → 표시된 주소에서 **테스트 계정**을 만듭니다. 이 명령은 개발용 DB·키·워커를 생성합니다. 개발용 서버를 인터넷에 노출하지 마세요.
3. 브랜치 하나당 변경 목적 하나를 담습니다. 해당 동작의 테스트를 먼저 추가하고 `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`, `node --check jobevent/static/app.js`, `uv build`를 실행합니다.
4. PR에 변경 이유, 사용자 영향, 실제로 실행한 검사, UI라면 샘플 데이터 스크린샷을 첨부합니다. 개인 이력서, 실제 키, 웹훅, 서버 구성, 외부 서비스 원문 응답을 붙이지 마세요.

| 변경 | 시작할 곳 |
|---|---|
| 새 알림 틀, 요일·시간대·입력 검증 | `jobevent/model.py` |
| 새 공고 공급자 | `jobevent/sources.py`와 `tests/test_boards.py`. 출처 약관·인증·페이지 한도부터 확인 |
| 모델 호출, 근거 링크, 중복 판정, 채널 전송 | `jobevent/pipeline.py`, `tests/test_pipeline.py` |
| 대시보드 | `jobevent/static/` (빌드 없는 HTML/CSS/JS) |
| 회원·권한·호스팅 API·운영 워커 | `jobevent/hosted/`, `tests/test_hosted*.py` |
| 로컬 단일 사용자 실행 | `jobevent/app.py`, `jobevent/store.py` |

GitHub 저장소 권한은 서비스 회원 권한과 무관합니다. 개발자 초대는 유지보수자가 GitHub에서 별도로 처리합니다.
