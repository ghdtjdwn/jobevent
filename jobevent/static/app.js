"use strict";
const $ = (s) => document.querySelector(s);
const settings = $("#settings"),
  room = $("#room"),
  f = room.elements;
const weekdays = ["월", "화", "수", "목", "금", "토", "일"];
const node = (tag, text) =>
  Object.assign(document.createElement(tag), { textContent: text });
let templates = {},
  busy = false;
function notice(msg) {
  $("#status").hidden = false;
  $("#status").textContent = msg;
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
  notice("처리 중입니다…");
  try {
    await fn();
  } catch (e) {
    notice(e.message);
  } finally {
    busy = false;
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
function edit(r) {
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
  $("#editor").open = true;
  f.name.focus();
}
function card(r) {
  const el = node("article", ""),
    actions = node("div", "");
  actions.className = "actions";
  el.append(
    node("small", r.kind.toUpperCase() + " / " + r.template),
    node("h3", r.name),
    node("p", r.query),
    node(
      "p",
      (r.enabled ? "예약 켜짐" : "예약 꺼짐") +
        " · " +
        r.days.map((i) => weekdays[i]).join(" ") +
        " " +
        r.time +
        " (" +
        r.zone +
        ")",
    ),
    node(
      "p",
      r.enabled
        ? "다음 실행: " +
            new Date(r.due * 1000).toLocaleString("ko-KR", { timeZone: r.zone })
        : "미리보기로 전송 전에 결과를 확인하세요.",
    ),
  );
  for (const [label, op] of [
    ["편집", "edit"],
    ["미리보기", "preview"],
    ["지금 발송", "send"],
    ["삭제", "delete"],
  ]) {
    actions.append(
      button(label, () => {
        if (op === "edit") return edit(r);
        const warning = {
          preview:
            "웹 검색과 추천에 내 API 키를 사용합니다. 발송하지 않습니다.",
          send: "새로 검색하고 추천 결과를 이 방에 실제 발송합니다. API 비용이 들 수 있습니다.",
          delete: "방, 웹훅, 발송 이력을 지웁니다.",
        };
        if (!confirm(r.name + " · " + warning[op])) return;
        task(async () => {
          const x = await api(op, { id: r.id });
          if (x.items) {
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
              const row = node("article", "");
              row.append(
                a,
                node("p", item.reason),
                node("small", "마감: " + (item.deadline || "원문 확인")),
              );
              box.append(row);
            }
            $("#results").scrollIntoView();
          }
          if (op === "delete" && f.id.value === r.id) edit(null);
          await load(false);
          notice(label + " 완료");
        });
      }),
    );
  }
  el.append(actions);
  return el;
}
async function load(initial) {
  const s = await api("state");
  templates = s.templates;
  if (initial && s.hosted) {
    $("#modeLabel").textContent = "내 대시보드";
    $("#privacyCopy").textContent =
      "추천을 실행하면 저장한 프로필과 선별 기준이 내 키로 OpenAI에 전달됩니다. 웹 검색에는 방의 공개 검색어만 사용합니다. 키·웹훅·프로필은 서버에서 암호화해 보관합니다. 회사 기밀, 연락처, 주민등록번호는 넣지 마세요.";
    $("#linkLabel").textContent =
      "GitHub 사용자 또는 공개 포트폴리오 주소 (github.io · vercel.app · notion.site)";
    $("#account").hidden = false;
    $("#who").textContent =
      s.username +
      " · 계정을 삭제하면 내 알림방·키·프로필·기록이 삭제됩니다. 이미 외부 채널에 발송한 메시지는 남습니다.";
  }
  if (initial) {
    settings.elements.profile.value = s.profile;
    settings.elements.model.value = s.model;
    for (const k of Object.keys(templates)) f.template.append(new Option(k, k));
    f.query.value = templates[f.template.value];
  }
  $("#keyState").textContent = s.hasKey
    ? "● 키 등록됨 · 빈칸으로 저장하면 기존 키를 유지합니다."
    : "○ 아직 키가 없습니다.";
  $("#cards").replaceChildren(...s.rooms.map(card));
  if (!s.rooms.length)
    $("#cards").append(
      node("p", "아직 알림방이 없습니다. 아래에서 첫 번째 방을 만드세요."),
    );
  $("#logs").replaceChildren(
    ...s.history.map((h) =>
      node(
        "p",
        new Date(h.stamp * 1000).toLocaleString() +
          " · " +
          (s.rooms.find((r) => r.id === h.room)?.name || "") +
          " · " +
          h.message,
      ),
    ),
  );
  if (!s.history.length)
    $("#logs").append(node("p", "실행하면 결과와 오류가 여기에 표시됩니다."));
}
settings.onsubmit = (e) => {
  e.preventDefault();
  task(async () => {
    await api("profile", Object.fromEntries(new FormData(settings)));
    settings.elements.key.value = "";
    await load(false);
    notice("프로필을 저장했습니다.");
  });
};
room.onsubmit = (e) => {
  e.preventDefault();
  task(async () => {
    const d = Object.fromEntries(new FormData(room));
    d.limit = Number(d.limit);
    d.enabled = f.enabled.checked;
    d.days = [...$("#days").querySelectorAll("input:checked")].map((c) =>
      Number(c.value),
    );
    await api("room", d);
    edit(null);
    $("#editor").open = false;
    await load(false);
    notice("알림방을 저장했습니다.");
  });
};
function appendProfile(text) {
  const p = settings.elements.profile,
    combined = [p.value, text].filter(Boolean).join("\n\n");
  if (combined.length > 20000)
    throw Error(
      "프로필은 총 20,000자까지입니다. 기존 내용을 줄인 뒤 다시 시도하세요.",
    );
  p.value = combined;
  notice("가져왔습니다. 내용을 검토하고 프로필을 저장하세요.");
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
$("#resetRoom").onclick = () => edit(null);
f.template.onchange = () => {
  f.query.value = templates[f.template.value];
};
$("#forget").onclick = () => {
  if (confirm("저장된 키와 프로필을 지우고 모든 예약을 끌까요?"))
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
load(true).catch((e) => notice(e.message));
