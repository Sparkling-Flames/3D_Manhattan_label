// ==UserScript==
// @name         HoHoNet Helper Official Annotator HTTPS EN
// @namespace    https://label.sparkle0825.top/
// @version      stage3_active_time_identity_20260725_v3
// @description  Self-contained HTTPS helper for foreign HoHoNet Stage 1 annotators. Based on the official annotator helper; adds same-origin HTTPS defaults and optional CloudResearch worker-id metadata.
// @author       HoHoNet
// @match        https://label.sparkle0825.top/*
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  // 防止在 iframe 中运行 (避免重复的调试面板)
  if (window.top !== window.self) return;

  // 防止同一页面同时运行多个 HoHoNet userscript（例如旧版+新版同时启用）
  // 这会导致重复热键注册、重复观察器与状态树报错。
  if (window.__HOHONET_HELPER_ACTIVE__) {
    console.warn("HoHoNet Helper: another instance is already active; skipping this script.");
    return;
  }
  window.__HOHONET_HELPER_ACTIVE__ = true;

  // 运行时再做一道闸门：不是 Label Studio 页面就立刻退出。
  // 这样即使 @match 写得太宽，也不会在非标注/非 LS 页面计时或发日志。
  function isLikelyLabelStudioPage() {
    try {
      // 常见的 Label Studio 根节点/结构
      if (
        document.querySelector("#label-studio") ||
        document.querySelector(".ls-room") ||
        document.querySelector(".lsf-main-view") ||
        document.querySelector(".ls-main-view")
      ) {
        return true;
      }
      // 兜底：存在 LabelStudio 全局实例
      if (window.LabelStudio && window.LabelStudio.instances) return true;
    } catch (e) {}
    return false;
  }

  function resolveAnnotationPageGate() {
    const gate = {
      routeTaskId: "",
      domTaskId: "",
      storeTaskId: "",
      storeTaskIds: [],
      storeTaskMatchStatus: "unavailable",
      storeMismatchPresent: false,
      locationPath: window.location.pathname || "",
      sanitizedLocationSearch: "",
      capturedAt: Date.now(),
      labelingRootPresent: false,
      editorDomPresent: false,
      mainViewDomPresent: false,
      taskIdentityMatched: false,
      eligible: false,
      reason: "no_task_route",
      sources: [],
    };
    try {
      const params = new URLSearchParams(window.location.search);
      const queryTaskId = String(params.get("task") || "").trim();
      const pathMatch = window.location.pathname.match(/\/tasks\/([^/?#]+)/);
      const pathTaskId = pathMatch ? String(pathMatch[1]).trim() : "";
      if (queryTaskId && pathTaskId && queryTaskId !== pathTaskId) {
        gate.reason = "task_route_conflict";
        return gate;
      }
      gate.routeTaskId = queryTaskId || pathTaskId;
      gate.sanitizedLocationSearch = gate.routeTaskId
        ? `?task=${encodeURIComponent(gate.routeTaskId)}`
        : "";
      if (!gate.routeTaskId) return gate;
      gate.sources.push(queryTaskId ? "url.query.task" : "url.path.tasks");

      const labelingRoot = document.querySelector(".lsf-root.lsf-root_mode_labeling");
      gate.labelingRootPresent = Boolean(labelingRoot);
      if (!labelingRoot) {
        gate.reason = "labeling_mode_not_ready";
        return gate;
      }
      gate.sources.push("dom.lsf-root_mode_labeling");
      const labelView = labelingRoot.querySelector(".lsf-label-view");
      const editor = labelView?.querySelector(
        "#label-studio-dm.lsf-label-view__lsf-container > .lsf-editor",
      );
      gate.editorDomPresent = Boolean(editor);
      if (!editor) {
        gate.reason = "annotation_editor_not_ready";
        return gate;
      }
      gate.sources.push("dom.lsf-editor");
      gate.mainViewDomPresent = Boolean(
        editor.querySelector(".lsf-main-content > .lsf-main-view"),
      );
      if (!gate.mainViewDomPresent) {
        gate.reason = "annotation_main_view_not_ready";
        return gate;
      }
      gate.sources.push("dom.lsf-main-view");
      gate.domTaskId = String(editor.querySelector(".lsf-current-task__task-id")?.textContent || "").trim();
      if (!gate.domTaskId) {
        gate.reason = "dom_task_identity_not_ready";
        return gate;
      }
      gate.sources.push("dom.lsf-current-task__task-id");
      if (gate.domTaskId !== gate.routeTaskId) {
        gate.reason = "route_dom_task_mismatch";
        return gate;
      }
      try {
        const store = getStore?.();
        gate.storeTaskIds = Array.from(new Set([
          store?.task?.id,
          store?.taskStore?.selected?.id,
          store?.annotationStore?.selected?.task?.id,
        ].filter((value) => value !== undefined && value !== null && String(value).trim())
          .map((value) => String(value).trim())));
      } catch (e) {}
      gate.storeTaskId = gate.storeTaskIds[0] || "";
      if (gate.storeTaskIds.length) {
        gate.sources.push("store.task.audit");
        const hasRouteMatch = gate.storeTaskIds.includes(gate.routeTaskId);
        gate.storeMismatchPresent = gate.storeTaskIds.some((id) => id !== gate.routeTaskId);
        gate.storeTaskMatchStatus = hasRouteMatch
          ? (gate.storeMismatchPresent ? "mixed_with_route_match" : "matches_route")
          : "mismatch_only";
        if (gate.storeTaskMatchStatus === "mismatch_only") {
          gate.reason = "route_store_task_mismatch";
          return gate;
        }
      }
      gate.taskIdentityMatched = true;
      gate.eligible = true;
      gate.reason = "eligible";
      return gate;
    } catch (e) {
      gate.reason = "annotation_editor_not_ready";
      return gate;
    }
  }

  function isLikelyAnnotationPage() {
    return resolveAnnotationPageGate().eligible;
  }

  // v0.20 修复: 不在此处做早期检查，让 tick 自己决定是否运行
  // 这样可以处理页面延迟加载和 SPA 切换的情况

  const IFRAME_ID = "hohonet-iframe";
  const BUTTON_ID = "hohonet-refresh-btn";
  const WRAPPER_ID = "hohonet-wrapper";
  const DEBUG_ID = "hohonet-debug-panel";
  const ACTIVE_TIME_TOKEN_PANEL_ID = "hohonet-active-time-token-panel";
  const ACTIVE_TIME_STATUS_PANEL_ID = "hohonet-active-time-status-panel";
  const ACTIVE_TIME_PANEL_MODE_KEY = "HOHONET_ACTIVE_TIME_PANEL_MODE";
  const ACTIVE_TIME_RETRY_QUEUE_KEY = "HOHONET_ACTIVE_TIME_RETRY_QUEUE_V1";
  const ACTIVE_TIME_RETRY_TTL_MS = 72 * 60 * 60 * 1000;
  const ACTIVE_TIME_RETRY_MAX_ITEMS = 200;
  const OVERLAY_ID = "hohonet-overlay";
  const TOGGLE_BTN_ID = "hohonet-toggle-labels-btn";
  const LABELS_VISIBLE_KEY = "hohonet_labels_visible"; // sessionStorage
  const CORNER_ORDER_CACHE_SCHEMA = "corner_order_cache_v1";
  const CORNER_ORDER_CACHE_HOTFIX_VERSION =
    "stage1_helper_ordercache_hotfix_20260617_v1";
  const PREVIEW_ORDER_OVERRIDES_KEY = CORNER_ORDER_CACHE_SCHEMA;
  const PREVIEW_ORDER_ROUND_DIGITS = 1;
  const PREVIEW_PANEL_ID = "hohonet-preview-order-panel";
  const PREVIEW_PANEL_STYLE_ID = "hohonet-preview-order-panel-style";
  const PREVIEW_PANEL_HEADER_ID = "hohonet-preview-order-header";
  const PREVIEW_PANEL_BODY_ID = "hohonet-preview-order-body";
  const PREVIEW_PANEL_TOGGLE_ID = "hohonet-preview-order-toggle";
  const PREVIEW_PANEL_STATUS_ID = "hohonet-preview-order-status";
  const PREVIEW_PANEL_SLOT_ID = "hohonet-preview-order-slot";
  const PREVIEW_PANEL_PAIR_INPUT_ID = "hohonet-preview-pair-input";
  const PREVIEW_PANEL_PAIR_PREV_ID = "hohonet-preview-pair-prev";
  const PREVIEW_PANEL_PAIR_NEXT_ID = "hohonet-preview-pair-next";
  const PREVIEW_PANEL_SWAP_INPUT_ID = "hohonet-preview-swap-input";
  const PREVIEW_PANEL_SWAP_RUN_ID = "hohonet-preview-swap-run";
  const PREVIEW_PANEL_SWAP_PREV_ID = "hohonet-preview-swap-prev";
  const PREVIEW_PANEL_SWAP_NEXT_ID = "hohonet-preview-swap-next";
  const PREVIEW_PANEL_SAVE_ID = "hohonet-preview-save";
  const PREVIEW_PANEL_RESET_ID = "hohonet-preview-reset";
  const PREVIEW_PANEL_DELETE_ID = "hohonet-preview-delete";
  const PREVIEW_PANEL_POSITION_KEY = "hohonet_preview_panel_parent_position_v4";
  const PREVIEW_PANEL_COLLAPSED_KEY = "hohonet_preview_panel_parent_collapsed_v4";

  // ---- 部署配置（中文）----
  // 推荐在浏览器控制台设置（一次即可）：
  //   localStorage.setItem('HOHONET_HELPER_BASE_URL', location.origin);
  // 如果你把 /tools 和 /log_time 反代到 LS 同源，也可设置为：
  //   localStorage.setItem('HOHONET_HELPER_BASE_URL', location.origin);
  function getHelperBaseUrl() {
    try {
      return (
        window.localStorage.getItem("HOHONET_HELPER_BASE_URL") || window.location.origin
      );
    } catch (e) {
      return window.location.origin;
    }
  }

  // Optional: protect /log_time from public abuse.
  // Set once in browser console:
  //   localStorage.setItem('HOHONET_LOG_TOKEN', '<your-secret>')
  function getLogToken() {
    try {
      return window.localStorage.getItem("HOHONET_LOG_TOKEN") || "";
    } catch (e) {
      return "";
    }
  }

  // 3D viewer 可单独指定基址；若已把 /tools 反代到 LS 同源，建议设为 location.origin。
  function getViewerBaseUrl() {
    try {
      return (
        window.localStorage.getItem("HOHONET_VIEWER_BASE_URL") ||
        getHelperBaseUrl()
      );
    } catch (e) {
      return getHelperBaseUrl();
    }
  }


  // Foreign HTTPS / CloudResearch metadata. These fields are optional audit aids;
  // they do not replace Label Studio user_id/task_id/session_id.
  const FOREIGN_WORKER_ID_KEYS = [
    "participantId",
    "workerId",
    "worker_id",
    "hohonet_worker_id",
    "wid",
  ];

  function getQueryValueByKeys(keys) {
    try {
      const params = new URLSearchParams(window.location.search);
      for (const key of keys) {
        const value = params.get(key);
        if (value && String(value).trim()) return String(value).trim();
      }
    } catch (e) {}
    return "";
  }

  function rememberForeignRecruitmentMetadata() {
    try {
      const participantId = getQueryValueByKeys(["participantId"]);
      const externalWorkerId =
        getQueryValueByKeys(FOREIGN_WORKER_ID_KEYS) ||
        window.localStorage.getItem("HOHONET_RECRUIT_WORKER_ID") ||
        "";
      const assignmentId = getQueryValueByKeys(["assignmentId"]);
      const connectProjectId = getQueryValueByKeys(["projectId"]);
      if (externalWorkerId) {
        window.localStorage.setItem("HOHONET_RECRUIT_WORKER_ID", externalWorkerId);
      }
      if (participantId) {
        window.localStorage.setItem("HOHONET_CONNECT_PARTICIPANT_ID", participantId);
      }
      if (assignmentId) {
        window.localStorage.setItem("HOHONET_CONNECT_ASSIGNMENT_ID", assignmentId);
      }
      if (connectProjectId) {
        window.localStorage.setItem("HOHONET_CONNECT_PROJECT_ID", connectProjectId);
      }
    } catch (e) {}
  }

  function getForeignRecruitmentMetadataForPayload() {
    try {
      const participantId =
        getQueryValueByKeys(["participantId"]) ||
        window.localStorage.getItem("HOHONET_CONNECT_PARTICIPANT_ID") ||
        "";
      const externalWorkerId =
        getQueryValueByKeys(FOREIGN_WORKER_ID_KEYS) ||
        window.localStorage.getItem("HOHONET_RECRUIT_WORKER_ID") ||
        participantId ||
        "";
      const assignmentId =
        getQueryValueByKeys(["assignmentId"]) ||
        window.localStorage.getItem("HOHONET_CONNECT_ASSIGNMENT_ID") ||
        "";
      const connectProjectId =
        getQueryValueByKeys(["projectId"]) ||
        window.localStorage.getItem("HOHONET_CONNECT_PROJECT_ID") ||
        "";
      const entries = {
        external_worker_id: externalWorkerId,
        connect_participant_id: participantId,
        connect_assignment_id: assignmentId,
        connect_project_id: connectProjectId,
        foreign_https_script_version: SCRIPT_VERSION,
      };
      return Object.fromEntries(
        Object.entries(entries).filter(([, value]) => value !== ""),
      );
    } catch (e) {
      return { foreign_https_script_version: SCRIPT_VERSION };
    }
  }

  rememberForeignRecruitmentMetadata();
  function maskToken(t) {
    if (!t) return "";
    const s = String(t);
    if (s.length <= 6) return "***";
    return `${s.slice(0, 3)}***${s.slice(-3)}`;
  }

  const HOHONET_VIS_3D_URL = (sessionId) =>
    `${getViewerBaseUrl()}/tools/vis_3d.html?v=${sessionId}`;
  const HOHONET_LOG_TIME_URL = () => `${getHelperBaseUrl()}/log_time`;
  const HOHONET_ASSET_URL = (filename) =>
    `${getHelperBaseUrl()}/assets/${filename}`;

  // 右下角调试面板默认关闭（避免每秒更新造成“闪”）。
  // 需要时手动开启：
  //   localStorage.setItem('HOHONET_DEBUG_PANEL', '1')
  // 关闭：
  //   localStorage.removeItem('HOHONET_DEBUG_PANEL')
  function isDebugPanelEnabled() {
    try {
      return window.localStorage.getItem("HOHONET_DEBUG_PANEL") === "1";
    } catch (e) {
      return false;
    }
  }

  // 清理现有的 UI 以防止重新加载时重复
  const existingWrapper = document.getElementById(WRAPPER_ID);
  if (existingWrapper) existingWrapper.remove();
  const existingDebug = document.getElementById(DEBUG_ID);
  if (existingDebug) existingDebug.remove();
  const existingTokenPanel = document.getElementById(ACTIVE_TIME_TOKEN_PANEL_ID);
  if (existingTokenPanel) existingTokenPanel.remove();
  const existingStatusPanel = document.getElementById(ACTIVE_TIME_STATUS_PANEL_ID);
  if (existingStatusPanel) existingStatusPanel.remove();
  const existingOverlay = document.getElementById(OVERLAY_ID);
  if (existingOverlay) existingOverlay.remove();
  const existingPreviewPanel = document.getElementById(PREVIEW_PANEL_ID);
  if (existingPreviewPanel) existingPreviewPanel.remove();
  const existingPreviewPanelStyle = document.getElementById(PREVIEW_PANEL_STYLE_ID);
  if (existingPreviewPanelStyle) existingPreviewPanelStyle.remove();

  const SCRIPT_VERSION = "stage3_active_time_identity_20260725_v3";
  window.__HOHONET_HELPER_SCRIPT_VERSION__ = SCRIPT_VERSION;
  window.__HOHONET_HELPER_SCRIPT_FLAVOR__ = "foreign_https_en";
  console.log(`HoHoNet Helper: loaded (v${SCRIPT_VERSION})`);
  console.log(
    "HoHoNet viewer base: set localStorage.HOHONET_VIEWER_BASE_URL = location.origin when /tools is reverse-proxied on LS origin",
  );
  const DEFAULT_PREVIEW_STATUS_TEXT = "Click Refresh 3D View first";

  function translatePreviewStatusText(statusText) {
    let text = String(statusText || DEFAULT_PREVIEW_STATUS_TEXT);
    const replacements = [
      ["本地缓存：有", "Local saved order: yes"],
      ["本地缓存：无", "Local saved order: no"],
      ["当前预览：已保存顺序", "Current preview: saved order"],
      ["当前预览：默认顺序", "Current preview: default order"],
      ["当前预览：临时调整", "Current preview: temporary order"],
      ["已保存到本地缓存", "Saved to local cache"],
      ["保存成功：本地缓存已更新", "Save successful: local cache updated"],
      ["已恢复当前预览到默认顺序", "Restored current preview to default order"],
      ["已删除当前缓存并恢复默认顺序", "Deleted saved order and restored default order"],
      ["删除成功：已恢复默认顺序", "Delete successful: default order restored"],
      ["本地缓存操作失败", "Local cache operation failed"],
      ["已载入已保存顺序", "Loaded saved order"],
      ["已载入默认顺序", "Loaded default order"],
    ];
    for (const [zh, en] of replacements) {
      text = text.split(zh).join(en);
    }
    text = text.replace(/已将第\s*(\d+)\s*对与第\s*(\d+)\s*对交换/g, "Swapped pair $1 with pair $2");
    return text;
  }

  function createPreviewInputDraft() {
    return {
      pairDirty: false,
      swapDirty: false,
      swapInitialized: false,
    };
  }

  function createPreviewUiState(statusText = DEFAULT_PREVIEW_STATUS_TEXT) {
    return {
      hasData: false,
      pairCount: 0,
      selectedPairIndex: 0,
      savedOverrideActive: false,
      statusText,
    };
  }

  function createPreviewUiStateFromMessage(data) {
    return {
      hasData: !!data?.hasData,
      pairCount: Number(data?.pairCount) || 0,
      selectedPairIndex: Number(data?.selectedPairIndex) || 0,
      savedOverrideActive: !!data?.savedOverrideActive,
      statusText: translatePreviewStatusText(data?.statusText),
    };
  }

  function getPreviewControlPanelElements() {
    return {
      panel: document.getElementById(PREVIEW_PANEL_ID),
      slotNode: document.getElementById(PREVIEW_PANEL_SLOT_ID),
      statusNode: document.getElementById(PREVIEW_PANEL_STATUS_ID),
      pairInput: document.getElementById(PREVIEW_PANEL_PAIR_INPUT_ID),
      swapInput: document.getElementById(PREVIEW_PANEL_SWAP_INPUT_ID),
      prevBtn: document.getElementById(PREVIEW_PANEL_PAIR_PREV_ID),
      nextBtn: document.getElementById(PREVIEW_PANEL_PAIR_NEXT_ID),
      swapRunBtn: document.getElementById(PREVIEW_PANEL_SWAP_RUN_ID),
      swapPrevBtn: document.getElementById(PREVIEW_PANEL_SWAP_PREV_ID),
      swapNextBtn: document.getElementById(PREVIEW_PANEL_SWAP_NEXT_ID),
      saveBtn: document.getElementById(PREVIEW_PANEL_SAVE_ID),
      resetBtn: document.getElementById(PREVIEW_PANEL_RESET_ID),
      deleteBtn: document.getElementById(PREVIEW_PANEL_DELETE_ID),
    };
  }

  function getPreviewSelectionSnapshot(uiState = currentPreviewUiState) {
    const hasData = !!uiState?.hasData;
    const pairCount = Number(uiState?.pairCount) || 0;
    const safeCount = Number.isInteger(pairCount) && pairCount > 0 ? pairCount : 0;
    const safeIndex =
      safeCount > 0
        ? Math.max(
            0,
            Math.min(Number(uiState?.selectedPairIndex) || 0, safeCount - 1),
          )
        : 0;
    return {
      hasData,
      savedOverrideActive: !!uiState?.savedOverrideActive,
      statusText: translatePreviewStatusText(uiState?.statusText),
      safeCount,
      safeIndex,
      currentPairNumber: safeCount > 0 ? safeIndex + 1 : 1,
    };
  }

  function getCurrentPreviewStorageTaskKey() {
    return currentPreviewTaskKey || getPreviewOverrideTaskKey();
  }

  function postPreviewOrderAck(iframe, action, ok = true, reason = "") {
    if (!iframe?.contentWindow) return;
    iframe.contentWindow.postMessage(
      {
        type: "hohonet_preview_order_ack",
        ok,
        action,
        ...(reason ? { reason } : {}),
      },
      "*",
    );
  }

  function resetPreviewRuntimeState(statusText = DEFAULT_PREVIEW_STATUS_TEXT) {
    currentPreviewTaskKey = null;
    currentPreviewSignature = null;
    currentPreviewDefaultCount = 0;
    currentPreviewBaseCorners = [];
    currentPreviewInputDraft = createPreviewInputDraft();
    currentPreviewUiState = createPreviewUiState(statusText);
  }

  function applyPreviewRuntimeFromLayout(taskKey, signature, pairedDefault) {
    currentPreviewTaskKey = taskKey || null;
    currentPreviewSignature = signature || "";
    currentPreviewDefaultCount = Array.isArray(pairedDefault) ? pairedDefault.length : 0;
    currentPreviewBaseCorners = clonePreviewCornerPairs(pairedDefault);
    currentPreviewInputDraft = createPreviewInputDraft();
  }

  let currentPreviewTaskKey = null;
  let currentPreviewSignature = null;
  let currentPreviewDefaultCount = 0;
  let currentPreviewBaseCorners = [];
  let currentPreviewInputDraft = createPreviewInputDraft();
  let currentPreviewUiState = createPreviewUiState();

  // --- 调试面板 ---
  function updateDebug(msg) {
    if (!isDebugPanelEnabled()) {
      const existing = document.getElementById(DEBUG_ID);
      if (existing) existing.remove();
      return;
    }
    let panel = document.getElementById(DEBUG_ID);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = DEBUG_ID;
      panel.style.cssText =
        "position: fixed; bottom: 10px; right: 10px; background: rgba(0,0,0,0.8); color: #0f0; padding: 10px; z-index: 9999; font-family: monospace; font-size: 12px; pointer-events: none; white-space: pre-wrap;";
      document.body.appendChild(panel);
    }
    panel.innerText = `HoHoNet Debug (v${SCRIPT_VERSION}):\n` + msg;
  }

  let lastActiveTimeUploadStatus = "pending";

  function ensureActiveTimePanel(id, bottomPx) {
    let panel = document.getElementById(id);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = id;
      panel.style.cssText = `position: fixed; right: 12px; bottom: ${bottomPx}px; max-width: 360px; background: rgba(24,24,27,0.94); color: #f4f4f5; padding: 8px 10px; z-index: 10000; font-family: Arial, sans-serif; font-size: 12px; line-height: 1.35; border-radius: 6px; box-shadow: 0 2px 10px rgba(0,0,0,0.25);`;
      document.body.appendChild(panel);
    }
    return panel;
  }

  function getActiveTimePanelMode() {
    try {
      const mode = window.localStorage.getItem(ACTIVE_TIME_PANEL_MODE_KEY);
      return ["compact", "details", "hidden"].includes(mode) ? mode : "compact";
    } catch (e) {
      return "compact";
    }
  }

  function setActiveTimePanelMode(mode) {
    try {
      window.localStorage.setItem(ACTIVE_TIME_PANEL_MODE_KEY, mode);
    } catch (e) {}
  }

  function isActiveTimePanelForcedOpen(metadata, uploadStatus, tokenOk) {
    const status = String(uploadStatus || "");
    return (
      !tokenOk ||
      ["missing_token", "forbidden_403", "fetch_failed"].includes(status) ||
      status.startsWith("http_") ||
      (metadata && metadata.annotationMatchStatus === "unknown_annotation")
    );
  }

  function setStoredLogTokenFromPrompt() {
    const token = window.prompt("Set HOHONET_LOG_TOKEN");
    if (token && token.trim()) {
      window.localStorage.setItem("HOHONET_LOG_TOKEN", token.trim());
      updateActiveTimePanels(null, "token_set");
      void retryQueuedActiveTime("TOKEN_SET");
    }
  }

  function clearStoredLogToken() {
    try {
      window.localStorage.removeItem("HOHONET_LOG_TOKEN");
    } catch (e) {}
    updateActiveTimePanels(null, "missing_token");
  }

  function getActiveTimeTokenUiState(uploadStatus, token) {
    const status = String(uploadStatus || "");
    if (!token || status === "missing_token") {
      return {
        title: "Active-time token missing",
        body: "Set the token before annotation so time can be uploaded.",
        border: "#ef4444",
        action: "Set active-time token",
        primary: true,
      };
    }
    if (status === "forbidden_403") {
      return {
        title: "Invalid active-time token",
        body: "Server rejected the token. Re-enter it to resume uploads.",
        border: "#ef4444",
        action: "Re-enter token",
        primary: true,
      };
    }
    if (status === "ok") {
      return {
        title: "Active-time upload ready",
        body: `Token verified by server (${maskToken(token)}).`,
        border: "#22c55e",
        action: "Change token",
        primary: false,
      };
    }
    if (status === "fetch_failed" || status.startsWith("http_")) {
      return {
        title: "Active-time upload not confirmed",
        body: "Upload failed. The saved token has not been verified yet.",
        border: "#f59e0b",
        action: "Change token",
        primary: false,
      };
    }
    return {
      title: "Active-time token saved",
      body: "Waiting for the next upload to verify the token.",
      border: "#f59e0b",
      action: "Change token",
      primary: false,
    };
  }

  function getActiveTimeAnnotationNotice(metadata) {
    if (metadata?.annotationIdSource === "selected_annotation_not_owned_by_current_user") {
      return "Selected annotation belongs to another user. Time is held until your own annotation is active.";
    }
    if (metadata?.annotationMatchStatus === "unknown_annotation") {
      return "Annotation is not confirmed yet. Time will remain unassigned unless it can be safely matched.";
    }
    if (metadata?.annotationMatchStatus === "client_annotation_id_only") {
      return "Only a temporary browser annotation ID is available. It binds after save and stays out of formal active-time until then.";
    }
    return "";
  }

  function appendActiveTimePanelButton(container, label, onClick, { primary = false, danger = false } = {}) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.style.cssText = [
      "padding: 6px 10px",
      "border-radius: 4px",
      "font-size: 12px",
      "font-weight: 600",
      "cursor: pointer",
      danger ? "border: 1px solid #ef4444" : primary ? "border: 1px solid #2563eb" : "border: 1px solid #d1d5db",
      danger ? "background: #fff" : primary ? "background: #2563eb" : "background: #fff",
      danger ? "color: #b91c1c" : primary ? "color: #fff" : "color: #111827",
    ].join("; ");
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      onClick();
    });
    container.appendChild(button);
  }

  function appendActiveTimeDetailRow(container, label, value, { badge = false } = {}) {
    const row = document.createElement("div");
    row.style.cssText = "display: grid; grid-template-columns: 128px minmax(0, 1fr); gap: 12px; align-items: center; padding: 9px 0; border-top: 1px solid #e5e7eb;";
    const labelEl = document.createElement("div");
    labelEl.textContent = label;
    labelEl.style.cssText = "color: #6b7280; font-size: 12px;";
    const valueEl = document.createElement("div");
    valueEl.style.cssText = badge
      ? "justify-self: end; display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px; background: #dcfce7; color: #15803d; font-size: 12px; font-weight: 700;"
      : "color: #111827; font-size: 12px; font-weight: 600; text-align: right; overflow-wrap: anywhere;";
    if (badge) {
      const dot = document.createElement("span");
      dot.style.cssText = "width: 7px; height: 7px; border-radius: 999px; background: #22c55e; display: inline-block;";
      const text = document.createElement("span");
      text.textContent = String(value || "unknown");
      valueEl.appendChild(dot);
      valueEl.appendChild(text);
    } else {
      valueEl.textContent = String(value || "unknown");
    }
    row.appendChild(labelEl);
    row.appendChild(valueEl);
    container.appendChild(row);
  }

  function updateActiveTimePanels(report = null, uploadStatus = lastActiveTimeUploadStatus, explicitPageGate = null) {
    lastActiveTimeUploadStatus = uploadStatus || lastActiveTimeUploadStatus;
    const tokenPanel = ensureActiveTimePanel(ACTIVE_TIME_TOKEN_PANEL_ID, 12);
    const statusPanel = ensureActiveTimePanel(ACTIVE_TIME_STATUS_PANEL_ID, 92);
    const token = getLogToken();
    const tokenOk = Boolean(token);
    const pageGate = explicitPageGate || report?.pageGate || resolveAnnotationPageGate();
    const metadata = report || (pageGate.eligible ? resolveActiveTimeMetadata(pageGate.routeTaskId) : {});
    const mode = getActiveTimePanelMode();
    const forcedOpen = isActiveTimePanelForcedOpen(metadata, lastActiveTimeUploadStatus, tokenOk);
    const showDetails = mode === "details" || forcedOpen;
    const hidden = mode === "hidden" && !forcedOpen;
    const minimized = !showDetails;
    tokenPanel.style.display = hidden ? "none" : "block";
    statusPanel.style.display = showDetails && !hidden ? "block" : "none";
    tokenPanel.textContent = "";
    tokenPanel.onclick = null;
    tokenPanel.style.cursor = "default";
    tokenPanel.style.background = "#fff";
    tokenPanel.style.color = "#111827";
    tokenPanel.style.padding = "10px 12px";
    tokenPanel.style.borderRadius = "8px";
    tokenPanel.style.maxWidth = "420px";
    tokenPanel.style.width = "min(420px, calc(100vw - 24px))";
    tokenPanel.style.boxShadow = "0 6px 20px rgba(15,23,42,0.18)";
    let tokenState = getActiveTimeTokenUiState(lastActiveTimeUploadStatus, token);
    if (tokenOk && pageGate.reason !== "eligible" && !["forbidden_403", "fetch_failed"].includes(lastActiveTimeUploadStatus) && !String(lastActiveTimeUploadStatus).startsWith("http_")) {
      tokenState = {
        title: "Active-Time: Not counting",
        body: "This is not a task labeling page.",
        border: "#94a3b8",
        action: "Change token",
        primary: false,
      };
    }
    tokenPanel.style.border = `1px solid ${tokenState.border}`;
    if (minimized) {
      tokenPanel.style.padding = "6px";
      tokenPanel.style.width = "auto";
      tokenPanel.style.maxWidth = "none";
      tokenPanel.style.border = "1px solid #e5e7eb";
      tokenPanel.style.boxShadow = "0 4px 14px rgba(15,23,42,0.14)";
      if (!pageGate.eligible) {
        const compactStatus = document.createElement("span");
        compactStatus.textContent = "Active-Time: Not counting (not a task labeling page)";
        compactStatus.style.cssText = "font-size: 12px; color: #475569; margin: 0 8px;";
        tokenPanel.appendChild(compactStatus);
      }
      appendActiveTimePanelButton(tokenPanel, "Details", () => {
        setActiveTimePanelMode("details");
        updateActiveTimePanels(report, lastActiveTimeUploadStatus);
      });
      return;
    }
    const title = document.createElement("div");
    title.textContent = tokenState.title;
    title.style.cssText = "font-size: 13px; font-weight: 700; margin-bottom: 3px;";
    tokenPanel.appendChild(title);
    const body = document.createElement("div");
    body.textContent = tokenState.body;
    body.style.cssText = "font-size: 12px; color: #4b5563; margin-bottom: 8px;";
    tokenPanel.appendChild(body);
    const noticeText = getActiveTimeAnnotationNotice(metadata);
    if (noticeText) {
      const notice = document.createElement("div");
      notice.textContent = noticeText;
      notice.style.cssText = "font-size: 12px; color: #92400e; margin-bottom: 8px;";
      tokenPanel.appendChild(notice);
    }
    const actions = document.createElement("div");
    actions.style.cssText = "display: flex; gap: 8px; flex-wrap: wrap;";
    appendActiveTimePanelButton(actions, tokenState.action, setStoredLogTokenFromPrompt, { primary: tokenState.primary });
    if (tokenOk) {
      appendActiveTimePanelButton(actions, "Clear token", clearStoredLogToken, { danger: true });
    }
    if (!forcedOpen) {
      appendActiveTimePanelButton(actions, mode === "details" ? "Hide details" : "Details", () => {
        setActiveTimePanelMode(mode === "details" ? "compact" : "details");
        updateActiveTimePanels(report, lastActiveTimeUploadStatus);
      });
    }
    tokenPanel.appendChild(actions);
    const seconds = pageGate.eligible ? (report && report.reportSeconds !== undefined ? report.reportSeconds : activeSeconds) : 0;
    statusPanel.textContent = "";
    statusPanel.style.background = "#fff";
    statusPanel.style.color = "#111827";
    statusPanel.style.padding = "14px 18px";
    statusPanel.style.borderRadius = "12px";
    statusPanel.style.maxWidth = "420px";
    statusPanel.style.width = "min(420px, calc(100vw - 24px))";
    statusPanel.style.boxShadow = "0 10px 28px rgba(15,23,42,0.22)";
    statusPanel.style.bottom = `${24 + (tokenPanel.offsetHeight || 96)}px`;
    const detailTitle = document.createElement("div");
    detailTitle.textContent = "Technical Active-Time Details";
    detailTitle.style.cssText = "font-size: 15px; font-weight: 800; margin-bottom: 10px;";
    statusPanel.appendChild(detailTitle);
    appendActiveTimeDetailRow(statusPanel, "Status", lastActiveTimeUploadStatus, { badge: lastActiveTimeUploadStatus === "ok" });
    appendActiveTimeDetailRow(statusPanel, "Key", metadata.activeTimeKey || "unknown");
    appendActiveTimeDetailRow(statusPanel, "Annotation", `${metadata.annotationId || "unknown_annotation"} (${metadata.annotationMatchStatus || "unknown_annotation"})`);
    appendActiveTimeDetailRow(statusPanel, "Task Source", metadata.taskIdSource || "unknown");
    appendActiveTimeDetailRow(statusPanel, "Project Source", metadata.projectIdSource || "unknown");
    appendActiveTimeDetailRow(statusPanel, "Annotation Source", metadata.annotationIdSource || "unknown");
    appendActiveTimeDetailRow(statusPanel, "Page Gate", pageGate.reason || "unknown");
    appendActiveTimeDetailRow(statusPanel, "Late-binding", metadata.lateBindingStatus || "none");
    appendActiveTimeDetailRow(statusPanel, "Seconds", seconds);
    statusPanel.style.border = pageGate.eligible && metadata.annotationMatchStatus === "unknown_annotation" ? "1px solid #f59e0b" : "1px solid #e5e7eb";
  }

  function getLabelsVisible() {
    try {
      const v = window.sessionStorage.getItem(LABELS_VISIBLE_KEY);
      if (v === null) return true;
      return v === "1";
    } catch (e) {
      return true;
    }
  }

  function setLabelsVisible(visible) {
    try {
      window.sessionStorage.setItem(LABELS_VISIBLE_KEY, visible ? "1" : "0");
    } catch (e) {}
  }

  function applyToggleBtnState(toggleBtn, visible) {
    if (!toggleBtn) return;
    if (visible) {
      toggleBtn.innerText = "🏷️ Hide Labels";
      toggleBtn.style.background = "#6c757d";
    } else {
      toggleBtn.innerText = "🏷️ Show Labels";
      toggleBtn.style.background = "#28a745";
    }
  }

  function ensureOverlay(img) {
    let overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = OVERLAY_ID;
      overlay.style.cssText =
        "position: fixed; pointer-events: none; z-index: 999999; overflow: hidden;";
      document.body.appendChild(overlay);
    } else {
      // 保证老的 overlay 也按新规则裁剪
      overlay.style.overflow = "hidden";
    }

    // 由 tick/刷新统一控制显示状态
    positionOverlayToImage(img, overlay);
    return overlay;
  }

  function intersectRects(a, b) {
    if (!a || !b) return null;
    const left = Math.max(a.left, b.left);
    const top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right);
    const bottom = Math.min(a.bottom, b.bottom);
    if (right <= left || bottom <= top) return null;
    return {
      left,
      top,
      right,
      bottom,
      width: right - left,
      height: bottom - top,
    };
  }

  function computeVisibleRectForImage(img) {
    // imgRect: 图片渲染后的矩形（可能包含被父容器裁剪掉的部分）
    // visibleRect: imgRect 与所有“裁剪型祖先”(overflow!=visible) 的交集
    try {
      const imgRect = img.getBoundingClientRect();
      if (!imgRect || imgRect.width <= 1 || imgRect.height <= 1) {
        return { imgRect: null, visibleRect: null };
      }

      let visible = {
        left: imgRect.left,
        top: imgRect.top,
        right: imgRect.right,
        bottom: imgRect.bottom,
        width: imgRect.width,
        height: imgRect.height,
      };

      // 向上找可能裁剪图片的容器（zoom/pan 通常发生在这里）
      let el = img.parentElement;
      while (el && el !== document.body && el !== document.documentElement) {
        const style = getComputedStyle(el);
        const overflowX = style.overflowX;
        const overflowY = style.overflowY;
        const isClipping =
          overflowX !== "visible" ||
          overflowY !== "visible" ||
          style.overflow === "hidden";

        if (isClipping) {
          const r = el.getBoundingClientRect();
          // 过滤掉异常的 0 尺寸容器
          if (r && r.width > 0 && r.height > 0) {
            const next = intersectRects(visible, r);
            if (!next) break;
            visible = next;
          }
        }

        el = el.parentElement;
      }

      return { imgRect, visibleRect: visible };
    } catch (e) {
      return { imgRect: null, visibleRect: null };
    }
  }

  function positionOverlayToImage(img, overlay) {
    try {
      const { imgRect, visibleRect } = computeVisibleRectForImage(img);
      const rect = visibleRect;
      if (!imgRect || !rect || rect.width <= 1 || rect.height <= 1) {
        overlay.style.left = "0px";
        overlay.style.top = "0px";
        overlay.style.width = "0px";
        overlay.style.height = "0px";
        overlay.dataset.imgLeft = "";
        overlay.dataset.imgTop = "";
        overlay.dataset.imgWidth = "";
        overlay.dataset.imgHeight = "";
        return null;
      }

      overlay.style.left = `${rect.left}px`;
      overlay.style.top = `${rect.top}px`;
      overlay.style.width = `${rect.width}px`;
      overlay.style.height = `${rect.height}px`;
      // 存下来，用于 badge 从“图片坐标系”映射到“可视区域坐标系”
      overlay.dataset.imgLeft = String(imgRect.left);
      overlay.dataset.imgTop = String(imgRect.top);
      overlay.dataset.imgWidth = String(imgRect.width);
      overlay.dataset.imgHeight = String(imgRect.height);
      return rect;
    } catch (e) {
      return null;
    }
  }

  function positionOverlayBadges(overlay, rect) {
    if (!overlay || !rect) return;
    const imgLeft = parseFloat(overlay.dataset.imgLeft);
    const imgTop = parseFloat(overlay.dataset.imgTop);
    const imgWidth = parseFloat(overlay.dataset.imgWidth);
    const imgHeight = parseFloat(overlay.dataset.imgHeight);
    if (
      ![imgLeft, imgTop, imgWidth, imgHeight].every((v) => Number.isFinite(v))
    ) {
      return;
    }

    const children = Array.from(overlay.children);
    children.forEach((badge) => {
      const pctX = parseFloat(badge.dataset.pctx);
      const pctY = parseFloat(badge.dataset.pcty);
      if (Number.isFinite(pctX) && Number.isFinite(pctY)) {
        // 超出图片范围的点不显示（例如 1/5/6 这类跑到框外的）
        if (pctX < 0 || pctX > 100 || pctY < 0 || pctY > 100) {
          badge.style.display = "none";
          return;
        }

        // 先算点在 viewport 的绝对位置（基于完整图片矩形）
        const absX = imgLeft + (pctX * imgWidth) / 100;
        const absY = imgTop + (pctY * imgHeight) / 100;

        // 如果点不在“图片可视区域”内，隐藏
        if (
          absX < rect.left ||
          absX > rect.right ||
          absY < rect.top ||
          absY > rect.bottom
        ) {
          badge.style.display = "none";
          return;
        }

        // 映射到 overlay 内部坐标
        const x = absX - rect.left;
        const y = absY - rect.top;

        badge.style.display = "block";
        badge.style.left = `${x}px`;
        badge.style.top = `${y}px`;
      }
    });
  }

  // --- Store 发现 (查找 Label Studio 实例) ---
  function getStore() {
    // 1. 标准全局变量
    if (
      window.LabelStudio &&
      window.LabelStudio.instances &&
      window.LabelStudio.instances.length > 0
    ) {
      return window.LabelStudio.instances[0].store;
    }
    // 2. 旧版全局变量
    if (window.H) return window.H;

    // 3. React 内部属性 (终极手段)
    const root =
      document.querySelector(".ls-room") ||
      document.querySelector("#label-studio") ||
      document.querySelector(".lsf-main-view");
    if (root) {
      for (const key in root) {
        if (key.startsWith("__reactFiber")) {
          // 向上遍历以在 props 或 context 中找到 store
          let fiber = root[key];
          while (fiber) {
            if (
              fiber.stateNode &&
              fiber.stateNode.props &&
              fiber.stateNode.props.store
            ) {
              return fiber.stateNode.props.store;
            }
            if (fiber.memoizedProps && fiber.memoizedProps.store) {
              return fiber.memoizedProps.store;
            }
            fiber = fiber.return;
          }
        }
      }
    }

    return null;
  }

  function normalizeChoiceToken(raw) {
    const s = String(raw || "").trim();
    const l = s.toLowerCase();
    if (!s) return "";

    if (l === "trivial" || l.includes("(trivial)") || s.includes("非常简单"))
      return "trivial";
    if (
      l === "acceptable" ||
      l.includes("acceptable") ||
      s.includes("模型标注质量好")
    )
      return "acceptable";

    return l;
  }

  function matchesFieldName(actual, expected) {
    const a = String(actual || "")
      .trim()
      .toLowerCase();
    const e = String(expected || "")
      .trim()
      .toLowerCase();
    if (!a || !e) return false;
    if (a === e) return true;
    if (a.endsWith(`.${e}`) || a.endsWith(`:${e}`) || a.endsWith(`/${e}`))
      return true;
    if (a.includes(e)) return true;
    return false;
  }

  function isTrivialToken(token) {
    const t = String(token || "")
      .trim()
      .toLowerCase();
    return t === "trivial" || t.includes("trivial") || t.includes("非常简单");
  }

  function isAcceptableToken(token) {
    const t = String(token || "")
      .trim()
      .toLowerCase();
    return (
      t === "acceptable" ||
      t.includes("acceptable") ||
      t.includes("模型标注质量好")
    );
  }

  function isMetaGuardDebugEnabled() {
    try {
      return (
        window.localStorage.getItem("HOHONET_META_GUARD_DEBUG") === "1" ||
        window.localStorage.getItem("HOHONET_DEBUG_META_GUARD") === "1" ||
        window.localStorage.getItem("HOHONET_META_DEBUG") === "1"
      );
    } catch (e) {
      return false;
    }
  }

  function metaGuardDebug(...args) {
    if (!isMetaGuardDebugEnabled()) return;
    console.log("[HoHoNet MetaGuard]", ...args);
  }

  function toArrayFromMaybeObservable(value) {
    try {
      if (!value) return [];
      if (Array.isArray(value)) return value;
      if (typeof value.toJSON === "function") {
        const j = value.toJSON();
        if (Array.isArray(j)) return j;
      }
      if (typeof value[Symbol.iterator] === "function") {
        return Array.from(value);
      }
    } catch (e) {}
    return [];
  }

  function collectSelectedResults(store) {
    const out = [];
    try {
      const selected = store?.annotationStore?.selected;
      if (!selected) return out;

      if (typeof selected?.serializeCompletion === "function") {
        const ser = selected.serializeCompletion();
        const serRes = toArrayFromMaybeObservable(ser?.result);
        if (serRes.length) out.push(...serRes);
      }

      if (typeof selected?.toJSON === "function") {
        const j = selected.toJSON();
        const jRes = toArrayFromMaybeObservable(j?.result || j?.results);
        if (jRes.length) out.push(...jRes);
      }

      const direct = toArrayFromMaybeObservable(selected?.results);
      if (direct.length) out.push(...direct);
    } catch (e) {
      metaGuardDebug("collectSelectedResults error", e);
    }
    return out;
  }

  function extractChoicesFromResult(result) {
    try {
      if (!result || typeof result !== "object") return [];
      const candidates = [
        result?.value,
        result?.area?.value,
        result?.origin?.value,
        result,
        result?.area,
        result?.origin,
      ];

      const out = [];
      for (const source of candidates) {
        if (!source || typeof source !== "object") continue;
        const choices = Array.isArray(source.choices) ? source.choices : [];
        if (!choices.length) continue;
        const normalized = choices
          .map((x) => normalizeChoiceToken(x))
          .filter(Boolean);
        for (const v of normalized) {
          if (!out.includes(v)) out.push(v);
        }
      }
      return out;
    } catch (e) {
      return [];
    }
  }

  function getResultFromName(result) {
    try {
      return String(
        result?.from_name ||
          result?.value?.from_name ||
          result?.area?.from_name ||
          result?.area?.value?.from_name ||
          result?.origin?.from_name ||
          result?.origin?.value?.from_name ||
          "",
      ).trim();
    } catch (e) {
      return "";
    }
  }

  function collectFromDomContainer(container) {
    const out = [];
    if (!container) return out;

    const checkedInputs = container.querySelectorAll(
      "input[type='checkbox']:checked, input[type='radio']:checked",
    );
    checkedInputs.forEach((input) => {
      let text = "";
      const id = input.getAttribute("id");
      if (id) {
        const label = container.querySelector(`label[for='${id}']`);
        if (label && label.innerText) text = label.innerText;
      }
      if (!text) {
        const near = input.closest("label,li,div,span");
        text = near?.innerText || input?.value || "";
      }
      const token = normalizeChoiceToken(text);
      if (token && !out.includes(token)) out.push(token);
    });

    const ariaChecked = container.querySelectorAll(
      "[role='checkbox'][aria-checked='true'], [role='radio'][aria-checked='true']",
    );
    ariaChecked.forEach((node) => {
      const token = normalizeChoiceToken(
        node?.innerText || node?.textContent || "",
      );
      if (token && !out.includes(token)) out.push(token);
    });

    return out;
  }

  function findMetaSectionContainer(fieldName) {
    const probes = Array.from(
      document.querySelectorAll("h1,h2,h3,h4,h5,h6,div,span,label"),
    );
    const patterns =
      fieldName === "difficulty"
        ? [/困难因素/, /difficulty/i]
        : [/模型初始化问题/, /model\s*issue/i];

    for (const el of probes) {
      const txt = String(el?.innerText || "").trim();
      if (!txt || txt.length > 180) continue;
      if (!patterns.some((re) => re.test(txt))) continue;
      const container = el.closest("section,fieldset,div");
      if (container) return container;
    }
    return null;
  }

  function getSelectedChoicesByFieldFromDom(fieldName) {
    const container = findMetaSectionContainer(fieldName);
    return collectFromDomContainer(container);
  }

  function isFieldPresent(store, fieldName) {
    try {
      const results = collectSelectedResults(store);
      for (const r of results) {
        const fromName = getResultFromName(r);
        if (matchesFieldName(fromName, fieldName)) return true;
      }
      return !!findMetaSectionContainer(fieldName);
    } catch (e) {
      return !!findMetaSectionContainer(fieldName);
    }
  }

  function getSelectedChoicesByField(store, fieldName) {
    try {
      const results = collectSelectedResults(store);
      const out = [];
      for (const r of results) {
        const fromName = getResultFromName(r);
        if (!matchesFieldName(fromName, fieldName)) continue;
        const vals = extractChoicesFromResult(r);
        for (const v of vals) {
          if (v && !out.includes(v)) out.push(v);
        }
      }

      if (out.length > 0) {
        metaGuardDebug(`${fieldName} from store`, out);
        return out;
      }

      const domVals = getSelectedChoicesByFieldFromDom(fieldName);
      metaGuardDebug(`${fieldName} from DOM fallback`, domVals);
      return domVals;
    } catch (e) {
      metaGuardDebug(`getSelectedChoicesByField error for ${fieldName}`, e);
      return [];
    }
  }

  function getTaskCondition(store) {
    const paths = [
      store?.taskStore?.selected?.data?.condition,
      store?.task?.data?.condition,
      store?.annotationStore?.selected?.task?.data?.condition,
    ];
    for (const p of paths) {
      if (p !== undefined && p !== null && String(p).trim()) {
        return String(p).trim();
      }
    }
    return "";
  }

  const META_GUARD_REJECT_LOG_KEY = "HOHONET_META_GUARD_REJECTIONS";
  const META_GUARD_REJECT_STATS_KEY = "HOHONET_META_GUARD_REJECT_STATS";
  const META_GUARD_REJECT_LOG_MAX = 200;

  function loadJsonFromLocalStorage(key, fallback) {
    try {
      const raw = window.localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  function saveJsonToLocalStorage(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {}
  }

  function getIdentityValue(value) {
    if (value === undefined || value === null) return null;
    if (typeof value === "object") {
      return getIdentityValue(value.id ?? value.pk ?? value.user_id);
    }
    const normalized = String(value).trim();
    return normalized && normalized !== "unknown" && normalized !== "[object Object]" ? normalized : null;
  }

  function getIdentityCandidate(value, source) {
    const id = getIdentityValue(value);
    return id ? { id, source } : null;
  }

  function firstIdentityCandidate(candidates, fallbackId = "unknown", fallbackSource = "unknown") {
    for (const [value, source] of candidates) {
      const candidate = getIdentityCandidate(value, source);
      if (candidate) return candidate;
    }
    return { id: fallbackId, source: fallbackSource };
  }

  function getTaskIdentity() {
    try {
      const store = getStore();
      const candidate = firstIdentityCandidate([
        [store?.task?.id, "store.task.id"],
        [store?.taskStore?.selected?.id, "store.taskStore.selected.id"],
        [store?.annotationStore?.selected?.task?.id, "store.annotationStore.selected.task.id"],
      ]);
      if (candidate.id !== "unknown") return candidate;
    } catch (e) {}
    try {
      const params = new URLSearchParams(window.location.search);
      const q = getIdentityValue(params.get("task"));
      if (q) return { id: q, source: "url.query" };
      const match = window.location.pathname.match(/tasks\/(\d+)/);
      if (match) return { id: match[1], source: "url.path" };
    } catch (e) {}
    return { id: "unknown", source: "unknown" };
  }

  function getProjectIdentity() {
    try {
      const store = getStore();
      const candidate = firstIdentityCandidate([
        [store?.project?.id, "store.project.id"],
        [store?.task?.project, "store.task.project"],
        [store?.task?.project_id, "store.task.project_id"],
        [store?.taskStore?.selected?.project, "store.taskStore.selected.project"],
        [store?.taskStore?.selected?.project_id, "store.taskStore.selected.project_id"],
        [store?.annotationStore?.selected?.task?.project, "store.annotationStore.selected.task.project"],
        [store?.annotationStore?.selected?.task?.project_id, "store.annotationStore.selected.task.project_id"],
      ]);
      if (candidate.id !== "unknown") return candidate;
    } catch (e) {}
    try {
      const match = window.location.pathname.match(/projects\/(\d+)/);
      if (match) return { id: match[1], source: "url.path" };
    } catch (e) {}
    return { id: "unknown", source: "unknown" };
  }

  function getAnnotationIdentity() {
    try {
      const store = getStore();
      const selected = store?.annotationStore?.selected;
      let selectedJson = null;
      try {
        selectedJson = selected?.toJSON?.();
      } catch (e) {}
      const annotation = firstIdentityCandidate([
        [selected?.pk, "store.annotationStore.selected.pk"],
        [selected?.annotation?.id, "store.annotationStore.selected.annotation.id"],
        [selectedJson?.id, "store.annotationStore.selected.toJSON.id"],
        [selected?.id, "store.annotationStore.selected.id"],
      ], "unknown_annotation", "unknown");
      if (annotation.id === "unknown_annotation") return annotation;

      const owner = firstIdentityCandidate([
        [selected?.completed_by, "store.annotationStore.selected.completed_by"],
        [selected?.completed_by?.id, "store.annotationStore.selected.completed_by.id"],
        [selected?.user, "store.annotationStore.selected.user"],
        [selected?.user?.id, "store.annotationStore.selected.user.id"],
        [selected?.user_id, "store.annotationStore.selected.user_id"],
        [selected?.createdBy, "store.annotationStore.selected.createdBy"],
        [selected?.createdBy?.id, "store.annotationStore.selected.createdBy.id"],
        [selected?.created_by, "store.annotationStore.selected.created_by"],
        [selected?.created_by?.id, "store.annotationStore.selected.created_by.id"],
        [selectedJson?.completed_by, "store.annotationStore.selected.toJSON.completed_by"],
        [selectedJson?.completed_by?.id, "store.annotationStore.selected.toJSON.completed_by.id"],
        [selectedJson?.user, "store.annotationStore.selected.toJSON.user"],
        [selectedJson?.user?.id, "store.annotationStore.selected.toJSON.user.id"],
        [selectedJson?.user_id, "store.annotationStore.selected.toJSON.user_id"],
      ], "", "");
      const currentAnnotator = getAnnotatorId();
      if (owner.id && currentAnnotator !== "unknown" && owner.id !== String(currentAnnotator)) {
        return {
          id: "unknown_annotation",
          source: "selected_annotation_not_owned_by_current_user",
          selectedAnnotationId: annotation.id,
          selectedAnnotationOwnerId: owner.id,
          selectedAnnotationOwnerSource: owner.source,
        };
      }
      return {
        ...annotation,
        serverAnnotationId: /^\d+$/.test(annotation.id) && annotation.source !== "store.annotationStore.selected.id" ? annotation.id : "",
        clientAnnotationId: getIdentityValue(selected?.id) || "",
        selectedAnnotationId: annotation.id,
        selectedAnnotationOwnerId: owner.id || "",
        selectedAnnotationOwnerSource: owner.source || "",
      };
    } catch (e) {}
    return { id: "unknown_annotation", source: "unknown" };
  }

  function getCurrentAnnotationId() {
    const identity = getAnnotationIdentity();
    if (identity.id !== "unknown") return identity.id;
    return "unknown_annotation";
  }

  function getCornerOrderCacheContext() {
    return {
      project_id: String(getProjectId() || "unknown_project"),
      task_id: String(getTaskId() || "unknown_task"),
      user_id: String(getAnnotatorId() || "unknown_user"),
    };
  }

  function getCornerOrderCacheKey(context = getCornerOrderCacheContext()) {
    return `project:${context.project_id}::task:${context.task_id}::user:${context.user_id}`;
  }

  function getLegacyPreviewOverrideTaskKey() {
    return `${getProjectId()}::${getTaskId()}::${getAnnotatorId()}`;
  }

  function getPreviewOverrideTaskKey() {
    return getCornerOrderCacheKey();
  }

  function getIdentityOrder(length) {
    return Array.from({ length }, (_, idx) => idx);
  }

  function roundForPreviewSignature(value) {
    const factor = 10 ** PREVIEW_ORDER_ROUND_DIGITS;
    return Math.round(Number(value || 0) * factor) / factor;
  }

  function buildPreviewSignature(pairedCorners) {
    if (!Array.isArray(pairedCorners) || pairedCorners.length === 0) return "";
    return pairedCorners
      .map((corner) =>
        [
          roundForPreviewSignature(corner.x),
          roundForPreviewSignature(corner.y_ceiling),
          roundForPreviewSignature(corner.y_floor),
        ].join(","),
      )
      .join("|");
  }

  function normalizePreviewOrder(order, length) {
    if (!Array.isArray(order) || order.length !== length) return null;
    const seen = new Set();
    const normalized = [];
    for (const rawIdx of order) {
      const idx = Number(rawIdx);
      if (!Number.isInteger(idx) || idx < 0 || idx >= length || seen.has(idx)) {
        return null;
      }
      seen.add(idx);
      normalized.push(idx);
    }
    return normalized;
  }

  function applyPreviewOrder(pairedCorners, order) {
    const normalized = normalizePreviewOrder(
      order,
      Array.isArray(pairedCorners) ? pairedCorners.length : 0,
    );
    if (!normalized) {
      return {
        corners: Array.isArray(pairedCorners) ? pairedCorners.slice() : [],
        order: null,
      };
    }
    return {
      corners: normalized.map((idx) => pairedCorners[idx]),
      order: normalized,
    };
  }

  function clonePreviewCornerPoint(point) {
    return {
      x: Number(point?.x || 0),
      y: Number(point?.y || 0),
      pctX: point?.pctX === undefined ? undefined : Number(point.pctX),
      pctY: point?.pctY === undefined ? undefined : Number(point.pctY),
    };
  }

  function clonePreviewCornerPair(pair) {
    return {
      x: Number(pair?.x || 0),
      y_ceiling: Number(pair?.y_ceiling || 0),
      y_floor: Number(pair?.y_floor || 0),
      originalPoints: Array.isArray(pair?.originalPoints)
        ? pair.originalPoints.map(clonePreviewCornerPoint)
        : [],
    };
  }

  function clonePreviewCornerPairs(pairs) {
    return Array.isArray(pairs) ? pairs.map(clonePreviewCornerPair) : [];
  }

  function renderPreviewOverlayPairs(pairedCorners) {
    try {
      const img = findMainImage();
      if (!img) return;

      const overlay = ensureOverlay(img);
      overlay.innerHTML = "";

      const visible = getLabelsVisible();
      overlay.style.display = visible ? "block" : "none";

      const toggleBtn = document.getElementById(TOGGLE_BTN_ID);
      if (toggleBtn) applyToggleBtnState(toggleBtn, visible);

      const rect = positionOverlayToImage(img, overlay);
      (Array.isArray(pairedCorners) ? pairedCorners : []).forEach((pair, idx) => {
        const label = String(idx + 1);
        (Array.isArray(pair?.originalPoints) ? pair.originalPoints : []).forEach((p) => {
          if (p?.pctX === undefined || p?.pctY === undefined) return;
          const badge = document.createElement("div");
          badge.innerText = label;
          badge.dataset.pctx = String(p.pctX);
          badge.dataset.pcty = String(p.pctY);
          badge.style.cssText = `
            position: absolute;
            transform: translate(-50%, -150%);
            background: rgba(255, 255, 0, 0.9);
            color: black;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
            border: 1px solid black;
            box-shadow: 0 2px 4px rgba(0,0,0,0.5);
          `;
          overlay.appendChild(badge);
        });
      });

      positionOverlayBadges(overlay, rect);
    } catch (e) {
      console.error("HoHoNet: 覆盖层错误", e);
    }
  }

  function syncPreviewOverlayWithOrder(order, signature = "") {
    if (!currentPreviewBaseCorners.length) return;
    if (signature && currentPreviewSignature && signature !== currentPreviewSignature) {
      return;
    }
    const applied = applyPreviewOrder(currentPreviewBaseCorners, order);
    const orderedCorners = applied.order ? applied.corners : currentPreviewBaseCorners;
    renderPreviewOverlayPairs(orderedCorners);
  }

  function loadPreviewOrderOverride(taskKey) {
    const cache = loadJsonFromLocalStorage(PREVIEW_ORDER_OVERRIDES_KEY, {});
    const entries =
      cache &&
      typeof cache === "object" &&
      !Array.isArray(cache) &&
      cache.schema === CORNER_ORDER_CACHE_SCHEMA &&
      cache.entries &&
      typeof cache.entries === "object" &&
      !Array.isArray(cache.entries)
        ? cache.entries
        : {};
    const value = entries[taskKey];
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    return value;
  }

  function savePreviewOrderOverride(taskKey, payload) {
    const context = getCornerOrderCacheContext();
    const order = normalizePreviewOrder(
      payload?.order,
      Number(payload?.corner_count) ||
        (Array.isArray(payload?.order) ? payload.order.length : 0),
    );
    if (!taskKey || !order) return false;
    const cache = loadJsonFromLocalStorage(PREVIEW_ORDER_OVERRIDES_KEY, {});
    const next =
      cache &&
      typeof cache === "object" &&
      !Array.isArray(cache) &&
      cache.schema === CORNER_ORDER_CACHE_SCHEMA
        ? cache
        : { schema: CORNER_ORDER_CACHE_SCHEMA, entries: {} };
    if (!next.entries || typeof next.entries !== "object" || Array.isArray(next.entries)) {
      next.entries = {};
    }
    next.schema = CORNER_ORDER_CACHE_SCHEMA;
    next.updated_at = Date.now();
    next.entries[taskKey] = {
      schema: CORNER_ORDER_CACHE_SCHEMA,
      cache_key: taskKey,
      project_id: context.project_id,
      task_id: context.task_id,
      user_id: context.user_id,
      corner_count: order.length,
      signature: String(payload?.signature || ""),
      order,
      updated_at: Date.now(),
      source: String(payload?.source || "preview_order_state"),
      script_version: SCRIPT_VERSION,
      hotfix_version: CORNER_ORDER_CACHE_HOTFIX_VERSION,
    };
    saveJsonToLocalStorage(PREVIEW_ORDER_OVERRIDES_KEY, next);
    window.__HOHONET_CORNER_ORDER_CACHE_LAST_STATUS__ = {
      ok: true,
      reason: "saved",
      cache_key: taskKey,
      order,
    };
    return true;
  }

  function clearPreviewOrderOverride(taskKey) {
    const cache = loadJsonFromLocalStorage(PREVIEW_ORDER_OVERRIDES_KEY, {});
    if (
      !cache ||
      typeof cache !== "object" ||
      Array.isArray(cache) ||
      !cache.entries ||
      typeof cache.entries !== "object" ||
      Array.isArray(cache.entries)
    ) {
      return false;
    }
    if (!(taskKey in cache.entries)) return false;
    delete cache.entries[taskKey];
    cache.updated_at = Date.now();
    saveJsonToLocalStorage(PREVIEW_ORDER_OVERRIDES_KEY, cache);
    window.__HOHONET_CORNER_ORDER_CACHE_LAST_STATUS__ = {
      ok: true,
      reason: "cleared",
      cache_key: taskKey,
    };
    return true;
  }

  function rejectCornerOrderCache(reason, extra = {}) {
    const status = {
      ok: false,
      reason,
      ...extra,
    };
    window.__HOHONET_CORNER_ORDER_CACHE_LAST_STATUS__ = status;
    console.warn("HoHoNet: corner-order cache rejected:", status);
    return { record: null, order: null, reason };
  }

  function validateCornerOrderCacheRecord(record, taskKey, expected = {}) {
    if (!record || typeof record !== "object" || Array.isArray(record)) {
      return rejectCornerOrderCache("missing_record", { cache_key: taskKey });
    }
    const context = getCornerOrderCacheContext();
    if (record.schema !== CORNER_ORDER_CACHE_SCHEMA) {
      return rejectCornerOrderCache("schema_mismatch", { cache_key: taskKey });
    }
    if (record.cache_key && record.cache_key !== taskKey) {
      return rejectCornerOrderCache("cache_key_mismatch", { cache_key: taskKey });
    }
    if (String(record.project_id || "") !== context.project_id) {
      return rejectCornerOrderCache("project_mismatch", { cache_key: taskKey });
    }
    if (String(record.task_id || "") !== context.task_id) {
      return rejectCornerOrderCache("task_mismatch", { cache_key: taskKey });
    }
    if (String(record.user_id || "") !== context.user_id) {
      return rejectCornerOrderCache("user_mismatch", { cache_key: taskKey });
    }
    const cornerCount = Number(expected.corner_count || 0);
    if (!Number.isInteger(cornerCount) || cornerCount <= 0) {
      return rejectCornerOrderCache("invalid_expected_corner_count", { cache_key: taskKey });
    }
    if (Number(record.corner_count) !== cornerCount) {
      return rejectCornerOrderCache("corner_count_mismatch", {
        cache_key: taskKey,
        expected_corner_count: cornerCount,
        cached_corner_count: Number(record.corner_count),
      });
    }
    if (
      expected.signature &&
      record.signature &&
      String(record.signature) !== String(expected.signature)
    ) {
      return rejectCornerOrderCache("signature_mismatch", { cache_key: taskKey });
    }
    const order = normalizePreviewOrder(record.order, cornerCount);
    if (!order) {
      return rejectCornerOrderCache("invalid_order_missing_duplicate_or_out_of_range", {
        cache_key: taskKey,
      });
    }
    window.__HOHONET_CORNER_ORDER_CACHE_LAST_STATUS__ = {
      ok: true,
      reason: "loaded",
      cache_key: taskKey,
      order,
    };
    return { record: { ...record, order }, order, reason: "loaded" };
  }

  function loadValidatedPreviewOrderOverride(taskKey, expected = {}) {
    const record = loadPreviewOrderOverride(taskKey);
    return validateCornerOrderCacheRecord(record, taskKey, expected);
  }

  function isIdentityPreviewOrder(order) {
    if (!Array.isArray(order)) return false;
    return order.every((value, idx) => Number(value) === idx);
  }

  function persistAdjustedPreviewOrder(order, cornerCount, signature, source) {
    const normalized = normalizePreviewOrder(order, cornerCount);
    if (!normalized || isIdentityPreviewOrder(normalized)) return false;
    const taskKey = getCurrentPreviewStorageTaskKey();
    return savePreviewOrderOverride(taskKey, {
      signature,
      order: normalized,
      corner_count: cornerCount,
      source,
    });
  }

  window.__HOHONET_CLEAR_CORNER_ORDER_CACHE_FOR_CURRENT_TASK__ = () => {
    const taskKey = getCurrentPreviewStorageTaskKey();
    return {
      cache_key: taskKey,
      cleared: clearPreviewOrderOverride(taskKey),
    };
  };

  function ensurePreviewControlPanelStyle() {
    if (document.getElementById(PREVIEW_PANEL_STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = PREVIEW_PANEL_STYLE_ID;
    style.textContent = `
#${PREVIEW_PANEL_ID} {
  position: fixed;
  z-index: 9998;
  width: 282px;
  color: #f4f7fb;
  background: rgba(40, 44, 50, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
  overflow: hidden;
  backdrop-filter: blur(14px);
}
#${PREVIEW_PANEL_ID}[data-collapsed="1"] #${PREVIEW_PANEL_BODY_ID} {
  display: none;
}
#${PREVIEW_PANEL_HEADER_ID} {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  cursor: move;
  user-select: none;
  background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.025));
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
#${PREVIEW_PANEL_BODY_ID} {
  padding: 9px 10px 10px;
}
#${PREVIEW_PANEL_ID} .hp-title {
  font-size: 13px;
  font-weight: 800;
}
#${PREVIEW_PANEL_ID} .hp-slot {
  font-size: 11px;
  color: #d9e2ec;
}
#${PREVIEW_PANEL_ID} .hp-toggle {
  border: none;
  border-radius: 7px;
  padding: 4px 7px;
  background: rgba(255,255,255,0.12);
  color: white;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
}
#${PREVIEW_PANEL_ID} .hp-note,
#${PREVIEW_PANEL_ID} .hp-status,
#${PREVIEW_PANEL_ID} .hp-subnote {
  font-size: 11px;
  line-height: 1.38;
}
#${PREVIEW_PANEL_ID} .hp-note {
  color: #d6deea;
  margin-bottom: 5px;
}
#${PREVIEW_PANEL_ID} .hp-status {
  color: #9fd0ff;
  margin-bottom: 7px;
}
#${PREVIEW_PANEL_ID} .hp-subnote {
  color: #9aa8b8;
  margin-top: 5px;
}
#${PREVIEW_PANEL_ID} .hp-section {
  margin-top: 7px;
}
#${PREVIEW_PANEL_ID} .hp-label {
  margin-bottom: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #9aa8b8;
  text-transform: uppercase;
}
#${PREVIEW_PANEL_ID} .hp-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
}
#${PREVIEW_PANEL_ID} .hp-row + .hp-row {
  margin-top: 5px;
}
#${PREVIEW_PANEL_ID} input[type="number"] {
  width: 54px;
  padding: 4px 6px;
  border-radius: 7px;
  border: 1px solid #415067;
  background: rgba(11, 17, 24, 0.85);
  color: white;
  font-size: 12px;
}
#${PREVIEW_PANEL_ID} button {
  border: none;
  border-radius: 7px;
  padding: 5px 8px;
  color: white;
  background: #5e6a7a;
  cursor: pointer;
  font-weight: 700;
  font-size: 12px;
}
#${PREVIEW_PANEL_ID} button.hp-primary {
  background: #2f5cff;
}
#${PREVIEW_PANEL_ID} button.hp-warn {
  background: #c84f4f;
}
#${PREVIEW_PANEL_ID} button:disabled,
#${PREVIEW_PANEL_ID} input:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
`;
    document.head.appendChild(style);
  }

  function loadPreviewPanelPosition() {
    try {
      const raw = window.localStorage.getItem(PREVIEW_PANEL_POSITION_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (
        !parsed ||
        typeof parsed !== "object" ||
        !Number.isFinite(parsed.left) ||
        !Number.isFinite(parsed.top)
      ) {
        return null;
      }
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function savePreviewPanelPosition(left, top) {
    try {
      window.localStorage.setItem(
        PREVIEW_PANEL_POSITION_KEY,
        JSON.stringify({ left, top }),
      );
    } catch (e) {}
  }

  function clampPreviewPanelPosition(left, top) {
    const panel = document.getElementById(PREVIEW_PANEL_ID);
    const width = panel ? panel.offsetWidth || 320 : 320;
    const height = panel ? panel.offsetHeight || 260 : 260;
    return {
      left: Math.min(Math.max(12, left), Math.max(12, window.innerWidth - width - 12)),
      top: Math.min(Math.max(12, top), Math.max(12, window.innerHeight - height - 12)),
    };
  }

  function applyPreviewPanelPosition(left, top, persist = false) {
    const panel = document.getElementById(PREVIEW_PANEL_ID);
    if (!panel) return;
    const next = clampPreviewPanelPosition(left, top);
    panel.style.left = `${next.left}px`;
    panel.style.top = `${next.top}px`;
    if (persist) savePreviewPanelPosition(next.left, next.top);
  }

  function initializePreviewPanelPosition(anchorEl = null) {
    const stored = loadPreviewPanelPosition();
    if (stored) {
      applyPreviewPanelPosition(stored.left, stored.top, false);
      return;
    }

    let left = Math.max(12, window.innerWidth - 304);
    let top = 96;
    if (anchorEl) {
      const rect = anchorEl.getBoundingClientRect();
      if (rect && rect.width > 0 && rect.height > 0) {
        left = rect.right + 16;
        top = Math.max(12, rect.top);
      }
    }
    applyPreviewPanelPosition(left, top, false);
  }

  function setPreviewPanelCollapsed(collapsed, persist = true) {
    const panel = document.getElementById(PREVIEW_PANEL_ID);
    const toggleBtn = document.getElementById(PREVIEW_PANEL_TOGGLE_ID);
    if (!panel || !toggleBtn) return;
    panel.dataset.collapsed = collapsed ? "1" : "0";
    toggleBtn.innerText = collapsed ? "Expand" : "Collapse";
    if (persist) {
      try {
        window.localStorage.setItem(
          PREVIEW_PANEL_COLLAPSED_KEY,
          collapsed ? "1" : "0",
        );
      } catch (e) {}
    }
  }

  function initializePreviewPanelCollapsed() {
    let collapsed = true;
    try {
      const stored = window.localStorage.getItem(PREVIEW_PANEL_COLLAPSED_KEY);
      collapsed = stored === null ? true : stored === "1";
    } catch (e) {}
    setPreviewPanelCollapsed(collapsed, false);
  }

  function initializePreviewPanelDrag() {
    const panel = document.getElementById(PREVIEW_PANEL_ID);
    const header = document.getElementById(PREVIEW_PANEL_HEADER_ID);
    if (!panel || !header || header.dataset.dragBound === "1") return;
    header.dataset.dragBound = "1";

    let dragging = false;
    let offsetX = 0;
    let offsetY = 0;

    header.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) return;
      const rect = panel.getBoundingClientRect();
      dragging = true;
      offsetX = event.clientX - rect.left;
      offsetY = event.clientY - rect.top;
      header.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    header.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      applyPreviewPanelPosition(event.clientX - offsetX, event.clientY - offsetY, false);
    });

    const stopDragging = (event) => {
      if (!dragging) return;
      dragging = false;
      const rect = panel.getBoundingClientRect();
      savePreviewPanelPosition(rect.left, rect.top);
      if (event && header.hasPointerCapture(event.pointerId)) {
        header.releasePointerCapture(event.pointerId);
      }
    };

    header.addEventListener("pointerup", stopDragging);
    header.addEventListener("pointercancel", stopDragging);
  }

  function updatePreviewControlPanelUi() {
    const controls = getPreviewControlPanelElements();
    if (!controls.panel) return;

    const {
      hasData,
      savedOverrideActive,
      statusText,
      safeCount,
      safeIndex,
      currentPairNumber,
    } = getPreviewSelectionSnapshot();

    if (controls.slotNode) {
      controls.slotNode.innerText = hasData
        ? `Current pair ${currentPairNumber} / ${safeCount}`
        : "Current pair -- / --";
    }
    if (controls.statusNode) {
      controls.statusNode.innerText =
        statusText || (savedOverrideActive ? "Local saved order: yes" : "Local saved order: no");
    }
    if (
      controls.pairInput &&
      document.activeElement !== controls.pairInput &&
      !currentPreviewInputDraft.pairDirty
    ) {
      controls.pairInput.value = String(currentPairNumber);
    }
    if (
      controls.swapInput &&
      document.activeElement !== controls.swapInput &&
      !currentPreviewInputDraft.swapDirty &&
      !currentPreviewInputDraft.swapInitialized
    ) {
      const suggestedTarget =
        safeCount > 1 ? Math.min(safeCount, currentPairNumber + 1) : 1;
      controls.swapInput.value = String(suggestedTarget);
      currentPreviewInputDraft.swapInitialized = true;
    }

    if (controls.pairInput) controls.pairInput.disabled = !hasData;
    if (controls.swapInput) controls.swapInput.disabled = !hasData;
    if (controls.prevBtn) controls.prevBtn.disabled = !hasData || safeIndex === 0;
    if (controls.nextBtn) {
      controls.nextBtn.disabled = !hasData || safeIndex >= safeCount - 1;
    }
    if (controls.swapRunBtn) controls.swapRunBtn.disabled = !hasData;
    if (controls.swapPrevBtn) {
      controls.swapPrevBtn.disabled = !hasData || safeIndex === 0;
    }
    if (controls.swapNextBtn) {
      controls.swapNextBtn.disabled = !hasData || safeIndex >= safeCount - 1;
    }
    if (controls.saveBtn) controls.saveBtn.disabled = !hasData;
    if (controls.resetBtn) controls.resetBtn.disabled = !hasData;
    if (controls.deleteBtn) {
      controls.deleteBtn.disabled = !hasData || !savedOverrideActive;
    }
  }

  function resetPreviewControlPanelState(statusText = DEFAULT_PREVIEW_STATUS_TEXT) {
    resetPreviewRuntimeState(statusText);
    updatePreviewControlPanelUi();
  }

  function handlePreviewOrderStateMessage(data) {
    currentPreviewUiState = createPreviewUiStateFromMessage(data);
    const orderLength =
      currentPreviewDefaultCount ||
      (Array.isArray(data.previewOrder) ? data.previewOrder.length : 0);
    const previewOrder = normalizePreviewOrder(
      data.previewOrder,
      orderLength,
    );
    const previewSignature = String(data.previewSignature || "");
    if (previewOrder) {
      syncPreviewOverlayWithOrder(previewOrder, previewSignature);
      persistAdjustedPreviewOrder(
        previewOrder,
        orderLength,
        previewSignature,
        "preview_order_state",
      );
    }
    updatePreviewControlPanelUi();
  }

  function handlePreviewOrderSaveMessage(iframe, data) {
    const taskKey = getCurrentPreviewStorageTaskKey();
    const signature = String(data.previewSignature || currentPreviewSignature || "");
    const orderLength =
      currentPreviewDefaultCount ||
      (Array.isArray(data.previewOrder) ? data.previewOrder.length : 0);
    const normalizedOrder = normalizePreviewOrder(
      data.previewOrder,
      orderLength,
    );
    if (!taskKey || !signature || !normalizedOrder) {
      postPreviewOrderAck(iframe, "save", false, "invalid_payload");
      return;
    }

    savePreviewOrderOverride(taskKey, {
      signature,
      order: normalizedOrder,
      corner_count: normalizedOrder.length,
      source: "preview_order_save",
      updated_at: Date.now(),
    });
    currentPreviewSignature = signature;
    postPreviewOrderAck(iframe, "save", true);
  }

  function handlePreviewOrderDeleteMessage(iframe, action) {
    const taskKey = getCurrentPreviewStorageTaskKey();
    if (taskKey) clearPreviewOrderOverride(taskKey);
    postPreviewOrderAck(iframe, action, true);
  }

  function postPreviewOrderCommand(action, extra = {}) {
    const iframe = document.getElementById(IFRAME_ID);
    if (!iframe || !iframe.contentWindow) {
      alert("3D view is not ready. Click Refresh 3D View first.");
      return;
    }
    iframe.contentWindow.postMessage(
      {
        type: "hohonet_preview_order_command",
        action,
        ...extra,
      },
      "*",
    );
  }

  function ensurePreviewControlPanel(anchorEl = null) {
    ensurePreviewControlPanelStyle();
    let panel = document.getElementById(PREVIEW_PANEL_ID);
    if (panel) {
      panel.style.display = "block";
      return panel;
    }

    panel = document.createElement("div");
    panel.id = PREVIEW_PANEL_ID;
    panel.innerHTML = `
      <div id="${PREVIEW_PANEL_HEADER_ID}">
        <div>
          <div class="hp-title">Preview Order</div>
          <div id="${PREVIEW_PANEL_SLOT_ID}" class="hp-slot">Current pair -- / --</div>
        </div>
        <button id="${PREVIEW_PANEL_TOGGLE_ID}" class="hp-toggle" type="button">Expand</button>
      </div>
      <div id="${PREVIEW_PANEL_BODY_ID}">
        <div class="hp-note">Affects only the 3D preview. It does not edit the annotation data.</div>
        <div id="${PREVIEW_PANEL_STATUS_ID}" class="hp-status">${DEFAULT_PREVIEW_STATUS_TEXT}</div>
        <div class="hp-section">
          <div class="hp-label">Go to Pair</div>
          <div class="hp-row">
            <span>Pair</span>
            <input id="${PREVIEW_PANEL_PAIR_INPUT_ID}" type="number" min="1" step="1" value="1" />
          </div>
          <div class="hp-row">
            <button id="${PREVIEW_PANEL_PAIR_PREV_ID}" type="button">Previous Pair</button>
            <button id="${PREVIEW_PANEL_PAIR_NEXT_ID}" type="button">Next Pair</button>
          </div>
        </div>
        <div class="hp-section">
          <div class="hp-label">Swap Current Pair</div>
          <div class="hp-row">
            <button id="${PREVIEW_PANEL_SWAP_PREV_ID}" type="button">Swap with Previous</button>
            <button id="${PREVIEW_PANEL_SWAP_NEXT_ID}" type="button">Swap with Next</button>
          </div>
          <div class="hp-row">
            <span>Swap with pair</span>
            <input id="${PREVIEW_PANEL_SWAP_INPUT_ID}" type="number" min="1" step="1" value="1" />
            <button id="${PREVIEW_PANEL_SWAP_RUN_ID}" type="button">Apply</button>
          </div>
        </div>
        <div class="hp-section">
          <div class="hp-label">Save and Reset</div>
          <div class="hp-row">
            <button id="${PREVIEW_PANEL_SAVE_ID}" type="button" class="hp-primary">Save</button>
            <button id="${PREVIEW_PANEL_RESET_ID}" type="button">Restore Default</button>
          </div>
          <div class="hp-row">
            <button id="${PREVIEW_PANEL_DELETE_ID}" type="button" class="hp-warn">Delete Saved Order</button>
          </div>
          <div class="hp-subnote">Restore Default affects the current preview only; Delete Saved Order removes the saved order for this task.</div>
        </div>
      </div>
    `;
    document.body.appendChild(panel);

    const pairInput = document.getElementById(PREVIEW_PANEL_PAIR_INPUT_ID);
    const swapInput = document.getElementById(PREVIEW_PANEL_SWAP_INPUT_ID);
    const applyPairSelectionFromInput = () => {
      currentPreviewInputDraft.pairDirty = false;
      postPreviewOrderCommand("set_pair", {
        index: Number(pairInput?.value),
      });
    };
    const syncSelectionFromPairInput = () => {
      if (!currentPreviewUiState.hasData || !pairInput) return;
      const desired = Number(pairInput.value);
      if (!Number.isInteger(desired)) return;
      const { currentPairNumber } = getPreviewSelectionSnapshot();
      const current = currentPairNumber;
      if (desired !== current) {
        currentPreviewInputDraft.pairDirty = false;
        applyPairSelectionFromInput();
      }
    };
    const runSwapTargetFromInput = () => {
      const targetIndex = Number(swapInput?.value);
      currentPreviewInputDraft.swapDirty = false;
      currentPreviewInputDraft.swapInitialized = true;
      syncSelectionFromPairInput();
      postPreviewOrderCommand("swap_target", {
        index: targetIndex,
      });
    };
    pairInput?.addEventListener("input", () => {
      currentPreviewInputDraft.pairDirty = true;
    });
    swapInput?.addEventListener("input", () => {
      currentPreviewInputDraft.swapDirty = true;
      currentPreviewInputDraft.swapInitialized = true;
    });

    pairInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        applyPairSelectionFromInput();
      }
    });
    pairInput?.addEventListener("change", applyPairSelectionFromInput);
    document
      .getElementById(PREVIEW_PANEL_PAIR_PREV_ID)
      .addEventListener("click", () => {
        syncSelectionFromPairInput();
        postPreviewOrderCommand("prev_pair");
      });
    document
      .getElementById(PREVIEW_PANEL_PAIR_NEXT_ID)
      .addEventListener("click", () => {
        syncSelectionFromPairInput();
        postPreviewOrderCommand("next_pair");
      });
    document
      .getElementById(PREVIEW_PANEL_SWAP_RUN_ID)
      .addEventListener("click", runSwapTargetFromInput);
    swapInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        runSwapTargetFromInput();
      }
    });
    document
      .getElementById(PREVIEW_PANEL_SWAP_PREV_ID)
      .addEventListener("click", () => {
        syncSelectionFromPairInput();
        postPreviewOrderCommand("swap_prev");
      });
    document
      .getElementById(PREVIEW_PANEL_SWAP_NEXT_ID)
      .addEventListener("click", () => {
        syncSelectionFromPairInput();
        postPreviewOrderCommand("swap_next");
      });
    document
      .getElementById(PREVIEW_PANEL_SAVE_ID)
      .addEventListener("click", () => postPreviewOrderCommand("save"));
    document
      .getElementById(PREVIEW_PANEL_RESET_ID)
      .addEventListener("click", () =>
        postPreviewOrderCommand("reset_default_order"),
      );
    document
      .getElementById(PREVIEW_PANEL_DELETE_ID)
      .addEventListener("click", () =>
        postPreviewOrderCommand("delete_saved_override"),
      );
    document
      .getElementById(PREVIEW_PANEL_TOGGLE_ID)
      .addEventListener("click", () => {
        const collapsed =
          document.getElementById(PREVIEW_PANEL_ID)?.dataset.collapsed === "1";
        setPreviewPanelCollapsed(!collapsed, true);
      });

    initializePreviewPanelCollapsed();
    initializePreviewPanelPosition(anchorEl);
    initializePreviewPanelDrag();
    updatePreviewControlPanelUi();
    return panel;
  }

  function recordMetaGuardRejection({ store, errs, difficulty, modelIssue }) {
    try {
      const now = Date.now();
      const taskId = getTaskId?.() || "unknown";
      const projectId = getProjectId?.() || "unknown";
      const projectName = getProjectName?.() || "unknown";
      const annotatorId = getAnnotatorId?.() || "unknown";
      const condition = getTaskCondition(store);

      const event = {
        timestamp: now,
        task_id: taskId,
        project_id: projectId,
        project_name: projectName,
        annotator_id: annotatorId,
        session_id: sessionId,
        script_version: SCRIPT_VERSION,
        condition,
        reject_reasons: Array.isArray(errs) ? errs.slice(0, 20) : [],
        difficulty: Array.isArray(difficulty) ? difficulty.slice(0, 50) : [],
        model_issue: Array.isArray(modelIssue) ? modelIssue.slice(0, 50) : [],
      };

      const log = loadJsonFromLocalStorage(META_GUARD_REJECT_LOG_KEY, []);
      const nextLog = Array.isArray(log) ? log : [];
      nextLog.push(event);
      if (nextLog.length > META_GUARD_REJECT_LOG_MAX) {
        nextLog.splice(0, nextLog.length - META_GUARD_REJECT_LOG_MAX);
      }
      saveJsonToLocalStorage(META_GUARD_REJECT_LOG_KEY, nextLog);

      const stats = loadJsonFromLocalStorage(META_GUARD_REJECT_STATS_KEY, {
        total_rejected: 0,
        by_reason: {},
        last_reject_ts: 0,
      });
      const nextStats =
        stats && typeof stats === "object" && !Array.isArray(stats)
          ? stats
          : { total_rejected: 0, by_reason: {}, last_reject_ts: 0 };
      nextStats.total_rejected = (nextStats.total_rejected || 0) + 1;
      nextStats.last_reject_ts = now;
      if (!nextStats.by_reason || typeof nextStats.by_reason !== "object") {
        nextStats.by_reason = {};
      }
      for (const r of Array.isArray(errs) ? errs : []) {
        const k = String(r || "").trim();
        if (!k) continue;
        nextStats.by_reason[k] = (nextStats.by_reason[k] || 0) + 1;
      }
      saveJsonToLocalStorage(META_GUARD_REJECT_STATS_KEY, nextStats);
    } catch (e) {
      metaGuardDebug("recordMetaGuardRejection error", e);
    }
  }

  function validateMetaChoices(store) {
    const errors = [];
    const hasDifficultyField = isFieldPresent(store, "difficulty");
    const hasModelIssueField = isFieldPresent(store, "model_issue");
    const difficulty = getSelectedChoicesByField(store, "difficulty");
    const modelIssue = hasModelIssueField
      ? getSelectedChoicesByField(store, "model_issue")
      : [];
    const condition = getTaskCondition(store).toLowerCase();
    metaGuardDebug("validateMetaChoices", {
      hasDifficultyField,
      hasModelIssueField,
      difficulty,
      modelIssue,
      condition,
    });

    const hasTrivial = difficulty.some((x) => isTrivialToken(x));
    const hasNonTrivial = difficulty.some((x) => !isTrivialToken(x));
    const hasAcceptable = modelIssue.some((x) => isAcceptableToken(x));
    const hasNonAcceptable = modelIssue.some((x) => !isAcceptableToken(x));
    metaGuardDebug("meta-eval", {
      difficulty,
      hasTrivial,
      hasNonTrivial,
      modelIssue,
      hasAcceptable,
      hasNonAcceptable,
      condition,
    });

    if (hasDifficultyField && hasTrivial && hasNonTrivial) {
      errors.push(
        "Difficulty conflict: `trivial` cannot be selected together with other difficulty labels. / Difficulty 冲突：trivial 不能与其他困难标签共存",
      );
    }
    if (hasModelIssueField && hasAcceptable && hasNonAcceptable) {
      errors.push(
        "Model Issue conflict: `acceptable` cannot be selected together with other issue labels. / Model Issue 冲突：acceptable 不能与其他 issue 共存",
      );
    }

    return errors;
  }

  function shouldGuardAction(target) {
    if (!target) return false;
    const text = String(
      target.innerText || target.textContent || "",
    ).toLowerCase();
    const aria = String(
      target.getAttribute?.("aria-label") || "",
    ).toLowerCase();
    const title = String(target.getAttribute?.("title") || "").toLowerCase();
    const testid = String(
      target.getAttribute?.("data-testid") || "",
    ).toLowerCase();
    const merged = `${text} ${aria} ${title} ${testid}`;
    if (!merged.trim()) return false;
    const keys = ["submit", "update", "完成", "提交", "更新"];
    return keys.some((k) => merged.includes(k));
  }

  function installMetaSubmitGuard() {
    if (window.__HOHONET_META_GUARD_INSTALLED__) return;
    window.__HOHONET_META_GUARD_INSTALLED__ = true;

    const isGuardEnabled = () => {
      try {
        return window.localStorage.getItem("HOHONET_STRICT_META_GUARD") !== "0";
      } catch (e) {
        return true;
      }
    };

    const runCheck = () => {
      const store = getStore();
      if (!store) return true;
      const errs = validateMetaChoices(store);
      if (!errs.length) return true;

      // 过程性证据：记录每次被硬阻断的原因/次数（不影响交互）
      try {
        const difficulty = getSelectedChoicesByField(store, "difficulty");
        const hasModelIssueField = isFieldPresent(store, "model_issue");
        const modelIssue = hasModelIssueField
          ? getSelectedChoicesByField(store, "model_issue")
          : [];
        recordMetaGuardRejection({ store, errs, difficulty, modelIssue });
      } catch (e) {}

      const msg = [
        "Submission blocked: inconsistent meta labels were detected.",
        "提交被拦截：检测到元标签不合规。",
        "Please fix the following issue(s), then submit again.",
        "请修正后再提交：",
        ...errs.map((x) => `- ${x}`),
      ].join("\n");
      alert(msg);
      console.warn("HoHoNet Meta Guard blocked submit:", errs);
      return false;
    };

    document.addEventListener(
      "click",
      (event) => {
        if (!isGuardEnabled() || !isLikelyAnnotationPage()) return;
        const node = event.target?.closest?.("button,[role='button']");
        if (!shouldGuardAction(node)) return;
        if (!runCheck()) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      },
      true,
    );

    document.addEventListener(
      "keydown",
      (event) => {
        if (!isGuardEnabled() || !isLikelyAnnotationPage()) return;
        const isSubmitHotkey =
          (event.ctrlKey || event.metaKey) && event.key === "Enter";
        if (!isSubmitHotkey) return;
        if (!runCheck()) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      },
      true,
    );

    console.log(
      "HoHoNet Meta Guard: enabled (disable: localStorage.HOHONET_STRICT_META_GUARD=0)",
    );
    console.log(
      "HoHoNet Meta Guard debug keys: HOHONET_META_GUARD_DEBUG=1 or HOHONET_DEBUG_META_GUARD=1",
    );
    console.log(
      "HoHoNet Meta Guard audit: localStorage.HOHONET_META_GUARD_REJECTIONS (capped) and HOHONET_META_GUARD_REJECT_STATS",
    );
  }

  function findSectionContainer() {
    const headers = Array.from(document.querySelectorAll("h3"));
    const header = headers.find(
      (h) => h.textContent && h.textContent.includes("3D Layout Preview"),
    );
    if (!header) return null;
    let sibling = header.nextElementSibling;
    if (
      sibling &&
      (sibling.classList.contains("lsf-object") ||
        sibling.classList.contains("lsf-richtext"))
    ) {
      return sibling;
    }
    return null;
  }

  function findMainImage() {
    // 1. 尝试在主标注区域内查找图像
    // Label Studio 结构通常有 .lsf-main-view 或 .ls-main-view
    const mainView =
      document.querySelector(".lsf-main-view") ||
      document.querySelector(".ls-main-view");
    if (mainView) {
      const imgs = Array.from(mainView.querySelectorAll("img"));
      // 过滤掉图标/缩略图等小图片
      const candidates = imgs.filter(
        (img) => img.naturalWidth > 200 || img.width > 200,
      );
      if (candidates.length > 0) {
        // 返回面积最大的图片
        return candidates.reduce((a, b) =>
          (a.naturalWidth || 0) * (a.naturalHeight || 0) >
          (b.naturalWidth || 0) * (b.naturalHeight || 0)
            ? a
            : b,
        );
      }
    }

    // 2. 备选方案：在整个页面上查找最大的图像
    const allImgs = Array.from(document.querySelectorAll("img"));
    if (allImgs.length > 0) {
      return allImgs.reduce((a, b) => {
        const areaA = (a.naturalWidth || 0) * (a.naturalHeight || 0);
        const areaB = (b.naturalWidth || 0) * (b.naturalHeight || 0);
        return areaA > areaB ? a : b;
      });
    }
    return null;
  }

  function getImageUrlFromStore() {
    try {
      const store = getStore();
      const data = store && store.task && store.task.data;
      if (!data || typeof data !== "object") return null;

      // Common keys first
      const preferredKeys = [
        "image",
        "img",
        "pano",
        "pano_url",
        "panoUrl",
        "url",
        "src",
        "file",
      ];
      for (const k of preferredKeys) {
        const v = data[k];
        if (typeof v === "string" && v.length > 0) return v;
      }

      // Fallback: first string-ish url in task data
      for (const v of Object.values(data)) {
        if (typeof v === "string" && v.length > 0) {
          if (
            v.startsWith("http://") ||
            v.startsWith("https://") ||
            v.startsWith("/")
          ) {
            return v;
          }
        }
      }
    } catch (e) {}
    return null;
  }

  function rewriteTextureUrlForViewer(originalUrl) {
    if (!originalUrl) return originalUrl;
    try {
      const helperBase = new URL(getHelperBaseUrl(), window.location.href);
      const u = new URL(originalUrl, window.location.href);

      // Already same-origin as helper (e.g. both on port 8000)
      if (u.origin === helperBase.origin) return u.toString();

      // Same host but different port (e.g. image is on 8080, helper is on 8000)
      // Route through nginx /ls/ to make it same-origin with the 3D viewer
      if (u.hostname === helperBase.hostname) {
        // Only proxy if it's NOT already on the helper port
        return `${helperBase.origin}/ls${u.pathname}${u.search}`;
      }
      return u.toString();
    } catch (e) {
      return originalUrl;
    }
  }

  function withCacheBust(url) {
    if (!url) return url;
    try {
      const u = new URL(url, window.location.href);
      u.searchParams.set("_hohonet_ts", String(Date.now()));
      return u.toString();
    } catch (e) {
      return url;
    }
  }

  // 生成会话 ID 以防止 iframe 缓存
  const SESSION_ID = Date.now();

  // --- 2D overlay 生命周期管理 ---
  // 修复: 在切任务/切页面时，旧的黄色角点标签(overlay badges)不会自动清理，导致残留。
  let lastTaskIdForOverlay = null;
  let lastAnnotationIdForOverlay = null;

  function getEffectiveState() {
    try {
      const store = getStore();
      const taskId = store?.task?.id ? String(store.task.id) : null;
      const annId = store?.annotationStore?.selected?.id
        ? String(store.annotationStore.selected.id)
        : null;

      // 如果 Store 还没准备好，回退到 URL
      if (!taskId) {
        const params = new URLSearchParams(window.location.search);
        const q = params.get("task");
        return { taskId: q || "unknown", annId: "unknown" };
      }
      return { taskId, annId };
    } catch (e) {
      return { taskId: "unknown", annId: "unknown" };
    }
  }

  function clearOverlay() {
    const overlay = document.getElementById(OVERLAY_ID);
    if (overlay) {
      console.log("HoHoNet: task/annotation state changed; clearing stale labels");
      overlay.remove();
    }
  }

  function tick() {
    let status = "";

    // v0.20 修复: 每次 tick 都检查是否在标注页面
    // 这样可以应对 SPA 导航和延迟加载
    if (!isLikelyLabelStudioPage()) {
      // 非 LS 页面：清理UI但继续运行（以便后续页面切换时能恢复）
      const wrapper = document.getElementById(WRAPPER_ID);
      if (wrapper) wrapper.style.display = "none";
      const panel = document.getElementById(PREVIEW_PANEL_ID);
      if (panel) panel.style.display = "none";
      return;
    }

    if (!isLikelyAnnotationPage()) {
      // 在 LS 网站内，但不是标注页面：隐藏UI
      const wrapper = document.getElementById(WRAPPER_ID);
      if (wrapper) wrapper.style.display = "none";
      const panel = document.getElementById(PREVIEW_PANEL_ID);
      if (panel) panel.style.display = "none";
      status += "Page type: not an annotation page\n";
      updateDebug(status);
      return;
    }

    // 确保wrapper可见（可能之前被隐藏了）
    const existingWrapper = document.getElementById(WRAPPER_ID);
    if (existingWrapper) existingWrapper.style.display = "block";
    const existingPanel = document.getElementById(PREVIEW_PANEL_ID);
    if (existingPanel) existingPanel.style.display = "block";

    // v0.11 修复: 延迟 store 查找直到交互，以避免 React 干扰
    // let store = getStore(); // 从 tick 中移除

    // --- URL 解析 ---
    let url = null;

    // 检测任务或标注切换
    const stateNow = getEffectiveState();
    if (
      stateNow.taskId !== lastTaskIdForOverlay ||
      stateNow.annId !== lastAnnotationIdForOverlay
    ) {
      lastTaskIdForOverlay = stateNow.taskId;
      lastAnnotationIdForOverlay = stateNow.annId;
      clearOverlay();
      resetPreviewControlPanelState("Task changed. Click Refresh 3D View again.");
    }

    const img = findMainImage();
    if (img) {
      status += "Image: found\n";
      // v0.17 修复: 添加缓存破坏参数
      url = HOHONET_VIS_3D_URL(SESSION_ID);
      if (img.naturalWidth) {
        url += `&w=${img.naturalWidth}&h=${img.naturalHeight}`;
      }

      // 如果已存在覆盖层，持续跟随图片位置（解决缩放/平移偏移）
      const overlay = document.getElementById(OVERLAY_ID);
      if (overlay) {
        const rect = positionOverlayToImage(img, overlay);
        const visible = getLabelsVisible();
        overlay.style.display = visible ? "block" : "none";
        positionOverlayBadges(overlay, rect);
      }
    } else {
      status += "Image: not found\n";
    }

    if (url) {
      status += "Target URL: ready\n";
    } else {
      status += "Target URL: missing\n";
    }

    // --- 注入 ---
    const container = findSectionContainer();
    if (!container) {
      updateDebug(status + "Container: not found");
      return;
    }

    try {
      // 隐藏原始子元素
      Array.from(container.children).forEach((child) => {
        if (child.id !== WRAPPER_ID) {
          child.style.display = "none";
        }
      });

      // 包装器
      let wrapper = document.getElementById(WRAPPER_ID);
      if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.id = WRAPPER_ID;
        container.appendChild(wrapper);
      }

      // Iframe
      let iframe = document.getElementById(IFRAME_ID);
      if (!iframe) {
        iframe = document.createElement("iframe");
        iframe.id = IFRAME_ID;
        iframe.style.cssText =
          "width: 100%; height: 400px; border: none; background: #000;";
        wrapper.appendChild(iframe);
      }

      ensurePreviewControlPanel(iframe);

      // 更新 URL
      if (url && iframe.dataset.src !== url) {
        if (
          !iframe.dataset.src ||
          (url.includes("data=") && !iframe.dataset.src.includes("data="))
        ) {
          iframe.dataset.src = url;
          iframe.src = url;
        } else if (!iframe.dataset.src) {
          iframe.dataset.src = url;
          iframe.src = url;
        }
      }

      // 按钮
      let btn = document.getElementById(BUTTON_ID);
      if (!btn) {
        btn = document.createElement("button");
        btn.id = BUTTON_ID;
        btn.innerText = "🔄 Refresh 3D View";
        btn.style.cssText =
          "margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";

        btn.onclick = function () {
          // v0.11 修复: 仅在点击时查找 store
          const store = getStore();
          if (!store) {
            alert("Cannot connect to the Label Studio store. Wait until the editor finishes loading.");
            return;
          }
          if (!store.annotationStore || !store.annotationStore.selected) {
            alert("Select an annotation first.");
            return;
          }

          const results = store.annotationStore.selected.results;
          const points = [];

          // 尺寸
          let W = 1024;
          let H = 512;
          try {
            const urlObj = new URL(iframe.src);
            const params = new URLSearchParams(urlObj.search);
            const pW = parseInt(params.get("w"));
            const pH = parseInt(params.get("h"));
            if (!isNaN(pW)) W = pW;
            if (!isNaN(pH)) H = pH;
          } catch (e) {}

          console.log("HoHoNet: parsed results:", results);

          // v0.9 修复: 彻底解包
          const clean = (obj) => {
            try {
              return JSON.parse(JSON.stringify(obj));
            } catch (e) {
              return obj;
            }
          };

          // v0.15 修复: 分离关键点和多边形
          const keypoints = [];
          results.forEach((r, idx) => {
            // v0.10 修复: 优先检查 r.area
            let source = r;
            if (r.area) source = r.area;

            // 解包
            let val = clean(source);
            if (!val) val = source.toJSON ? source.toJSON() : source;

            console.log(`HoHoNet: result ${idx} (cleaned):`, val);

            // 确定类型 (检查 r 和 val)
            const type = r.type || val.type;

            // 1. 关键点 (角点)
            // 兼容: keypointlabels, keypointregion
            if (type === "keypointlabels" || type === "keypointregion") {
              let x, y;
              if (val.x !== undefined) {
                x = val.x;
                y = val.y;
              } else if (val.value && val.value.x !== undefined) {
                x = val.value.x;
                y = val.value.y;
              }

              if (typeof x === "number" && typeof y === "number") {
                const px = (x * W) / 100;
                const py = (y * H) / 100;
                keypoints.push({ x: px, y: py, pctX: x, pctY: y });
              }
            }
          });

          // 决策: 优先使用关键点
          if (keypoints.length > 0) {
            console.log("HoHoNet: building 3D geometry from corner keypoints");
            points.push(...keypoints);
          } else {
            alert("No Corner points found. Please draw the corner keypoints first.");
            return;
          }

          console.log("HoHoNet: raw points:", points);

          points.sort((a, b) => a.x - b.x);
          const pairedDefault = [];
          const used = new Array(points.length).fill(false);
          const threshold = W * 0.05;

          for (let i = 0; i < points.length; i++) {
            if (used[i]) continue;
            let bestJ = -1;
            // 寻找最佳匹配点 (X 轴最近)
            let minDiff = Infinity;

            for (let j = i + 1; j < points.length; j++) {
              if (!used[j]) {
                const diff = Math.abs(points[j].x - points[i].x);
                if (diff < threshold && diff < minDiff) {
                  minDiff = diff;
                  bestJ = j;
                }
              }
            }
            if (bestJ !== -1) {
              used[i] = true;
              used[bestJ] = true;
              pairedDefault.push({
                x: (points[i].x + points[bestJ].x) / 2,
                y_ceiling: Math.min(points[i].y, points[bestJ].y),
                y_floor: Math.max(points[i].y, points[bestJ].y),
                originalPoints: [points[i], points[bestJ]],
              });
            }
          }

          const previewTaskKey = getPreviewOverrideTaskKey();
          const previewSignature = buildPreviewSignature(pairedDefault);
          const identityOrder = getIdentityOrder(pairedDefault.length);
          applyPreviewRuntimeFromLayout(
            previewTaskKey,
            previewSignature,
            pairedDefault,
          );
          const cacheResult = loadValidatedPreviewOrderOverride(previewTaskKey, {
            corner_count: pairedDefault.length,
            signature: previewSignature,
          });
          const storedOverride = cacheResult.record;
          let previewOrderActive = false;
          let previewOrder = identityOrder;
          let pairedForPreview = pairedDefault.slice();

          if (
            storedOverride &&
            storedOverride.signature === previewSignature &&
            storedOverride.order
          ) {
            const applied = applyPreviewOrder(pairedDefault, storedOverride.order);
            if (applied.order) {
              previewOrderActive = true;
              previewOrder = applied.order;
              pairedForPreview = applied.corners;
            }
          }

          console.log("HoHoNet: paired default:", pairedDefault);
          console.log("HoHoNet: preview order state:", {
            previewTaskKey,
            previewSignature,
            previewOrderActive,
            previewOrder,
          });
          const paired = pairedForPreview;

          console.log("HoHoNet: paired corners:", paired);

          // --- 2D 覆盖层逻辑：按当前预览顺序重绘标签 ---
          renderPreviewOverlayPairs(pairedForPreview);

          if (pairedDefault.length === 0) {
            alert(
              `Found ${points.length} points, but no vertical wall pairs could be formed. Try drawing straighter vertical lines.`,
            );
            return;
          }

          // 获取用于纹理的图像 URL
          const img = findMainImage();
          let imageUrl = img ? img.src : null;
          if (!imageUrl) {
            imageUrl = getImageUrlFromStore();
          }

          // 关键修复：不依赖 /assets/，用 nginx 的 /ls/ 同源代理来加载 Label Studio 图片
          const textureUrl = rewriteTextureUrlForViewer(imageUrl);
          const textureUrlFinal = withCacheBust(textureUrl || imageUrl);
          if (imageUrl && textureUrl && textureUrl !== imageUrl) {
            console.log(
              `HoHoNet: textureUrl rewritten via /ls proxy: ${textureUrl}`,
            );
          }
          iframe.contentWindow.postMessage(
            {
              type: "update_layout",
              corners: pairedForPreview,
              baseCorners: pairedDefault,
              width: W,
              height: H,
              imageUrl: textureUrlFinal,
              preserveOrder: true,
              previewOrderActive,
              previewOrder,
              previewSignature,
            },
            "*",
          );
        };
        wrapper.appendChild(btn);
      }

      // 切换标签按钮
      let toggleBtn = document.getElementById(TOGGLE_BTN_ID);
      if (!toggleBtn) {
        toggleBtn = document.createElement("button");
        toggleBtn.id = TOGGLE_BTN_ID;
        toggleBtn.style.cssText =
          "margin-top: 10px; margin-left: 10px; padding: 8px 16px; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";

        applyToggleBtnState(toggleBtn, getLabelsVisible());

        toggleBtn.onclick = function () {
          const overlay = document.getElementById(OVERLAY_ID);
          if (overlay) {
            const nowVisible = overlay.style.display === "none";
            setLabelsVisible(nowVisible);
            overlay.style.display = nowVisible ? "block" : "none";
            applyToggleBtnState(toggleBtn, nowVisible);
          } else {
            alert("Click Refresh 3D View first to generate labels.");
          }
        };
        wrapper.appendChild(toggleBtn);
      }
    } catch (e) {
      status += "Error: " + e.message;
    }

    updateDebug(status);
  }

  // --- 活动时间跟踪 (新功能) ---
  let activeSeconds = 0;
  let lastActivityTime = 0; // v0.21: init to 0, require real user interaction
  // 修改: 将空闲阈值降低到 15s 以获得更精确的“活动”测量
  const IDLE_THRESHOLD = 15 * 1000;
  let currentTaskId = null;
  let currentActiveTimeKey = null;
  let currentActiveTimeMetadata = null;
  const lateBindingActualByContext = new Map();

  // v0.21: cumulative seconds per active_time_key within same session.
  const taskCumulativeSeconds = new Map();
  const lastPostedSecondsByTask = new Map();
  const ACTIVE_TIME_METADATA_KEYS = [
    "taskId",
    "projectId",
    "projectName",
    "annotatorId",
    "annotationId",
    "taskIdSource",
    "projectIdSource",
    "annotationIdSource",
    "selectedAnnotationId",
    "selectedAnnotationOwnerId",
    "selectedAnnotationOwnerSource",
  ];
  const lastKnownActiveTimeMetadata = {
    taskId: null,
    projectId: null,
    projectName: null,
    annotatorId: null,
    annotationId: null,
    taskIdSource: null,
    projectIdSource: null,
    annotationIdSource: null,
    selectedAnnotationId: null,
    selectedAnnotationOwnerId: null,
    selectedAnnotationOwnerSource: null,
    updatedAt: 0,
  };

  let isPageVisible = true;
  let isWindowFocused = document.hasFocus();
  let pageHiddenTime = null;
  const PAGE_HIDDEN_THRESHOLD = 6 * 1000; // 页面被切出超过6秒后才停止计时（可调整此参数）
  let wasOnAnnotationPageForActiveTime = false;
  let annotationGateUnavailableTicks = 0;

  function resetCurrentActiveTimeSegment() {
    activeSeconds = 0;
    lastActivityTime = 0;
  }

  function clearActiveTimeTaskContext() {
    currentTaskId = null;
    currentActiveTimeKey = null;
    currentActiveTimeMetadata = null;
    wasOnAnnotationPageForActiveTime = false;
    for (const key of ACTIVE_TIME_METADATA_KEYS) {
      if (key !== "annotatorId") lastKnownActiveTimeMetadata[key] = null;
    }
    lastKnownActiveTimeMetadata.updatedAt = 0;
  }

  function hasActiveTimeSegmentToReport(
    taskId = currentTaskId,
    fragmentSeconds = activeSeconds,
  ) {
    return (
      Number(fragmentSeconds) > 0 &&
      taskId !== undefined &&
      taskId !== null &&
      String(taskId) !== "unknown" &&
      String(taskId).length > 0
    );
  }

  function isKnownActiveTimeMetadataValue(value) {
    const normalized = String(value ?? "").trim();
    return normalized.length > 0 && normalized !== "unknown";
  }

  function cacheLastKnownActiveTimeMetadata(partial = {}) {
    let changed = false;
    for (const key of ACTIVE_TIME_METADATA_KEYS) {
      if (!isKnownActiveTimeMetadataValue(partial[key])) continue;
      const normalized = String(partial[key]).trim();
      if (lastKnownActiveTimeMetadata[key] !== normalized) {
        lastKnownActiveTimeMetadata[key] = normalized;
        changed = true;
      }
    }
    if (changed) {
      lastKnownActiveTimeMetadata.updatedAt = Date.now();
    }
    return lastKnownActiveTimeMetadata;
  }

  function captureCurrentActiveTimeMetadata(preferredTaskId = null) {
    const taskIdentity = getTaskIdentity();
    const projectIdentity = getProjectIdentity();
    const annotationIdentity = getAnnotationIdentity();
    const taskId =
      preferredTaskId !== null && preferredTaskId !== undefined
        ? preferredTaskId
        : currentTaskId || taskIdentity.id;
    return {
      taskId,
      taskIdSource: taskIdentity.source,
      projectId: projectIdentity.id,
      projectIdSource: projectIdentity.source,
      projectName: getProjectName(),
      annotatorId: getAnnotatorId(),
      annotationId: annotationIdentity.id,
      annotationIdSource: annotationIdentity.source,
      serverAnnotationId: annotationIdentity.serverAnnotationId || "",
      clientAnnotationId: annotationIdentity.clientAnnotationId || "",
      selectedAnnotationId: annotationIdentity.selectedAnnotationId || "",
      selectedAnnotationOwnerId: annotationIdentity.selectedAnnotationOwnerId || "",
      selectedAnnotationOwnerSource: annotationIdentity.selectedAnnotationOwnerSource || "",
    };
  }

  function annotationMatchStatus(annotationId) {
    return isKnownActiveTimeMetadataValue(annotationId) && String(annotationId) !== "unknown_annotation"
      ? "annotation_id_present"
      : "unknown_annotation";
  }

  function buildActiveTimeKey(metadata) {
    return [
      metadata.projectId || "unknown",
      metadata.taskId || "unknown",
      metadata.annotatorId || "unknown",
      metadata.annotationId || "unknown_annotation",
    ].join("|");
  }

  function activeTimeContextKey(metadata) {
    return [
      sessionId,
      metadata.projectId || "unknown",
      metadata.taskId || "unknown",
      metadata.annotatorId || "unknown",
    ].join("|");
  }

  function isUnknownAnnotationMetadata(metadata) {
    return !metadata || metadata.annotationId === "unknown_annotation";
  }

  function noteActualAnnotationForContext(metadata) {
    if (!metadata || isUnknownAnnotationMetadata(metadata)) return "unknown_annotation";
    const contextKey = activeTimeContextKey(metadata);
    const existing = lateBindingActualByContext.get(contextKey);
    if (existing && existing !== metadata.annotationId) {
      lateBindingActualByContext.set(contextKey, "__ambiguous__");
      return "ambiguous_multiple_annotations";
    }
    if (existing === "__ambiguous__") return "ambiguous_multiple_annotations";
    lateBindingActualByContext.set(contextKey, metadata.annotationId);
    return "single_actual_annotation";
  }

  function getLateBindingStatusForSwitch(oldMetadata, nextMetadata) {
    if (!isUnknownAnnotationMetadata(oldMetadata) || isUnknownAnnotationMetadata(nextMetadata)) {
      return "";
    }
    if (activeTimeContextKey(oldMetadata) !== activeTimeContextKey(nextMetadata)) {
      return "";
    }
    return noteActualAnnotationForContext(nextMetadata);
  }

  function resolveActiveTimeMetadata(preferredTaskId = null) {
    const pageGate = resolveAnnotationPageGate();
    const live = captureCurrentActiveTimeMetadata(preferredTaskId);
    cacheLastKnownActiveTimeMetadata(live);

    const resolvedProjectId = isKnownActiveTimeMetadataValue(live.projectId)
      ? String(live.projectId).trim()
      : lastKnownActiveTimeMetadata.projectId || "unknown";

    const annotationId = isKnownActiveTimeMetadataValue(live.annotationId)
      ? String(live.annotationId).trim()
      : "unknown_annotation";
    const resolved = {
      taskId: isKnownActiveTimeMetadataValue(live.taskId)
        ? String(live.taskId).trim()
        : lastKnownActiveTimeMetadata.taskId || "unknown",
      projectId: resolvedProjectId,
      projectName: isKnownActiveTimeMetadataValue(live.projectName)
        ? String(live.projectName).trim()
        : resolvedProjectId !== "unknown" &&
            lastKnownActiveTimeMetadata.projectId === resolvedProjectId &&
            isKnownActiveTimeMetadataValue(lastKnownActiveTimeMetadata.projectName)
          ? lastKnownActiveTimeMetadata.projectName
          : "unknown",
      annotatorId: isKnownActiveTimeMetadataValue(live.annotatorId)
        ? String(live.annotatorId).trim()
        : lastKnownActiveTimeMetadata.annotatorId || "unknown",
      annotationId,
      annotationMatchStatus: annotationId === "unknown_annotation"
        ? "unknown_annotation"
        : live.serverAnnotationId ? "annotation_id_present" : "client_annotation_id_only",
      serverAnnotationId: String(live.serverAnnotationId || ""),
      clientAnnotationId: String(live.clientAnnotationId || ""),
      taskIdSource: isKnownActiveTimeMetadataValue(live.taskIdSource)
        ? String(live.taskIdSource).trim()
        : lastKnownActiveTimeMetadata.taskIdSource || "unknown",
      projectIdSource: isKnownActiveTimeMetadataValue(live.projectIdSource)
        ? String(live.projectIdSource).trim()
        : lastKnownActiveTimeMetadata.projectIdSource || "unknown",
      annotationIdSource: isKnownActiveTimeMetadataValue(live.annotationIdSource)
        ? String(live.annotationIdSource).trim()
        : lastKnownActiveTimeMetadata.annotationIdSource || "unknown",
      selectedAnnotationId: String(live.selectedAnnotationId || ""),
      selectedAnnotationOwnerId: String(live.selectedAnnotationOwnerId || ""),
      selectedAnnotationOwnerSource: String(live.selectedAnnotationOwnerSource || ""),
      lateBindingStatus: "",
      pageGate,
    };
    noteActualAnnotationForContext(resolved);
    resolved.activeTimeKey = buildActiveTimeKey(resolved);
    return resolved;
  }

  function buildActiveTimeReport(
    forceTaskId = null,
    forcedActiveSeconds = null,
    forceMetadata = null,
  ) {
    // fragment 表示“当前连续活动片段”，不是“自上次网络上报以来的增量”。
    const metadata = forceMetadata || resolveActiveTimeMetadata(forceTaskId);
    const reportTaskId = metadata.taskId;
    const currentFragment =
      forcedActiveSeconds !== null ? forcedActiveSeconds : activeSeconds;

    if (!hasActiveTimeSegmentToReport(reportTaskId, currentFragment)) {
      return null;
    }

    const previousCumulative = taskCumulativeSeconds.get(metadata.activeTimeKey) || 0;
    const reportSeconds = previousCumulative + currentFragment;
    if (reportSeconds <= 0) return null;

    return {
      reportTaskId,
      annotationId: metadata.annotationId,
      annotationMatchStatus: metadata.annotationMatchStatus,
      activeTimeKey: metadata.activeTimeKey,
      activeTimeAliasFrom: metadata.activeTimeAliasFrom || "",
      activeTimeAliasReason: metadata.activeTimeAliasReason || "",
      lateBindingStatus: metadata.lateBindingStatus || "",
      pageGate: metadata.pageGate || resolveAnnotationPageGate(),
      projectId: metadata.projectId,
      taskIdSource: metadata.taskIdSource || "unknown",
      projectIdSource: metadata.projectIdSource || "unknown",
      annotationIdSource: metadata.annotationIdSource || "unknown",
      serverAnnotationId: metadata.serverAnnotationId || "",
      clientAnnotationId: metadata.clientAnnotationId || "",
      selectedAnnotationId: metadata.selectedAnnotationId || "",
      selectedAnnotationOwnerId: metadata.selectedAnnotationOwnerId || "",
      selectedAnnotationOwnerSource: metadata.selectedAnnotationOwnerSource || "",
      projectName: metadata.projectName,
      annotatorId: metadata.annotatorId,
      currentFragment,
      reportSeconds,
      pageType:
        metadata.pageGate?.eligible || wasOnAnnotationPageForActiveTime
          ? "annotation"
          : "other",
    };
  }

  function buildActiveTimePayload(report, manualFlush) {
    return {
      task_id: report.reportTaskId,
      task_id_source: report.taskIdSource,
      annotation_id: report.annotationId,
      annotation_id_source: report.annotationIdSource,
      server_annotation_id: report.serverAnnotationId,
      client_annotation_id: report.clientAnnotationId,
      selected_annotation_id: report.selectedAnnotationId,
      selected_annotation_owner_id: report.selectedAnnotationOwnerId,
      selected_annotation_owner_source: report.selectedAnnotationOwnerSource,
      active_time_key: report.activeTimeKey,
      active_time_alias_from: report.activeTimeAliasFrom || "",
      active_time_alias_reason: report.activeTimeAliasReason || "",
      late_binding_status: report.lateBindingStatus || "",
      annotation_match_status: report.annotationMatchStatus,
      project_id: report.projectId,
      project_id_source: report.projectIdSource,
      project_name: report.projectName,
      annotator_id: report.annotatorId,
      session_id: sessionId,
      active_seconds: report.reportSeconds,
      active_seconds_fragment: report.currentFragment,
      timestamp: Date.now(),
      is_manual_flush: manualFlush,
      script_version: SCRIPT_VERSION,
      page_type: report.pageType,
      location_path: report.pageGate?.locationPath || "",
      location_search: report.pageGate?.sanitizedLocationSearch || "",
      page_gate_captured_at: report.pageGate?.capturedAt || null,
      page_gate_eligible: Boolean(report.pageGate?.eligible),
      page_gate_reason: report.pageGate?.reason || "unknown",
      page_gate_sources: (report.pageGate?.sources || []).join(";"),
      task_route_present: Boolean(report.pageGate?.routeTaskId),
      resolved_route_task_id: report.pageGate?.routeTaskId || "",
      resolved_dom_task_id: report.pageGate?.domTaskId || "",
      resolved_store_task_id: report.pageGate?.storeTaskId || "",
      store_task_ids: (report.pageGate?.storeTaskIds || []).join(";"),
      store_task_match_status: report.pageGate?.storeTaskMatchStatus || "unavailable",
      store_mismatch_present: Boolean(report.pageGate?.storeMismatchPresent),
      labeling_root_present: Boolean(report.pageGate?.labelingRootPresent),
      annotation_editor_dom_present: Boolean(report.pageGate?.editorDomPresent),
      annotation_main_view_dom_present: Boolean(report.pageGate?.mainViewDomPresent),
      ...getForeignRecruitmentMetadataForPayload(),
    };
  }

  function loadActiveTimeRetryQueue() {
    try {
      const raw = window.localStorage.getItem(ACTIVE_TIME_RETRY_QUEUE_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function saveActiveTimeRetryQueue(queue) {
    try {
      window.localStorage.setItem(ACTIVE_TIME_RETRY_QUEUE_KEY, JSON.stringify(queue));
    } catch (e) {}
  }

  function activeTimeQueueKey(payload) {
    return `${payload.session_id || sessionId}|${payload.active_time_key}`;
  }

  function pruneActiveTimeRetryQueue(queue) {
    const now = Date.now();
    for (const key of Object.keys(queue)) {
      const item = queue[key] || {};
      const updatedAt = Number(item.updated_at || item.created_at || 0);
      if (updatedAt && now - updatedAt > ACTIVE_TIME_RETRY_TTL_MS) {
        item.retry_status = "expired_orphaned";
        queue[key] = item;
      }
    }
    const liveEntries = Object.entries(queue)
      .filter(([, item]) => item.retry_status !== "expired_orphaned")
      .sort((a, b) => Number(b[1].updated_at || 0) - Number(a[1].updated_at || 0));
    const keep = new Set(liveEntries.slice(0, ACTIVE_TIME_RETRY_MAX_ITEMS).map(([key]) => key));
    for (const [key, item] of Object.entries(queue)) {
      if (item.retry_status !== "expired_orphaned" && !keep.has(key)) {
        delete queue[key];
      }
    }
    return queue;
  }

  function upsertActiveTimeRetryPayload(payload) {
    const queue = pruneActiveTimeRetryQueue(loadActiveTimeRetryQueue());
    const key = activeTimeQueueKey(payload);
    const existing = queue[key];
    const now = Date.now();
    if (
      !existing ||
      existing.retry_status === "expired_orphaned" ||
      Number(payload.active_seconds || 0) >= Number(existing.payload?.active_seconds || 0)
    ) {
      queue[key] = {
        payload,
        created_at: existing?.retry_status === "expired_orphaned" ? now : existing?.created_at || now,
        updated_at: now,
        retry_status: "pending",
      };
    }
    saveActiveTimeRetryQueue(queue);
  }

  function deleteActiveTimeRetryPayload(payload) {
    const queue = loadActiveTimeRetryQueue();
    delete queue[activeTimeQueueKey(payload)];
    saveActiveTimeRetryQueue(queue);
  }

  function deleteActiveTimeRetryKey(activeTimeKey) {
    const queue = loadActiveTimeRetryQueue();
    delete queue[`${sessionId}|${activeTimeKey}`];
    saveActiveTimeRetryQueue(queue);
  }

  async function retryQueuedActiveTime(logPrefix = "RETRY") {
    const tokenNow = getLogToken();
    if (!tokenNow) return;
    const queue = pruneActiveTimeRetryQueue(loadActiveTimeRetryQueue());
    const currentAnnotator = getAnnotatorId();
    for (const [key, item] of Object.entries(queue)) {
      if (!item || item.retry_status === "expired_orphaned") continue;
      const payload = item.payload || {};
      if (String(payload.annotator_id || "") !== String(currentAnnotator || "")) continue;
      try {
        const response = await fetch(HOHONET_LOG_TIME_URL(), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-HOHONET-TOKEN": tokenNow,
          },
          body: JSON.stringify(payload),
        });
        if (response.ok) {
          delete queue[key];
        }
      } catch (e) {
        console.warn(`[${logPrefix}] retry failed:`, e);
      }
    }
    saveActiveTimeRetryQueue(queue);
  }

  function handleActiveTimeKeyChange(nextMetadata) {
    if (!nextMetadata || nextMetadata.taskId === "unknown") return;
    if (
      currentActiveTimeKey &&
      nextMetadata.activeTimeKey !== currentActiveTimeKey &&
      (activeSeconds > 0 || taskCumulativeSeconds.has(currentActiveTimeKey))
    ) {
      const lateBindingStatus = getLateBindingStatusForSwitch(currentActiveTimeMetadata, nextMetadata);
      let reportMetadata = currentActiveTimeMetadata;
      let secondsForReport = activeSeconds;
      const unknownCumulativeSeconds = (taskCumulativeSeconds.get(currentActiveTimeKey) || 0) + activeSeconds;
      if (lateBindingStatus === "single_actual_annotation" && nextMetadata.serverAnnotationId) {
        reportMetadata = {
          ...nextMetadata,
          activeTimeAliasFrom: currentActiveTimeKey,
          activeTimeAliasReason: "unknown_annotation_late_bound",
          lateBindingStatus: "single_actual_annotation",
        };
        secondsForReport = unknownCumulativeSeconds;
        taskCumulativeSeconds.delete(currentActiveTimeKey);
        deleteActiveTimeRetryKey(currentActiveTimeKey);
      } else if (lateBindingStatus === "single_actual_annotation") {
        reportMetadata = {
          ...currentActiveTimeMetadata,
          lateBindingStatus: "unknown_annotation_unassigned",
        };
      } else if (lateBindingStatus === "ambiguous_multiple_annotations") {
        reportMetadata = {
          ...currentActiveTimeMetadata,
          lateBindingStatus: "unknown_annotation_ambiguous",
        };
      }
      const report = buildActiveTimeReport(null, secondsForReport, reportMetadata);
      if (report) {
        taskCumulativeSeconds.set(report.activeTimeKey, report.reportSeconds);
        void postActiveTimeReport(report, {
          manualFlush: true,
          logPrefix: "ACTIVE_TIME_KEY_SWITCH",
        });
      }
      resetCurrentActiveTimeSegment();
    }
    currentActiveTimeKey = nextMetadata.activeTimeKey;
    currentActiveTimeMetadata = nextMetadata;
    currentTaskId = nextMetadata.taskId;
    updateActiveTimePanels(nextMetadata, lastActiveTimeUploadStatus);
  }

  async function postActiveTimeReport(
    report,
    { manualFlush = false, keepalive = false, logPrefix = "LOG" } = {},
  ) {
    if (!report) return null;

    const lastPostedSeconds = lastPostedSecondsByTask.get(report.activeTimeKey) || 0;
    if (report.reportSeconds <= lastPostedSeconds) {
      return null;
    }

    const tokenNow = getLogToken();
    const payload = buildActiveTimePayload(report, manualFlush);
    upsertActiveTimeRetryPayload(payload);
    if (!tokenNow) {
      updateActiveTimePanels(report, "missing_token");
      console.warn(
        `[${logPrefix}] Missing HOHONET_LOG_TOKEN. Set localStorage.HOHONET_LOG_TOKEN before annotation. Active-time upload may be rejected with 403.`,
      );
    }
    try {
      const response = await fetch(HOHONET_LOG_TIME_URL(), {
        method: "POST",
        keepalive,
        headers: {
          "Content-Type": "application/json",
          ...(tokenNow ? { "X-HOHONET-TOKEN": tokenNow } : {}),
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        updateActiveTimePanels(report, response.status === 403 ? "forbidden_403" : `http_${response.status}`);
        console.warn(
          `[${logPrefix}] upload error: ${response.status} ${response.statusText}`,
        );
        if (response.status === 403) {
          console.warn(
            `[${logPrefix}] 403 Forbidden. helperBase=${getHelperBaseUrl()} token=${maskToken(tokenNow)} (len=${String(tokenNow || "").length})`,
          );
        }
      } else {
        lastPostedSecondsByTask.set(report.activeTimeKey, report.reportSeconds);
        deleteActiveTimeRetryPayload(payload);
        updateActiveTimePanels(report, "ok");
      }
      if (response.ok && manualFlush) {
          console.log(
            `[${logPrefix}] uploaded ${report.reportSeconds}s active time for task ${report.reportTaskId}`,
          );
      }
      return response;
    } catch (e) {
      console.warn(`[${logPrefix}] upload failed:`, e);
      updateActiveTimePanels(report, "fetch_failed");
      return null;
    }
  }

  function closeActiveTimeSegment(
    reason = "PAGE_EXIT",
    { keepalive = false } = {},
  ) {
    const report = buildActiveTimeReport(currentTaskId || getTaskId(), activeSeconds, currentActiveTimeMetadata);
    resetCurrentActiveTimeSegment();
    clearActiveTimeTaskContext();
    annotationGateUnavailableTicks = 0;

    if (!report) return;

    taskCumulativeSeconds.set(report.activeTimeKey, report.reportSeconds);
    void postActiveTimeReport(report, {
      manualFlush: true,
      keepalive,
      logPrefix: reason,
    });
  }

  // 检测页面可见性（仅在隐藏超过阈值时停止计时，允许短暂切换）
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      // 页面被隐藏，记录隐藏开始时间
      pageHiddenTime = Date.now();
      isPageVisible = false;
      if (wasOnAnnotationPageForActiveTime && activeSeconds > 0) {
        closeActiveTimeSegment("VISIBILITY_HIDDEN", { keepalive: true });
      }
    } else {
      // 页面重新显示
      if (pageHiddenTime !== null) {
        const hiddenDuration = Date.now() - pageHiddenTime;
        if (hiddenDuration >= PAGE_HIDDEN_THRESHOLD) {
          // v0.21: 隐藏时长超过阈值 => lastActivityTime=0
          // 要求用户下一次真实交互才重新开始计时
          // (旧版设 Date.now() 会导致切回后 0-15s 被误计)
          lastActivityTime = 0;
        }
        // 否则继续计时，不重置（允许短暂切换）
      }
      pageHiddenTime = null;
      isPageVisible = true;
    }
  });

  // 监听用户活动（只在页面可见时更新）
  function isActiveTimeCountingPage(pageGate = resolveAnnotationPageGate()) {
    return isPageVisible && isWindowFocused && pageGate.eligible;
  }

  function shouldFlushActiveTimeOnCountingStop(pageGate = resolveAnnotationPageGate()) {
    return !isPageVisible || !pageGate.eligible;
  }

  ["mousemove", "keydown", "click", "scroll", "wheel"].forEach((evt) => {
    window.addEventListener(
      evt,
      () => {
        if (isActiveTimeCountingPage()) {
          lastActivityTime = Date.now();
        }
      },
      true,
    );
  });

  // 累积活动时间的计时器
  // v0.21 修复: 仅在「页面可见 + 标注任务页面 + 有近期交互」时累积
  setInterval(() => {
    const pageGate = resolveAnnotationPageGate();
    const onCountingPage = isActiveTimeCountingPage(pageGate);
    if (onCountingPage) {
      annotationGateUnavailableTicks = 0;
      handleActiveTimeKeyChange(resolveActiveTimeMetadata(pageGate.routeTaskId));
    } else {
      updateActiveTimePanels(null, lastActiveTimeUploadStatus, pageGate);
    }
    if (!onCountingPage) {
      const transientEditorState = pageGate.routeTaskId && [
        "labeling_mode_not_ready",
        "annotation_editor_not_ready",
        "annotation_main_view_not_ready",
        "dom_task_identity_not_ready",
      ].includes(pageGate.reason);
      annotationGateUnavailableTicks = transientEditorState
        ? annotationGateUnavailableTicks + 1
        : 2;
      const shouldFlush = shouldFlushActiveTimeOnCountingStop(pageGate);
      if (shouldFlush && wasOnAnnotationPageForActiveTime && activeSeconds > 0 && annotationGateUnavailableTicks >= 2) {
        closeActiveTimeSegment("LEAVE_ANNOTATION_PAGE");
      }
      lastActivityTime = 0;
      if (shouldFlush && annotationGateUnavailableTicks >= 2) {
        wasOnAnnotationPageForActiveTime = false;
      }
    }

    if (
      onCountingPage &&
      lastActivityTime > 0 &&
      Date.now() - lastActivityTime < IDLE_THRESHOLD
    ) {
      activeSeconds += 1;
      wasOnAnnotationPageForActiveTime = true;
    }

    // 更新 UI
    const totalForTask =
      onCountingPage && currentActiveTimeKey && taskCumulativeSeconds.has(currentActiveTimeKey)
        ? taskCumulativeSeconds.get(currentActiveTimeKey) + activeSeconds
        : onCountingPage ? activeSeconds : 0;
    if (isDebugPanelEnabled()) {
      const debugPanel = document.getElementById(DEBUG_ID);
      if (debugPanel) {
        debugPanel.innerText = `Active time: ${totalForTask}s (current segment ${activeSeconds}s) | updated ${new Date().toLocaleTimeString()}`;
      }
    }
  }, 1000);

  // 尝试从 URL 或 UI 提取任务 ID
  function getTaskId() {
    return getTaskIdentity().id;
  }

  // 尝试从 URL 提取项目 ID
  function getProjectId() {
    return getProjectIdentity().id;
  }

  // 尝试提取项目名称
  function getProjectName() {
    // 1. 尝试 Store (如果可用，最可靠)
    const store = getStore();
    if (store && store.project && store.project.title) {
      return store.project.title;
    }
    // 2. DOM 回退 (面包屑)
    // 查找类似 /projects/123 的链接
    const crumbs = Array.from(
      document.querySelectorAll("a[href*='/projects/']"),
    );
    const projectLink = crumbs.find((a) =>
      a.getAttribute("href").match(/\/projects\/\d+$/),
    );
    if (projectLink && projectLink.innerText) return projectLink.innerText;

    return "unknown";
  }

  // 尝试从 Label Studio 提取标注者/用户 ID
  function getAnnotatorId() {
    try {
      const store = getStore();
      const candidates = [
        store && store.user && store.user.id,
        store && store.currentUser && store.currentUser.id,
        store &&
          store.authStore &&
          store.authStore.user &&
          store.authStore.user.id,
        store &&
          store.userStore &&
          store.userStore.currentUser &&
          store.userStore.currentUser.id,
      ];
      for (const c of candidates) {
        if (c !== undefined && c !== null && String(c).length > 0) {
          return String(c);
        }
      }
    } catch (e) {}

    // 回退 (尽力而为)
    try {
      if (
        window.LabelStudio &&
        window.LabelStudio.user &&
        window.LabelStudio.user.id
      ) {
        return String(window.LabelStudio.user.id);
      }
    } catch (e) {}

    return "unknown";
  }

  // 【关键修复】立即上报（flush）当前任务的累积时间
  // v0.21: 支持累积秒数 (taskCumulativeSeconds + 当前片段)
  function isPreviewOrderMessage(data) {
    return (
      data &&
      typeof data === "object" &&
      [
        "hohonet_preview_order_state",
        "hohonet_preview_order_save",
        "hohonet_preview_order_delete_saved",
        "hohonet_preview_order_clear",
      ].includes(data.type)
    );
  }

  window.addEventListener("message", (event) => {
    const data = event.data;
    if (!isPreviewOrderMessage(data)) return;

    const iframe = document.getElementById(IFRAME_ID);
    if (!iframe || !iframe.contentWindow) return;

    if (data.type === "hohonet_preview_order_state") {
      handlePreviewOrderStateMessage(data);
      return;
    }

    if (data.type === "hohonet_preview_order_save") {
      handlePreviewOrderSaveMessage(iframe, data);
      return;
    }

    if (data.type === "hohonet_preview_order_delete_saved") {
      handlePreviewOrderDeleteMessage(iframe, "delete_saved");
      return;
    }

    if (data.type === "hohonet_preview_order_clear") {
      // Backward-compatible alias kept for older iframe builds.
      handlePreviewOrderDeleteMessage(iframe, "clear");
    }
  });


  window.addEventListener("blur", () => {
    isWindowFocused = false;
    // Window blur can abort fetches in some browsers. Pause counting here and
    // keep the current segment for the next successful in-page upload.
    lastActivityTime = 0;
  });

  window.addEventListener("focus", () => {
    isWindowFocused = document.hasFocus();
    lastActivityTime = 0;
    void retryQueuedActiveTime("FOCUS_RETRY");
  });

  window.addEventListener("pagehide", () => {
    closeActiveTimeSegment("PAGEHIDE", { keepalive: true });
  });

  async function flushActiveTime(
    forceTaskId = null,
    forcedActiveSeconds = null,
  ) {
    const report = buildActiveTimeReport(forceTaskId, forcedActiveSeconds);
    if (!report) {
      return;
    }

    taskCumulativeSeconds.set(report.activeTimeKey, report.reportSeconds);
    await postActiveTimeReport(report, {
      manualFlush: true,
      logPrefix: "FLUSH",
    });
  }

  // 会话 ID (每个标签页) 用于区分并发客户端
  const SESSION_STORAGE_KEY = "hohonet_ls_session_id";
  const sessionId = (() => {
    try {
      let sid = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!sid) {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
          sid = window.crypto.randomUUID();
        } else {
          sid = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        }
        window.sessionStorage.setItem(SESSION_STORAGE_KEY, sid);
      }
      return sid;
    } catch (e) {
      return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }
  })();

  // 【独立的任务切换检测器】每秒检测一次任务ID变化，立即上报
  // 这是一个独立的机制，不依赖30秒周期，保证任务切换时立即上报
  setInterval(() => {
    const pageGate = resolveAnnotationPageGate();
    if (!isActiveTimeCountingPage(pageGate)) {
      return;
    }

    const taskId = pageGate.routeTaskId;

    if (taskId === "unknown") {
      return;
    }

    handleActiveTimeKeyChange(resolveActiveTimeMetadata(taskId));

    cacheLastKnownActiveTimeMetadata(captureCurrentActiveTimeMetadata(taskId));

    // 检测到任务切换：立即flush前一个任务
    if (
      currentTaskId !== undefined &&
      currentTaskId !== null &&
      taskId !== currentTaskId &&
      activeSeconds > 0
    ) {
      const secondsToReport = activeSeconds;
      const cumulativeTotal =
        (taskCumulativeSeconds.get(currentTaskId) || 0) + secondsToReport;
      console.log(
        `[TASK_SWITCH] ${currentTaskId} -> ${taskId}，上报片段${secondsToReport}s (累积${cumulativeTotal}s)`,
      );
      flushActiveTime(currentTaskId, secondsToReport); // 传入当前片段值，flush内部会加上累积
      activeSeconds = 0;
      lastActivityTime = 0; // v0.21: 切换后需要新交互才开始计时
    }

    // 初始化或更新任务ID
    if (currentTaskId === null && taskId !== "unknown") {
      console.log(`[TASK_INIT] initialized task ID: ${taskId}`);
    }
    currentTaskId = taskId;
  }, 1000); // 每秒检测一次，保证任务切换时立即响应

  // 每 30 秒发送一次日志 (从 10 秒修改以减少流量)
  setInterval(() => {
    // 只在“标注页面”尝试记日志，避免在项目列表/首页等页面误计时/误上报。
    const pageGate = resolveAnnotationPageGate();
    if (!isActiveTimeCountingPage(pageGate)) {
      return;
    }

    const taskId = pageGate.routeTaskId;
    const projectId = getProjectId();

    // 配置:
    // - ENABLE_LOGGING: 总开关。为 false 时，脚本不会发送日志。
    //   当你想开始记录时 (例如正式标注开始时) 设置为 true。
    // - TARGET_PROJECTS: 当 ENABLE_LOGGING === true 时:
    //     [] (空) => 记录所有项目
    //     ['15','28'] => 仅记录这些项目 ID
    // 示例:
    //   const ENABLE_LOGGING = false;
    //   const TARGET_PROJECTS = ['15', '28'];
    const ENABLE_LOGGING = true; // 开启日志记录
    const TARGET_PROJECTS = [];

    if (!ENABLE_LOGGING) {
      return; // 全局禁用日志
    }

    if (TARGET_PROJECTS.length > 0 && !TARGET_PROJECTS.includes(projectId)) {
      return; // 如果不在目标项目中，跳过日志记录
    }

    void retryQueuedActiveTime("PERIODIC_RETRY");

    // 周期性上报当前任务的累积时间
    // v0.21: active_seconds 改为累积值 (之前片段 + 当前片段)
    if (activeSeconds > 0 && taskId !== "unknown") {
      const report = buildActiveTimeReport(taskId, activeSeconds);
      if (!report) return;
      void postActiveTimeReport(report, {
        manualFlush: false,
        logPrefix: "LOG",
      });
    }
  }, 30000);

  setInterval(tick, 1000);

  // v0.20 新增: 监听 DOM 变化，以便在 SPA 导航时重新激活
  // 当 Label Studio 切换任务/页面时，强制触发一次 tick
  const observer = new MutationObserver((mutations) => {
    // 检测到重要的 DOM 变化时，延迟执行 tick 让 DOM 稳定
    for (const mutation of mutations) {
      if (mutation.addedNodes.length > 0) {
        // 检查是否添加了标注相关的节点
        for (const node of mutation.addedNodes) {
          if (node.nodeType === 1) {
            // Element node
            if (
              node.classList &&
              (node.classList.contains("lsf-main-view") ||
                node.classList.contains("ls-main-view") ||
                (node.querySelector && node.querySelector('img[src*="pano"]')))
            ) {
              console.log("HoHoNet: page change detected; reactivating");
              setTimeout(tick, 500);
              return;
            }
          }
        }
      }
    }
  });

  // 监听整个 body 的子树变化
  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  window.addEventListener("resize", () => {
    const panel = document.getElementById(PREVIEW_PANEL_ID);
    if (!panel || panel.style.display === "none") return;
    const rect = panel.getBoundingClientRect();
    applyPreviewPanelPosition(rect.left, rect.top, false);
  });

  // 提交前元标签合规拦截（best-effort）：阻止空选/互斥冲突进入后端。
  installMetaSubmitGuard();

  // 监听 URL 变化（用于 SPA 导航）
  let lastUrl = location.href;
  setInterval(() => {
    const currentUrl = location.href;
    if (currentUrl !== lastUrl) {
      console.log("HoHoNet: URL changed; reactivating");
      lastUrl = currentUrl;
      // 清理可能残留的状态
      lastTaskIdForOverlay = null;
      lastAnnotationIdForOverlay = null;
      clearOverlay();
      resetPreviewControlPanelState("URL changed. Click Refresh 3D View again.");
      // 延迟执行以确保新页面DOM已加载
      setTimeout(tick, 500);
    }
  }, 1000);
})();
