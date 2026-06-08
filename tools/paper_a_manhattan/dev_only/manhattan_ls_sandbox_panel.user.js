// ==UserScript==
// @name         HOHONET Manhattan LS Sandbox Panel
// @namespace    hohonet-dev-only
// @version      0.1.0
// @description  dev-only sandbox-only Manhattan preview panel for expert/developer tester use only.
// @match        http://175.178.71.217:8080/*
// @match        https://175.178.71.217:8080/*
// @grant        none
// ==/UserScript==

/*
 * HOHONET Manhattan LS Sandbox Panel
 *
 * dev-only
 * sandbox-only
 * expert/developer tester only
 * not official userscript
 * not worker-facing
 * no writeback
 * no submit
 * no routing
 * no formal g_t
 * no P1/C1/C2/T1/V1 artifact
 *
 * This prototype injects a read-only panel for a separate Label Studio
 * sandbox project. It is not part of the current Manual/Semi-Auto
 * worker-facing experiment and must not be installed in formal projects.
 *
 * M8.1 operation should use the explicit debug/timed variants in this
 * directory. This original prototype is also server-scoped to prevent broad
 * installation by accident.
 */

(function () {
  "use strict";

  const PANEL_ID = "hohonet-manhattan-sandbox-panel";
  const VERSION = "m8-dev-only-0.1.0";
  const GUARDRAILS = [
    "dev-only sandbox-only panel",
    "expert/developer tester only",
    "not official userscript",
    "not worker-facing",
    "no writeback",
    "no submit",
    "no routing",
    "no formal g_t",
    "no P1/C1/C2/T1/V1 artifact",
    "no correctness label",
    "no worker tier",
    "no snap coordinates",
    "no adjustment vector",
    "no auto-correction",
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

  function renderPanel(state) {
    let panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = document.createElement("aside");
      panel.id = PANEL_ID;
      panel.setAttribute("aria-label", "HOHONET Manhattan sandbox panel");
      document.body.appendChild(panel);
    }

    panel.innerHTML = "";

    const title = document.createElement("h2");
    title.appendChild(text("Manhattan Sandbox Panel"));
    panel.appendChild(title);

    panel.appendChild(makeRow("version", VERSION));
    panel.appendChild(makeRow("keypoint_read_status", state.keypoint_read_status));
    panel.appendChild(makeRow("keypoint_count", state.keypoints.length));

    const compatibility = document.createElement("section");
    compatibility.appendChild(document.createElement("h3")).appendChild(text("Compatibility"));
    compatibility.appendChild(text("placeholder only; Python parity logic is not ported in M8"));
    panel.appendChild(compatibility);

    const residual = document.createElement("section");
    residual.appendChild(document.createElement("h3")).appendChild(text("Residual"));
    residual.appendChild(text("placeholder only; no residual calculator is embedded in M8"));
    panel.appendChild(residual);

    const suggestion = document.createElement("section");
    suggestion.appendChild(document.createElement("h3")).appendChild(text("Preview-only suggestion"));
    suggestion.appendChild(text("placeholder only; no automated review prompt is computed in M8"));
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

  function refresh() {
    installStyles();
    renderPanel(extractKeypointsFromDom());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh, { once: true });
  } else {
    refresh();
  }
})();
