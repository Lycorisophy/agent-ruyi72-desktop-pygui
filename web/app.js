function waitForPywebview() {
  return new Promise((resolve) => {
    if (window.pywebview) {
      resolve();
      return;
    }
    window.addEventListener("pywebviewready", () => resolve(), { once: true });
  });
}

function el(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
}

function appendMessage(role, text, isError) {
  const box = document.getElementById("messages");
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

function setBusy(busy) {
  const input = document.getElementById("input");
  const send = document.getElementById("send");
  input.disabled = busy;
  send.disabled = busy;
}

async function loadSettings() {
  const line = document.getElementById("settings-line");
  try {
    const s = await window.pywebview.api.get_settings_snapshot();
    const auth =
      s.api_key_configured === true
        ? " · 已配置 API Key"
        : " · 未配置 API Key（远程/云端通常需要）";
    const te =
      s.trust_env === false
        ? " · 直连(不走系统代理)"
        : " · 使用系统代理环境变量";
    line.textContent = `${s.provider} · ${s.api_mode} · ${s.model} · ${s.base_url}${auth}${te}`;
  } catch (e) {
    line.textContent = "无法读取配置：" + String(e);
  }
}

async function onSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("input");
  const text = input.value.trim();
  if (!text) return;

  appendMessage("user", text, false);
  input.value = "";
  setBusy(true);
  try {
    const res = await window.pywebview.api.send_message(text);
    if (res.ok) {
      appendMessage("assistant", res.message, false);
    } else {
      appendMessage("assistant", res.message, true);
    }
  } catch (err) {
    appendMessage("assistant", "调用失败：" + String(err), true);
  } finally {
    setBusy(false);
  }
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
}

waitForPywebview()
  .then(() => {
    init();
    return loadSettings();
  })
  .catch((e) => {
    document.getElementById("settings-line").textContent =
      "pywebview 未就绪：" + String(e);
  });
