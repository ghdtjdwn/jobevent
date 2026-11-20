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

실제 브라우저에서 로그인·자료 보관·방 생성/복제·모바일 탐색을 회귀 검사하려면 Chrome이 있는 환경에서 `uv run --with playwright==1.65.2 python checks/browser.py`를 실행하세요. 임시 로컬 DB만 쓰며 외부 AI·채널을 호출하지 않습니다. `--screenshots docs`는 README의 화면 자료를 갱신합니다.

## 두 명이 변경을 릴리스하는 순서

1. 최신 `main`에서 작업 브랜치를 만듭니다: `git switch main && git pull --ff-only && git switch -c feat/변경이름`.
2. PR을 올리고 다른 개발자에게 리뷰를 요청합니다. 코드뿐 아니라 데이터 삭제·외부 발송·API 비용 변화도 확인합니다. 실제 고객 자료와 비밀키는 리뷰에도 사용하지 않습니다. 보안 신고는 [비공개 절차](SECURITY.md)를 따릅니다.
3. 상대방의 승인과 필수 검사 `test (3.11)`, `test (3.12)`, `container`가 끝나면 squash merge합니다. 새 커밋 후에는 최신 diff를 다시 검토합니다. 실패한 검사를 우회하지 않습니다.
4. `main`의 push CI가 통과한 뒤 Actions의 **Production delivery**에서 같은 SHA가 운영에 반영됐는지 확인합니다. PR CI 성공은 배포 완료가 아닙니다. SSH 키, 서버 환경변수, 고객 API 키를 개발자 간 공유하거나 GitHub에 업로드하지 않습니다.
5. 주간 CI는 코드가 그대로여도 ARM64 이미지의 설치 패키지를 새 보안 공지와 대조합니다. Dependabot PR은 자동 병합하지 않고 호환성·암호문 복호화·잠금 회귀를 다른 변경과 같은 기준으로 검토합니다.
