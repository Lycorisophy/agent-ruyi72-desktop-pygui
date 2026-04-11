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

const LS_LLM_CLIENT_LOG = "ruyi72_llmClientLog";

function isLlmClientLogEnabled() {
  try {
    return localStorage.getItem(LS_LLM_CLIENT_LOG) === "1";
  } catch (_) {
    return false;
  }
}

function applyLlmClientLogCheckbox() {
  const cb = document.getElementById("llm-client-log-enabled");
  if (cb) cb.checked = isLlmClientLogEnabled();
}

function summarizeApiResult(res) {
  if (res == null) return res;
  if (typeof res !== "object") return String(res).slice(0, 200);
  const o = {};
  if ("ok" in res) o.ok = res.ok;
  if ("sync" in res) o.sync = res.sync;
  if ("append_error" in res) o.append_error = res.append_error;
  if (res.error != null) o.error = String(res.error).slice(0, 200);
  if (res.message != null) {
    const m = String(res.message);
    o.message_len = m.length;
    if (m.length > 160) o.message_preview = m.slice(0, 160) + "…";
    else o.message = m;
  }
  if (res.stats && typeof res.stats === "object") o.stats = res.stats;
  return o;
}

/**
 * @template T
 * @param {string} label
 * @param {() => Promise<T>} fn
 * @returns {Promise<T>}
 */
async function withLlmApiLog(label, fn) {
  if (!isLlmClientLogEnabled()) {
    return fn();
  }
  const t0 = performance.now();
  try {
    const res = await fn();
    console.info(
      "[Ruyi LLM API]",
      label,
      "ok",
      `${Math.round(performance.now() - t0)}ms`,
      summarizeApiResult(res)
    );
    return res;
  } catch (err) {
    console.warn(
      "[Ruyi LLM API]",
      label,
      "error",
      `${Math.round(performance.now() - t0)}ms`,
      err
    );
    throw err;
  }
}

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
    const btnSplit = el("button", "btn-msg-split", "分屏打开");
    btnSplit.type = "button";
    btnSplit.title = "在预览栏打开本条正文";
    btnSplit.addEventListener("click", (ev) => {
      ev.stopPropagation();
      openMessageInSplit(body);
    });
    row.appendChild(btnSplit);
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

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function insertAtCursor(textarea, text) {
  const ta = textarea;
  if (!ta) return;
  const start = ta.selectionStart ?? ta.value.length;
  const end = ta.selectionEnd ?? ta.value.length;
  const v = ta.value;
  ta.value = v.slice(0, start) + text + v.slice(end);
  const pos = start + text.length;
  ta.selectionStart = pos;
  ta.selectionEnd = pos;
  ta.focus();
}

function showSecondaryDirPanel() {
  secondaryPaneMode = "dir";
  const panel = document.getElementById("workspace-preview-panel");
  const msg = document.getElementById("secondary-message-view");
  if (panel) panel.classList.remove("hidden");
  if (msg) msg.classList.add("hidden");
}

function showSecondaryMessagePanel(text, statusLine) {
  secondaryPaneMode = "message";
  const panel = document.getElementById("workspace-preview-panel");
  const msg = document.getElementById("secondary-message-view");
  const bc = document.getElementById("preview-dir-breadcrumb");
  if (panel) panel.classList.add("hidden");
  if (msg) {
    msg.classList.remove("hidden");
    msg.textContent = text || "";
  }
  if (bc) bc.textContent = "";
  const st = document.getElementById("preview-status");
  if (st) st.textContent = statusLine || "";
}

function setSecondaryPreviewText(text, statusLine) {
  showSecondaryMessagePanel(text, statusLine);
}

function workspacePreviewParentPath(current) {
  const c = (current || "").trim();
  if (!c) return null;
  const i = c.lastIndexOf("/");
  return i < 0 ? "" : c.slice(0, i);
}

function joinWorkspaceRelPath(base, name) {
  const b = (base || "").replace(/\\/g, "/").replace(/\/+$/, "");
  return b ? `${b}/${name}` : name;
}

function formatFileSize(n) {
  if (n == null) return "—";
  const b = Number(n);
  if (!Number.isFinite(b)) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`;
  return `${(b / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatMtimeShort(iso) {
  if (!iso) return "—";
  const s = String(iso);
  return s.length >= 19 ? s.slice(0, 19).replace("T", " ") : s;
}

function updateWorkspacePreviewUpButton() {
  const btn = document.getElementById("btn-preview-up");
  if (!btn) return;
  const canUp = workspacePreviewParentPath(workspacePreviewCurrentPath) != null;
  btn.disabled = !canUp;
}

async function refreshWorkspacePreview(relPath) {
  showSecondaryDirPanel();
  const rel =
    relPath === undefined || relPath === null
      ? workspacePreviewCurrentPath
      : String(relPath);
  workspacePreviewCurrentPath = rel;
  const st = document.getElementById("preview-status");
  const tbody = document.getElementById("workspace-preview-tbody");
  const bc = document.getElementById("preview-dir-breadcrumb");
  if (st) st.textContent = "加载中…";
  if (tbody) tbody.innerHTML = "";
  updateWorkspacePreviewUpButton();
  try {
    const r = await api().list_workspace_preview(rel || "");
    if (!r.ok) {
      if (st) st.textContent = r.error || "加载失败";
      if (bc) bc.textContent = "";
      return;
    }
    if (bc) {
      bc.textContent = r.path
        ? `当前：${r.path}`
        : "当前：工作区根目录";
    }
    let tail = r.truncated ? "（仅显示前 500 项）" : "";
    if (st) st.textContent = `共 ${(r.entries || []).length} 项${tail}`;
    if (tbody) {
      for (const e of r.entries || []) {
        const tr = document.createElement("tr");
        const kind = e.kind === "dir" ? "dir" : "file";
        tr.className =
          kind === "dir"
            ? "workspace-preview-row-dir"
            : "workspace-preview-row-file";
        tr.dataset.kind = kind;
        tr.dataset.name = e.name || "";
        const tdName = document.createElement("td");
        tdName.textContent = e.name || "";
        const tdKind = document.createElement("td");
        tdKind.textContent = kind === "dir" ? "文件夹" : "文件";
        const tdSize = document.createElement("td");
        tdSize.textContent =
          kind === "dir" ? "—" : formatFileSize(e.size);
        const tdTime = document.createElement("td");
        tdTime.textContent = formatMtimeShort(e.mtime);
        tr.appendChild(tdName);
        tr.appendChild(tdKind);
        tr.appendChild(tdSize);
        tr.appendChild(tdTime);
        if (kind === "dir") {
          tr.addEventListener("click", () => {
            const next = joinWorkspaceRelPath(workspacePreviewCurrentPath, e.name);
            void refreshWorkspacePreview(next);
          });
        } else {
          tr.title = "第一版仅展示基本信息，不读取文件内容";
        }
        tbody.appendChild(tr);
      }
    }
    updateWorkspacePreviewUpButton();
  } catch (e) {
    if (st) st.textContent = String(e);
  }
}

function refreshWorkspacePreviewIfSplitActive() {
  if (!document.body.classList.contains("split-active")) return;
  if (secondaryPaneMode !== "dir") return;
  void refreshWorkspacePreview(workspacePreviewCurrentPath);
}

function setSplitActive(active) {
  document.body.classList.toggle("split-active", !!active);
  const btn = document.getElementById("btn-toggle-split");
  const pane = document.getElementById("pane-secondary");
  if (btn) btn.setAttribute("aria-pressed", active ? "true" : "false");
  if (pane) pane.setAttribute("aria-hidden", active ? "false" : "true");
  if (active && secondaryPaneMode === "dir") {
    void refreshWorkspacePreview(workspacePreviewCurrentPath);
  }
}

function openMessageInSplit(bodyEl) {
  const t = (bodyEl && bodyEl.textContent) || "";
  showSecondaryMessagePanel(t, "来自对话消息（纯文本）");
  setSplitActive(true);
}

const PROMPT_TEMPLATES_GENERAL = [
  {
    label: "总结上文",
    text: "请基于当前对话上文做简要总结，条目不超过 8 条。",
  },
  {
    label: "列出要点",
    text: "请把上文整理为分级要点（Markdown），尽量简洁。",
  },
  {
    label: "解释代码",
    text: "请解释下面代码在做什么、关键逻辑与潜在风险（如有）：\n\n```\n\n```",
  },
  {
    label: "中译",
    text: "请将下面内容译为通顺的简体中文，保留专有名词必要时附原文：\n\n",
  },
];

function getModeFromDom() {
  const r = document.querySelector('input[name="mode"]:checked');
  return r ? r.value : "chat";
}

/** 与后端 mode 值对应的中文展示名 */
function modeDisplayLabel(mode) {
  if (mode === "chat") return "安全";
  if (mode === "react") return "普通";
  if (mode === "persona") return "拟人";
  return mode || "—";
}

function updatePromptTemplateBar() {
  const bar = document.getElementById("prompt-template-bar");
  if (!bar) return;
  bar.innerHTML = "";
  const mode = getModeFromDom();
  const meta = lastSessionMeta;
  /** @type {{ label: string, text: string }[]} */
  const items = PROMPT_TEMPLATES_GENERAL.map((x) => ({ ...x }));
  if (mode === "react") {
    items.push({
      label: "列出根目录",
      text: "请用 list_dir 查看工作区根目录，并概括有哪些文件与子文件夹。",
    });
  }
  if (meta && meta.session_variant === "knowledge") {
    items.push(
      {
        label: "收录整理",
        text: "请查看工作区目录结构，对待整理或收件箱中的文件给出归类与命名建议；不要删除任何文件，先列方案。",
      },
      {
        label: "摘要索引",
        text: "请阅读相关文档后，生成可写入索引的「标题 + 一句话摘要」列表（Markdown）。",
      },
      {
        label: "库内问答",
        text: "请仅根据工作区内已有文件回答（若信息不足请说明已查看的路径）：",
      }
    );
  }
  const ta = document.getElementById("input");
  for (const { label, text } of items) {
    const b = el("button", "prompt-chip", label);
    b.type = "button";
    b.addEventListener("click", () => insertAtCursor(ta, text));
    bar.appendChild(b);
  }
}

async function updateContextRail() {
  const sessionEl = document.getElementById("context-session-block");
  const toolsEl = document.getElementById("context-tools-block");
  const skillsEl = document.getElementById("context-skills-block");
  if (!sessionEl || !toolsEl || !skillsEl) return;

  const m = lastSessionMeta;
  if (!m) {
    sessionEl.innerHTML = '<p class="context-kv">暂无会话</p>';
    toolsEl.innerHTML = "";
    skillsEl.innerHTML = "";
    return;
  }

  const variantLabel =
    m.session_variant === "team"
      ? "团队"
      : m.session_variant === "knowledge"
        ? "知识库"
        : "普通";
  let teamLine = "";
  if (m.session_variant === "team" && m.team_size != null) {
    teamLine = `<p class="context-kv">团队人数：${escapeHtml(String(m.team_size))}</p>`;
  }
  let presetLine = "";
  if (m.session_variant === "knowledge") {
    presetLine = `<p class="context-kv">知识库预设：${escapeHtml(
      kbPresetLabel(m.kb_preset)
    )}</p>`;
  }

  sessionEl.innerHTML = `
    <h4>当前会话</h4>
    <p class="context-kv">标题：${escapeHtml(m.title || m.id || "")}</p>
    <p class="context-kv">id：${escapeHtml(m.id || "")}</p>
    <p class="context-kv">类型：${escapeHtml(variantLabel)}</p>
    ${teamLine}
    ${presetLine}
    <p class="context-kv">模式：${escapeHtml(modeDisplayLabel(m.mode))}</p>
    <p class="context-kv">智能体步数上限：${escapeHtml(
      String(m.react_max_steps != null ? m.react_max_steps : 8)
    )}</p>
    <p class="context-kv">工作区：${escapeHtml(m.workspace || "（未设置）")}</p>
  `;

  const mode = m.mode || "chat";
  let toolsHtml = "<h4>可用工具</h4>";
  if (m.session_variant === "team") {
    toolsHtml +=
      "<p>团队会话为链式多模型编排，无本地 ReAct 工具调用。</p>";
  } else if (mode === "react") {
    toolsHtml += `<ul class="context-tools-ul">
      <li><strong>read_file</strong> — 读取工作区内 UTF-8 文本</li>
      <li><strong>list_dir</strong> — 列出目录内容</li>
      <li><strong>write_file</strong> — 写入或覆盖 UTF-8 文本文件</li>
      <li><strong>run_shell</strong> — 在工作区根目录执行 shell 命令</li>
      <li><strong>load_skill</strong> — 按名称加载技能文档</li>
      <li><strong>browse_memory</strong> — 浏览跨会话记忆摘要</li>
      <li><strong>search_memory</strong> — 按关键词搜索记忆（可选按事件的 world_kind / temporal_kind 过滤）</li>
    </ul>`;
  } else {
    toolsHtml +=
      "<p>当前为<strong>安全</strong>模式：仅注入安全技能目录与确认卡片说明，模型不会自动执行 ReAct 工具循环。需要某技能全文时可发送：<code>加载技能:技能名</code>。</p>";
    if (mode === "persona") {
      toolsHtml +=
        "<p>拟人模式由运行时注入技能与安全说明，仍无智能体工具循环。</p>";
    }
  }
  toolsEl.innerHTML = toolsHtml;

  try {
    const skills = await api().list_skills_compact();
    const byLevel = [[], [], []];
    for (const s of skills) {
      const lv = Math.min(2, Math.max(0, Number(s.level) || 0));
      byLevel[lv].push(s);
    }
    const labels = ["safe(0)", "act(1)", "warn_act(2)"];
    let html = "";
    for (let i = 0; i < 3; i++) {
      if (!byLevel[i].length) continue;
      html += `<p class="context-kv" style="margin-top:8px;font-weight:600;color:var(--text-label)">${labels[i]}</p>`;
      for (const s of byLevel[i]) {
        html += `<div class="context-skill-item"><span class="context-skill-name">${escapeHtml(
          s.name || ""
        )}</span><br/><span>${escapeHtml(s.description || "")}</span></div>`;
      }
    }
    skillsEl.innerHTML = html || '<p class="context-kv">（无技能）</p>';
  } catch (e) {
    skillsEl.innerHTML = `<p class="context-kv">${escapeHtml(
      "技能列表加载失败：" + String(e)
    )}</p>`;
  }
}

let currentSessionId = null;
/** @type {object | null} */
let lastSessionMeta = null;

function setAvatarSpeaking(on) {
  const stage = document.getElementById("avatar-strip-stage");
  if (stage) stage.classList.toggle("avatar-speaking", !!on);
}

/** @param {string} mode */
function avatarDefaultsForMode(mode) {
  if (mode === "pixel")
    return { avatar_mode: "pixel", avatar_ref: "bundled:pixel_cat" };
  if (mode === "live2d")
    return { avatar_mode: "live2d", avatar_ref: "bundled:live2d_default" };
  return { avatar_mode: "off", avatar_ref: "" };
}

/**
 * 与下拉框一致；像素模式用「角色」；若未改模式则保留 meta.avatar_ref（如 live2d 或 file:）。
 */
function avatarPayloadFromUi() {
  const sel = document.getElementById("session-avatar-mode");
  const mode = (sel && sel.value) || "off";
  const m = lastSessionMeta;
  if (mode === "pixel") {
    const pk = document.getElementById("session-avatar-pixel-kind");
    const k = (pk && pk.value) || "cat";
    const fromUi = "bundled:pixel_" + k;
    if (
      m &&
      (m.avatar_mode || "off") === "pixel" &&
      typeof m.avatar_ref === "string" &&
      m.avatar_ref.startsWith("file:")
    ) {
      return { avatar_mode: "pixel", avatar_ref: m.avatar_ref };
    }
    return { avatar_mode: "pixel", avatar_ref: fromUi };
  }
  if (
    m &&
    (m.avatar_mode || "off") === mode &&
    typeof m.avatar_ref === "string" &&
    m.avatar_ref.length
  ) {
    return { avatar_mode: mode, avatar_ref: m.avatar_ref };
  }
  return avatarDefaultsForMode(mode);
}

function applyAvatarToForm(meta) {
  const sel = document.getElementById("session-avatar-mode");
  const wrap = document.getElementById("session-avatar-pixel-kind-wrap");
  const pixelKind = document.getElementById("session-avatar-pixel-kind");
  if (!sel) return;
  if (!meta) {
    sel.value = "off";
    if (wrap) {
      wrap.classList.add("hidden");
      wrap.setAttribute("aria-hidden", "true");
    }
    return;
  }
  const m = meta.avatar_mode || "off";
  sel.value =
    m === "pixel" || m === "live2d" || m === "off" ? m : "off";
  if (wrap) {
    const show = m === "pixel";
    wrap.classList.toggle("hidden", !show);
    wrap.setAttribute("aria-hidden", show ? "false" : "true");
  }
  if (pixelKind && m === "pixel") {
    const ref = meta.avatar_ref || "";
    const match = ref.match(/^bundled:pixel_(cat|dog|rabbit|fox)$/);
    if (match) pixelKind.value = match[1];
    else if (ref === "bundled:pixel_default") pixelKind.value = "cat";
    else pixelKind.value = "cat";
  }
}

/**
 * @param {object | null} meta
 */
async function refreshSessionAvatar(meta) {
  const stage = document.getElementById("avatar-strip-stage");
  const status = document.getElementById("avatar-strip-status");
  const strip = document.getElementById("avatar-strip");
  if (!stage || !window.RuyiAvatar) return;
  const off = !meta || (meta.avatar_mode || "off") === "off";
  if (strip) strip.classList.toggle("avatar-strip-off", off);
  await window.RuyiAvatar.mount(meta, stage, status);
}
/** 分屏右侧：当前列出的工作区相对目录，"" 表示根 */
let workspacePreviewCurrentPath = "";
/** "dir" | "message" — 消息分屏正文与目录表互斥 */
let secondaryPaneMode = "dir";
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

/** ReAct 阻塞期间由后端 evaluate_js 推送的步骤摘要 */
let reactStreamProgressEl = null;
let reactStreamLines = [];

/** ReAct 运行中节流拉取 dialogue_state（更新状态条步序，避免每步打 API） */
let dialogueStateRefreshTimer = null;

function scheduleDialogueStateRefreshFromReact() {
  if (dialogueStateRefreshTimer) return;
  dialogueStateRefreshTimer = setTimeout(() => {
    dialogueStateRefreshTimer = null;
    refreshDialogueState().catch(() => {});
  }, 450);
}

function dispatchReactEvent(evt) {
  if (!evt || typeof evt !== "object") return;
  const t = evt.type;
  if (t === "react.start") {
    scheduleDialogueStateRefreshFromReact();
    return;
  }
  if (t === "react.done") {
    refreshDialogueState().catch(() => {});
    return;
  }
  if (t === "react.progress" && reactStreamProgressEl) {
    const line = String(evt.line || "").trim();
    if (!line) return;
    reactStreamLines.push(line);
    if (reactStreamLines.length > 32) {
      reactStreamLines = reactStreamLines.slice(-32);
    }
    reactStreamProgressEl.textContent = reactStreamLines.join("\n");
    reactStreamProgressEl.scrollTop = reactStreamProgressEl.scrollHeight;
    scrollMessagesToEnd();
    scheduleDialogueStateRefreshFromReact();
  }
}

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

/** @param {{ phase?: string, last_error?: string | null, state_extension?: Record<string, unknown> }} snap */
function updateDialogueStateBarFromSnapshot(snap) {
  const bar = document.getElementById("dialogue-state-bar");
  if (!bar) return;
  const phase = snap && snap.phase;
  const err =
    snap && snap.last_error != null && String(snap.last_error).trim()
      ? String(snap.last_error).trim()
      : "";
  bar.classList.toggle("dialogue-state-warning", Boolean(err));
  if (err) {
    bar.textContent = err;
    bar.hidden = false;
    return;
  }
  const labels = {
    idle: "就绪",
    streaming: "输出中…",
    react_running: "ReAct 中…",
    team_running: "团队编排中…",
    followup_pending: "后续处理中…",
  };
  const base = labels[phase] || (phase && phase !== "idle" ? String(phase) : "");
  const ext = snap && snap.state_extension;
  let line = base;
  if (ext && typeof ext === "object") {
    const team = /** @type {{ current_slot?: number, team_size?: number }} */ (ext.team);
    const react = /** @type {{ step_index?: number }} */ (ext.react);
    if (team && team.current_slot != null && phase === "team_running") {
      const sz = team.team_size != null ? team.team_size : "?";
      line = `${base} · A${team.current_slot}/${sz}`;
    } else if (react && react.step_index != null && phase === "react_running") {
      line = `${base} · 步序 ${react.step_index}`;
    }
  }
  bar.textContent = line;
  bar.hidden = !line || phase === "idle";
}

async function refreshDialogueState() {
  try {
    const apiFn = api();
    if (!apiFn || typeof apiFn.get_dialogue_state !== "function") return;
    const res = await apiFn.get_dialogue_state();
    if (res && res.ok !== false) {
      updateDialogueStateBarFromSnapshot(res);
    }
  } catch (_) {
    /* ignore */
  }
}

function dispatchPersonaEvent(evt) {
  if (!evt || !evt.type) return;
  const box = document.getElementById("messages");
  const t = evt.type;

  if (t === "state.changed") {
    const snap = {
      phase: evt.phase,
      last_error: evt.last_error,
      state_extension: evt.state_extension,
    };
    if (evt.recovered && evt.message) {
      snap.last_error = evt.message;
    }
    updateDialogueStateBarFromSnapshot(snap);
    return;
  }

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
      setAvatarSpeaking(true);
    }
    scrollMessagesToEnd();
    return;
  }

  if (t === "error") {
    setAvatarSpeaking(false);
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
    setAvatarSpeaking(false);
    personaStreamWrap.classList.add("persona-interrupted");
  }

  if (t === "message.final" && personaStreamWrap) {
    const btn = personaStreamWrap.querySelector(".btn-msg-copy");
    if (btn) btn.disabled = false;
  }

  if (t === "turn.finished") {
    setAvatarSpeaking(false);
    personaTurnActive = false;
    personaResetStreamDom();
    reactStreamProgressEl = null;
    reactStreamLines = [];
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
  updateInterruptButtonUi(meta);
}

function updateInterruptButtonUi(meta) {
  const m = meta || lastSessionMeta;
  const isTeam = m && m.session_variant === "team";
  const show =
    m &&
    !isTeam &&
    (m.mode === "persona" || m.mode === "chat" || m.mode === "react");
  const btn = document.getElementById("btn-persona-interrupt");
  if (btn) btn.classList.toggle("hidden", !show);
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

function openPendingIdentityModal() {
  const overlay = document.getElementById("pending-identity-overlay");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
  refreshPendingIdentityList();
}

function closePendingIdentityModal() {
  const overlay = document.getElementById("pending-identity-overlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
  overlay.setAttribute("aria-hidden", "true");
}

async function refreshPendingIdentityList() {
  const el = document.getElementById("pending-identity-list");
  if (!el) return;
  el.textContent = "加载中…";
  try {
    const res = await api().list_pending_identity_merges(100);
    const items = res && Array.isArray(res.items) ? res.items : [];
    if (!items.length) {
      el.textContent = "当前没有待合并条目。";
      return;
    }
    el.innerHTML = "";
    items.forEach((it) => {
      const row = document.createElement("div");
      row.className = "pending-identity-row";
      const tid = it.identity_target || "memory";
      const sum = it.summary || "";
      const k = it.key || "";
      const v = it.value || "";
      const pid = it.id || "";
      row.innerHTML =
        `<p class="pending-identity-summary"><strong>${escapeHtml(
          String(sum)
        )}</strong> <code>${escapeHtml(String(k))}</code> = ${escapeHtml(
          String(v)
        )}</p>` +
        `<p class="pending-identity-meta">目标: ${escapeHtml(
          String(tid)
        )} · id: <code>${escapeHtml(String(pid))}</code></p>`;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-small btn-primary";
      btn.textContent = "应用";
      btn.addEventListener("click", async () => {
        if (!window.confirm("确定将本条合并到身份文件并从队列移除？")) return;
        setBusy(true);
        try {
          const ar = await api().apply_pending_identity_merge(pid);
          if (!ar.ok) {
            appendMessage(
              "assistant",
              "应用失败：" + (ar.error || "未知错误"),
              true
            );
          } else {
            appendMessage(
              "assistant",
              "已合并到身份文件：" + (ar.applied_to || ""),
              false
            );
            await refreshPendingIdentityList();
          }
        } catch (e) {
          appendMessage("assistant", String(e), true);
        } finally {
          setBusy(false);
        }
      });
      row.appendChild(btn);
      el.appendChild(row);
    });
  } catch (e) {
    el.textContent = "加载失败：" + String(e);
  }
}

function setMemoryModalBusy(busy) {
  const ta = document.getElementById("memory-input");
  const cancel = document.getElementById("memory-cancel");
  const confirm = document.getElementById("memory-confirm");
  if (ta) ta.disabled = busy;
  if (cancel) cancel.disabled = busy;
  if (confirm) confirm.disabled = busy;
}

let llmProviderPresets = {};
let llmClearApiKeyNextSave = false;

function applyLlmPresetHint(provider) {
  const el = document.getElementById("llm-preset-hint");
  if (!el) return;
  const p = llmProviderPresets[provider];
  el.textContent = p && p.hint ? p.hint : "";
}

function toggleLlmOllamaOnly(isOllama) {
  const wrap = document.getElementById("llm-api-mode-wrap");
  if (wrap) wrap.classList.toggle("hidden", !isOllama);
}

function fillLlmFormFromSnapshot(s) {
  const prov = document.getElementById("llm-provider");
  if (prov) prov.value = s.provider || "ollama";
  const bu = document.getElementById("llm-base-url");
  if (bu) bu.value = s.base_url || "";
  const mo = document.getElementById("llm-model");
  if (mo) mo.value = s.model || "";
  const te = document.getElementById("llm-temperature");
  if (te) te.value = String(s.temperature != null ? s.temperature : 0.6);
  const mt = document.getElementById("llm-max-tokens");
  if (mt) mt.value = String(s.max_tokens != null ? s.max_tokens : 2048);
  const am = document.getElementById("llm-api-mode");
  if (am) am.value = s.api_mode || "native";
  const trust = document.getElementById("llm-trust-env");
  if (trust) {
    const tc = s.trust_env_config;
    trust.value =
      tc === null || tc === undefined ? "" : tc === true ? "true" : "false";
  }
  const key = document.getElementById("llm-api-key");
  if (key) {
    key.value = "";
    key.type = "password";
  }
  const vis = document.getElementById("llm-api-key-visible");
  if (vis) vis.checked = false;
  llmClearApiKeyNextSave = false;
  toggleLlmOllamaOnly((s.provider || "ollama") === "ollama");
  applyLlmPresetHint(s.provider || "ollama");
}

async function loadSettings() {
  const line = document.getElementById("settings-line");
  const hint = document.getElementById("storage-hint");
  try {
    const [s, defs] = await Promise.all([
      api().get_settings_snapshot(),
      api().get_llm_defaults(),
    ]);
    llmProviderPresets = (defs && defs.presets) || {};
    fillLlmFormFromSnapshot(s);
    const auth =
      s.api_key_configured === true
        ? " · 已配置 API Key"
        : " · 未配置 API Key（远程/云端通常需要）";
    const te =
      s.trust_env === false
        ? " · 直连(不走系统代理)"
        : " · 使用系统代理环境变量";
    const temp =
      s.temperature != null ? ` · temp ${s.temperature}` : "";
    line.textContent = `${s.provider} · ${s.api_mode} · ${s.model} · ${s.base_url}${temp}${auth}${te}`;
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
  await loadIdentityPrompts();
}

async function loadIdentityPrompts() {
  const st = document.getElementById("identity-settings-status");
  try {
    const r = await api().get_identity_prompt_files();
    if (!r.ok) {
      if (st) st.textContent = r.error || "读取失败";
      return;
    }
    const pu = document.getElementById("identity-path-user");
    const ps = document.getElementById("identity-path-soul");
    const pm = document.getElementById("identity-path-memory");
    if (pu && r.paths) pu.textContent = r.paths.user || "";
    if (ps && r.paths) ps.textContent = r.paths.soul || "";
    if (pm && r.paths) pm.textContent = r.paths.memory || "";
    const u = document.getElementById("identity-user");
    const s = document.getElementById("identity-soul");
    const m = document.getElementById("identity-memory");
    if (u) u.value = r.user != null ? r.user : "";
    if (s) s.value = r.soul != null ? r.soul : "";
    if (m) m.value = r.memory != null ? r.memory : "";
    const trunc =
      r.user_truncated || r.soul_truncated || r.memory_truncated;
    if (st) {
      st.textContent = trunc
        ? "部分内容超过约 256KB，已截断显示；完整内容请直接打开上述路径下的文件编辑。"
        : "";
    }
  } catch (e) {
    if (st) st.textContent = "读取身份提示词失败：" + String(e);
  }
}

async function saveIdentityPromptsFromForm() {
  const st = document.getElementById("identity-settings-status");
  const payload = {
    user: (document.getElementById("identity-user") || {}).value,
    soul: (document.getElementById("identity-soul") || {}).value,
    memory: (document.getElementById("identity-memory") || {}).value,
  };
  if (st) st.textContent = "保存中…";
  try {
    const r = await api().save_identity_prompt_files(payload);
    if (!r.ok) {
      if (st) st.textContent = "保存失败：" + (r.error || "");
      return;
    }
    if (st) st.textContent = "已保存。";
    await loadIdentityPrompts();
  } catch (e) {
    if (st) st.textContent = "保存异常：" + String(e);
  }
}

async function saveLlmSettingsFromForm() {
  const st = document.getElementById("llm-settings-status");
  const provEl = document.getElementById("llm-provider");
  const payload = {
    provider: provEl ? provEl.value : "ollama",
    base_url: (document.getElementById("llm-base-url") || {}).value.trim(),
    model: (document.getElementById("llm-model") || {}).value.trim(),
    temperature: parseFloat(
      (document.getElementById("llm-temperature") || {}).value
    ),
    max_tokens: parseInt(
      (document.getElementById("llm-max-tokens") || {}).value,
      10
    ),
    api_mode: (document.getElementById("llm-api-mode") || {}).value,
  };
  if (Number.isNaN(payload.temperature)) payload.temperature = 0.6;
  if (Number.isNaN(payload.max_tokens)) payload.max_tokens = 2048;
  const trustSel = document.getElementById("llm-trust-env");
  if (trustSel) {
    const tv = trustSel.value;
    if (tv === "") payload.trust_env = null;
    else if (tv === "true") payload.trust_env = true;
    else payload.trust_env = false;
  }
  const keyInp = document.getElementById("llm-api-key");
  if (llmClearApiKeyNextSave) {
    payload.api_key = "";
    llmClearApiKeyNextSave = false;
  } else if (keyInp && keyInp.value.trim()) {
    payload.api_key = keyInp.value.trim();
  }
  if (st) st.textContent = "保存中…";
  try {
    const r = await api().save_llm_settings(payload);
    if (!r.ok) {
      if (st) st.textContent = "保存失败：" + (r.error || "");
      return;
    }
    if (st) st.textContent = "已保存并应用。";
    await loadSettings();
  } catch (e) {
    if (st) st.textContent = "保存异常：" + String(e);
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
  if (!meta) {
    lastSessionMeta = null;
    currentSessionId = null;
    applyAvatarToForm(null);
    void refreshSessionAvatar({ avatar_mode: "off", avatar_ref: "" });
    updateSessionSchedulerPanelVisibility();
    void refreshSessionSchedulerPanel();
    updateInterruptButtonUi(null);
    return;
  }
  const prevId = lastSessionMeta && lastSessionMeta.id;
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
  updatePromptTemplateBar();
  void updateContextRail();
  if (prevId !== meta.id) {
    workspacePreviewCurrentPath = "";
  }
  refreshWorkspacePreviewIfSplitActive();
  applyAvatarToForm(meta);
  void refreshSessionAvatar(meta);
  updateSessionSchedulerPanelVisibility();
  void refreshSessionSchedulerPanel();
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
  await refreshDialogueState();
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
  await refreshDialogueState();
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
  const av = avatarPayloadFromUi();
  await api().update_session({
    workspace: workspace || null,
    mode,
    react_max_steps,
    avatar_mode: av.avatar_mode,
    avatar_ref: av.avatar_ref,
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
      const res = await withLlmApiLog("persona_send", () =>
        api().persona_send(text)
      );
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
      refreshDialogueState().catch(() => {});
    }
    return;
  }

  if ((mode === "chat" || mode === "react") && !isTeam) {
    let reactWaitTimer = null;
    if (mode === "react") {
      const box = document.getElementById("messages");
      removeEmptyPlaceholderIfAny(box);
      const { wrap: rw, body: rb } = createMessageBubble("pending", false, {
        initialText: "智能体运行中…（0s）",
        withCopy: false,
      });
      const pr = document.createElement("div");
      pr.className = "msg-react-progress";
      pr.setAttribute("role", "log");
      pr.setAttribute("aria-live", "polite");
      const cr = rw.querySelector(".msg-copy-row");
      if (cr) rw.insertBefore(pr, cr);
      else rw.appendChild(pr);
      box.appendChild(rw);
      reactStreamProgressEl = pr;
      reactStreamLines = [];
      let sec = 0;
      reactWaitTimer = setInterval(() => {
        sec += 1;
        if (rb) rb.textContent = `智能体运行中…（${sec}s）`;
      }, 1000);
      box.scrollTop = box.scrollHeight;
    }
    setBusy(true);
    try {
      await pushWorkspaceAndMode();
      const res = await withLlmApiLog("send_message", () =>
        api().send_message(text)
      );
      if (reactWaitTimer) clearInterval(reactWaitTimer);
      if (res.sync) {
        if (!res.ok && res.append_error) {
          appendMessage("assistant", res.message || "失败", true);
        } else if (res.ok && res.message) {
          appendMessage("assistant", res.message, false);
        }
      }
    } catch (err) {
      if (reactWaitTimer) clearInterval(reactWaitTimer);
      appendMessage("assistant", "调用失败：" + String(err), true);
    } finally {
      setBusy(false);
      refreshDialogueState().catch(() => {});
    }
    return;
  }

  const pendingBase = "正在思考…";

  appendMessageInstant("user", text, false);
  const box = document.getElementById("messages");
  const { wrap: pendingWrap, body: pendingBody } = createMessageBubble(
    "pending",
    false,
    {
      initialText: `${pendingBase}（0s）`,
    }
  );
  box.appendChild(pendingWrap);
  const pendingEl = pendingWrap;
  let waitSec = 0;
  const pendingTimer = setInterval(() => {
    waitSec += 1;
    if (pendingBody) {
      pendingBody.textContent = `${pendingBase}（${waitSec}s）`;
    }
  }, 1000);

  box.scrollTop = box.scrollHeight;

  setBusy(true);
  try {
    await pushWorkspaceAndMode();
    const res = await withLlmApiLog("send_message", () =>
      api().send_message(text)
    );
    clearInterval(pendingTimer);
    pendingEl.remove();
    setMainWaiting(false);
    await refreshActive({ typewriterLastAssistant: true });
    if (!res.ok && res.append_error) {
      appendMessage("assistant", res.message, true);
    }
  } catch (err) {
    clearInterval(pendingTimer);
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

function setBuiltinSchedulerStatus(msg) {
  const st = document.getElementById("builtin-scheduler-status");
  if (st) st.textContent = msg || "";
}

async function refreshAllSchedulerUIs() {
  await refreshGlobalSchedulerList();
  await refreshSessionSchedulerPanel();
}

function renderBuiltinSchedulerRows(container, tasks, kind, sessionId, onAfterDelete) {
  container.innerHTML = "";
  if (!tasks || !tasks.length) {
    container.textContent = "（无）";
    return;
  }
  const afterDel = typeof onAfterDelete === "function" ? onAfterDelete : null;
  for (const t of tasks) {
    const row = el("div", "builtin-scheduler-row");
    const tr = t.trigger || {};
    const ac = t.action || {};
    const summary = `${t.enabled === false ? "[停] " : ""}${tr.type || "?"} ${
      tr.value != null && tr.value !== "" ? String(tr.value) : ""
    } → ${ac.type || "?"}`;
    const lab = (t.label && String(t.label).trim()) ? String(t.label).trim() : "";
    const textWrap = el("div", "builtin-scheduler-task-block");
    if (lab) {
      textWrap.appendChild(el("div", "scheduler-task-title", lab));
    }
    textWrap.appendChild(el("div", "scheduler-task-meta", summary));
    row.appendChild(textWrap);
    const idc = document.createElement("code");
    idc.textContent = t.id || "";
    row.appendChild(idc);
    const btn = el("button", "btn btn-small btn-ghost", "删除");
    btn.type = "button";
    btn.addEventListener("click", async () => {
      if (!window.confirm("删除此定时任务？")) return;
      const payload = { kind, task_id: t.id };
      if (kind === "session" && sessionId) payload.session_id = sessionId;
      try {
        const r = await api().delete_scheduled_task(payload);
        if (!r.ok) {
          window.alert(r.error || "删除失败");
          return;
        }
        if (afterDel) await afterDel();
      } catch (e) {
        window.alert(String(e));
      }
    });
    row.appendChild(btn);
    container.appendChild(row);
  }
}

async function refreshGlobalSchedulerList() {
  const gEl = document.getElementById("builtin-scheduler-global");
  if (!gEl) return;
  setBuiltinSchedulerStatus("");
  try {
    const gr = await api().list_scheduled_tasks({ kind: "global" });
    gEl.innerHTML = "";
    if (!gr.ok) {
      gEl.textContent = gr.error || "加载失败";
    } else {
      renderBuiltinSchedulerRows(gEl, gr.tasks, "global", null, refreshAllSchedulerUIs);
    }
  } catch (e) {
    setBuiltinSchedulerStatus(String(e));
  }
}

async function refreshSessionSchedulerPanel() {
  const sEl = document.getElementById("session-scheduler-list");
  const st = document.getElementById("session-scheduler-status");
  if (!sEl) return;
  if (st) st.textContent = "";
  if (!currentSessionId) {
    sEl.textContent = "暂无选中会话。";
    return;
  }
  try {
    const sr = await api().list_scheduled_tasks({
      kind: "session",
      session_id: currentSessionId,
    });
    sEl.innerHTML = "";
    if (!sr.ok) {
      sEl.textContent = sr.error || "加载失败";
    } else {
      renderBuiltinSchedulerRows(
        sEl,
        sr.tasks,
        "session",
        currentSessionId,
        refreshAllSchedulerUIs
      );
    }
  } catch (e) {
    if (st) st.textContent = String(e);
  }
}

function updateSessionSchedulerPanelVisibility() {
  const noSess = document.getElementById("session-scheduler-no-session");
  const body = document.getElementById("session-scheduler-body");
  if (!noSess || !body) return;
  if (!currentSessionId) {
    noSess.classList.remove("hidden");
    body.classList.add("hidden");
  } else {
    noSess.classList.add("hidden");
    body.classList.remove("hidden");
  }
}

function toggleGlobalSchedTriggerFields() {
  const sel = document.getElementById("global-sched-trigger");
  const iw = document.getElementById("global-sched-interval-wrap");
  const dw = document.getElementById("global-sched-daily-wrap");
  if (!sel || !iw || !dw) return;
  const v = sel.value;
  iw.classList.toggle("hidden", v !== "interval_sec");
  dw.classList.toggle("hidden", v !== "daily_at");
}

function toggleSessionSchedTriggerFields() {
  const sel = document.getElementById("session-sched-trigger");
  const iw = document.getElementById("session-sched-interval-wrap");
  const dw = document.getElementById("session-sched-daily-wrap");
  if (!sel || !iw || !dw) return;
  const v = sel.value;
  iw.classList.toggle("hidden", v !== "interval_sec");
  dw.classList.toggle("hidden", v !== "daily_at");
}

function toggleSessionSchedActionFields() {
  const sel = document.getElementById("session-sched-action");
  const wrap = document.getElementById("session-sched-msg-wrap");
  const llm = document.getElementById("session-sched-llm-wrap");
  if (!sel) return;
  if (wrap) wrap.classList.toggle("hidden", sel.value !== "append_system_message");
  if (llm) llm.classList.toggle("hidden", sel.value !== "call_llm_once");
}

function openTaskRunsView() {
  const ov = document.getElementById("task-runs-overlay");
  if (!ov) return;
  ov.classList.remove("hidden");
  ov.setAttribute("aria-hidden", "false");
  void loadTaskRunsTable();
}

function closeTaskRunsView() {
  const ov = document.getElementById("task-runs-overlay");
  if (!ov) return;
  ov.classList.add("hidden");
  ov.setAttribute("aria-hidden", "true");
}

async function loadTaskRunsTable() {
  const wrap = document.getElementById("task-runs-table-wrap");
  const st = document.getElementById("task-runs-status");
  if (!wrap) return;
  if (st) st.textContent = "加载中…";
  wrap.innerHTML = "";
  try {
    const res = await api().list_scheduled_task_runs();
    if (!res.ok) {
      if (st) st.textContent = res.error || "加载失败";
      return;
    }
    const entries = res.entries || [];
    if (!entries.length) {
      wrap.textContent = "暂无记录。";
      if (st) st.textContent = "";
      return;
    }
    const table = document.createElement("table");
    table.className = "task-runs-table";
    table.innerHTML =
      "<thead><tr>" +
      "<th scope=\"col\">时间</th>" +
      "<th scope=\"col\">任务名称</th>" +
      "<th scope=\"col\">范围</th>" +
      "<th scope=\"col\">会话</th>" +
      "<th scope=\"col\">task_id</th>" +
      "<th scope=\"col\">动作</th>" +
      "<th scope=\"col\">详情</th>" +
      "</tr></thead><tbody></tbody>";
    const tb = table.querySelector("tbody");
    for (const e of entries) {
      const tr = document.createElement("tr");
      const scope = e.scope === "global" ? "全局" : "会话";
      const sess =
        e.scope === "session"
          ? `${escapeHtml(e.session_title || "")} <code>${escapeHtml(
              e.session_id || ""
            )}</code>`
          : "—";
      let detailHtml = "";
      if (e.action === "call_llm_once") {
        const bits = [];
        if (e.ask_only === true) bits.push("安全模式（仅 SAFE 工具）");
        if (e.model) bits.push(`模型: ${escapeHtml(String(e.model))}`);
        if (e.provider) bits.push(`提供商: ${escapeHtml(String(e.provider))}`);
        if (e.latency_ms != null) bits.push(`耗时: ${e.latency_ms}ms`);
        if (e.system_prompt) bits.push(`系统提示:\n${escapeHtml(String(e.system_prompt))}`);
        if (e.user_prompt) bits.push(`用户:\n${escapeHtml(String(e.user_prompt))}`);
        if (e.ok !== false && e.assistant_text) {
          bits.push(`模型回复:\n${escapeHtml(String(e.assistant_text))}`);
        }
        if (e.ok === false && e.error) {
          bits.push(`错误:\n${escapeHtml(String(e.error))}`);
        }
        detailHtml =
          bits.length > 0
            ? `<pre class="task-runs-detail">${bits.join("\n\n")}</pre>`
            : "—";
      } else {
        const prev =
          e.preview != null && String(e.preview) !== ""
            ? escapeHtml(String(e.preview))
            : e.ok === false
              ? "失败"
              : "ok";
        detailHtml = prev;
      }
      const lab = (e.label && String(e.label).trim()) ? escapeHtml(String(e.label).trim()) : "—";
      tr.innerHTML =
        `<td>${escapeHtml(e.ts || "")}</td>` +
        `<td>${lab}</td>` +
        `<td>${escapeHtml(scope)}</td>` +
        `<td>${sess}</td>` +
        `<td><code>${escapeHtml(e.task_id || "")}</code></td>` +
        `<td>${escapeHtml(e.action || "")}</td>` +
        `<td>${detailHtml}</td>`;
      tb.appendChild(tr);
    }
    wrap.appendChild(table);
    if (st) {
      st.textContent = `共 ${entries.length} 条（展示最近最多 1000 条）`;
    }
  } catch (err) {
    if (st) st.textContent = String(err);
  }
}

function init() {
  window.__ruyiPersonaDispatch = dispatchPersonaEvent;
  window.__ruyiReactDispatch = dispatchReactEvent;

  applySavedSessionListPrefs();
  applyTheme(getSavedTheme());
  const themeSelect = document.getElementById("theme-select");
  if (themeSelect) {
    themeSelect.addEventListener("change", () => applyTheme(themeSelect.value));
  }

  const llmProv = document.getElementById("llm-provider");
  if (llmProv) {
    llmProv.addEventListener("change", () => {
      toggleLlmOllamaOnly(llmProv.value === "ollama");
      applyLlmPresetHint(llmProv.value);
    });
  }
  const llmKeyVis = document.getElementById("llm-api-key-visible");
  const llmKeyInp = document.getElementById("llm-api-key");
  if (llmKeyVis && llmKeyInp) {
    llmKeyVis.addEventListener("change", () => {
      llmKeyInp.type = llmKeyVis.checked ? "text" : "password";
    });
  }
  const llmClientLog = document.getElementById("llm-client-log-enabled");
  if (llmClientLog) {
    llmClientLog.addEventListener("change", () => {
      try {
        localStorage.setItem(
          LS_LLM_CLIENT_LOG,
          llmClientLog.checked ? "1" : "0"
        );
      } catch (_) {
        /* ignore */
      }
    });
    applyLlmClientLogCheckbox();
  }
  const btnIdentityReload = document.getElementById("btn-identity-reload");
  if (btnIdentityReload) {
    btnIdentityReload.addEventListener("click", () => loadIdentityPrompts());
  }
  const btnIdentitySave = document.getElementById("btn-identity-save");
  if (btnIdentitySave) {
    btnIdentitySave.addEventListener("click", () => saveIdentityPromptsFromForm());
  }

  const gTrig = document.getElementById("global-sched-trigger");
  if (gTrig) {
    gTrig.addEventListener("change", () => toggleGlobalSchedTriggerFields());
    toggleGlobalSchedTriggerFields();
  }
  const sTrig = document.getElementById("session-sched-trigger");
  if (sTrig) {
    sTrig.addEventListener("change", () => toggleSessionSchedTriggerFields());
    toggleSessionSchedTriggerFields();
  }
  const sAct = document.getElementById("session-sched-action");
  if (sAct) {
    sAct.addEventListener("change", () => toggleSessionSchedActionFields());
    toggleSessionSchedActionFields();
  }

  const btnGlobalSchedCreate = document.getElementById("btn-global-sched-create");
  if (btnGlobalSchedCreate) {
    btnGlobalSchedCreate.addEventListener("click", async () => {
      const missed = document.getElementById("global-sched-missed");
      const en = document.getElementById("global-sched-enabled");
      const trig = document.getElementById("global-sched-trigger");
      let trigger;
      if (trig && trig.value === "daily_at") {
        const hh = (document.getElementById("global-sched-daily") || {}).value || "09:00";
        trigger = { type: "daily_at", value: String(hh).trim() || "09:00" };
      } else {
        let sec = parseInt(
          (document.getElementById("global-sched-interval") || {}).value || "3600",
          10
        );
        if (Number.isNaN(sec)) sec = 3600;
        sec = Math.max(30, Math.min(sec, 604800));
        trigger = { type: "interval_sec", value: sec };
      }
      const labelInp = document.getElementById("global-sched-label");
      const labelRaw = labelInp ? String(labelInp.value || "").trim().slice(0, 200) : "";
      const usr = (document.getElementById("global-sched-user") || {}).value || "";
      const ut = String(usr).trim();
      if (!ut) {
        setBuiltinSchedulerStatus("请填写「任务」内容。");
        return;
      }
      const askOnly = !!(document.getElementById("global-sched-ask-only") || {}).checked;
      const action = {
        type: "call_llm_once",
        system_prompt: "",
        user_prompt: ut.slice(0, 12000),
        ask_only: askOnly,
      };
      const payload = {
        kind: "global",
        label: labelRaw,
        enabled: !!(en && en.checked),
        trigger,
        action,
        missed_run_after_wake: missed ? missed.value : "skip",
        run_when_session_inactive: true,
        persist_output_to: "messages",
      };
      setBuiltinSchedulerStatus("");
      try {
        const r = await api().save_scheduled_task(payload);
        if (!r.ok) {
          setBuiltinSchedulerStatus(r.error || "保存失败");
          return;
        }
        setBuiltinSchedulerStatus("已添加。");
        if (labelInp) labelInp.value = "";
        const uEl = document.getElementById("global-sched-user");
        const askEl = document.getElementById("global-sched-ask-only");
        if (uEl) uEl.value = "";
        if (askEl) askEl.checked = false;
        await refreshGlobalSchedulerList();
      } catch (e) {
        setBuiltinSchedulerStatus(String(e));
      }
    });
  }

  const btnSessionSchedCreate = document.getElementById("btn-session-sched-create");
  if (btnSessionSchedCreate) {
    btnSessionSchedCreate.addEventListener("click", async () => {
      const st = document.getElementById("session-scheduler-status");
      if (!currentSessionId) {
        if (st) st.textContent = "请先选择会话。";
        return;
      }
      const missed = document.getElementById("session-sched-missed");
      const en = document.getElementById("session-sched-enabled");
      const trig = document.getElementById("session-sched-trigger");
      const act = document.getElementById("session-sched-action");
      const persist = document.getElementById("session-sched-persist");
      let trigger;
      if (trig && trig.value === "daily_at") {
        const hh = (document.getElementById("session-sched-daily") || {}).value || "09:00";
        trigger = { type: "daily_at", value: String(hh).trim() || "09:00" };
      } else {
        let sec = parseInt(
          (document.getElementById("session-sched-interval") || {}).value || "3600",
          10
        );
        if (Number.isNaN(sec)) sec = 3600;
        sec = Math.max(30, Math.min(sec, 604800));
        trigger = { type: "interval_sec", value: sec };
      }
      let action;
      if (act && act.value === "append_system_message") {
        const msg = (document.getElementById("session-sched-msg") || {}).value || "";
        const t = String(msg).trim();
        if (!t) {
          if (st) st.textContent = "请填写消息正文。";
          return;
        }
        action = { type: "append_system_message", text: t };
      } else if (act && act.value === "call_llm_once") {
        const sys = (document.getElementById("session-sched-sys") || {}).value || "";
        const usr = (document.getElementById("session-sched-user") || {}).value || "";
        const ut = String(usr).trim();
        if (!ut) {
          if (st) st.textContent = "请填写用户提示。";
          return;
        }
        action = {
          type: "call_llm_once",
          system_prompt: String(sys).trim().slice(0, 4000),
          user_prompt: ut.slice(0, 12000),
        };
      } else {
        action = { type: "noop" };
      }
      const labelInp = document.getElementById("session-sched-label");
      const labelRaw = labelInp ? String(labelInp.value || "").trim().slice(0, 200) : "";
      const payload = {
        kind: "session",
        session_id: currentSessionId,
        label: labelRaw,
        enabled: !!(en && en.checked),
        trigger,
        action,
        missed_run_after_wake: missed ? missed.value : "skip",
        run_when_session_inactive: true,
        persist_output_to: persist ? persist.value : "messages",
      };
      if (st) st.textContent = "";
      try {
        const r = await api().save_scheduled_task(payload);
        if (!r.ok) {
          if (st) st.textContent = r.error || "保存失败";
          return;
        }
        if (st) st.textContent = "已添加。";
        if (labelInp) labelInp.value = "";
        const uEl = document.getElementById("session-sched-user");
        const sEl = document.getElementById("session-sched-sys");
        if (uEl) uEl.value = "";
        if (sEl) sEl.value = "";
        await refreshSessionSchedulerPanel();
      } catch (e) {
        if (st) st.textContent = String(e);
      }
    });
  }

  const btnSessionSchedRefresh = document.getElementById("btn-session-sched-refresh");
  if (btnSessionSchedRefresh) {
    btnSessionSchedRefresh.addEventListener("click", () => {
      void refreshSessionSchedulerPanel();
    });
  }

  const btnSchedulerRefresh = document.getElementById("btn-scheduler-refresh");
  const schDetails = document.getElementById("builtin-scheduler-details");
  if (btnSchedulerRefresh) {
    btnSchedulerRefresh.addEventListener("click", () => {
      void refreshGlobalSchedulerList();
    });
  }
  if (schDetails) {
    schDetails.addEventListener("toggle", () => {
      if (schDetails.open) void refreshGlobalSchedulerList();
    });
  }

  const sessSchDetails = document.getElementById("session-scheduler-details");
  if (sessSchDetails) {
    sessSchDetails.addEventListener("toggle", () => {
      if (sessSchDetails.open) void refreshSessionSchedulerPanel();
    });
  }

  const btnTaskRuns = document.getElementById("btn-task-runs-view");
  if (btnTaskRuns) {
    btnTaskRuns.addEventListener("click", () => openTaskRunsView());
  }
  const btnTaskRunsClose = document.getElementById("btn-task-runs-close");
  if (btnTaskRunsClose) {
    btnTaskRunsClose.addEventListener("click", () => closeTaskRunsView());
  }
  const btnTaskRunsRefresh = document.getElementById("btn-task-runs-refresh");
  if (btnTaskRunsRefresh) {
    btnTaskRunsRefresh.addEventListener("click", () => void loadTaskRunsTable());
  }

  const btnLlmSave = document.getElementById("btn-llm-save");
  if (btnLlmSave) {
    btnLlmSave.addEventListener("click", () => {
      void saveLlmSettingsFromForm();
    });
  }
  const btnLlmClear = document.getElementById("btn-llm-clear-key");
  if (btnLlmClear) {
    btnLlmClear.addEventListener("click", () => {
      llmClearApiKeyNextSave = true;
      const st = document.getElementById("llm-settings-status");
      if (st) {
        st.textContent = "下次点击「保存并应用」时将清除已写入的 API Key。";
      }
    });
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

  const sessionAvatarMode = document.getElementById("session-avatar-mode");
  const sessionAvatarPixelKind = document.getElementById(
    "session-avatar-pixel-kind"
  );
  if (sessionAvatarMode) {
    sessionAvatarMode.addEventListener("change", async () => {
      try {
        const v = avatarPayloadFromUi();
        const res = await api().update_session({
          avatar_mode: v.avatar_mode,
          avatar_ref: v.avatar_ref,
        });
        if (res && res.meta) {
          lastSessionMeta = res.meta;
          applyAvatarToForm(res.meta);
          await refreshSessionAvatar(res.meta);
        }
      } catch (e) {
        appendMessage("assistant", "形象设置失败：" + String(e), true);
      }
    });
  }
  if (sessionAvatarPixelKind) {
    sessionAvatarPixelKind.addEventListener("change", async () => {
      try {
        const v = avatarPayloadFromUi();
        const res = await api().update_session({
          avatar_mode: v.avatar_mode,
          avatar_ref: v.avatar_ref,
        });
        if (res && res.meta) {
          lastSessionMeta = res.meta;
          applyAvatarToForm(res.meta);
          await refreshSessionAvatar(res.meta);
        }
      } catch (e) {
        appendMessage("assistant", "形象设置失败：" + String(e), true);
      }
    });
  }

  document.getElementById("btn-toggle-split").addEventListener("click", () => {
    const on = !document.body.classList.contains("split-active");
    setSplitActive(on);
  });

  document.getElementById("btn-preview-refresh").addEventListener("click", () => {
    void refreshWorkspacePreview(workspacePreviewCurrentPath);
  });

  document.getElementById("btn-preview-up").addEventListener("click", () => {
    const p = workspacePreviewParentPath(workspacePreviewCurrentPath);
    if (p === null) return;
    void refreshWorkspacePreview(p);
  });

  const personaInterruptBtn = document.getElementById("btn-persona-interrupt");
  if (personaInterruptBtn) {
    personaInterruptBtn.addEventListener("click", async () => {
      try {
        await withLlmApiLog("interrupt_turn", () => api().interrupt_turn());
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
      updatePromptTemplateBar();
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
    const taskOv = document.getElementById("task-runs-overlay");
    if (taskOv && !taskOv.classList.contains("hidden")) {
      closeTaskRunsView();
      return;
    }
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
    const pendOv = document.getElementById("pending-identity-overlay");
    if (pendOv && !pendOv.classList.contains("hidden")) {
      closePendingIdentityModal();
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
    const memT0 = performance.now();
    const memIso = new Date().toISOString();
    console.info("[Ruyi memory extract] 请求开始", {
      at: memIso,
      charCount: text.length,
      sessionId: currentSessionId || "",
    });
    try {
      const res = await withLlmApiLog("extract_memory", () =>
        api().extract_memory(text, currentSessionId || "")
      );
      const memMs = Math.round(performance.now() - memT0);
      console.info("[Ruyi memory extract] 请求结束", {
        wallMs: memMs,
        ok: res.ok,
        error: res.error || null,
        stats: res.stats || null,
      });
      const st = res.stats || {};
      const pid = st.pending_identity || 0;
      let msg = "";
      if (!res.ok) {
        msg =
          "记忆提取失败：" + (res.error || "未知错误") + `（已写入：事实 ${
            st.facts || 0
          } 条，永驻待合并 ${pid} 条，事件 ${st.events || 0} 条，关系 ${st.relations || 0} 条）`;
        appendMessage("assistant", msg, true);
      } else {
        msg = `已提取记忆：事实 ${st.facts || 0} 条，永驻待合并 ${pid} 条，事件 ${
          st.events || 0
        } 条，关系 ${st.relations || 0} 条。`;
        appendMessage("assistant", msg, false);
      }
    } catch (e) {
      console.warn("[Ruyi memory extract] 请求异常", {
        wallMs: Math.round(performance.now() - memT0),
        err: String(e),
      });
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

  const btnPend = document.getElementById("btn-pending-identity");
  if (btnPend) btnPend.addEventListener("click", () => openPendingIdentityModal());
  const pendClose = document.getElementById("pending-identity-close");
  if (pendClose) pendClose.addEventListener("click", () => closePendingIdentityModal());
  const pendRefresh = document.getElementById("pending-identity-refresh");
  if (pendRefresh) pendRefresh.addEventListener("click", () => refreshPendingIdentityList());
  const pendOverlay = document.getElementById("pending-identity-overlay");
  if (pendOverlay) {
    pendOverlay.addEventListener("click", (ev) => {
      if (ev.target.id === "pending-identity-overlay") closePendingIdentityModal();
    });
  }
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
