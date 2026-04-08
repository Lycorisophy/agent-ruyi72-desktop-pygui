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
  document.querySelectorAll('input[name="mode"]').forEach((r) => {
    if (isTeam) {
      r.disabled = true;
      if (r.value === "react") r.checked = false;
      if (r.value === "chat") r.checked = true;
    } else {
      r.disabled = false;
    }
  });
  const steps = document.getElementById("react-steps");
  if (steps) steps.disabled = !!isTeam;
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

/**
 * @param {object} [options]
 * @param {boolean} [options.instant] 默认 true：服务端同步列表一次写入，避免长历史打字机拖慢
 */
function renderMessages(messages, options) {
  const opts = options || {};
  const instant = opts.instant !== false;
  const box = document.getElementById("messages");
  box.innerHTML = "";
  messageRenderGen += 1;
  const gen = messageRenderGen;
  const emptyHint = "暂无消息。设置工作区并选择模式后发送。";
  if (!messages || !messages.length) {
    const { wrap, body } = createMessageBubble("system", false, {
      initialText: instant ? emptyHint : undefined,
    });
    box.appendChild(wrap);
    if (!instant) startTypewriter(body, emptyHint, gen);
    box.scrollTop = box.scrollHeight;
    return;
  }
  for (const m of messages) {
    const role = m.role;
    const text = m.content || "";
    if (role === "system") {
      const { wrap, body } = createMessageBubble("system", false, {
        initialText: instant ? text : undefined,
      });
      box.appendChild(wrap);
      if (!instant) startTypewriter(body, text, gen);
      continue;
    }
    const r = role === "user" ? "user" : "assistant";
    const { wrap, body } = createMessageBubble(r, false, {
      initialText: instant ? text : undefined,
    });
    box.appendChild(wrap);
    if (!instant) startTypewriter(body, text, gen);
  }
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
  for (const s of list) {
    const li = el("li", "session-item");
    li.dataset.id = s.id;
    if (s.id === currentSessionId) li.classList.add("active");
    const t = el("div", "session-item-title", s.title || s.id);
    let subLine = `${s.mode || "chat"} · ${(s.updated_at || "").slice(0, 19)}`;
    if (s.session_variant === "team" && s.team_size != null) {
      subLine = `团队·${s.team_size} · ${subLine}`;
    }
    const sub = el("div", "session-item-meta", subLine);
    li.appendChild(t);
    li.appendChild(sub);
    li.addEventListener("click", () => openSession(s.id));
    ul.appendChild(li);
  }
}

async function openSession(id) {
  const data = await api().open_session(id);
  applyMetaToForm(data.meta);
  renderMessages(data.messages, { instant: true });
  await renderSessionList();
}

async function refreshActive() {
  const data = await api().get_active_session();
  applyMetaToForm(data.meta);
  renderMessages(data.messages, { instant: true });
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
  const mode = document.querySelector('input[name="mode"]:checked').value;
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
  setGlobalLoading(true);
  setGlobalLoadingText(
    isTeam ? "团队多模型处理中，请稍候…" : "正在生成回复…"
  );
  try {
    await pushWorkspaceAndMode();
    const res = await api().send_message(text);
    pendingEl.remove();
    await refreshActive();
    if (!res.ok && res.append_error) {
      appendMessage("assistant", res.message, true);
    }
  } catch (err) {
    pendingEl.remove();
    appendMessage("assistant", "调用失败：" + String(err), true);
  } finally {
    setBusy(false);
    setGlobalLoading(false);
    setGlobalLoadingText("请稍候…");
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
  document.getElementById("chat-form").addEventListener("submit", onSubmit);
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
