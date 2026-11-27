# Jobevent

**내 PC에서 내 AI 키로 돌리는, 목적별 공고 알림방 오픈소스.** 채용·인턴·동아리·공모전·해커톤처럼 받고 싶은 기회마다 알림방을 만들면, 내가 정한 요일과 시각에 Jobevent가 공고를 찾아 고른 뒤 Discord·Slack 채널로 보냅니다. 서버나 회원가입이 없고, 데이터와 키는 설치한 PC에만 저장됩니다.

```sh
uv tool install git+https://github.com/ghdtjdwn/jobevent@v0.2.0
jobevent
```

![Jobevent 알림방 화면](docs/studio.png)

## 설치와 실행

GitHub에서 직접 설치해 쓰는 개발자·개발 직군 학생을 대상으로 합니다. [uv](https://docs.astral.sh/uv/getting-started/installation/)가 필요하며, Python 3.11 이상이 없으면 uv가 설치 중에 받아 옵니다.

1. 위의 `uv tool install` 명령으로 설치합니다. 태그는 [릴리스 목록](https://github.com/ghdtjdwn/jobevent/releases)에서 고릅니다.
2. `jobevent`를 실행하면 브라우저에서 `http://127.0.0.1:8765`가 열립니다. 브라우저를 열지 않으려면 `jobevent --no-browser`, 포트를 바꾸려면 `--port 8766`을 씁니다.
3. 업데이트는 같은 명령을 새 태그로 다시 실행합니다(`uv tool install git+https://github.com/ghdtjdwn/jobevent@<새 태그>`). 프로그램 삭제는 `uv tool uninstall jobevent`이며, 저장한 자료·키·웹훅은 남으므로 [데이터 삭제 방법](SECURITY.md)을 따라 먼저 지우세요.

화면은 이 PC(127.0.0.1)에서만 열립니다. 같은 PC에서 두 번 실행할 수 없습니다.

**예약은 PC가 켜져 있고 `jobevent` 프로세스가 실행 중일 때만 동작합니다.** 터미널을 닫으면 멈추고, PC가 꺼져 있거나 잠자기 상태인 동안에는 보내지 않습니다. 꺼져 있는 동안 지난 예약은 다음 실행 때 방마다 한 번만 처리하고 밀린 회차를 모두 다시 실행하지 않습니다.

## 처음 쓰기

1. **프로필 관리 → AI 연결**에서 회사(OpenAI·Google Gemini·Anthropic Claude)를 고르고 API 키를 등록합니다. 모델은 Jobevent가 정합니다.
2. **내 자료**에 이력서를 파일(텍스트 PDF·TXT·MD, 4MB·40쪽 이하)이나 글로 저장합니다. GitHub 사용자 주소나 GitHub Pages·Vercel·Notion 기본 주소의 자기소개 사이트는 **내 공개 링크**에 한 번 저장합니다. 링크 본문은 가져와서 확인·수정하며 자동으로 다시 읽지 않습니다.
3. **알림방 만들기**에서 채용, 인턴, 동아리·연합, 공모전, 해커톤, 교육, 장학·펠로십, 오픈소스 또는 직접 정의를 고릅니다. 검색에 써도 되는 조건과 비공개 선별 기준을 나눠 적고, 방에서 쓸 자료와 공개 링크 포함 여부를 정합니다.
4. 받을 채널의 웹훅을 입력합니다. [Discord](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)는 서버 설정 → 연동 → 웹후크, [Slack](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)은 앱 → Incoming Webhooks → 워크스페이스에 추가 → 채널 선택에서 발급합니다.
5. 말투, 시간대, 요일, 현지 시각, 최대 건수를 정해 저장합니다. **채널 연결 확인**은 AI를 호출하지 않고 고정 메시지 한 건만 보냅니다. **미리보기**는 검색·추천까지만 하고, 15분 안에 **이 결과 그대로 발송**을 누르면 추가 비용 없이 그 목록에서 마감되지 않은 미발송 항목만 보냅니다. **새로 검색해 발송**은 별도의 유료 검색입니다. 예약은 방마다 따로 켭니다.

중간에 막히면 [사용 중 막힘 이슈](https://github.com/ghdtjdwn/jobevent/issues/new?template=stuck.yml)로 어느 단계에서 멈췄는지 알려 주세요. 코드를 몰라도 됩니다.

예: 평일 오전 9시엔 Slack에 서울 백엔드 인턴 3건을 짧은 존댓말로, 토요일 오후 2시엔 Discord에 대학생 해커톤 2건을 친근한 말투로 받을 수 있습니다. 두 방의 발송 이력은 서로 독립적입니다.

## 어떤 공고를 찾나요?

| 방식 | 언제 쓰나요? | 제한 |
|---|---|---|
| 회사별 검색: [OpenAI](https://developers.openai.com/api/docs/guides/tools-web-search) · [Google](https://ai.google.dev/gemini-api/docs/google-search) · [Anthropic](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool) | 국내외 채용·동아리·대회 등 넓게 발굴 | 검색 호출에서 인용된 HTTPS URL만 추천 후보. 모든 공고를 망라하지 않으며 모집 상태·자격은 원문 확인 |
| [Greenhouse](https://docs.greenhouse.io/job-board.html) | 지정한 회사의 현재 공개 보드 | 보드 식별자 필요. 최근 갱신 순 최대 50개 후보 |
| [Lever](https://github.com/lever/postings-api) / EU | 지정한 회사의 공개 채용 목록 | 회사 식별자·리전 필요. 최대 50개 후보 |

사이트를 직접 수집하지 않고, 인증이 필요한 국내 API나 근거 없는 생성 링크도 쓰지 않습니다. 채널에 보내는 공고 알림에는 `[AI 추천]`이 붙습니다. AI의 추천은 합격·자격·마감 보증이 아니므로 지원 전에 원문을 확인하세요.

## 비용과 AI 제공 회사 약관

- 웹 검색과 추천은 내 키로 호출하므로 제공 회사 요금이 내 계정에 청구됩니다. 회사 보드 방식은 웹 검색 없이 추천 모델만 호출합니다. 방별 최대 건수는 발송량 제한이지 금액 상한이 아닙니다.
- 제공 회사마다 **Jobevent 전용 프로젝트, 월 지출 한도, 전용 키**를 만들어 쓰기를 권장합니다. 키가 새도 피해가 그 한도 안에 머뭅니다: [OpenAI 지출 한도](https://developers.openai.com/api/docs/guides/spend-limits) · [Anthropic 워크스페이스](https://platform.claude.com/docs/en/manage-claude/workspaces) · [Gemini 결제와 지출 상한](https://ai.google.dev/gemini-api/docs/billing)
- 제공 회사의 약관을 지킬 책임은 이용자에게 있습니다. 예를 들어 [Gemini API 약관](https://aistudio.google.com/docs/terms)은 만 18세 이상만 쓸 수 있고 검색 결과의 표시·재배포 조건을 둡니다. 여러 사람이 보는 채널로 검색 결과를 보내기 전에 쓰는 회사의 약관을 확인하세요.

## 데이터는 어디에 있나요?

| 데이터 | 저장 위치 |
|---|---|
| 프로필·자료·공개 링크 본문, 알림방 설정, 실행 기록, 발송한 공고 주소 | `~/.jobevent/jobevent.sqlite3` (암호화하지 않은 SQLite) |
| AI 키, 웹훅 | OS 자격 증명 저장소(macOS 키체인, Windows 자격 증명 관리자, Linux Secret Service) |

검색에는 방의 공개 조건만 보내고, 추천 단계에는 방에서 고른 자료(연락처·링크 형식은 지움)와 비공개 선별 기준을 내 키로 고른 제공 회사에 보냅니다. 유지보수자에게는 어떤 데이터도 전송되지 않으며 사용 통계도 수집하지 않습니다. 자세한 경계는 [보안과 개인정보](SECURITY.md)를 확인하세요.

**백업:** `jobevent`를 종료한 뒤 `~/.jobevent` 폴더를 복사합니다. 키와 웹훅은 이 폴더에 들어 있지 않으므로, 다른 PC나 다른 경로로 옮기면 다시 입력합니다. Linux에서는 로그인 세션의 Secret Service(GNOME Keyring, KWallet 등)가 있어야 키를 저장할 수 있습니다.

## 개발

```sh
git clone https://github.com/ghdtjdwn/jobevent.git
cd jobevent
uv sync --locked
uv run jobevent
```

- [협업 가이드](CONTRIBUTING.md) · [보안 신고](SECURITY.md) · [제품 명세와 결정 기록](docs/product-spec.md) · [화면 설계](DESIGN.md) · [폼팩터 비교와 유사 사례 조사](docs/design.md)
- Python 3.11+, 표준 라이브러리 HTTP 서버, SQLite, keyring, 빌드 없는 HTML/CSS/JS. MIT License.
