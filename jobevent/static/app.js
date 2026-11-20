"use strict";
const $ = (s) => document.querySelector(s);
const settings = $("#settings"),
  room = $("#room"),
  f = room.elements;
const weekdays = ["월", "화", "수", "목", "금", "토", "일"];
const node = (tag, text) =>
  Object.assign(document.createElement(tag), { textContent: text });
let templates = {},
  state = null,
  busy = false,
  noticeTimer;
const providers = {
  openai: ["OpenAI", "https://platform.openai.com/api-keys"],
  google: ["Google Gemini", "https://aistudio.google.com/apikey"],
  anthropic: [
    "Anthropic Claude",
    "https://console.anthropic.com/settings/keys",
  ],
};
function notice(msg, kind = "done") {
  clearTimeout(noticeTimer);
  const status = $("#status");
  status.hidden = false;
  status.dataset.kind = kind;
  status.replaceChildren(node("span", msg));
  if (kind !== "busy")
    status.append(button("닫기", () => (status.hidden = true)));
  if (kind === "done")
    noticeTimer = setTimeout(() => (status.hidden = true), 6500);
}
function providerDetails() {
  const selected = settings.elements.provider.value;
  const [label, link] = providers[selected];
  $("#keyLabel").textContent = label + " API 키";
  $("#keyLink").textContent = label + "에서 키 발급하기";
  $("#keyLink").href = link;
  const changed = !!state?.hasKey && selected !== (state.provider || "openai");
  settings.elements.key.required = changed;
  $("#keyState").textContent = changed
    ? "제공자를 바꾸려면 새 API 키를 입력하세요."
    : state?.hasKey
      ? "키 등록됨 · 빈칸으로 저장하면 현재 키를 유지합니다."
      : "키 미등록 · 연결 전에도 프로필을 작성할 수 있습니다.";
}
function group(tag, cls, ...children) {
  const el = document.createElement(tag);
  el.className = cls;
  el.append(...children);
  return el;
}
function empty(title, copy) {
  return group("div", "empty", node("h3", title), node("p", copy));
}
function go(path) {
  if (location.hash === "#" + path) route();
  else location.hash = path;
}
function route(focus = true) {
  if (!state) return;
  const [path, id] = location.hash.slice(1).split("/");
  let screen = ["profile", "library", "history"].includes(path)
    ? path
    : "rooms";
  if (path === "account" && state.hosted) screen = "account";
  if (["new", "edit", "copy"].includes(path)) {
    const r = id && state.rooms.find((item) => item.id === id);
    if (path === "new" || r) {
      screen = "editor";
      edit(r || null, path === "copy");
    }
  }
  document
    .querySelectorAll(".page")
    .forEach((el) => (el.hidden = el.id !== screen));
  const active = screen === "editor" ? "rooms" : screen;
  document.querySelectorAll(".rail nav a").forEach((a) => {
    if (a.hash === "#" + active) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const title = $("#" + screen + " h1").textContent;
  $("#locationLabel").textContent = title;
  document.title = title + " · Jobevent";
  if (focus) {
    $("#main").focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
}
window.addEventListener("hashchange", () => route());
function sourceFields() {
  const web = f.source.value === "web";
  $("#boardField").hidden = web;
  f.board.disabled = web;
  f.board.required = !web;
}
function templateHint() {
  $("#templateHint").textContent = templates[f.template.value]
    ? "선택한 틀: " +
      templates[f.template.value] +
      " · 검색 조건과 일정은 이 방에서 변경할 수 있습니다."
    : "찾고 싶은 기회의 종류를 검색 조건에 직접 입력하세요.";
}
function csrf() {
  return (
    document.cookie
      .split("; ")
      .find((v) => v.startsWith("csrftoken="))
      ?.slice(10) || ""
  );
}
async function api(path, data) {
  const r = await fetch(
    "/api/" + path,
    data === undefined
      ? {}
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Jobevent": "1",
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify(data),
        },
  );
  if (r.status === 401) {
    location.assign("/signin");
    throw Error("다시 로그인하세요.");
  }
  if (!r.headers.get("content-type")?.includes("application/json"))
    throw Error("요청이 거부되었습니다. 페이지를 새로고침하세요.");
  const result = await r.json();
  if (!r.ok) throw Error(result.error || "요청을 처리하지 못했습니다.");
  return result;
}
async function task(fn) {
  if (busy) return;
  busy = true;
  document.body.setAttribute("aria-busy", "true");
  notice("처리 중입니다…", "busy");
  try {
    await fn();
  } catch (e) {
    notice(e.message, "error");
  } finally {
    busy = false;
    document.body.removeAttribute("aria-busy");
  }
}
function button(label, fn) {
  const b = node("button", label);
  b.type = "button";
  b.onclick = fn;
  return b;
}
for (const [i, day] of weekdays.entries()) {
  const l = node("label", "");
  const c = document.createElement("input");
  c.type = "checkbox";
  c.value = i;
  c.defaultChecked = true;
  l.append(c, day);
  $("#days").append(l);
}
function edit(r, copy = false) {
  room.reset();
  if (r) {
    for (const k of [
      "id",
      "name",
      "template",
      "query",
      "preferences",
      "source",
      "board",
      "tone",
      "zone",
      "time",
      "limit",
    ])
      f[k].value = r[k] ?? (k === "source" ? "web" : "");
    f.enabled.checked = r.enabled;
    $("#days")
      .querySelectorAll("input")
      .forEach((c, i) => (c.checked = r.days.includes(i)));
  } else {
    f.id.value = "";
    f.query.value = templates[f.template.value] || "";
  }
  if (copy) {
    f.id.value = "";
    f.name.value = r.name.slice(0, 55) + " 복사본";
    f.enabled.checked = false;
  }
  $("#editorTitle").textContent = copy
    ? "알림방 복제"
    : r
      ? "알림방 편집"
      : "알림방 만들기";
  f.hook.required = !r || copy;
  $("#hookHelp").textContent = copy
    ? "조건·자료·일정만 복사했습니다. 새 웹훅을 입력하세요. 발송 기록과 예약 활성 상태는 복사하지 않습니다."
    : r
      ? "빈칸이면 현재 연결을 유지합니다."
      : "저장한 뒤 AI 비용 없이 연결 확인 메시지를 보낼 수 있습니다.";
  roomRefs(r?.referenceIds ?? null);
  sourceFields();
  templateHint();
}
function card(r) {
  const el = node("article", ""),
    actions = node("div", "");
  el.className = "room-card";
  actions.className = "actions";
  const badge = node("span", r.enabled ? "예약 켜짐" : "수동 실행");
  badge.className = "badge" + (r.enabled ? " on" : "");
  el.append(
    group(
      "div",
      "card-head",
      group(
        "div",
        "",
        group("span", "eyebrow", r.kind + " · " + r.template),
        node("h3", r.name),
      ),
      badge,
    ),
    group("p", "query", r.query),
    group(
      "p",
      "schedule",
      r.enabled
        ? "다음 실행 " +
            new Date(r.due * 1000).toLocaleString("ko-KR", {
              timeZone: r.zone,
            }) +
            " · " +
            r.zone
        : "예약 꺼짐 · 수동으로 미리보거나 발송할 수 있습니다.",
    ),
  );
  const controls = {};
  for (const [label, op] of [
    ["편집", "edit"],
    ["채널 연결 확인", "channel-test"],
    ["미리보기", "preview"],
    ["새로 검색해 발송", "send"],
    ["삭제", "delete"],
  ]) {
    controls[op] = button(label, () => {
      if (op === "edit") return go("edit/" + r.id);
      const warning = {
        "channel-test":
          "이 방에 연결 확인 메시지 1건을 보냅니다. AI를 호출하거나 프로필을 보내지 않습니다.",
        preview: "웹 검색과 추천에 내 API 키를 사용합니다. 발송하지 않습니다.",
        send: "새로 검색하고 추천 결과를 이 방에 실제 발송합니다. API 비용이 들 수 있습니다.",
        delete:
          "이 방의 웹훅·실행 기록·중복 발송 이력을 지웁니다. 다른 방과 참고 자료는 유지됩니다.",
      };
      if (!confirm(r.name + " · " + warning[op])) return;
      task(async () => {
        const x = await api(op, { id: r.id });
        if (x.items) {
          $("#resultTitle").textContent =
            r.name + " · " + (op === "preview" ? "미리보기" : "발송 결과");
          $("#results").hidden = false;
          const box = $("#items");
          box.replaceChildren();
          if (!x.items.length)
            box.append(node("p", "근거 있는 신규 추천이 없습니다."));
          for (const item of x.items) {
            const a = node("a", item.title + " ↗");
            a.href = item.url;
            a.target = "_blank";
            a.rel = "noopener noreferrer";
            const row = group("article", "result-row");
            row.append(
              a,
              node("p", item.reason),
              node("small", "마감: " + (item.deadline || "원문 확인")),
            );
            if (item.check) row.append(node("p", "확인할 조건: " + item.check));
            box.append(row);
          }
          if (x.previewToken) {
            const send = button("이 결과 그대로 발송", () => {
              if (
                !confirm(
                  r.name +
                    "에 확인한 신규 결과만 보낼까요? 추가 AI 비용은 없습니다.",
                )
              )
                return;
              task(async () => {
                const out = await api("send-preview", {
                  id: r.id,
                  token: x.previewToken,
                });
                send.disabled = true;
                await load(false);
                notice(
                  out.items.length +
                    "건 발송 · 이미 보냈거나 마감된 결과는 제외했습니다.",
                );
              });
            });
            box.append(
              node(
                "p",
                r.name + " · 15분 안에 추가 검색 없이 보낼 수 있습니다.",
              ),
              send,
            );
          }
          $("#results").scrollIntoView();
        }
        if (op === "delete") $("#results").hidden = true;
        await load(false);
        notice(label + " 완료");
      });
    });
  }
  const extra = document.createElement("details");
  extra.append(
    node("summary", "기타 작업"),
    group(
      "div",
      "actions",
      button("새 방으로 복제", () => go("copy/" + r.id)),
      controls.send,
      controls.delete,
    ),
  );
  controls.preview.classList.add("primary");
  actions.replaceChildren(
    controls.preview,
    controls["channel-test"],
    controls.edit,
  );
  el.append(actions, extra);
  return el;
}
async function load(initial) {
  const s = await api("state");
  state = s;
  templates = s.templates;
  $("#loading").hidden = true;
  $("#briefLabel").textContent = s.rooms.length ? "현재 상태" : "처음 시작하기";
  const hasContext = Boolean(s.profile.trim() || s.references?.length);
  const ready = !!(s.hasKey && hasContext);
  const next = s.rooms
    .filter((r) => r.enabled)
    .sort((a, b) => a.due - b.due)[0];
  $("#briefTitle").textContent = !ready
    ? "추천 프로필을 준비하세요"
    : !s.rooms.length
      ? "첫 알림방을 만드세요"
      : next
        ? "다음 예약 · " + next.name
        : "알림방에서 미리보기를 실행하세요";
  $("#briefCopy").textContent = !ready
    ? "사용할 AI와 내 경험을 등록하면 공고를 맞춤 선별할 수 있습니다."
    : !s.rooms.length
      ? "받고 싶은 기회와 Discord 또는 Slack 채널을 연결하세요."
      : next
        ? new Date(next.due * 1000).toLocaleString("ko-KR", {
            timeZone: next.zone,
          }) +
          " (" +
          next.zone +
          ")에 시작할 예정입니다."
        : "자동 발송은 꺼져 있습니다. 아래 방에서 연결과 추천 결과를 먼저 확인하세요.";
  const act = $("#briefAction");
  act.hidden = ready && s.rooms.length && !next;
  act.href = !ready
    ? "#profile"
    : !s.rooms.length
      ? "#new"
      : next
        ? "#edit/" + next.id
        : "#rooms";
  act.textContent = !ready
    ? "추천 프로필 설정"
    : !s.rooms.length
      ? "알림방 만들기"
      : "예약 설정 보기";
  $("#steps").replaceChildren(
    ...[
      ["키 등록", s.hasKey],
      ["추천 자료", hasContext],
      ["알림방 생성", !!s.rooms.length],
    ].map(([label, done], i) => {
      const dot = node("b", done ? "✓" : String(i + 1));
      dot.setAttribute("aria-hidden", "true");
      const step = group("span", "step" + (done ? " done" : ""), dot, label);
      step.setAttribute("aria-label", label + " " + (done ? "완료" : "미완료"));
      return step;
    }),
  );
  $("#roomCount").textContent = s.rooms.length;
  $("#activeCount").textContent =
    "예약 중 " + s.rooms.filter((r) => r.enabled).length + "개";
  if (initial && s.hosted) {
    $("#identity").textContent = s.username;
    $("#privacyCopy").textContent =
      "추천을 실행하면 저장한 프로필과 선별 기준이 내 키로 선택한 AI 제공자에 전달됩니다. 웹 검색에는 방의 공개 검색어만 사용합니다. 키·웹훅·프로필은 서버에서 암호화해 보관합니다. 회사 기밀, 연락처, 주민등록번호는 넣지 마세요.";
    $("#linkLabel").textContent =
      "GitHub 사용자 또는 공개 포트폴리오 주소 (github.io · vercel.app · notion.site)";
    $("#accountNav").hidden = false;
    $("#who").textContent = s.username + " 님의 계정입니다.";
  }
  if (initial) {
    settings.elements.profile.value = s.profile;
    settings.elements.provider.value = s.provider || "openai";
    for (const [k, v] of Object.entries(templates)) {
      f.template.append(new Option(k, k));
      $("#templateGuide").append(
        node("dt", k),
        node("dd", (v || "직접 입력한 조건에 맞는 공개 모집 공고") + " · " + s.templateChecks[k]),
      );
    }
    f.query.value = templates[f.template.value];
    templateHint();
  }
  providerDetails();
  renderRefs();
  $("#cards").replaceChildren(...s.rooms.map(card));
  if (!s.rooms.length)
    $("#cards").append(
      empty(
        "아직 만든 알림방이 없습니다",
        "방을 만들면 채널, 다음 실행 시각, 발송 작업이 여기에 표시됩니다.",
      ),
    );
  $("#logs").replaceChildren(
    ...s.history.map((h) => {
      const stamp = new Date(h.stamp * 1000),
        t = node("time", stamp.toLocaleString("ko-KR"));
      t.dateTime = stamp.toISOString();
      return group(
        "div",
        "log-entry",
        t,
        group(
          "div",
          "",
          node(
            "strong",
            s.rooms.find((r) => r.id === h.room)?.name || "알림방",
          ),
          node("p", h.message),
        ),
      );
    }),
  );
  if (!s.history.length)
    $("#logs").append(
      empty(
        "아직 실행 기록이 없습니다",
        "채널 연결 확인이나 미리보기를 실행하면 결과가 여기에 남습니다.",
      ),
    );
  if (initial) route(false);
}
settings.elements.provider.onchange = () => {
  settings.elements.key.value = "";
  providerDetails();
};
$("#refresh").onclick = () =>
  task(async () => {
    await load(false);
    notice("최신 실행 기록입니다.");
  });
f.source.onchange = sourceFields;
settings.onsubmit = (e) => {
  e.preventDefault();
  task(async () => {
    await api("profile", Object.fromEntries(new FormData(settings)));
    settings.elements.key.value = "";
    await load(false);
    $("#results").hidden = true;
    notice("프로필을 저장했습니다.");
  });
};
room.onsubmit = (e) => {
  e.preventDefault();
  task(async () => {
    const d = Object.fromEntries(new FormData(room));
    d.limit = Number(d.limit);
    d.enabled = f.enabled.checked;
    d.referenceIds =
      f.refMode.value === "all"
        ? null
        : [...$("#refChoices").querySelectorAll("input:checked")].map(
            (c) => c.value,
          );
    delete d.refMode;
    d.days = [...$("#days").querySelectorAll("input:checked")].map((c) =>
      Number(c.value),
    );
    await api("room", d);
    await load(false);
    go("rooms");
    notice("알림방을 저장했습니다.");
  });
};
const refForm = $("#refForm");
function editRef(ref) {
  refForm.reset();
  refForm.hidden = false;
  $("#refFormTitle").textContent = ref ? "자료 편집" : "자료 추가";
  refForm.elements.id.value = ref?.id || "";
  refForm.elements.title.value = ref?.title || "";
  refForm.elements.text.value = ref?.text || "";
  refForm.elements.title.focus();
}
function closeRef() {
  refForm.reset();
  refForm.hidden = true;
  $("#newRef").focus();
}
function renderRefs() {
  const refs = state.references || [];
  $("#refCount").textContent = refs.length + " / 30";
  $("#refs").replaceChildren(
    ...refs.map((ref) => {
      const heading = node("h3", ref.title),
        details = group(
          "p",
          "caption",
          ref.text.length.toLocaleString() + "자",
        );
      const rem = button("삭제", () => {
        if (
          confirm(
            ref.title +
              " 자료를 보관함과 이 자료를 쓰는 모든 방에서 제거할까요? 다른 자료와 기존 발송 이력은 유지됩니다.",
          )
        )
          task(async () => {
            await api("reference-delete", { id: ref.id });
            if (refForm.elements.id.value === ref.id) closeRef();
            await load(false);
            notice("자료를 삭제했습니다.");
          });
      });
      rem.className = "quiet danger";
      return group(
        "article",
        "room-card",
        heading,
        details,
        group(
          "div",
          "actions",
          button("편집", () => editRef(ref)),
          rem,
        ),
      );
    }),
  );
  if (!refs.length)
    $("#refs").append(
      empty(
        "보관한 자료가 없습니다",
        "자료 추가에서 본문을 입력하거나 파일·공개 링크를 가져오세요.",
      ),
    );
}
function roomRefs(ids) {
  f.refMode.value = ids === null ? "all" : "selected";
  const refs = state.references || [];
  const box = $("#refChoices");
  box.hidden = ids === null;
  box.replaceChildren(
    ...refs.map((ref) => {
      const c = document.createElement("input");
      c.type = "checkbox";
      c.value = ref.id;
      c.checked = ids?.includes(ref.id) ?? false;
      return group("label", "check", c, ref.title);
    }),
  );
  if (!refs.length)
    box.append(node("p", "고를 자료가 없습니다. 공통 프로필만 사용합니다."));
}
f.refMode.onchange = () =>
  ($("#refChoices").hidden = f.refMode.value === "all");
$("#newRef").onclick = () => editRef(null);
$("#cancelRef").onclick = closeRef;
refForm.onsubmit = (e) => {
  e.preventDefault();
  task(async () => {
    await api("reference-save", Object.fromEntries(new FormData(refForm)));
    await load(false);
    closeRef();
    notice("참고 자료를 저장했습니다.");
  });
};
function appendProfile(text) {
  const p = refForm.elements.text;
  const merged = [p.value, text].filter(Boolean).join("\n\n");
  if (merged.length > 12000) {
    if (!confirm("12,000자를 넘었습니다. 앞부분만 가져와 편집할까요?")) {
      notice("가져오기를 취소했습니다.");
      return;
    }
  }
  p.value = merged.slice(0, 12000);
  p.focus();
  notice("본문을 확인하고 자료를 저장하세요.");
}
$("#import").onclick = () =>
  task(async () =>
    appendProfile(
      (await api("reference", { url: $("#reference").value })).text,
    ),
  );
$("#file").onchange = () =>
  task(async () => {
    const file = $("#file").files[0];
    if (!file) return;
    if (file.size > 4_000_000) throw Error("4MB 이하 파일을 선택하세요.");
    if (file.name.toLowerCase().endsWith(".pdf")) {
      const data = await new Promise((ok, fail) => {
        const rd = new FileReader();
        rd.onload = () => ok(rd.result.split(",")[1]);
        rd.onerror = fail;
        rd.readAsDataURL(file);
      });
      appendProfile((await api("pdf", { data })).text);
    } else appendProfile(await file.text());
    $("#file").value = "";
  });

f.template.onchange = () => {
  f.query.value = templates[f.template.value];
  templateHint();
};
$("#forget").onclick = () => {
  if (
    confirm(
      "키·공통 프로필·보관한 참고 자료를 모두 지우고 모든 방의 예약을 끌까요? 되돌릴 수 없습니다.",
    )
  )
    task(async () => {
      await api("forget", {});
      settings.elements.key.value = "";
      settings.elements.profile.value = "";
      await load(false);
      notice("삭제했습니다.");
    });
};
function accountPost(path, values = {}) {
  const form = document.createElement("form");
  form.method = "post";
  form.action = path;
  for (const [name, value] of Object.entries({
    ...values,
    csrfmiddlewaretoken: csrf(),
  })) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.append(input);
  }
  document.body.append(form);
  form.submit();
}
$("#logout").onclick = () => accountPost("/logout");
$("#deleteAccount").onsubmit = (e) => {
  e.preventDefault();
  if (confirm("계정과 저장한 모든 데이터를 영구 삭제할까요?"))
    accountPost("/account/delete", {
      password: e.currentTarget.elements.password.value,
    });
};
load(true).catch((e) => {
  const loading = $("#loading");
  loading.textContent = "워크스페이스를 불러오지 못했습니다. ";
  loading.append(button("다시 시도", () => location.reload()));
  notice(e.message, "error");
});
