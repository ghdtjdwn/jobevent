# JobEvent: 조사 근거와 제품 설계 기준

조사일: 2026-11-20. 아래의 외부 기능은 공식 문서·운영자 문서에서 확인했다. **적용 방향은 JobEvent를 위한 설계 판단이며, 해당 제품이 JobEvent의 구현이나 보안을 보증한다는 뜻은 아니다.** 이 문서는 구현 완료 목록이 아니다. 실제 지원 범위는 README와 테스트를 따른다.

## 최종 선택

이 문서의 첫 비교 후 이용 대상이 명확해졌다. 두 명은 **공동 개발자**이고, 가입자는 불특정 다수다. 기본 배포는 설치 없는 **회원제 웹 + 항상 켜진 서버 워커**로 정했다. 사용자별 키·데이터를 서버에서 격리·암호화하고 선택형 로컬 실행만 보조로 유지한다. 현재 수집기는 웹 검색의 인용 링크 및 Greenhouse·Lever 보드다. 아래 표의 RSS·공공 API 등은 조사 후보이지 탑재 목록이 아니다.

## 1. 어떤 앱이 적합한가

**권고: 반응형 웹 설정 화면 + 독립적으로 실행되는 개인용 runner를 먼저 제공한다.** 사용자는 브라우저로 설정하고 Discord/Slack에서 결과를 받는다. 로컬에서도 실행할 수 있지만, 컴퓨터가 꺼지거나 잠들면 실행되지 않는다. 항상 켜진 개인 서버에서 실행하면 브라우저를 닫아도 동작한다. 서버 비용·운영 책임은 별도이며, BYOK가 호스팅까지 무료로 만드는 것은 아니다.

| 형태 | 장점 | 제약 및 적용 판단 |
| --- | --- | --- |
| 로컬 웹 앱 + runner | 운영자에게 이력서·API 키를 맡기지 않고 시작 가능. 같은 UI를 서버에서도 사용 | 사용자의 기기/프로세스가 실행 중이어야 함. 첫 배포의 단일 사용자 범위에 적합 |
| 개인 서버/self-host | 클라이언트가 꺼져도 예약 수집 가능 | HTTPS, 인증, 백업, 업데이트 필요. 공개 인터넷 노출을 기본으로 하지 않음 |
| 호스팅 SaaS | 비개발자 가입·모바일 설정 경험이 쉬움 | 타인의 키·이력서를 보관하는 서비스가 됨. 테넌트 격리·키 관리·삭제·과금 제한·사고 대응을 갖춘 별도 단계 |
| 데스크톱 패키지 | 설치·트레이·OS 비밀 저장소 연동에 유리 | 서명·자동 업데이트·다중 OS 배포 추가. 기기 절전 문제는 남음. runner 검증 후 포장 가능 |
| 모바일 단독 실행 | 휴대폰에서 설정하기 편리 | 정확한 예약 수집 엔진으로 부적합. iOS 실행 시점은 OS가 결정하고 Android 주기 작업도 정확 시각을 보장하지 않음 |
| PWA만으로 실행 | 설치 부담이 작음 | Periodic Background Sync는 브라우저가 실행 여부·시점을 결정. 서버 runner의 대체물이 아님 |

근거: [Apple Background Strategies](https://developer.apple.com/documentation/BackgroundTasks/choosing-background-strategies-for-your-app), [Android WorkManager 주기 작업](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work), [WICG Periodic Background Sync 초안](https://wicg.github.io/background-sync/spec/PeriodicBackgroundSync-index.html). WICG 문서는 표준 확정본이 아닌 커뮤니티 초안이며, 지원 여부는 출시 시 재확인한다.

## 2. 유사 사례에서 가져올 것과 가져오지 않을 것

기능·패턴을 조사한 것이며, 코드를 복사하거나 아래 서비스를 필수 의존성으로 채택한 것은 아니다.

| 사례 / 공식 근거 | 확인한 패턴 | JobEvent 적용 방향 | 가져오지 않을 범위 |
| --- | --- | --- | --- |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 웹 감시, Discord/Slack 등 알림, 사용자 LLM 연결, 전역/감시별 프롬프트 | 방별 관심사·말투, 원문 근거가 있는 알림, 결과 미리보기 | 로그인 자동화·범용 브라우저 스크래핑을 기본값으로 두지 않음 |
| [Huginn](https://github.com/huginn/huginn) | RSS/웹훅 이벤트를 수집·가공·전달하는 agent 연결, 예약 digest | 수집→정규화→필터→설명→전송 경계 분리 | 처음부터 노드 그래프 편집기·임의 코드 실행기를 만들지 않음 |
| [n8n self-host](https://docs.n8n.io/deploy/host-n8n.md), [credential encryption](https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/configuration-examples/set-a-custom-encryption-key.md) | 개인 호스팅, DB 저장 전 credential 암호화, worker 간 암호화 키 일치 | 키와 일반 설정 분리, 재시작·백업·복원 기준 마련 | 범용 자동화 플랫폼 전체나 플러그인 런타임을 제품 핵심에 넣지 않음 |
| [Automatisch](https://github.com/automatisch/automatisch) | 서비스 간 자동화와 자기 서버 데이터 보관 | 연결 설정을 기술 지식보다 작업 목적 중심으로 안내 | 복잡한 서비스 연결 카탈로그를 먼저 늘리지 않음. CE/EE 혼합 라이선스 코드를 무심코 재사용하지 않음 |
| [Miniflux 필터](https://miniflux.app/docs/rules.html) | 전역/피드별 keep·block, 날짜 조건, 규칙 순서 | 포함/제외 키워드와 기간을 먼저 적용해 비용·잡음 감소 | 비개발자에게 정규식 작성 강요 금지 |
| [RSSHub](https://github.com/DIYgod/RSSHub) | 다양한 사이트를 RSS로 변환하는 route 생태계 | 안정적인 RSS 입력 경계와 출처별 adapter 확장성 | 제3자 route 존재를 원본 서비스의 수집 허가로 해석하지 않음 |
| [Apprise](https://github.com/caronc/apprise) | 여러 알림 플랫폼의 송신 형식 통일 | 전송 adapter와 메시지 내용 분리 | 지원하지 않는 플랫폼까지 지원한다고 표시하지 않음 |
| [ntfy](https://docs.ntfy.sh/publish/) | HTTP POST/PUT로 알림, 제목·우선순위·클릭 동작 | 나중에 모바일 push 채널을 추가하기 쉬운 출력 경계 | 공개 topic을 비밀 없는 안전한 저장소로 취급하지 않음 |

## 3. 수집 소스: 실제로 가능한 범위

**AI 키는 검색 API 키가 아니다.** 모델이 링크를 지어내게 하지 않는다. source adapter가 실제로 받은 항목만 추천 후보로 사용한다. “회사/동아리/공모전”은 사용자 목적 템플릿이며, 템플릿을 고른 것만으로 모든 사이트의 수집 권한과 데이터가 생기지 않는다.

| 소스 | 확인한 접근 방식 | 제약 / 적용 방향 |
| --- | --- | --- |
| [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html) | `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` | 공개 게시물 조회는 인증 불필요. 회사별 board token 필요. 전 세계 회사 검색 API가 아님. 제출용 POST는 범위 밖 |
| [Lever Postings API](https://github.com/lever/postings-api) | `GET https://api.lever.co/v0/postings/{site}?mode=json` | 회사별 공개 공고. 전체 공고의 full-text 검색 API가 아님. global/EU 인스턴스 구분. 지원서 제출은 하지 않음 |
| [K-Startup 공공데이터](https://www.data.go.kr/data/15125364/openapi.do) | 창업진흥원 지원사업 공고 REST, JSON/XML, `serviceKey` 필수 | 창업지원·교육·행사 템플릿 후보. 사용자 명의 공공데이터 인증키와 활용 조건 확인 필요. 일반 공모전 전체 데이터는 아님 |
| [고용24 Open API](https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do) | HTTP/XML, 인증키 신청·심사 | 기업회원 전용이며 키 양도 불가 안내. 누구나 무키로 쓰는 기본 수집 소스로 약속하지 않음 |
| [Remotive Public API](https://github.com/remotive-com/remote-jobs-api) | 원격 일자리 JSON API | 출처·원문 링크 의무, 24시간 지연, 하루 최대 4회 권고 및 재배포 제한. 약관 검토 없이 기본 소스로 편입하지 않음 |
| 기관/주최자 RSS·Atom | 사용자가 제공한 공개 feed를 실제 조회 | 동아리/대회/장학금/교육을 동일 경계로 처리 가능. feed 항목의 날짜는 모집 마감일과 다름. 원문 확인 필요 |

### 공개 API 응답 관찰

2026-11-20 로컬에서 개인 정보·인증 없이 GET을 한 결과다. 이는 지속적인 가용성이나 수집/재배포 권한 보증이 아니다.

- Greenhouse `stripe/jobs?content=true`: HTTP 200, 770개. `id`, `title`, `content`, `absolute_url`, `updated_at`, `location` 등 확인.
- Lever `leverdemo?mode=json`: HTTP 200, 10개. `id`, `text`, `descriptionPlain`, `hostedUrl`, `categories` 등 확인. **데모 board 검증이며 실제 모든 회사 검증이 아니다.**
- Lever `netflix?mode=json`: HTTP 404. 회사 식별자를 추측해 내장하지 않고 사용자 입력을 검증해야 한다.
- 공모아뷰 RSS 소개는 검색 결과로 존재를 확인했지만 본문·feed 요청은 403으로 검증 실패. 동작하는 기본 feed라고 표시하지 않는다.

이번 조사에서 국내 개발 동아리/연합 전체를 제공하는 공식 범용 API는 확인하지 못했다. “없다”는 단정은 아니다. 초기 제품은 사용자가 구독할 공식 RSS/원문을 명시하도록 하고, 피드 없는 주최자에는 허용된 별도 adapter를 기여받는다. 수집 실패를 공고 0건으로 바꾸지 않는다.

## 4. 템플릿과 방별 설정의 경계

템플릿은 초기값일 뿐 고정된 봇이 아니다. 템플릿을 고른 뒤에도 방마다 source·조건·주기·말투를 바꿀 수 있어야 한다.

- **채용/인턴:** 역할·지역·경력·근무 방식·필수/제외 키워드. 지원 자격과 이력서 근거를 나눠 표시.
- **동아리/연합:** 모집 파트·학생/졸업 자격·활동 지역·시간·회비·모집 기수. 활동 시간 등 미확인 값은 추정하지 않음.
- **공모전/해커톤:** 분야·팀/개인·참가 자격·일정·필수 결과물·비용. 마감일 원문 확인 링크 유지.
- **교육/부트캠프·장학금·창업지원·커스텀:** 같은 검증된 항목 구조와 사용자 필터 재사용. 데이터 소스가 없는 템플릿은 설정 안내가 필요.
- **방별 공통:** 선택 프로필, 전송 대상, 포함/제외 조건, 일시 정지, 주기, 최대 결과 수, 언어·말투·추가 지시, 미리보기, 실행 이력.

## 5. 외부 연동에서 지켜야 할 계약

### Discord / Slack

- [Discord Webhook Resource](https://docs.discord.com/developers/resources/webhook): 봇 계정 없이 채널에 전송 가능. 텍스트는 2,000자 제한. `wait=true`는 전송 확인 응답을 받는다. `allowed_mentions`를 사용해 외부 원문이나 AI 출력이 의도치 않은 호출을 만들지 않게 한다.
- [Slack Incoming Webhooks](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/): 앱에서 Incoming Webhooks 활성화→워크스페이스에 추가→채널 선택→URL 복사. URL은 비밀이며 공개 Git에 넣지 않는다. webhook은 지정 채널에 묶이고 요청에서 채널·이름·아이콘을 임의로 바꿀 수 없다. 따라서 방마다 다른 webhook을 저장한다.
- 성공 기록은 HTTP 응답을 확인한 후 남긴다. timeout은 수신 여부가 불명확할 수 있다. 외부 서비스와 DB 사이의 정확히 한 번 전송은 보장할 수 없으므로 무조건 재시도로 중복을 만들지 않도록 정책을 명시한다.

### 개인 자료 / BYOK

- 이력서·포트폴리오·GitHub는 **추천 근거**이지 수집 엔진의 명령이나 자격 보증이 아니다. 자료 수집과 모델 전송 전에 사용자가 내용과 공개 범위를 이해해야 한다.
- API 키, webhook, 원문 자료는 export·로그·에러·테스트 fixture·Git에 포함하지 않는다. 키를 UI로 다시 반환하지 않는다. 암호화 키와 DB를 함께 공개하지 않는다.
- 모델은 사용자 키로 호출한다. 프로필과 후보의 필요한 부분이 선택한 AI 제공자에 전달된다는 점, API 과금이 구독과 별개일 수 있다는 점을 UI에 알린다. 무료 사용을 보증하지 않는다.
- 추천에는 실제 수집한 원문 URL·추천 이유·미확인 조건을 남긴다. 점수나 자연스러운 말투가 검증된 자격이라는 뜻은 아니다.
- 임의 URL은 SSRF 경계다. 내부 IP/로컬 주소·리다이렉트·응답 크기·timeout·스킴을 제한해야 한다. 공개 링크에 숨은 프롬프트나 실행 지시를 따르지 않는다.

## 6. 배포 단계별 검증 기준

1. **개인용 실행:** 프로필→소스→템플릿→방별 설정→비전송 미리보기→명시적 전송→재시작 후 중복 방지. 키 없이 재현 가능한 fixture 테스트와 오류 경로를 포함한다.
2. **친구와 협업:** 설치·개발·테스트·기여 가이드, 명시된 라이선스, CI, 버전 고정, 보안 보고 경로. 개인 실자료를 예제로 올리지 않는다.
3. **공개 서버 운영 전:** 계정 인증, 테넌트별 권한, TLS, CSRF/SSRF 보호, rate limit, 데이터 삭제·복원, 제공자 과금 상한·관찰, 장애 시 전송 정책을 검증한다. 개인용 runner가 동작한다는 이유만으로 SaaS 준비 완료라고 하지 않는다.
