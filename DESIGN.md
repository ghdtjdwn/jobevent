# Design

## Source of truth

Active · 2026-11-20 · 회원 진입, 모바일/데스크톱 작업공간, 알림방 편집과 발송. 이전 릴리스의 `docs/studio.png`, 가입 템플릿, 대시보드 DOM, 기존 [제품 명세](docs/product-spec.md)와 [설계 조사](docs/design.md)를 대조했다. 관찰: 이전 대시보드는 프로필 입력이 방 목록보다 먼저 나오고 설정 폼·기록이 한 문서에 이어졌다. 사용자 피드백: 실제 서비스보다 소개 사이트처럼 보인다. **변경 기준은 예쁜 첫인상보다 반복 작업의 속도·안전성이다.** 실제 모집자의 사용성 조사 결과는 아직 없다.

## Brand

개인 알림 관리 도구. 회원 수·추천 성공률·샘플 추천·온라인 상태를 지어내 신뢰를 만들지 않는다. 대신 실제 예약 시각, 채널 종류, 공개 검색어, 실행 결과를 보여준다. 슬로건이나 장식용 숫자로 첫 화면을 채우지 않는다.

## Product goals

가입자는 첫 방을 만들고 과금 없이 채널을 확인할 수 있어야 한다. 재방문자는 프로필을 다시 입력하지 않고 방 상태를 확인하거나 수정할 수 있어야 한다. 미리 본 공고를 보내는 행동과 유료로 다시 검색하는 행동은 구분한다. 자동 지원·채용 포털·홍보 랜딩은 목표가 아니다.

## Personas and jobs

- 처음 방문한 구직자: 무엇이 공개 검색으로 나가고 어떤 정보가 모델에 전달되는지 확인한 다음 첫 방을 만든다.
- 여러 방을 운영하는 학생: 모바일에서 동아리·공모전 방의 수신 채널과 실행 시각을 빠르게 구분한다.
- 발송 문제를 겪은 이용자: 연결 확인과 검색을 분리해 불필요한 과금 없이 어디서 실패했는지 판단한다.

## Information architecture

공유 링크 → `/app` → 세션이 없을 때만 로그인. 가입은 로그인 화면에서 선택. 첫 화면의 주체는 서비스 소개가 아닌 **내 알림방**이다. 프로필은 계정 공통 설정이고 공개 검색어·대상 채널·주기는 방 소유다. 실행 기록은 편집 양식과 분리한다. 서버 예약 실행은 모바일 앱의 실행 여부와 독립적이다.

## Design principles

다음 사례는 시각 복제가 아닌 기능 판단의 근거다. 링크는 공식 도움말·디자인 시스템으로 연결된다.

| 실제 업무 / 사례 | Jobevent 결정 및 가져오지 않을 범위 |
|---|---|
| [Indeed: 공고 알림 관리](https://support.indeed.com/hc/en-in/articles/204488890-Starting-Stopping-and-Managing-Job-Alerts) | 검색 조건과 알림 제어를 같은 방에서 확인. 이메일 구독 관리 페이지로 보내지 않는다. |
| [USAJOBS: 검색 알림](https://help.usajobs.gov/how-to/search/job-alerts) | 재사용할 조건을 이름 있는 방으로 저장. 이용자마다 다른 시각과 요일을 둔다. |
| [Handshake: 검색 저장과 알림](https://support.joinhandshake.com/hc/en-us/articles/218693388-Saving-Job-Searches-and-Receiving-Job-Alerts) | 채용과 학생 활동을 탐색 조건으로 분리하되 두 개의 앱으로 나누지 않는다. |
| [Grafana: 수신 대상](https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/) | 목적지 연결을 모델 호출과 독립적으로 테스트. 복잡한 라우팅 트리는 제외. |
| [n8n: 수동·운영 실행](https://docs.n8n.io/workflows/executions/manual-partial-and-production-executions/) | 확인용 실행과 예약 발송을 구분. 가짜 공고로 성공한 것처럼 표시하지 않는다. |
| [Linear: Inbox](https://linear.app/docs/inbox) · [GitHub: 알림 분류](https://docs.github.com/en/subscriptions-and-notifications/how-tos/viewing-and-triaging-notifications/managing-notifications-from-your-inbox) | 반복 방문에서는 상태와 다음 행동이 콘텐츠보다 먼저 읽혀야 한다. 알림을 이미 Discord/Slack에서 받으므로 또 다른 공고 수신함을 만들지 않는다. |
| [GOV.UK: Task list](https://design-system.service.gov.uk/components/task-list/) · [Check answers](https://design-system.service.gov.uk/patterns/check-answers/) | 첫 사용의 미완료 작업을 실제 상태에서 도출. 확인한 뒤 보내면 같은 내용을 보내고 두 번째 AI 호출을 만들지 않는다. |
| [IBM Carbon: 빈 상태](https://carbondesignsystem.com/patterns/empty-states-pattern/) | 신규 계정·신규 공고 없음·가져오기 실패를 다른 상태로 다룬다. 가짜 추천이나 도표로 빈 화면을 채우지 않는다. |
| [USWDS: 진행 단계](https://designsystem.digital.gov/components/step-indicator/) | 순서가 있는 작업에만 단계 표현을 사용한다. 프로필과 실행 기록을 상시 진행률로 바꾸지 않는다. |
| [W3C WAI: 폼 그룹](https://www.w3.org/WAI/tutorials/forms/grouping/) · [입력 피드백](https://www.w3.org/WAI/tutorials/forms/notifications/) | 채널·일정·조건을 의미 단위로 구분하고 결과를 텍스트로 알린다. 오류를 빨간색만으로 표현하지 않는다. |

## Visual language

정보 위계는 방 이름 → 예약 상태 → 목적지·조건 → 조작 순서. 한 화면에서 강조색은 주 행동과 포커스에 집중한다. 한글 시스템 글꼴, 의미 있는 여백, 얇은 구분선과 명도 차를 사용한다. 스톡 사진·외부 폰트·마케팅 애니메이션은 사용하지 않는다.

## Components

작업 탐색, 첫 설정 안내, 알림방 목록, 방 편집 폼, 실행 기록, 확인 결과, 로그인/가입 폼. 예약과 채널 상태를 혼동하지 않는다. 실제 연결 확인 전 단지 URL이 저장된 것을 ‘연결 성공’이라고 표기하지 않는다.

## Accessibility

키보드 조작, 레이블 연결, 보이는 포커스, 상태 텍스트, 색에만 의존하지 않는 예약 표시가 기준이다. 표준 적합 인증을 주장하지 않는다. 오류를 지운다고 사용자가 작성한 폼까지 초기화하지 않는다.

## Responsive behavior

모바일은 가로 스크롤 없이 주 행동을 누를 수 있어야 한다. 데스크톱의 정보 밀도를 줄일 때는 우선순위 낮은 동작을 접되 채널·예약 요약은 숨기지 않는다. 휴대폰 홈 화면 진입 시에도 같은 계정 작업공간을 사용한다.

## Interaction states

빈 계정에는 다음 설정 행동, 기존 계정에는 현재 방을 표시한다. 저장·검색·발송의 성공은 응답 확인 후에만 표시한다. 발송 시점에 이미 전송됐거나 마감된 추천은 제외하고 실제 전송 건수를 알린다. 미리보기는 15분 유효하며 새 미리보기나 관련 설정 변경 후에는 이전 결과를 보낼 수 없다. 오프라인은 비밀 정보 없이 연결 복구 안내만 표시한다.

## Content voice

‘지금 시작’, ‘AI 기반 혁신’ 대신 ‘알림방 만들기’, ‘채널 연결 확인’, ‘미리보기’, ‘이 결과 그대로 발송’처럼 대상과 결과를 쓴다. 검색 비용과 실제 외부 메시지 전송은 클릭 전에 구분한다.

## Implementation constraints

빌드 없는 HTML/CSS/JS + Django 인증. UI 때문에 외부 트래커나 새 디자인 프레임워크를 추가하지 않는다. 상태는 사용자 저장소에서 읽는다. 테스트용 데이터는 격리된 환경에서만 사용한다. 릴리스 확인은 단위 테스트 외에 브라우저에서 비회원 진입, 빈 계정, 저장된 방, 모바일 폭과 키보드 이동을 포함한다.

## Open questions

- [ ] 운영자: 첫 사용자들이 키 발급과 웹훅 연결 중 어디서 멈추는지 관찰해 이후 온보딩 우선순위를 결정한다.
- [ ] 개발자: iOS·Android 실기기에서 파일 선택과 홈 화면 재진입을 확인한다. 에뮬레이션 통과를 실기기 검증으로 갈음하지 않는다.

### 자료와 AI 설정

프로필은 공통 요약과 AI 회사·키, 자료 보관함은 이름 있는 개별 자료의 추가·편집·삭제를 맡는다. 각 방은 모든 자료를 동적으로 참조하거나 일부 자료만 참조한다. 복제는 선별 조건·자료 선택·주기를 재사용하지만 웹훅 비밀·예약 활성·발송 이력을 복제하지 않는다. 모델 ID를 사용자가 기억하거나 입력하도록 요구하지 않는다. 발송 직전에는 서버가 보관한 확인본만 허용한다.
