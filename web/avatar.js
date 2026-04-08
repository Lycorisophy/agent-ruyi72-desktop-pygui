/**
 * 会话级形象：像素内置（小猫/小狗/兔子/狐狸）、Live2D（需本地 Cubism Core）、失败回退像素。
 */
(function (global) {
  "use strict";

  var GRID = 16;
  var SCALE = 64 / GRID;

  /** @param {CanvasRenderingContext2D} ctx */
  function pxl(ctx, x, y, w, h, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x * SCALE, y * SCALE, w * SCALE, h * SCALE);
  }

  /**
   * @param {string} ref
   * @returns {"cat"|"dog"|"rabbit"|"fox"}
   */
  function resolvePixelKind(ref) {
    if (!ref || typeof ref !== "string") return "cat";
    var m = ref.match(/^bundled:pixel_(cat|dog|rabbit|fox)$/);
    if (m) return m[1];
    if (ref === "bundled:pixel_default") return "cat";
    return "cat";
  }

  /**
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} frame
   */
  function drawPixelCat(ctx, frame) {
    var ear = frame % 20 < 2 ? 1 : 0;
    pxl(ctx, 4, 1 + ear, 2, 2, "#d4a056");
    pxl(ctx, 10 - ear, 1, 2, 2, "#d4a056");
    pxl(ctx, 3, 3, 10, 8, "#f4a261");
    pxl(ctx, 4, 11, 8, 4, "#e76f51");
    var blink = frame % 16 < 2;
    pxl(ctx, 5, 6, 2, 2, blink ? "#f4a261" : "#2d3142");
    pxl(ctx, 9, 6, 2, 2, blink ? "#f4a261" : "#2d3142");
    if (!blink) {
      pxl(ctx, 6, 7, 1, 1, "#fff");
      pxl(ctx, 10, 7, 1, 1, "#fff");
    }
    pxl(ctx, 7, 9, 2, 1, "#e5989b");
    pxl(ctx, 6, 4, 1, 1, "#fff");
    pxl(ctx, 11, 4, 1, 1, "#fff");
  }

  function drawPixelDog(ctx, frame) {
    var wag = Math.sin(frame / 4) > 0 ? 1 : 0;
    pxl(ctx, 1, 5, 2, 3, "#8b6914");
    pxl(ctx, 13, 5, 2, 3, "#8b6914");
    pxl(ctx, 4, 2, 8, 8, "#c9a227");
    pxl(ctx, 5, 10, 6, 4, "#a67c52");
    pxl(ctx, 5, 3 + wag, 2, 2, "#2d3142");
    pxl(ctx, 9, 3 + wag, 2, 2, "#2d3142");
    pxl(ctx, 6, 5 + wag, 1, 1, "#fff");
    pxl(ctx, 10, 5 + wag, 1, 1, "#fff");
    pxl(ctx, 7, 8 + wag, 2, 1, "#333");
    pxl(ctx, 6, 9 + wag, 4, 1, "#e5989b");
    pxl(ctx, 12, 8 + wag, 2, 1 + wag, "#c9a227");
  }

  function drawPixelRabbit(ctx, frame) {
    var hop = Math.sin(frame / 5) * 0.5;
    var y0 = hop > 0 ? 0 : 1;
    pxl(ctx, 5, y0, 2, 5, "#f5f5f5");
    pxl(ctx, 9, y0, 2, 5, "#f5f5f5");
    pxl(ctx, 5, 4 + y0, 1, 3, "#ffb7c5");
    pxl(ctx, 10, 4 + y0, 1, 3, "#ffb7c5");
    pxl(ctx, 4, 5 + y0, 8, 7, "#ececec");
    pxl(ctx, 5, 11 + y0, 6, 3, "#ececec");
    pxl(ctx, 6, 7 + y0, 2, 2, "#2d3142");
    pxl(ctx, 10, 7 + y0, 2, 2, "#2d3142");
    pxl(ctx, 7, 10 + y0, 4, 2, "#ffb7c5");
    pxl(ctx, 8, 9 + y0, 2, 1, "#ff6b9d");
  }

  function drawPixelFox(ctx, frame) {
    var tip = frame % 18 < 3 ? 1 : 0;
    pxl(ctx, 3, 1 + tip, 2, 2, "#e07c3d");
    pxl(ctx, 11, 1 + tip, 2, 2, "#e07c3d");
    pxl(ctx, 4, 3, 8, 7, "#dd6f20");
    pxl(ctx, 5, 6, 3, 3, "#fff5e6");
    pxl(ctx, 10, 6, 3, 3, "#fff5e6");
    pxl(ctx, 5, 10, 6, 3, "#c45d1a");
    pxl(ctx, 6, 5, 2, 2, "#2d3142");
    pxl(ctx, 10, 5, 2, 2, "#2d3142");
    pxl(ctx, 7, 7, 1, 1, "#fff");
    pxl(ctx, 11, 7, 1, 1, "#fff");
    pxl(ctx, 7, 9, 2, 1, "#222");
    pxl(ctx, 5, 4, 2, 1, "#fff5e6");
    pxl(ctx, 11, 4, 2, 1, "#fff5e6");
  }

  var DRAWERS = {
    cat: drawPixelCat,
    dog: drawPixelDog,
    rabbit: drawPixelRabbit,
    fox: drawPixelFox,
  };

  var LABELS = {
    cat: "像素小猫",
    dog: "像素小狗",
    rabbit: "像素兔子",
    fox: "像素狐狸",
  };

  /** @param {string} src */
  function loadScriptOnce(src) {
    return new Promise(function (resolve, reject) {
      var abs;
      try {
        abs = new URL(src, document.baseURI).href;
      } catch (e) {
        reject(e);
        return;
      }
      var nodes = document.getElementsByTagName("script");
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        if (!n.src) continue;
        try {
          if (new URL(n.src).href === abs) {
            resolve();
            return;
          }
        } catch (_) {
          /* ignore */
        }
      }
      var s = document.createElement("script");
      s.async = true;
      s.src = src;
      s.onload = function () {
        resolve();
      };
      s.onerror = function () {
        reject(new Error("script " + src));
      };
      document.head.appendChild(s);
    });
  }

  function clearStage(stage) {
    if (!stage) return;
    if (typeof stage._ruyiLive2dTeardown === "function") {
      try {
        stage._ruyiLive2dTeardown();
      } catch (e) {
        /* ignore */
      }
      stage._ruyiLive2dTeardown = null;
    }
    var canvases = stage.querySelectorAll("canvas.pixel-avatar-canvas");
    for (var i = 0; i < canvases.length; i++) {
      var c = canvases[i];
      if (c._ruyiPixelTid) {
        clearInterval(c._ruyiPixelTid);
        c._ruyiPixelTid = null;
      }
    }
    while (stage.firstChild) stage.removeChild(stage.firstChild);
  }

  /**
   * @param {HTMLElement} stage
   * @param {string} [avatarRef]
   */
  function mountPixelAvatar(stage, avatarRef) {
    var kind = resolvePixelKind(avatarRef || "");
    var canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    canvas.className = "pixel-avatar-canvas";
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", LABELS[kind] || "内置像素形象");
    var ctx = canvas.getContext("2d");
    if (!ctx) {
      stage.appendChild(canvas);
      return;
    }
    var frame = 0;
    var drawer = DRAWERS[kind] || drawPixelCat;
    function draw() {
      frame += 1;
      ctx.clearRect(0, 0, 64, 64);
      ctx.save();
      var bob = Math.sin(frame / 5) * 1.2;
      ctx.translate(0, bob);
      drawer(ctx, frame);
      ctx.restore();
    }
    draw();
    canvas._ruyiPixelTid = setInterval(draw, 120);
    stage.appendChild(canvas);
  }

  /**
   * 先本地 web/live2d/vendor/，失败则 jsDelivr（需联网）。
   */
  async function loadPixiLive2dStack() {
    var pairs = [
      [
        "live2d/vendor/pixi.min.js",
        "https://cdn.jsdelivr.net/npm/pixi.js@7.3.2/dist/pixi.min.js",
      ],
      [
        "live2d/vendor/pixi-live2d-display.cubism4.min.js",
        "https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.5.0-beta/dist/cubism4.min.js",
      ],
    ];
    for (var i = 0; i < pairs.length; i++) {
      try {
        await loadScriptOnce(pairs[i][0]);
      } catch (e) {
        await loadScriptOnce(pairs[i][1]);
      }
    }
    if (typeof global.PIXI === "undefined") {
      throw new Error("PIXI 未定义");
    }
    if (!PIXI.live2d || !PIXI.live2d.Live2DModel) {
      throw new Error("PIXI.live2d 未就绪（请确认 cubism4 脚本在 Core 之后加载）");
    }
    global.PIXI = PIXI;
  }

  /**
   * Cubism Core + Pixi + pixi-live2d-display + 本地 Haru 模型目录。
   * @param {HTMLElement} stage
   * @param {HTMLElement | null} statusEl
   * @param {string} [avatarRef]
   * @returns {Promise<boolean>}
   */
  async function tryLoadLive2dWithModel(stage, statusEl, avatarRef) {
    var relCore = "live2d/Core/live2dcubismcore.min.js";
    try {
      await loadScriptOnce(relCore);
    } catch (e) {
      if (statusEl) {
        statusEl.textContent =
          "未检测到 web/live2d/Core/live2dcubismcore.min.js，已使用像素形象。详见 docs/session-avatar-design.md";
        statusEl.classList.remove("hidden");
      }
      return false;
    }
    if (typeof global.Live2DCubismCore === "undefined") {
      if (statusEl) {
        statusEl.textContent =
          "Cubism Core 已加载但未暴露 Live2DCubismCore，已回退像素形象。";
        statusEl.classList.remove("hidden");
      }
      return false;
    }
    var modelPath = "live2d/bundled/Haru/Haru.model3.json";
    var modelUrl = new URL(modelPath, document.baseURI).href;
    try {
      var fr = await fetch(modelUrl, { method: "GET", cache: "default" });
      if (!fr.ok) throw new Error("status " + fr.status);
    } catch (e) {
      if (statusEl) {
        statusEl.textContent =
          "未找到示例模型 Haru：请将官方 CubismWebSamples 中 Samples/Resources/Haru 整夹复制到 web/live2d/bundled/Haru（见 bundled/README.txt）。仅放 Core 的 .js 无法渲染完整模型。";
        statusEl.classList.remove("hidden");
      }
      return false;
    }
    try {
      await loadPixiLive2dStack();
    } catch (e) {
      if (statusEl) {
        statusEl.textContent =
          "加载 Pixi / pixi-live2d-display 失败（可联网重试，或将脚本保存为 web/live2d/vendor/pixi.min.js 与 pixi-live2d-display.cubism4.min.js）：" +
          String(e && e.message ? e.message : e);
        statusEl.classList.remove("hidden");
      }
      return false;
    }
    var canvas = document.createElement("canvas");
    canvas.className = "live2d-canvas";
    var W = 300;
    var H = 200;
    var dpr =
      typeof global.devicePixelRatio === "number"
        ? global.devicePixelRatio
        : 1;
    var app = new PIXI.Application({
      width: W,
      height: H,
      view: canvas,
      backgroundAlpha: 0,
      antialias: true,
      resolution: dpr,
      autoDensity: true,
    });
    if (typeof PIXI.live2d.Live2DModel.registerTicker === "function") {
      var tk = PIXI.Ticker.shared || app.ticker;
      PIXI.live2d.Live2DModel.registerTicker(tk);
    }
    stage.appendChild(canvas);
    var model;
    try {
      model = await PIXI.live2d.Live2DModel.from(modelUrl, {
        autoInteract: false,
      });
    } catch (err) {
      try {
        app.destroy(true);
      } catch (_) {
        /* ignore */
      }
      if (statusEl) {
        statusEl.textContent =
          "模型解析失败（路径/纹理是否齐全）：" +
          String(err && err.message ? err.message : err);
        statusEl.classList.remove("hidden");
      }
      return false;
    }
    var iw = model.width || 1;
    var ih = model.height || 1;
    var s = Math.min((W - 8) / iw, (H - 8) / ih) * 0.92;
    model.scale.set(s);
    model.anchor.set(0.5, 0.5);
    model.position.set(W / 2, H * 0.52);
    app.stage.addChild(model);
    try {
      model.motion("Idle", 0, 2);
    } catch (_) {
      /* 无 Idle 组时仍可静态展示 */
    }
    stage._ruyiLive2dTeardown = function () {
      try {
        if (model && typeof model.destroy === "function") model.destroy();
      } catch (_) {
        /* ignore */
      }
      try {
        app.destroy(true, { children: true, texture: true });
      } catch (_) {
        /* ignore */
      }
    };
    if (statusEl) {
      statusEl.textContent = "";
      statusEl.classList.add("hidden");
    }
    return true;
  }

  /**
   * @param {object | null} meta
   * @param {HTMLElement} stage
   * @param {HTMLElement | null} statusEl
   */
  async function mount(meta, stage, statusEl) {
    clearStage(stage);
    if (statusEl) {
      statusEl.textContent = "";
      statusEl.classList.add("hidden");
    }
    if (!stage) return;
    var mode = (meta && meta.avatar_mode) || "off";
    var ref = (meta && meta.avatar_ref) || "";
    if (mode === "off") {
      var off = document.createElement("p");
      off.className = "avatar-strip-placeholder";
      off.textContent = "形象已关闭";
      stage.appendChild(off);
      return;
    }
    if (mode === "pixel") {
      mountPixelAvatar(stage, ref);
      return;
    }
    if (mode === "live2d") {
      var ok = await tryLoadLive2dWithModel(stage, statusEl, ref);
      if (!ok) {
        clearStage(stage);
        if (statusEl && !statusEl.textContent) {
          statusEl.textContent = "Live2D 不可用，已使用像素形象。";
          statusEl.classList.remove("hidden");
        }
        mountPixelAvatar(stage, ref);
      }
    }
  }

  function unmount(stage) {
    clearStage(stage);
  }

  global.RuyiAvatar = {
    mount: mount,
    unmount: unmount,
  };
})(typeof window !== "undefined" ? window : this);
