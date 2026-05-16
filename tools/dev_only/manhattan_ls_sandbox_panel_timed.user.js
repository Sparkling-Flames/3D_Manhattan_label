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

  const WINDOW_GUARD = "__HOHONET_M8_SANDBOX_PANEL_ACTIVE__";
  if (window[WINDOW_GUARD]) {
    return;
  }
  window[WINDOW_GUARD] = { script_variant: "timed" };

  const PANEL_ID = "hohonet-manhattan-sandbox-panel";
  const PANEL_VERSION = "m8-dev-only-timed-0.1.0";
  const START_TIME_MS = Date.now();
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

  function extractKeypointsFromDom() {
    const points = [];

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
    };
  }

  function sandboxTelemetryPayload(eventName) {
    return {
      event: eventName,
      elapsed_ms: Date.now() - START_TIME_MS,
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
    fetch("/log_time", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sandboxTelemetryPayload(eventName)),
      keepalive: true,
    }).catch(function () {
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
    if (!panel) {
      panel = document.createElement("aside");
      panel.id = PANEL_ID;
      panel.setAttribute("aria-label", "HOHONET Manhattan sandbox panel timed");
      document.body.appendChild(panel);
    }

    panel.innerHTML = "";
    const title = document.createElement("h2");
    title.appendChild(text("Manhattan Sandbox Panel"));
    panel.appendChild(title);
    panel.appendChild(makeRow("script_variant", "timed"));
    panel.appendChild(makeRow("manhattan_panel_version", PANEL_VERSION));
    panel.appendChild(makeRow("keypoint_read_status", state.keypoint_read_status));
    panel.appendChild(makeRow("keypoint_count", state.keypoints.length));
    panel.appendChild(makeRow("log_context", "manhattan_ls_sandbox"));

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
    renderPanel(extractKeypointsFromDom());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh, { once: true });
  } else {
    refresh();
  }

  sendSandboxTelemetry("panel_loaded");
  window.addEventListener("beforeunload", function () {
    sendSandboxTelemetry("panel_unloaded");
  });
})();
