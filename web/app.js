function waitForPywebview() {
  return new Promise((resolve) => {
    if (window.pywebview) {
      resolve();
      return;
    }
    window.addEventListener("pywebviewready", () => resolve(), { once: true });
  });
}

const api = () => window.pywebview.api;

function copyToClipboard(text) {
  const s = text == null ? "" : String(text);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(s);
  }
  return new Promise((resolve, reject) => {
    const ta = document.createElement("textarea");
    ta.value = s;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      if (document.execCommand("copy")) resolve();
      else reject(new Error("copy failed"));
    } catch (e) {
      reject(e);
    } finally {
      document.body.removeChild(ta);
    }
  });
}

function bubbleBodyClass(role, isError) {
  const base = "msg msg-body";
  if (role === "user") return `${base} msg-user`;
  if (role === "system") return `${base} msg-system`;
  if (isError) return `${base} msg-error`;
  if (role === "pending") return `${base} msg-pending msg-assistant`;
  return `${base} msg-assistant`;
}

function bubbleWrapClass(role, isError) {
  if (role === "user") return "msg-wrap msg-wrap-user";
  if (role === "system") return "msg-wrap msg-wrap-system";
  if (isError) return "msg-wrap msg-wrap-error";
  if (role === "pending") return "msg-wrap msg-wrap-assistant";
  return "msg-wrap msg-wrap-assistant";
}

/**
 * @param {string} role user | assistant | system | pending
 * @param {boolean} isError
 * @param {{ initialText?: string, withCopy?: boolean }} [opts]
 */
function createMessageBubble(role, isError, opts) {
  const o = opts || {};
  const withCopy = o.withCopy !== false;
  const wrap = el("div", bubbleWrapClass(role, isError));
  const body = el(
    "div",
    bubbleBodyClass(role, isError),
    o.initialText !== undefined ? o.initialText : undefined
  );
  wrap.appendChild(body);
  if (withCopy) {
    const row = el("div", "msg-copy-row");
    const btn = el("button", "btn-msg-copy", "全部复制");
    btn.type = "button";
    btn.addEventListener("click", async () => {
      try {
        await copyToClipboard(body.textContent || "");
        const prev = btn.textContent;
        btn.textContent = "已复制";
        setTimeout(() => {
          btn.textContent = prev;
        }, 1200);
      } catch (_) {
        /* ignore */
      }
    });
    row.appendChild(btn);
    wrap.appendChild(row);
  }
  return { wrap, body };
}

function removeEmptyPlaceholderIfAny(box) {
  const bodies = box.querySelectorAll(".msg-body.msg-system");
  for (const b of bodies) {
    if (b.textContent.includes("暂无消息")) {
      const w = b.closest(".msg-wrap");
      if (w) w.remove();
      else b.remove();
      break;
    }
  }
}

function el(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
}

let currentSessionId = null;
/** @type {object | null} */
let lastSessionMeta = null;
let teamMaxAgents = 0;
/** 递增后可使进行中的打字机动画停止（避免切换会话时旧动画写新 DOM） */
let messageRenderGen = 0;

const LS_SESSION_SORT = "ruyi72_sessionSort";
const LS_SESSION_GROUP = "ruyi72_sessionGroup";
const LS_THEME = "ruyi72_theme";

const THEME_IDS = ["default", "emerald", "violet", "amber"];

const SORT_UPDATED_DESC = "updated_desc";
const SORT_TITLE_ASC = "title_asc";
const SORT_TITLE_DESC = "title_desc";
const SORT_ID_ASC = "id_asc";

const GROUP_NONE = "none";
const GROUP_TYPE = "type";
const GROUP_TIME = "time";

const SESSION_SORT_MODES = [
  SORT_UPDATED_DESC,
  SORT_TITLE_ASC,
  SORT_TITLE_DESC,
  SORT_ID_ASC,
];
const SESSION_GROUP_MODES = [GROUP_NONE, GROUP_TYPE, GROUP_TIME];

const KB_PRESET_LABELS = {
  general: "通用",
  ingest: "收录整理",
  summarize: "摘要索引",
  qa: "问答检索",
};

function kbPresetLabel(p) {
  return KB_PRESET_LABELS[p] || p || "通用";
}

function getSessionSortMode() {
  try {
    const v = localStorage.getItem(LS_SESSION_SORT);
    if (SESSION_SORT_MODES.includes(v)) return v;
  } catch (_) {
    /* ignore */
  }
  return SORT_UPDATED_DESC;
}

function getSessionGroupMode() {
  try {
    const v = localStorage.getItem(LS_SESSION_GROUP);
    if (SESSION_GROUP_MODES.includes(v)) return v;
  } catch (_) {
    /* ignore */
  }
  return GROUP_NONE;
}

function applySavedSessionListPrefs() {
  const sortEl = document.getElementById("session-sort");
  const groupEl = document.getElementById("session-group");
  if (sortEl) sortEl.value = getSessionSortMode();
  if (groupEl) groupEl.value = getSessionGroupMode();
}

function getSavedTheme() {
  try {
    const v = localStorage.getItem(LS_THEME);
    if (THEME_IDS.includes(v)) return v;
  } catch (_) {
    /* ignore */
  }
  return "default";
}

function applyTheme(themeId) {
  const t = THEME_IDS.includes(themeId) ? themeId : "default";
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(LS_THEME, t);
  } catch (_) {
    /* ignore */
  }
  const themeEl = document.getElementById("theme-select");
  if (themeEl) themeEl.value = t;
}

function sessionDisplayTitle(s) {
  return String((s.title || s.id || "").trim() || s.id);
}

function sortSessions(list, mode) {
  const arr = list.slice();
  const zh = "zh-CN";
  if (mode === SORT_TITLE_ASC) {
    arr.sort((a, b) =>
      sessionDisplayTitle(a).localeCompare(sessionDisplayTitle(b), zh)
    );
  } else if (mode === SORT_TITLE_DESC) {
    arr.sort((a, b) =>
      sessionDisplayTitle(b).localeCompare(sessionDisplayTitle(a), zh)
    );
  } else if (mode === SORT_ID_ASC) {
    arr.sort((a, b) => String(a.id).localeCompare(String(b.id)));
  } else {
    arr.sort((a, b) => {
      const ta = String(a.updated_at || "");
      const tb = String(b.updated_at || "");
      return tb.localeCompare(ta);
    });
  }
  return arr;
}

function parseSessionUpdatedMs(s) {
  const t = Date.parse(s.updated_at || "");
  return Number.isNaN(t) ? null : t;
}

function sessionTimeBucket(s, nowMs) {
  const t = parseSessionUpdatedMs(s);
  if (t == null) return "earlier";
  const now = nowMs ?? Date.now();
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const sod = startOfToday.getTime();
  if (t >= sod) return "today";
  const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;
  if (t >= sevenDaysAgo) return "week";
  return "earlier";
}

function groupSessions(sorted, mode) {
  if (mode === GROUP_NONE) {
    return [{ label: "", items: sorted }];
  }
  if (mode === GROUP_TYPE) {
    const team = sorted.filter((s) => s.session_variant === "team");
    const kb = sorted.filter((s) => s.session_variant === "knowledge");
    const std = sorted.filter(
      (s) => s.session_variant !== "team" && s.session_variant !== "knowledge"
    );
    const out = [];
    if (kb.length) out.push({ label: "知识库", items: kb });
    if (team.length) out.push({ label: "团队", items: team });
    if (std.length) out.push({ label: "普通", items: std });
    if (!out.length) out.push({ label: "", items: [] });
    return out;
  }
  const nowMs = Date.now();
  const today = [];
  const week = [];
  const earlier = [];
  for (const s of sorted) {
    const b = sessionTimeBucket(s, nowMs);
    if (b === "today") today.push(s);
    else if (b === "week") week.push(s);
    else earlier.push(s);
  }
  const out = [];
  if (today.length) out.push({ label: "今天", items: today });
  if (week.length) out.push({ label: "近 7 天", items: week });
  if (earlier.length) out.push({ label: "更早", items: earlier });
  if (!out.length) out.push({ label: "", items: [] });
  return out;
}

/**
 * @param {object} s
 * @param {HTMLUListElement} parentUl
 */
function appendSessionRow(s, parentUl) {
  const li = el("li", "session-item");
  li.dataset.id = s.id;
  if (s.id === currentSessionId) li.classList.add("active");

  const body = el("div", "session-item-body");
  const t = el("div", "session-item-title", s.title || s.id);
  let subLine = `${s.mode || "chat"} · ${(s.updated_at || "").slice(0, 19)}`;
  if (s.session_variant === "team" && s.team_size != null) {
    subLine = `团队·${s.team_size} · ${subLine}`;
  } else if (s.session_variant === "knowledge") {
    subLine = `知识库·${kbPresetLabel(s.kb_preset)} · ${subLine}`;
  }
  const sub = el("div", "session-item-meta", subLine);
  body.appendChild(t);
  body.appendChild(sub);
  body.addEventListener("click", () => openSession(s.id));

  const actions = el("div", "session-item-actions");
  const btnRename = el("button", "btn-session-action", "重命名");
  btnRename.type = "button";
  btnRename.title = "重命名";
  btnRename.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    const cur = (s.title || s.id || "").trim() || s.id;
    const name = window.prompt("会话标题", cur);
    if (name === null) return;
    const next = name.trim();
    if (!next) return;
    try {
      const res = await api().rename_session(s.id, next);
      if (!res.ok) {
        window.alert(res.error || "重命名失败");
        return;
      }
      if (res.meta && s.id === currentSessionId) {
        applyMetaToForm(res.meta);
      }
      await renderSessionList();
    } catch (err) {
      window.alert("重命名失败：" + String(err));
    }
  });

  const btnDel = el("button", "btn-session-action", "删除");
  btnDel.type = "button";
  btnDel.title = "删除会话";
  btnDel.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    if (!window.confirm("确定删除此会话？将删除该会话目录及历史。")) return;
    try {
      const res = await api().delete_session(s.id);
      if (res && res.ok === false && res.error) {
        window.alert(res.error);
        return;
      }
      if (res.meta != null && res.messages != null) {
        applyMetaToForm(res.meta);
        renderMessages(res.messages, { instant: true });
      }
      await renderSessionList();
    } catch (err) {
      window.alert("删除失败：" + String(err));
    }
  });

  actions.appendChild(btnRename);
  actions.appendChild(btnDel);
  li.appendChild(body);
  li.appendChild(actions);
  parentUl.appendChild(li);
}

/** 拟人模式流式 UI */
let personaStreamWrap = null;
let personaThinkingEl = null;
let personaContentEl = null;
let personaTurnActive = false;

function scrollMessagesToEnd() {
  const box = document.getElementById("messages");
  if (box) box.scrollTop = box.scrollHeight;
}

function personaResetStreamDom() {
  personaStreamWrap = null;
  personaThinkingEl = null;
  personaContentEl = null;
  personaTurnActive = false;
}

function dispatchPersonaEvent(evt) {
  if (!evt || !evt.type) return;
  const box = document.getElementById("messages");
  const t = evt.type;

  if (t === "turn.started") {
    messageRenderGen += 1;
    personaResetStreamDom();
    removeEmptyPlaceholderIfAny(box);
    appendMessageInstant("user", evt.user_text || "", false);
    const wrap = document.createElement("div");
    wrap.className = "msg-wrap msg-wrap-assistant persona-stream-wrap";
    wrap.dataset.turnId = String(evt.turn_id != null ? evt.turn_id : "");
    const body = document.createElement("div");
    body.className = "msg msg-body msg-assistant persona-stream-body";
    const think = document.createElement("div");
    think.className = "persona-thinking";
    think.hidden = true;
    const content = document.createElement("div");
    content.className = "persona-content";
    body.appendChild(think);
    body.appendChild(content);
    const row = document.createElement("div");
    row.className = "msg-copy-row";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-msg-copy";
    btn.textContent = "全部复制";
    btn.disabled = true;
    btn.addEventListener("click", async () => {
      const parts = [
        think.textContent || "",
        content.textContent || "",
      ].filter(Boolean);
      const txt = parts.join(parts.length > 1 ? "\n\n" : "");
      try {
        await copyToClipboard(txt);
        const prev = btn.textContent;
        btn.textContent = "已复制";
        setTimeout(() => {
          btn.textContent = prev;
        }, 1200);
      } catch (_) {
        /* ignore */
      }
    });
    row.appendChild(btn);
    wrap.appendChild(body);
    wrap.appendChild(row);
    box.appendChild(wrap);
    personaStreamWrap = wrap;
    personaThinkingEl = think;
    personaContentEl = content;
    personaTurnActive = true;
    scrollMessagesToEnd();
    return;
  }

  if (t === "token.delta" && personaTurnActive) {
    if (evt.channel === "thinking" && personaThinkingEl) {
      personaThinkingEl.hidden = false;
      personaThinkingEl.textContent += evt.text || "";
    } else if (evt.channel === "content" && personaContentEl) {
      personaContentEl.textContent += evt.text || "";
    }
    scrollMessagesToEnd();
    return;
  }

  if (t === "error") {
    appendMessage("assistant", evt.message || "错误", true);
    personaTurnActive = false;
    if (personaStreamWrap) {
      personaStreamWrap.classList.add("persona-stream-error");
      const btn = personaStreamWrap.querySelector(".btn-msg-copy");
      if (btn) btn.disabled = false;
    }
    personaResetStreamDom();
    refreshActive().catch(() => {});
    return;
  }

  if (t === "agent.proactive") {
    removeEmptyPlaceholderIfAny(box);
    appendMessageInstant("assistant", evt.text || "", false);
    scrollMessagesToEnd();
    return;
  }

  if (t === "turn.cancelled" && personaStreamWrap) {
    personaStreamWrap.classList.add("persona-interrupted");
  }

  if (t === "message.final" && personaStreamWrap) {
    const btn = personaStreamWrap.querySelector(".btn-msg-copy");
    if (btn) btn.disabled = false;
  }

  if (t === "turn.finished") {
    personaTurnActive = false;
    personaResetStreamDom();
    refreshActive().catch(() => {});
  }
}

function normalizeWorkspaceInput(raw) {
  let s = (raw || "").trim();
  if (!s) return "";
  if (
    (s.startsWith('"') && s.endsWith('"')) ||
    (s.startsWith("'") && s.endsWith("'"))
  ) {
    s = s.slice(1, -1).trim();
  }
  return s;
}

function startTypewriter(node, fullText, renderGen) {
  if (!node) return;
  node.textContent = "";
  const charsPerTick = 4;
  let i = 0;
  function tick() {
    if (renderGen !== messageRenderGen) return;
    i = Math.min(i + charsPerTick, fullText.length);
    node.textContent = fullText.slice(0, i);
    const box = document.getElementById("messages");
    if (box) box.scrollTop = box.scrollHeight;
    if (i < fullText.length) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function setGlobalLoadingText(msg) {
  const el = document.getElementById("global-loading-text");
  if (el) el.textContent = msg;
}

let wsApplyStatusTimer = null;

function setWsApplyStatus(text, clearAfterMs) {
  const st = document.getElementById("ws-apply-status");
  if (!st) return;
  if (wsApplyStatusTimer) {
    clearTimeout(wsApplyStatusTimer);
    wsApplyStatusTimer = null;
  }
  st.textContent = text || "";
  if (clearAfterMs && text) {
    wsApplyStatusTimer = setTimeout(() => {
      st.textContent = "";
      wsApplyStatusTimer = null;
    }, clearAfterMs);
  }
}

function updateTeamModeUi(meta) {
  const isTeam = meta && meta.session_variant === "team";
  const isKb = meta && meta.session_variant === "knowledge";
  document.querySelectorAll('input[name="mode"]').forEach((r) => {
    if (isTeam) {
      r.disabled = true;
      if (r.value === "react") r.checked = false;
      if (r.value === "persona") r.checked = false;
      if (r.value === "chat") r.checked = true;
    } else if (isKb) {
      r.disabled = r.value === "persona";
      if (r.value === "persona") r.checked = false;
    } else {
      r.disabled = false;
    }
  });
  const steps = document.getElementById("react-steps");
  if (steps) steps.disabled = !!isTeam;
  updatePersonaComposerUi(meta);
}

function updatePersonaComposerUi(meta) {
  const m = meta || lastSessionMeta;
  const isPersona =
    m &&
    m.mode === "persona" &&
    m.session_variant !== "team" &&
    m.session_variant !== "knowledge";
  const btn = document.getElementById("btn-persona-interrupt");
  if (btn) btn.classList.toggle("hidden", !isPersona);
}

function openTeamModal() {
  if (teamMaxAgents < 2) return;
  const overlay = document.getElementById("team-modal-overlay");
  const sel = document.getElementById("team-size-select");
  if (!overlay || !sel) return;
  sel.innerHTML = "";
  const maxN = teamMaxAgents;
  for (let n = 2; n <= maxN; n++) {
    const opt = document.createElement("option");
    opt.value = String(n);
    opt.textContent = `${n} 个 Agent（A1…A${n}）`;
    sel.appendChild(opt);
  }
  if (maxN >= 2) {
    const prefer = Math.min(3, maxN);
    sel.value = String(prefer);
  }
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
}

function closeTeamModal() {
  const overlay = document.getElementById("team-modal-overlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
  overlay.setAttribute("aria-hidden", "true");
}

function openKbModal() {
  const overlay = document.getElementById("kb-modal-overlay");
  const titleInp = document.getElementById("kb-title-input");
  const preset = document.getElementById("kb-preset-select");
  if (!overlay) return;
  if (titleInp) titleInp.value = "";
  if (preset) preset.value = "general";
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
}

function closeKbModal() {
  const overlay = document.getElementById("kb-modal-overlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
  overlay.setAttribute("aria-hidden", "true");
}

function copyActionCardSummary(content, card) {
  const parts = [];
  if (content) parts.push(content);
  if (card && Array.isArray(card.options)) {
    const lines = card.options.map((o) => {
      const mark = o.default ? "[建议] " : "";
      return `${mark}${o.label || o.id}`;
    });
    parts.push("[选项]\n" + lines.join("\n"));
  }
  return parts.join("\n\n");
}

function formatCardStatusLabel(card) {
  const s = card && card.status;
  if (s === "confirmed") return "已确认";
  if (s === "rejected") return "已拒绝";
  if (s === "expired") return "已超时自动确认";
  if (s === "superseded") return "已由新卡片替代";
  return s || "";
}

/**
 * @param {object} m
 * @param {HTMLElement} box
 * @param {boolean} instant
 * @param {number} gen
 */
function appendAssistantMessage(m, box, instant, gen) {
  const card = m.card;
  const text = m.content || "";
  if (!card) {
    const { wrap, body } = createMessageBubble("assistant", false, {
      initialText: instant ? text : undefined,
    });
    box.appendChild(wrap);
    if (!instant) startTypewriter(body, text, gen);
    return;
  }

  const wrap = el("div", "msg-wrap msg-wrap-assistant");
  if (text) {
    const tb = el(
      "div",
      "msg msg-body msg-assistant",
      instant ? text : undefined
    );
    wrap.appendChild(tb);
    if (!instant) startTypewriter(tb, text, gen);
  }

  const cardRoot = el("div", "msg-action-card");

  if (card.status === "pending") {
    cardRoot.classList.add("msg-action-card-pending");
    cardRoot.appendChild(
      el("div", "msg-action-card-title", card.title || "请确认")
    );
    if (card.body) {
      cardRoot.appendChild(el("div", "msg-action-card-body", card.body));
    }
    const optsBox = el("div", "msg-action-card-options");
    /** @type {HTMLInputElement[]} */
    const checks = [];
    (card.options || []).forEach((o) => {
      const row = el("label", "msg-action-card-option");
      const inp = document.createElement("input");
      inp.type = "checkbox";
      inp.value = String(o.id || "");
      inp.checked = !!o.default;
      checks.push(inp);
      row.appendChild(inp);
      row.appendChild(document.createTextNode(" "));
      row.appendChild(el("span", "msg-action-card-option-label", o.label || o.id));
      optsBox.appendChild(row);
    });
    cardRoot.appendChild(optsBox);

    const countdown = el("div", "msg-action-card-countdown", "");
    const actions = el("div", "msg-action-card-actions");
    const btnOk = el("button", "btn btn-small btn-primary", "确认");
    btnOk.type = "button";
    const btnNo = el("button", "btn btn-small", "拒绝");
    btnNo.type = "button";
    actions.appendChild(btnOk);
    actions.appendChild(btnNo);
    cardRoot.appendChild(countdown);
    cardRoot.appendChild(actions);

    function gatherIds() {
      return checks.filter((c) => c.checked).map((c) => c.value);
    }
    function lock() {
      btnOk.disabled = true;
      btnNo.disabled = true;
      checks.forEach((c) => {
        c.disabled = true;
      });
    }

    let settled = false;
    /** @type {ReturnType<typeof setInterval> | null} */
    let iv = null;
    function settle() {
      if (settled) return;
      settled = true;
      if (iv != null) {
        clearInterval(iv);
        iv = null;
      }
      lock();
    }

    async function submitCard(action, ids, fromTimeout) {
      settle();
      try {
        const res = await api().submit_action_card(
          card.id,
          action,
          ids,
          !!fromTimeout
        );
        if (!res.ok) {
          window.alert(res.error || "提交失败");
          await refreshActive();
          return;
        }
        if (res.meta) applyMetaToForm(res.meta);
        if (res.messages) renderMessages(res.messages, { instant: true });
        if (res.followup_error) {
          appendMessage("assistant", res.followup_error, true);
        }
        await renderSessionList();
      } catch (e) {
        window.alert(String(e));
        await refreshActive();
      }
    }

    btnOk.addEventListener("click", () => {
      submitCard("confirm", gatherIds(), false);
    });
    btnNo.addEventListener("click", () => {
      submitCard("reject", [], false);
    });

    const total = Math.max(
      10,
      Math.min(600, Number(card.countdown_sec) || 60)
    );
    let remaining = total;
    function tickCountdown() {
      if (gen !== messageRenderGen) return;
      if (remaining <= 0) {
        if (iv != null) {
          clearInterval(iv);
          iv = null;
        }
        countdown.textContent = "正在确认…";
        submitCard("confirm", gatherIds(), true);
        return;
      }
      countdown.textContent = `${remaining} 秒后按当前勾选自动确认`;
      remaining -= 1;
    }
    tickCountdown();
    iv = setInterval(tickCountdown, 1000);
  } else {
    cardRoot.classList.add("msg-action-card-resolved");
    cardRoot.appendChild(
      el("div", "msg-action-card-title", card.title || "确认项")
    );
    if (card.body) {
      cardRoot.appendChild(el("div", "msg-action-card-body", card.body));
    }
    const st = el(
      "div",
      "msg-action-card-status",
      formatCardStatusLabel(card)
    );
    cardRoot.appendChild(st);
    if (card.resolved_at) {
      cardRoot.appendChild(
        el(
          "div",
          "msg-action-card-meta",
          (card.resolved_at || "").slice(0, 19).replace("T", " ")
        )
      );
    }
    const ids = Array.isArray(card.selected_ids) ? card.selected_ids : [];
    if (
      ids.length &&
      Array.isArray(card.options) &&
      card.status !== "rejected"
    ) {
      const labelById = {};
      card.options.forEach((o) => {
        labelById[String(o.id)] = o.label || o.id;
      });
      const line = ids.map((id) => labelById[id] || id).join("，");
      cardRoot.appendChild(
        el("div", "msg-action-card-selected", `选用：${line}`)
      );
    }
  }

  wrap.appendChild(cardRoot);

  const copyRow = el("div", "msg-copy-row");
  const copyBtn = el("button", "btn-msg-copy", "全部复制");
  copyBtn.type = "button";
  copyBtn.addEventListener("click", async () => {
    try {
      await copyToClipboard(copyActionCardSummary(text, card));
      const prev = copyBtn.textContent;
      copyBtn.textContent = "已复制";
      setTimeout(() => {
        copyBtn.textContent = prev;
      }, 1200);
    } catch (_) {
      /* ignore */
    }
  });
  copyRow.appendChild(copyBtn);
  wrap.appendChild(copyRow);
  box.appendChild(wrap);
}

/**
 * @param {object} [options]
 * @param {boolean} [options.instant] 默认 true：服务端同步列表一次写入，避免长历史打字机拖慢
 * @param {boolean} [options.typewriterLastAssistant] 为 true 时仅最后一条 assistant 用打字机，其余仍 instant
 */
function renderMessages(messages, options) {
  const opts = options || {};
  const instantDefault = opts.instant !== false;
  const twLastAsst = opts.typewriterLastAssistant === true;
  let lastAssistantIdx = -1;
  if (twLastAsst && messages && messages.length) {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") {
        lastAssistantIdx = i;
        break;
      }
    }
  }
  const box = document.getElementById("messages");
  box.innerHTML = "";
  messageRenderGen += 1;
  const gen = messageRenderGen;
  const emptyHint = "暂无消息。设置工作区并选择模式后发送。";
  if (!messages || !messages.length) {
    const { wrap, body } = createMessageBubble("system", false, {
      initialText: instantDefault ? emptyHint : undefined,
    });
    box.appendChild(wrap);
    if (!instantDefault) startTypewriter(body, emptyHint, gen);
    box.scrollTop = box.scrollHeight;
    return;
  }
  messages.forEach((m, idx) => {
    const role = m.role;
    const text = m.content || "";
    const msgInstant =
      instantDefault &&
      !(
        twLastAsst &&
        lastAssistantIdx >= 0 &&
        idx === lastAssistantIdx &&
        role === "assistant"
      );
    if (role === "system") {
      const { wrap, body } = createMessageBubble("system", false, {
        initialText: msgInstant ? text : undefined,
      });
      box.appendChild(wrap);
      if (!msgInstant) startTypewriter(body, text, gen);
      return;
    }
    if (role === "user") {
      const { wrap, body } = createMessageBubble("user", false, {
        initialText: msgInstant ? text : undefined,
      });
      box.appendChild(wrap);
      if (!msgInstant) startTypewriter(body, text, gen);
      return;
    }
    if (role === "assistant") {
      appendAssistantMessage(m, box, msgInstant, gen);
    }
  });
  box.scrollTop = box.scrollHeight;
}

function setBusy(busy) {
  const input = document.getElementById("input");
  const send = document.getElementById("send");
  input.disabled = busy;
  send.disabled = busy;
}

function setGlobalLoading(show) {
  const node = document.getElementById("global-loading");
  if (!node) return;
  node.classList.toggle("hidden", !show);
  node.setAttribute("aria-hidden", show ? "false" : "true");
}

/** 仅主内容区（消息 + 输入条）等待态，不遮挡侧栏与顶栏 */
function setMainWaiting(show, text) {
  const node = document.getElementById("main-waiting");
  const te = document.getElementById("main-waiting-text");
  if (!node) return;
  if (show) {
    if (te) te.textContent = text || "请稍候…";
    node.classList.remove("hidden");
    node.setAttribute("aria-hidden", "false");
  } else {
    node.classList.add("hidden");
    node.setAttribute("aria-hidden", "true");
    if (te) te.textContent = "请稍候…";
  }
}

function openMemoryModal() {
  const overlay = document.getElementById("memory-modal-overlay");
  const ta = document.getElementById("memory-input");
  const cancel = document.getElementById("memory-cancel");
  const confirm = document.getElementById("memory-confirm");
  if (!overlay || !ta) return;
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
  ta.value = "";
  ta.disabled = false;
  if (cancel) cancel.disabled = false;
  if (confirm) confirm.disabled = false;
  ta.focus();
}

function closeMemoryModal() {
  const overlay = document.getElementById("memory-modal-overlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
  overlay.setAttribute("aria-hidden", "true");
}

function setMemoryModalBusy(busy) {
  const ta = document.getElementById("memory-input");
  const cancel = document.getElementById("memory-cancel");
  const confirm = document.getElementById("memory-confirm");
  if (ta) ta.disabled = busy;
  if (cancel) cancel.disabled = busy;
  if (confirm) confirm.disabled = busy;
}

async function loadSettings() {
  const line = document.getElementById("settings-line");
  const hint = document.getElementById("storage-hint");
  try {
    const s = await api().get_settings_snapshot();
    const auth =
      s.api_key_configured === true
        ? " · 已配置 API Key"
        : " · 未配置 API Key（远程/云端通常需要）";
    const te =
      s.trust_env === false
        ? " · 直连(不走系统代理)"
        : " · 使用系统代理环境变量";
    line.textContent = `${s.provider} · ${s.api_mode} · ${s.model} · ${s.base_url}${auth}${te}`;
    hint.textContent = s.sessions_root
      ? `历史目录: ${s.sessions_root}`
      : "";
    teamMaxAgents = s.team_max_agents != null ? s.team_max_agents : 0;
    const teamBtn = document.getElementById("btn-team-session");
    if (teamBtn) {
      teamBtn.disabled = teamMaxAgents < 2;
      teamBtn.title =
        teamMaxAgents < 2
          ? "请先在 ruyi72.yaml 配置至少 2 条 team.models"
          : `可创建 2～${teamMaxAgents} 人的团队会话`;
    }
  } catch (e) {
    line.textContent = "无法读取配置：" + String(e);
  }
}

let sessionSearchDebounceTimer = null;

function getSessionSearchQuery() {
  const inp = document.getElementById("session-search-input");
  return inp ? inp.value.trim() : "";
}

function showSessionListPanel() {
  const listEl = document.getElementById("session-list");
  const resultsEl = document.getElementById("session-search-results");
  const emptyEl = document.getElementById("session-search-empty");
  if (listEl) listEl.classList.remove("hidden");
  if (resultsEl) resultsEl.classList.add("hidden");
  if (emptyEl) emptyEl.classList.add("hidden");
}

function showSearchResultsPanel() {
  const listEl = document.getElementById("session-list");
  const resultsEl = document.getElementById("session-search-results");
  if (listEl) listEl.classList.add("hidden");
  if (resultsEl) resultsEl.classList.remove("hidden");
}

function scheduleSessionSearch() {
  if (sessionSearchDebounceTimer) {
    clearTimeout(sessionSearchDebounceTimer);
    sessionSearchDebounceTimer = null;
  }
  sessionSearchDebounceTimer = setTimeout(async () => {
    sessionSearchDebounceTimer = null;
    const q = getSessionSearchQuery();
    if (!q) {
      showSessionListPanel();
      await renderSessionList();
      return;
    }
    await renderSessionSearchResults(q);
  }, 320);
}

function searchHitRoleLabel(role) {
  const m = {
    user: "用户",
    assistant: "助手",
    system: "系统",
    title: "标题",
  };
  return m[role] || role || "—";
}

async function renderSessionSearchResults(query) {
  const q = (query || "").trim();
  const resultsEl = document.getElementById("session-search-results");
  const emptyEl = document.getElementById("session-search-empty");
  if (!resultsEl) return;
  if (!q) {
    showSessionListPanel();
    return;
  }
  showSearchResultsPanel();
  resultsEl.innerHTML = "";
  if (emptyEl) emptyEl.classList.add("hidden");
  let rows = [];
  try {
    rows = await api().search_sessions_text(q);
  } catch (e) {
    const li = el("li", "session-search-error", "搜索失败：" + String(e));
    resultsEl.appendChild(li);
    return;
  }
  if (!rows.length) {
    if (emptyEl) emptyEl.classList.remove("hidden");
    return;
  }
  for (const row of rows) {
    const li = el("li", "session-search-session");
    li.dataset.id = row.session_id;
    if (row.session_id === currentSessionId) li.classList.add("active");
    li.appendChild(
      el("div", "session-search-session-title", row.title || row.session_id)
    );
    (row.hits || []).forEach((h) => {
      const line = el("div", "session-search-hit");
      line.appendChild(
        el("span", "session-search-hit-role", searchHitRoleLabel(h.role))
      );
      const sn = el("span", "session-search-hit-snippet", h.snippet || "");
      line.appendChild(sn);
      li.appendChild(line);
    });
    li.addEventListener("click", () => openSession(row.session_id));
    resultsEl.appendChild(li);
  }
}

function applyMetaToForm(meta) {
  if (!meta) return;
  lastSessionMeta = meta;
  currentSessionId = meta.id;
  const ws = document.getElementById("workspace");
  ws.value = meta.workspace || "";
  const mode = meta.mode || "chat";
  const radios = document.querySelectorAll('input[name="mode"]');
  radios.forEach((r) => {
    r.checked = r.value === mode;
  });
  const steps = document.getElementById("react-steps");
  steps.value = meta.react_max_steps != null ? meta.react_max_steps : 8;
  updateTeamModeUi(meta);
}

async function renderSessionList() {
  const ul = document.getElementById("session-list");
  ul.innerHTML = "";
  const list = await api().list_sessions();
  const sortEl = document.getElementById("session-sort");
  const groupEl = document.getElementById("session-group");
  const sortMode = sortEl ? sortEl.value : getSessionSortMode();
  const groupMode = groupEl ? groupEl.value : getSessionGroupMode();
  const sorted = sortSessions(list, sortMode);
  const groups = groupSessions(sorted, groupMode);
  for (const g of groups) {
    if (g.label) {
      const gli = el("li", "session-group");
      const title = el("div", "session-group-title", g.label);
      const innerUl = el("ul", "session-group-items");
      gli.appendChild(title);
      gli.appendChild(innerUl);
      ul.appendChild(gli);
      for (const s of g.items) appendSessionRow(s, innerUl);
    } else {
      for (const s of g.items) appendSessionRow(s, ul);
    }
  }
  if (getSessionSearchQuery()) {
    await renderSessionSearchResults(getSessionSearchQuery());
  } else {
    showSessionListPanel();
  }
}

async function openSession(id) {
  const data = await api().open_session(id);
  applyMetaToForm(data.meta);
  renderMessages(data.messages, { instant: true });
  await renderSessionList();
}

/**
 * @param {{ typewriterLastAssistant?: boolean, instant?: boolean }} [options]
 */
async function refreshActive(options) {
  const opts = options || {};
  const data = await api().get_active_session();
  applyMetaToForm(data.meta);
  renderMessages(data.messages, {
    instant: opts.instant !== false,
    typewriterLastAssistant: opts.typewriterLastAssistant === true,
  });
  await renderSessionList();
}

async function pushWorkspaceAndMode() {
  const wsEl = document.getElementById("workspace");
  const workspace = normalizeWorkspaceInput(wsEl.value);
  wsEl.value = workspace;
  const mode = document.querySelector('input[name="mode"]:checked').value;
  let react_max_steps = parseInt(
    document.getElementById("react-steps").value,
    10
  );
  if (Number.isNaN(react_max_steps)) react_max_steps = 8;
  await api().update_session({
    workspace: workspace || null,
    mode,
    react_max_steps,
  });
}

async function loadSettingsAndSession() {
  await loadSettings();
  await refreshActive();
}

function appendMessageInstant(role, text, isError) {
  const box = document.getElementById("messages");
  removeEmptyPlaceholderIfAny(box);
  const r = role === "user" ? "user" : "assistant";
  const { wrap, body } = createMessageBubble(r, isError, {
    initialText: text || "",
  });
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
  return body;
}

async function onSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  const isTeam =
    lastSessionMeta && lastSessionMeta.session_variant === "team";
  const isKb =
    lastSessionMeta && lastSessionMeta.session_variant === "knowledge";
  const mode = document.querySelector('input[name="mode"]:checked').value;

  if (mode === "persona" && !isTeam && !isKb) {
    setBusy(true);
    try {
      await pushWorkspaceAndMode();
      const res = await api().persona_send(text);
      if (res.sync) {
        if (!res.ok) {
          appendMessage(
            "assistant",
            res.message || res.error || "失败",
            true
          );
        } else if (res.message) {
          appendMessage("assistant", res.message, false);
        }
      }
    } catch (err) {
      appendMessage("assistant", "调用失败：" + String(err), true);
    } finally {
      setBusy(false);
    }
    return;
  }

  const pendingLabel =
    mode === "react" ? "正在推理与执行…" : "正在思考…";

  appendMessageInstant("user", text, false);
  const box = document.getElementById("messages");
  const { wrap: pendingWrap } = createMessageBubble("pending", false, {
    initialText: pendingLabel,
  });
  box.appendChild(pendingWrap);
  const pendingEl = pendingWrap;
  box.scrollTop = box.scrollHeight;

  setBusy(true);
  try {
    await pushWorkspaceAndMode();
    const res = await api().send_message(text);
    pendingEl.remove();
    setMainWaiting(false);
    await refreshActive({ typewriterLastAssistant: true });
    if (!res.ok && res.append_error) {
      appendMessage("assistant", res.message, true);
    }
  } catch (err) {
    pendingEl.remove();
    setMainWaiting(false);
    appendMessage("assistant", "调用失败：" + String(err), true);
  } finally {
    setBusy(false);
    setMainWaiting(false);
  }
}

function appendMessage(role, text, isError) {
  const box = document.getElementById("messages");
  removeEmptyPlaceholderIfAny(box);
  const r = role === "user" ? "user" : "assistant";
  const { wrap, body } = createMessageBubble(r, isError, {
    initialText: undefined,
  });
  box.appendChild(wrap);
  const gen = messageRenderGen;
  startTypewriter(body, text || "", gen);
}

function init() {
  window.__ruyiPersonaDispatch = dispatchPersonaEvent;

  applySavedSessionListPrefs();
  applyTheme(getSavedTheme());
  const themeSelect = document.getElementById("theme-select");
  if (themeSelect) {
    themeSelect.addEventListener("change", () => applyTheme(themeSelect.value));
  }

  const sortEl = document.getElementById("session-sort");
  const groupEl = document.getElementById("session-group");
  if (sortEl) {
    sortEl.addEventListener("change", () => {
      try {
        localStorage.setItem(LS_SESSION_SORT, sortEl.value);
      } catch (_) {
        /* ignore */
      }
      renderSessionList();
    });
  }
  if (groupEl) {
    groupEl.addEventListener("change", () => {
      try {
        localStorage.setItem(LS_SESSION_GROUP, groupEl.value);
      } catch (_) {
        /* ignore */
      }
      renderSessionList();
    });
  }

  const searchInp = document.getElementById("session-search-input");
  if (searchInp) {
    searchInp.addEventListener("input", () => scheduleSessionSearch());
  }

  document.getElementById("chat-form").addEventListener("submit", onSubmit);

  const personaInterruptBtn = document.getElementById("btn-persona-interrupt");
  if (personaInterruptBtn) {
    personaInterruptBtn.addEventListener("click", async () => {
      try {
        await api().persona_interrupt();
      } catch (_) {
        /* ignore */
      }
    });
  }

  const input = document.getElementById("input");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      document.getElementById("chat-form").requestSubmit();
    }
  });

  document.getElementById("btn-new-session").addEventListener("click", async () => {
    setBusy(true);
    try {
      await api().create_session(null);
      await refreshActive();
    } catch (e) {
      appendMessage("assistant", "新建失败：" + String(e), true);
    } finally {
      setBusy(false);
    }
  });

  document.getElementById("btn-kb-session").addEventListener("click", () => {
    openKbModal();
  });

  document.getElementById("kb-cancel").addEventListener("click", () => {
    closeKbModal();
  });

  document
    .getElementById("kb-modal-overlay")
    .addEventListener("click", (ev) => {
      if (ev.target.id !== "kb-modal-overlay") return;
      closeKbModal();
    });

  document.getElementById("kb-confirm").addEventListener("click", async () => {
    const presetEl = document.getElementById("kb-preset-select");
    const titleInp = document.getElementById("kb-title-input");
    const preset = presetEl ? presetEl.value : "general";
    const titleRaw = titleInp ? titleInp.value.trim() : "";
    setBusy(true);
    try {
      const res = await api().create_knowledge_session(
        preset,
        titleRaw || null
      );
      if (!res.ok) {
        window.alert(res.error || "创建知识库会话失败");
        return;
      }
      closeKbModal();
      if (res.meta) applyMetaToForm(res.meta);
      if (res.messages) renderMessages(res.messages, { instant: true });
      await renderSessionList();
      setWsApplyStatus(
        "知识库会话已创建：请将「工作区」设为文档根目录后点击「应用」。",
        10000
      );
    } catch (e) {
      window.alert("创建知识库会话失败：" + String(e));
    } finally {
      setBusy(false);
    }
  });

  document.getElementById("btn-apply-ws").addEventListener("click", () => {
    const btn = document.getElementById("btn-apply-ws");
    if (!btn || btn.disabled) return;
    if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "应用中…";
    setWsApplyStatus("正在保存工作区与模式…");

    queueMicrotask(async () => {
      setBusy(true);
      setGlobalLoading(true);
      setGlobalLoadingText("正在应用工作区与模式…");
      try {
        await pushWorkspaceAndMode();
        await refreshActive();
        setWsApplyStatus("已应用", 2000);
      } catch (e) {
        setWsApplyStatus("应用失败：" + String(e));
        appendMessage("assistant", "应用失败：" + String(e), true);
      } finally {
        setGlobalLoading(false);
        setGlobalLoadingText("请稍候…");
        setBusy(false);
        btn.disabled = false;
        btn.textContent = btn.dataset.defaultLabel || "应用";
      }
    });
  });

  document.querySelectorAll('input[name="mode"]').forEach((r) => {
    r.addEventListener("change", async () => {
      try {
        await pushWorkspaceAndMode();
        await refreshActive();
      } catch (_) {
        /* ignore */
      }
    });
  });

  document.getElementById("react-steps").addEventListener("change", async () => {
    try {
      await pushWorkspaceAndMode();
      await refreshActive();
    } catch (_) {
      /* ignore */
    }
  });

  document.getElementById("btn-memory-save").addEventListener("click", () => {
    openMemoryModal();
  });

  document.getElementById("memory-cancel").addEventListener("click", () => {
    closeMemoryModal();
  });

  document
    .getElementById("memory-modal-overlay")
    .addEventListener("click", (ev) => {
      if (ev.target.id !== "memory-modal-overlay") return;
      const loading = document.getElementById("global-loading");
      if (loading && !loading.classList.contains("hidden")) return;
      closeMemoryModal();
    });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const loading = document.getElementById("global-loading");
    if (loading && !loading.classList.contains("hidden")) return;
    const kbOv = document.getElementById("kb-modal-overlay");
    if (kbOv && !kbOv.classList.contains("hidden")) {
      closeKbModal();
      return;
    }
    const teamOv = document.getElementById("team-modal-overlay");
    if (teamOv && !teamOv.classList.contains("hidden")) {
      closeTeamModal();
      return;
    }
    const overlay = document.getElementById("memory-modal-overlay");
    if (!overlay || overlay.classList.contains("hidden")) return;
    closeMemoryModal();
  });

  document.getElementById("memory-confirm").addEventListener("click", async () => {
    const ta = document.getElementById("memory-input");
    const text = (ta && ta.value) ? ta.value.trim() : "";
    if (!text) {
      appendMessage("assistant", "请输入我要记住的内容。", true);
      return;
    }
    setGlobalLoading(true);
    setGlobalLoadingText("正在提取记忆，请稍候…");
    setMemoryModalBusy(true);
    try {
      const res = await api().extract_memory(text);
      const st = res.stats || {};
      let msg = "";
      if (!res.ok) {
        msg =
          "记忆提取失败：" + (res.error || "未知错误") + `（已写入：事实 ${
            st.facts || 0
          } 条，事件 ${st.events || 0} 条，关系 ${st.relations || 0} 条）`;
        appendMessage("assistant", msg, true);
      } else {
        msg = `已提取记忆：事实 ${st.facts || 0} 条，事件 ${
          st.events || 0
        } 条，关系 ${st.relations || 0} 条。`;
        appendMessage("assistant", msg, false);
      }
    } catch (e) {
      appendMessage("assistant", "记忆提取异常：" + String(e), true);
    } finally {
      setGlobalLoading(false);
      setGlobalLoadingText("请稍候…");
      setMemoryModalBusy(false);
      if (ta) ta.value = "";
      closeMemoryModal();
    }
  });

  document.getElementById("btn-team-session").addEventListener("click", () => {
    if (teamMaxAgents < 2) return;
    openTeamModal();
  });

  document.getElementById("team-cancel").addEventListener("click", () => {
    closeTeamModal();
  });

  document
    .getElementById("team-modal-overlay")
    .addEventListener("click", (ev) => {
      if (ev.target.id === "team-modal-overlay") closeTeamModal();
    });

  document.getElementById("team-confirm").addEventListener("click", async () => {
    const sel = document.getElementById("team-size-select");
    const n = sel ? parseInt(sel.value, 10) : 2;
    if (Number.isNaN(n) || n < 2) return;
    setBusy(true);
    try {
      const r = await api().create_team_session(n, null);
      if (!r.ok) {
        appendMessage("assistant", r.error || "创建团队会话失败", true);
        return;
      }
      applyMetaToForm(r.meta);
      renderMessages(r.messages, { instant: true });
      await renderSessionList();
      closeTeamModal();
    } catch (e) {
      appendMessage("assistant", "创建团队会话失败：" + String(e), true);
    } finally {
      setBusy(false);
    }
  });

  document
    .getElementById("btn-memory-view")
    .addEventListener("click", async () => {
      setBusy(true);
      try {
        const res = await api().browse_memory(10);
        appendMessage("assistant", res.text || "当前还没有记忆条目。", false);
      } catch (e) {
        appendMessage("assistant", "浏览记忆失败：" + String(e), true);
      } finally {
        setBusy(false);
      }
    });
}

waitForPywebview()
  .then(() => {
    init();
    return loadSettingsAndSession();
  })
  .catch((e) => {
    document.getElementById("settings-line").textContent =
      "pywebview 未就绪：" + String(e);
  });
