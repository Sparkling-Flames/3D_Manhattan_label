// ==UserScript==
// @name         HOHONET Manhattan LS Sandbox Panel Timed
// @namespace    hohonet-dev-only
// @version      0.1.0
// @description  dev-only sandbox-only read-only Manhattan panel; timed variant with sandbox-excluded active_time telemetry.
// @match        http://175.178.71.217:8080/*
// @match        https://175.178.71.217:8080/*
// @grant        none
// ==/UserScript==

/*
 * HOHONET Manhattan LS Sandbox Panel Timed
 *
 * dev-only
 * sandbox-only
 * expert/developer tester only
 * not official userscript
 * not worker-facing
 * no annotation writeback
 * no submit
 * no routing
 * no formal g_t
 * no P1/C1/C2/T1/V1 artifact
 *
 * This timed variant may POST sandbox telemetry to /log_time. Every payload
 * is tagged for exclusion from primary active_time and thesis evidence.
 */

(function () {
  "use strict";

  if (window.top !== window.self) {
    return;
  }

  const WINDOW_GUARD = "__HOHONET_M8_SANDBOX_PANEL_ACTIVE__";
  if (window[WINDOW_GUARD]) {
    return;
  }
  window[WINDOW_GUARD] = { script_variant: "timed" };

  const PANEL_ID = "hohonet-manhattan-sandbox-panel";
  const PANEL_VERSION = "m8-dev-only-timed-0.1.0";
  const OFFICIAL_IFRAME_ID = "hohonet-iframe";
  const OFFICIAL_WRAPPER_ID = "hohonet-wrapper";
  const OFFICIAL_BUTTON_ID = "hohonet-refresh-btn";
  const DEFAULT_WIDTH = 1024;
  const DEFAULT_HEIGHT = 512;
  const START_TIME_MS = Date.now();
  const HEARTBEAT_INTERVAL_MS = 15000;
  const SESSION_STORAGE_KEY = "hohonet_m8_sandbox_session_id";
  let lastTelemetryMs = START_TIME_MS;
  const telemetryState = {
    status: "not_sent",
    lastEvent: "none",
    lastHttpStatus: "none",
    lastError: "none",
  };
  const GUARDRAILS = [
    "dev-only sandbox-only panel",
    "expert/developer tester only",
    "not official userscript",
    "not worker-facing",
    "no annotation writeback",
    "no submit",
    "no routing",
    "no formal g_t",
    "no P1/C1/C2/T1/V1 artifact",
    "no correctness label",
    "no worker tier",
    "no snap coordinates",
    "no adjustment vector",
    "no auto-correction",
    "timed variant: sandbox telemetry only",
  ];

  function text(value) {
    return document.createTextNode(String(value));
  }

  function makeRow(label, value) {
    const row = document.createElement("div");
    row.className = "hohonet-m8-row";
    const key = document.createElement("span");
    key.className = "hohonet-m8-key";
    key.appendChild(text(label));
    const val = document.createElement("span");
    val.className = "hohonet-m8-value";
    val.appendChild(text(value));
    row.appendChild(key);
    row.appendChild(val);
    return row;
  }

  function makeMutableRow(label, value, id) {
    const row = makeRow(label, value);
    const val = row.querySelector(".hohonet-m8-value");
    if (val) val.id = id;
    return row;
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = String(value);
  }

  function numericAttr(element, names) {
    for (const name of names) {
      const raw = element.getAttribute(name);
      if (raw === null || raw === "") {
        continue;
      }
      const value = Number(raw);
      if (Number.isFinite(value)) {
        return value;
      }
    }
    return null;
  }

  function getHelperBaseUrl() {
    try {
      return (
        window.localStorage.getItem("HOHONET_HELPER_BASE_URL") ||
        "http://175.178.71.217:8000"
      );
    } catch (e) {
      return "http://175.178.71.217:8000";
    }
  }

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

  function getLogToken() {
    try {
      return window.localStorage.getItem("HOHONET_LOG_TOKEN") || "";
    } catch (e) {
      return "";
    }
  }

  function logTimeUrl() {
    return `${getHelperBaseUrl()}/log_time`;
  }

  const sessionId = (() => {
    try {
      let sid = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!sid) {
        sid = `m8-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
        window.sessionStorage.setItem(SESSION_STORAGE_KEY, sid);
      }
      return sid;
    } catch (e) {
      return `m8-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    }
  })();

  function getStore() {
    if (
      window.LabelStudio &&
      window.LabelStudio.instances &&
      window.LabelStudio.instances.length > 0
    ) {
      return window.LabelStudio.instances[0].store;
    }
    if (window.H) return window.H;
    const roots = [
      document.querySelector(".ls-room"),
      document.querySelector("#label-studio"),
      document.querySelector(".lsf-main-view"),
      document.querySelector(".ls-main-view"),
      document.body,
    ].filter(Boolean);
    const scoped = Array.from(
      document.querySelectorAll(
        "#label-studio, .ls-room, .lsf-main-view, .ls-main-view, [class*='lsf'], [class*='label']",
      ),
    );
    for (const root of roots.concat(scoped)) {
      for (const key in root) {
        if (!key.startsWith("__reactFiber") && !key.startsWith("__reactProps")) continue;
        let fiber = root[key];
        while (fiber) {
          if (fiber.stateNode?.props?.store) return fiber.stateNode.props.store;
          if (fiber.memoizedProps?.store) return fiber.memoizedProps.store;
          if (fiber.pendingProps?.store) return fiber.pendingProps.store;
          fiber = fiber.return;
        }
      }
    }
    return null;
  }

  function knownText(value) {
    if (value === undefined || value === null) return "unknown";
    const textValue = String(value).trim();
    return textValue || "unknown";
  }

  function getTaskId() {
    try {
      const storeTaskId = getStore()?.task?.id;
      if (storeTaskId !== undefined && storeTaskId !== null) {
        return knownText(storeTaskId);
      }
      const params = new URLSearchParams(window.location.search);
      const queryTaskId = params.get("task") || params.get("task_id");
      if (queryTaskId) return knownText(queryTaskId);
      const match = window.location.pathname.match(/\/tasks\/(\d+)/);
      if (match) return match[1];
    } catch (e) {}
    return "unknown";
  }

  function getProjectId() {
    try {
      const store = getStore();
      const candidates = [
        store?.project?.id,
        store?.task?.project,
        store?.task?.projectId,
        store?.task?.data?.project_id,
      ];
      for (const candidate of candidates) {
        if (candidate !== undefined && candidate !== null && String(candidate).trim()) {
          return knownText(candidate);
        }
      }
      const match = window.location.pathname.match(/\/projects\/(\d+)/);
      if (match) return match[1];
    } catch (e) {}
    return "unknown";
  }

  function getProjectName() {
    try {
      const store = getStore();
      const candidates = [
        store?.project?.title,
        store?.project?.name,
        store?.task?.data?.project_name,
      ];
      for (const candidate of candidates) {
        if (candidate !== undefined && candidate !== null && String(candidate).trim()) {
          return knownText(candidate);
        }
      }
      const crumbs = Array.from(document.querySelectorAll("a, span, div"))
        .map((node) => node.textContent?.trim())
        .filter(Boolean);
      const projectsIndex = crumbs.findIndex((value) => value === "Projects");
      if (projectsIndex >= 0 && crumbs[projectsIndex + 1]) {
        return knownText(crumbs[projectsIndex + 1]);
      }
      if (document.title) return knownText(document.title);
    } catch (e) {}
    return "unknown";
  }

  function getAnnotatorId() {
    try {
      const store = getStore();
      const candidates = [
        store?.user?.id,
        store?.user?.pk,
        store?.currentUser?.id,
        store?.task?.data?.annotator_id,
      ];
      for (const candidate of candidates) {
        if (candidate !== undefined && candidate !== null && String(candidate).trim()) {
          return knownText(candidate);
        }
      }
      const profileText = document.querySelector("[data-testid*='user'], [class*='user']")?.textContent;
      if (profileText) return knownText(profileText);
    } catch (e) {}
    return "unknown";
  }

  function getPageType() {
    return /\/labeling\/?/.test(window.location.pathname) ||
      Boolean(document.querySelector(".lsf-main-view, .ls-main-view"))
      ? "annotation"
      : "other";
  }

  function toArrayFromMaybeObservable(value) {
    try {
      if (!value) return [];
      if (Array.isArray(value)) return value;
      if (typeof value.toJSON === "function") {
        const json = value.toJSON();
        if (Array.isArray(json)) return json;
      }
      if (typeof value[Symbol.iterator] === "function") {
        return Array.from(value);
      }
      if (typeof value.forEach === "function") {
        const out = [];
        value.forEach((item) => out.push(item));
        return out;
      }
    } catch (e) {}
    return [];
  }

  function collectSelectedResults(store) {
    const out = [];
    try {
      const selected = store?.annotationStore?.selected;
      if (!selected) return out;
      if (typeof selected.serializeCompletion === "function") {
        const serialized = selected.serializeCompletion();
        out.push(...toArrayFromMaybeObservable(serialized?.result));
      }
      if (typeof selected.toJSON === "function") {
        const json = selected.toJSON();
        out.push(...toArrayFromMaybeObservable(json?.result || json?.results));
      }
      out.push(...toArrayFromMaybeObservable(selected?.results));
    } catch (e) {}
    return out;
  }

  function cleanResult(value) {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (e) {
      return value;
    }
  }

  function readPercentPoint(result) {
    const source = result?.area || result;
    const cleaned = cleanResult(source);
    const type = result?.type || cleaned?.type;
    if (type !== "keypointlabels" && type !== "keypointregion") {
      return null;
    }
    const candidates = [cleaned?.value, cleaned, result?.value, result];
    for (const candidate of candidates) {
      const x = candidate?.x;
      const y = candidate?.y;
      if (typeof x === "number" && typeof y === "number") {
        return { pctX: x, pctY: y };
      }
    }
    return null;
  }

  function extractKeypointsFromStore(store, width, height) {
    const results = collectSelectedResults(store);
    const keypoints = [];
    for (const result of results) {
      const point = readPercentPoint(result);
      if (!point) continue;
      keypoints.push({
        x: (point.pctX * width) / 100,
        y: (point.pctY * height) / 100,
        pctX: point.pctX,
        pctY: point.pctY,
        source: "label-studio-store",
      });
    }
    return { keypoints, result_count: results.length };
  }

  function getImageUrlFromStore() {
    try {
      const data = getStore()?.task?.data;
      if (!data || typeof data !== "object") return null;
      for (const key of ["image", "img", "pano", "pano_url", "panoUrl", "url", "src", "file"]) {
        const value = data[key];
        if (typeof value === "string" && value) return value;
      }
    } catch (e) {}
    return null;
  }

  function findMainImage() {
    const mainView =
      document.querySelector(".lsf-main-view") ||
      document.querySelector(".ls-main-view") ||
      document;
    const images = Array.from(mainView.querySelectorAll("img")).filter(
      (img) => img.naturalWidth > 200 || img.width > 200,
    );
    if (!images.length) return null;
    return images.reduce((a, b) =>
      (a.naturalWidth || a.width || 0) * (a.naturalHeight || a.height || 0) >
      (b.naturalWidth || b.width || 0) * (b.naturalHeight || b.height || 0)
        ? a
        : b,
    );
  }

  function rewriteTextureUrlForViewer(originalUrl) {
    if (!originalUrl) return originalUrl;
    try {
      const helperBase = new URL(getHelperBaseUrl(), window.location.href);
      const url = new URL(originalUrl, window.location.href);
      if (url.origin === helperBase.origin) return url.toString();
      if (url.hostname === helperBase.hostname) {
        return `${helperBase.origin}/ls${url.pathname}${url.search}`;
      }
      return url.toString();
    } catch (e) {
      return originalUrl;
    }
  }

  function withCacheBust(url) {
    if (!url) return url;
    try {
      const parsed = new URL(url, window.location.href);
      parsed.searchParams.set("_hohonet_ts", String(Date.now()));
      return parsed.toString();
    } catch (e) {
      return url;
    }
  }

  function buildPreviewPairs(points, width) {
    const sorted = points.slice().sort((a, b) => a.x - b.x);
    const used = new Array(sorted.length).fill(false);
    const threshold = width * 0.05;
    const pairs = [];
    for (let i = 0; i < sorted.length; i += 1) {
      if (used[i]) continue;
      let bestJ = -1;
      let minDiff = Infinity;
      for (let j = i + 1; j < sorted.length; j += 1) {
        if (used[j]) continue;
        const diff = Math.abs(sorted[j].x - sorted[i].x);
        if (diff < threshold && diff < minDiff) {
          minDiff = diff;
          bestJ = j;
        }
      }
      if (bestJ !== -1) {
        used[i] = true;
        used[bestJ] = true;
        pairs.push({
          x: (sorted[i].x + sorted[bestJ].x) / 2,
          y_ceiling: Math.min(sorted[i].y, sorted[bestJ].y),
          y_floor: Math.max(sorted[i].y, sorted[bestJ].y),
        });
      }
    }
    return pairs;
  }

  function normalizePreviewUrl(rawUrl) {
    if (!rawUrl) return null;
    try {
      const url = new URL(rawUrl, window.location.href);
      if (!url.href.includes("vis_3d.html")) return null;
      return url.toString();
    } catch (e) {
      return null;
    }
  }

  function findExistingPreviewUrl() {
    const selectors = [
      "iframe[src*='vis_3d.html']",
      "a[href*='vis_3d.html']",
      "[src*='vis_3d.html']",
      "[href*='vis_3d.html']",
    ];
    for (const selector of selectors) {
      for (const element of document.querySelectorAll(selector)) {
        if (element.closest(`#${PANEL_ID}`)) continue;
        const raw = element.getAttribute("src") || element.getAttribute("href");
        const url = normalizePreviewUrl(raw);
        if (url && url.includes("data=")) return url;
      }
    }
    return null;
  }

  function findSectionContainer() {
    const headers = Array.from(document.querySelectorAll("h3"));
    const header = headers.find(
      (node) => node.textContent && node.textContent.includes("3D Layout Preview"),
    );
    if (!header) return null;
    const sibling = header.nextElementSibling;
    if (
      sibling &&
      (sibling.classList.contains("lsf-object") ||
        sibling.classList.contains("lsf-richtext") ||
        sibling.querySelector("iframe, a, [src], [href]"))
    ) {
      return sibling;
    }
    return header.parentElement || null;
  }

  function findNativePreviewIframe() {
    const byId = document.getElementById(OFFICIAL_IFRAME_ID);
    if (byId && !byId.closest(`#${PANEL_ID}`)) return byId;
    const frames = Array.from(document.querySelectorAll("iframe[src*='vis_3d.html']")).filter(
      (iframe) => !iframe.closest(`#${PANEL_ID}`),
    );
    return frames[0] || null;
  }

  function getNativePreviewUrl() {
    const image = findMainImage();
    const url = new URL(`${getViewerBaseUrl()}/tools/vis_3d.html`, window.location.href);
    url.searchParams.set("v", String(Date.now()));
    if (image) {
      const width = image.naturalWidth || DEFAULT_WIDTH;
      const height = image.naturalHeight || DEFAULT_HEIGHT;
      url.searchParams.set("w", String(width));
      url.searchParams.set("h", String(height));
    }
    return url.toString();
  }

  function ensureNativePreviewArea() {
    const container = findSectionContainer();
    if (!container) return null;
    Array.from(container.children).forEach((child) => {
      if (child.id !== OFFICIAL_WRAPPER_ID) {
        child.style.display = "none";
      }
    });
    let wrapper = document.getElementById(OFFICIAL_WRAPPER_ID);
    if (!wrapper) {
      wrapper = document.createElement("div");
      wrapper.id = OFFICIAL_WRAPPER_ID;
      container.appendChild(wrapper);
    }
    let iframe = document.getElementById(OFFICIAL_IFRAME_ID);
    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.id = OFFICIAL_IFRAME_ID;
      iframe.style.cssText = "width: 100%; height: 400px; border: none; background: #000;";
      wrapper.appendChild(iframe);
    }
    const url = getNativePreviewUrl();
    if (!iframe.dataset.src || !iframe.src) {
      iframe.dataset.src = url;
      iframe.src = url;
    }
    let button = document.getElementById(OFFICIAL_BUTTON_ID);
    if (!button) {
      button = document.createElement("button");
      button.id = OFFICIAL_BUTTON_ID;
      button.type = "button";
      button.textContent = "Refresh 3D Preview";
      button.style.cssText =
        "margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";
      button.addEventListener("click", function () {
        const state = extractKeypointsFromDom();
        state.preview_update_status = updatePreviewIframe(state);
        renderPanel(state);
      });
      wrapper.appendChild(button);
    }
    return iframe;
  }

  function extractPairsFromPreviewUrl(previewUrl) {
    try {
      const url = new URL(previewUrl, window.location.href);
      const rawData = url.searchParams.get("data");
      if (!rawData) return [];
      const parsed = JSON.parse(rawData);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .map((corner) => ({
          x: Number(corner.x),
          y_ceiling: Number(corner.y_ceiling),
          y_floor: Number(corner.y_floor),
        }))
        .filter(
          (corner) =>
            Number.isFinite(corner.x) &&
            Number.isFinite(corner.y_ceiling) &&
            Number.isFinite(corner.y_floor),
        );
    } catch (e) {
      return [];
    }
  }

  function getPreviewUrl(state) {
    return state?.preview_url || `${getViewerBaseUrl()}/tools/vis_3d.html?v=${Date.now()}`;
  }

  function extractOverlayKeypoints(points) {
    const mainImage = findMainImage();
    if (!mainImage) return;
    const imageRect = mainImage.getBoundingClientRect();
    if (!imageRect.width || !imageRect.height) return;
    const candidates = Array.from(
      document.querySelectorAll(
        "[class*='keypoint'], [class*='Keypoint'], [class*='point'], [class*='Point'], [aria-label*='Corner'], [title*='Corner']",
      ),
    );
    for (const element of candidates) {
      if (element.closest(`#${PANEL_ID}`)) continue;
      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) continue;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      if (
        centerX < imageRect.left ||
        centerX > imageRect.right ||
        centerY < imageRect.top ||
        centerY > imageRect.bottom
      ) {
        continue;
      }
      points.push({
        x: ((centerX - imageRect.left) / imageRect.width) * DEFAULT_WIDTH,
        y: ((centerY - imageRect.top) / imageRect.height) * DEFAULT_HEIGHT,
        source: "dom-keypoint-overlay",
      });
    }
  }

  function extractKeypointsFromDom() {
    const store = getStore();
    const storeStatus = store ? "available" : "unavailable";
    const storeExtraction = extractKeypointsFromStore(store, DEFAULT_WIDTH, DEFAULT_HEIGHT);
    const points = storeExtraction.keypoints;
    const previewUrl = findExistingPreviewUrl();
    const previewPairs = extractPairsFromPreviewUrl(previewUrl);

    for (const circle of document.querySelectorAll("svg circle")) {
      const x = numericAttr(circle, ["cx"]);
      const y = numericAttr(circle, ["cy"]);
      if (x !== null && y !== null) {
        points.push({ x, y, source: "svg-circle" });
      }
    }

    for (const element of document.querySelectorAll("[data-x][data-y], [data-keypoint-x][data-keypoint-y]")) {
      const x = numericAttr(element, ["data-keypoint-x", "data-x"]);
      const y = numericAttr(element, ["data-keypoint-y", "data-y"]);
      if (x !== null && y !== null) {
        points.push({ x, y, source: "data-attribute" });
      }
    }

    extractOverlayKeypoints(points);

    const unique = [];
    const seen = new Set();
    for (const point of points) {
      const key = `${point.source}:${point.x}:${point.y}`;
      if (!seen.has(key)) {
        unique.push(point);
        seen.add(key);
      }
    }

    return {
      keypoint_read_status: unique.length > 0 ? "available" : "unavailable",
      keypoints: unique,
      store_status: storeStatus,
      result_count: storeExtraction.result_count,
      keypoint_sources: Array.from(new Set(unique.map((point) => point.source))).join(",") || "none",
      preview_url_status: previewUrl ? "available" : "unavailable",
      preview_url: previewUrl,
      preview_pairs: previewPairs,
      native_preview_status: findNativePreviewIframe() ? "available" : "unavailable",
      preview_update_status: "not_run",
    };
  }

  function updatePreviewIframe(state) {
    const iframe = findNativePreviewIframe() || ensureNativePreviewArea();
    if (!iframe) return "native_preview_unavailable";
    const pairs = state.preview_pairs?.length
      ? state.preview_pairs
      : buildPreviewPairs(state.keypoints, DEFAULT_WIDTH);
    if (state.preview_url && state.preview_pairs?.length) {
      return "native_preview_already_loaded";
    }
    if (!pairs.length) return "no_preview_pairs";
    const imageUrl = findMainImage()?.src || getImageUrlFromStore();
    const textureUrl = withCacheBust(rewriteTextureUrlForViewer(imageUrl));
    iframe.contentWindow?.postMessage(
      {
        type: "update_layout",
        corners: pairs,
        baseCorners: pairs,
        width: DEFAULT_WIDTH,
        height: DEFAULT_HEIGHT,
        imageUrl: textureUrl,
        preserveOrder: true,
        previewOrderActive: false,
        previewOrder: pairs.map((_, index) => index),
        previewSignature: String(Date.now()),
      },
      "*",
    );
    return "native_preview_update_sent";
  }

  function secondsSinceStart() {
    return Math.max(0, Math.round((Date.now() - START_TIME_MS) / 1000));
  }

  function secondsSinceLastTelemetry(nowMs) {
    return Math.max(0, Math.round((nowMs - lastTelemetryMs) / 1000));
  }

  function updateTelemetryPanel() {
    setText(`${PANEL_ID}-telemetry-status`, telemetryState.status);
    setText(`${PANEL_ID}-last-telemetry-event`, telemetryState.lastEvent);
    setText(`${PANEL_ID}-last-telemetry-http-status`, telemetryState.lastHttpStatus);
    setText(`${PANEL_ID}-last-telemetry-error`, telemetryState.lastError);
  }

  function sandboxTelemetryPayload(eventName, nowMs = Date.now()) {
    const activeSeconds = secondsSinceStart();
    const fragmentSeconds = secondsSinceLastTelemetry(nowMs);
    return {
      task_id: getTaskId(),
      project_id: getProjectId(),
      project_name: getProjectName(),
      annotator_id: getAnnotatorId(),
      session_id: sessionId,
      page_type: getPageType(),
      active_seconds: activeSeconds,
      active_seconds_fragment: fragmentSeconds,
      timestamp: nowMs,
      event: eventName,
      telemetry_elapsed_seconds: activeSeconds,
      elapsed_ms: nowMs - START_TIME_MS,
      page_url: window.location.href,
      log_context: "manhattan_ls_sandbox",
      tool_stage: "M8",
      script_variant: "timed",
      is_sandbox: true,
      sandbox_project: true,
      exclude_from_primary_active_time: true,
      exclude_from_thesis_evidence: true,
      not_worker_facing: true,
      not_p1_c1_c2_t1_v1_artifact: true,
      manhattan_panel_version: PANEL_VERSION,
    };
  }

  function sendSandboxTelemetry(eventName) {
    const token = getLogToken();
    const nowMs = Date.now();
    const payload = sandboxTelemetryPayload(eventName, nowMs);
    telemetryState.status = "sending";
    telemetryState.lastEvent = eventName;
    telemetryState.lastHttpStatus = "pending";
    telemetryState.lastError = "none";
    updateTelemetryPanel();
    fetch(logTimeUrl(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-HOHONET-TOKEN": token } : {}),
      },
      body: JSON.stringify(payload),
      keepalive: true,
    })
      .then(function (response) {
        telemetryState.status = response.ok ? "sent" : "http_error";
        telemetryState.lastHttpStatus = String(response.status);
        telemetryState.lastError = response.ok ? "none" : response.statusText || "non_2xx_response";
        lastTelemetryMs = nowMs;
        updateTelemetryPanel();
      })
      .catch(function (error) {
        telemetryState.status = "network_error";
        telemetryState.lastHttpStatus = "network_error";
        telemetryState.lastError = error?.message || "unknown_error";
        lastTelemetryMs = nowMs;
        updateTelemetryPanel();
      // Sandbox telemetry failure must not interrupt annotation or panel display.
      });
  }

  function installStyles() {
    if (document.getElementById(`${PANEL_ID}-style`)) {
      return;
    }
    const style = document.createElement("style");
    style.id = `${PANEL_ID}-style`;
    style.textContent = `
      #${PANEL_ID} {
        position: fixed;
        right: 12px;
        bottom: 12px;
        z-index: 2147483647;
        width: 340px;
        max-height: 70vh;
        overflow: auto;
        box-sizing: border-box;
        padding: 12px;
        border: 1px solid #6b7280;
        background: #111827;
        color: #f9fafb;
        font: 12px/1.4 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
      }
      #${PANEL_ID} h2,
      #${PANEL_ID} h3 {
        margin: 0 0 8px;
        font-size: 13px;
        letter-spacing: 0;
      }
      #${PANEL_ID} section {
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid #374151;
      }
      #${PANEL_ID} ul {
        margin: 0;
        padding-left: 18px;
      }
      .hohonet-m8-row {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin: 4px 0;
      }
      .hohonet-m8-key {
        color: #d1d5db;
      }
      .hohonet-m8-value {
        color: #ffffff;
        font-weight: 600;
      }
    `;
    document.head.appendChild(style);
  }

  function renderPanel(state) {
    let panel = document.getElementById(PANEL_ID);
    if (panel) {
      setText(`${PANEL_ID}-read-status`, state.keypoint_read_status);
      setText(`${PANEL_ID}-keypoint-count`, state.keypoints.length);
      setText(`${PANEL_ID}-store-status`, state.store_status);
      setText(`${PANEL_ID}-result-count`, state.result_count);
      setText(`${PANEL_ID}-keypoint-sources`, state.keypoint_sources);
      setText(`${PANEL_ID}-preview-url-status`, state.preview_url_status);
      setText(`${PANEL_ID}-native-preview-status`, state.native_preview_status);
      setText(`${PANEL_ID}-preview-update-status`, state.preview_update_status);
      setText(`${PANEL_ID}-viewer-base-url`, getViewerBaseUrl());
      setText(`${PANEL_ID}-log-time-url`, logTimeUrl());
      updateTelemetryPanel();
      return;
    }

    panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.setAttribute("aria-label", "HOHONET Manhattan sandbox panel timed");
    document.body.appendChild(panel);

    const title = document.createElement("h2");
    title.appendChild(text("Manhattan Sandbox Panel"));
    panel.appendChild(title);
    panel.appendChild(makeRow("script_variant", "timed"));
    panel.appendChild(makeRow("manhattan_panel_version", PANEL_VERSION));
    panel.appendChild(makeMutableRow("keypoint_read_status", state.keypoint_read_status, `${PANEL_ID}-read-status`));
    panel.appendChild(makeMutableRow("keypoint_count", state.keypoints.length, `${PANEL_ID}-keypoint-count`));
    panel.appendChild(makeMutableRow("store_status", state.store_status, `${PANEL_ID}-store-status`));
    panel.appendChild(makeMutableRow("result_count", state.result_count, `${PANEL_ID}-result-count`));
    panel.appendChild(makeMutableRow("keypoint_sources", state.keypoint_sources, `${PANEL_ID}-keypoint-sources`));
    panel.appendChild(makeMutableRow("preview_url_status", state.preview_url_status, `${PANEL_ID}-preview-url-status`));
    panel.appendChild(makeMutableRow("native_preview_status", state.native_preview_status, `${PANEL_ID}-native-preview-status`));
    panel.appendChild(makeMutableRow("preview_update_status", state.preview_update_status, `${PANEL_ID}-preview-update-status`));
    panel.appendChild(makeRow("log_context", "manhattan_ls_sandbox"));
    panel.appendChild(makeMutableRow("viewer_base_url", getViewerBaseUrl(), `${PANEL_ID}-viewer-base-url`));
    panel.appendChild(makeMutableRow("log_time_url", logTimeUrl(), `${PANEL_ID}-log-time-url`));
    panel.appendChild(makeMutableRow("telemetry_status", telemetryState.status, `${PANEL_ID}-telemetry-status`));
    panel.appendChild(makeMutableRow("last_telemetry_event", telemetryState.lastEvent, `${PANEL_ID}-last-telemetry-event`));
    panel.appendChild(makeMutableRow("last_telemetry_http_status", telemetryState.lastHttpStatus, `${PANEL_ID}-last-telemetry-http-status`));
    panel.appendChild(makeMutableRow("last_telemetry_error", telemetryState.lastError, `${PANEL_ID}-last-telemetry-error`));
    panel.appendChild(makeRow("heartbeat_interval_ms", HEARTBEAT_INTERVAL_MS));

    const controls = document.createElement("section");
    controls.appendChild(document.createElement("h3")).appendChild(text("Controls"));
    const refreshButton = document.createElement("button");
    refreshButton.type = "button";
    refreshButton.textContent = "Refresh 3D Preview";
    refreshButton.addEventListener("click", function () {
      const nextState = extractKeypointsFromDom();
      nextState.preview_update_status = updatePreviewIframe(nextState);
      renderPanel(nextState);
    });
    controls.appendChild(refreshButton);
    panel.appendChild(controls);

    const preview = document.createElement("section");
    preview.appendChild(document.createElement("h3")).appendChild(text("3D Preview"));
    preview.appendChild(text("Uses the existing page 3D Layout Preview only; no sandbox iframe is embedded."));
    panel.appendChild(preview);

    const compatibility = document.createElement("section");
    compatibility.appendChild(document.createElement("h3")).appendChild(text("Compatibility"));
    compatibility.appendChild(text("placeholder only; no Python logic is ported in M8.1"));
    panel.appendChild(compatibility);

    const residual = document.createElement("section");
    residual.appendChild(document.createElement("h3")).appendChild(text("Residual"));
    residual.appendChild(text("placeholder only; no residual calculator is embedded"));
    panel.appendChild(residual);

    const suggestion = document.createElement("section");
    suggestion.appendChild(document.createElement("h3")).appendChild(text("Preview-only suggestion"));
    suggestion.appendChild(text("placeholder only; no automated review prompt is computed"));
    panel.appendChild(suggestion);

    const guards = document.createElement("section");
    guards.appendChild(document.createElement("h3")).appendChild(text("Guardrails"));
    const list = document.createElement("ul");
    for (const guard of GUARDRAILS) {
      const item = document.createElement("li");
      item.appendChild(text(guard));
      list.appendChild(item);
    }
    guards.appendChild(list);
    panel.appendChild(guards);
  }

  function refresh() {
    installStyles();
    ensureNativePreviewArea();
    const state = extractKeypointsFromDom();
    renderPanel(state);
    window.setTimeout(function () {
      state.preview_update_status = updatePreviewIframe(state);
      renderPanel(state);
    }, 500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh, { once: true });
  } else {
    refresh();
  }

  window.setInterval(function () {
    ensureNativePreviewArea();
  }, 1500);

  sendSandboxTelemetry("panel_loaded");
  window.setInterval(function () {
    sendSandboxTelemetry("heartbeat");
  }, HEARTBEAT_INTERVAL_MS);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      sendSandboxTelemetry("visibility_hidden");
    }
  });
  window.addEventListener("pagehide", function () {
    sendSandboxTelemetry("pagehide");
  });
  window.addEventListener("beforeunload", function () {
    sendSandboxTelemetry("panel_unloaded");
  });
})();
