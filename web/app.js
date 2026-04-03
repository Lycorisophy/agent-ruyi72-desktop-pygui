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

function el(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
}

let currentSessionId = null;

function renderMessages(messages) {
  const box = document.getElementById("messages");
  box.innerHTML = "";
  if (!messages || !messages.length) {
    box.appendChild(
      el("div", "msg msg-system", "暂无消息。设置工作区并选择模式后发送。")
    );
    return;
  }
  for (const m of messages) {
    const role = m.role;
    const text = m.content || "";
    if (role === "system") {
      const node = el("div", "msg msg-system", text);
      box.appendChild(node);
      continue;
    }
    const cls =
      role === "user"
        ? "msg msg-user"
        : role === "assistant"
          ? "msg msg-assistant"
          : "msg msg-assistant";
    box.appendChild(el("div", cls, text));
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
  } catch (e) {
    line.textContent = "无法读取配置：" + String(e);
  }
}

function applyMetaToForm(meta) {
  if (!meta) return;
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
    const sub = el(
      "div",
      "session-item-meta",
      `${s.mode || "chat"} · ${(s.updated_at || "").slice(0, 19)}`
    );
    li.appendChild(t);
    li.appendChild(sub);
    li.addEventListener("click", () => openSession(s.id));
    ul.appendChild(li);
  }
}

async function openSession(id) {
  const data = await api().open_session(id);
  applyMetaToForm(data.meta);
  renderMessages(data.messages);
  await renderSessionList();
}

async function refreshActive() {
  const data = await api().get_active_session();
  applyMetaToForm(data.meta);
  renderMessages(data.messages);
  await renderSessionList();
}

async function pushWorkspaceAndMode() {
  const workspace = document.getElementById("workspace").value.trim();
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

async function onSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  setBusy(true);
  try {
    await pushWorkspaceAndMode();
    const res = await api().send_message(text);
    await refreshActive();
    if (!res.ok && res.append_error) {
      appendMessage("assistant", res.message, true);
    }
  } catch (err) {
    appendMessage("assistant", "调用失败：" + String(err), true);
  } finally {
    setBusy(false);
  }
}

function appendMessage(role, text, isError) {
  const box = document.getElementById("messages");
  const empty = box.querySelector(".msg-system");
  if (empty && empty.textContent.includes("暂无消息")) empty.remove();
  const cls =
    role === "user"
      ? "msg msg-user"
      : isError
        ? "msg msg-error"
        : "msg msg-assistant";
  const node = el("div", cls, text);
  box.appendChild(node);
  box.scrollTop = box.scrollHeight;
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

  document.getElementById("btn-apply-ws").addEventListener("click", async () => {
    setBusy(true);
    try {
      await pushWorkspaceAndMode();
      await refreshActive();
    } catch (e) {
      appendMessage("assistant", "应用失败：" + String(e), true);
    } finally {
      setBusy(false);
    }
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
    const overlay = document.getElementById("memory-modal-overlay");
    if (!overlay || overlay.classList.contains("hidden")) return;
    const loading = document.getElementById("global-loading");
    if (loading && !loading.classList.contains("hidden")) return;
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
      setMemoryModalBusy(false);
      if (ta) ta.value = "";
      closeMemoryModal();
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
