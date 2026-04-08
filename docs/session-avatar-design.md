# 会话级动态形象（Live2D / 像素）

## 数据模型

会话元数据 `SessionMeta`（`sessions/<id>/meta.json`）中的可选字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `avatar_mode` | `"off"` \| `"live2d"` \| `"pixel"` | 默认 `off`，与旧版无该字段的会话兼容（读入时补默认）。 |
| `avatar_ref` | 字符串 | 资源引用；像素内置为 `bundled:pixel_cat` / `bundled:pixel_dog` / `bundled:pixel_rabbit` / `bundled:pixel_fox`（旧版 `bundled:pixel_default` 视为小猫）；Live2D 示例为 `bundled:live2d_default`。 |

`avatar_ref` 写入时校验：禁止 `..`、空字符 `\0`、以及以 `/`、`\` 或 Windows 盘符形式开头的绝对路径（仅允许相对会话目录的语义化引用，由前端与后续导入功能约定）。

## 前端

- 主栏 `avatar-strip` 在 `main-split` 上方；模式由下拉框 `session-avatar-mode` 选择，变更时调用 `Api.update_session` 写入上述字段并刷新舞台。
- `web/avatar.js`：`RuyiAvatar.mount(meta, stage, statusEl)` 按模式挂载；`live2d` 在依赖缺失时回退为内置像素动画并可在 `avatar-strip-status` 显示一句说明。

## Live2D（Cubism SDK for Web）

1. **许可**：使用 Live2D Cubism SDK for Web 前须阅读并遵守 [Live2D 官方软件许可协议](https://www.live2d.com/download/cubism-sdk/release-license/)。本仓库**不**默认附带 Cubism 运行时或示例模型；请勿在未确认授权的情况下再分发第三方模型。SDK 再分发相关说明见仓库根目录 **`NOTICE`**。
2. **完整渲染所需文件**（缺一不可）：
   - **`web/live2d/Core/live2dcubismcore.min.js`**：Cubism Core（`README.txt` 说明来源；`.gitignore` 忽略误提交）。
   - **示例模型 Haru 整夹**：复制到 **`web/live2d/bundled/Haru/`**，使存在 **`Haru.model3.json`** 及同目录 **moc3、纹理、motions** 等（见 **`web/live2d/bundled/README.txt`**）。来源：Cubism SDK 包内 `Samples/Resources/Haru`，或 [CubismWebSamples](https://github.com/Live2D/CubismWebSamples) 同路径。
   - **PixiJS + pixi-live2d-display（cubism4）**：默认从 **jsDelivr CDN** 加载（需联网）。**离线**时请将 `pixi.min.js`（建议 7.3.x）与 `pixi-live2d-display` 的 **`cubism4.min.js`**（0.5.0-beta 与 Core 配套）保存为 **`web/live2d/vendor/pixi.min.js`** 与 **`web/live2d/vendor/pixi-live2d-display.cubism4.min.js`**（本地优先于 CDN）。
3. **运行时顺序**：Core →（可选 vendor）Pixi → cubism4 插件 → `Live2DModel.from('live2d/bundled/Haru/Haru.model3.json')`，并尝试播放 **Idle** 动作组。
4. **失败降级**：缺少 Core、模型目录不完整、CDN/脚本失败或 WebGL 不可用时，自动使用内置像素形象。

## 会话目录资源（后续扩展）

可在会话目录中约定（与计划一致，供将来导入功能使用）：

- `avatar/live2d/`：Cubism 导出目录（含 `.model3.json`、纹理、`.moc3` 等）。
- `avatar/pixel/`：`sprite.json` + `sheet.png` 或逐帧图。

全局只读内置包可选路径：`~/.ruyi72/avatars/builtin/`。

## API

- `Api.get_session_avatar_meta()`：返回当前活动会话的 `session_id`、`avatar_mode`、`avatar_ref`。
- `Api.set_session_avatar({ avatar_mode, avatar_ref })`：仅更新形象字段（内部走 `update_session`）。
- `Api.update_session`：可同时提交工作区、模式、`avatar_mode`、`avatar_ref` 等。
