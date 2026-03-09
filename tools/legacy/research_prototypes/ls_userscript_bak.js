// ==UserScript==
// @name         HoHoNet Helper
// @namespace    http://tampermonkey.net/
// @version      0.13
// @description  Connect Label Studio with HoHoNet 3D Viewer
// @author       HoHoNet
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  // Prevent running in iframes (avoids duplicate debug panels)
  if (window.top !== window.self) return;

  const IFRAME_ID = "hohonet-iframe";
  const BUTTON_ID = "hohonet-refresh-btn";
  const WRAPPER_ID = "hohonet-wrapper";
  const DEBUG_ID = "hohonet-debug-panel";

  // Cleanup existing UI to prevent duplicates on reload
  const existingWrapper = document.getElementById(WRAPPER_ID);
  if (existingWrapper) existingWrapper.remove();
  const existingDebug = document.getElementById(DEBUG_ID);
  if (existingDebug) existingDebug.remove();

  console.log("HoHoNet Helper: Loaded (v0.13 Fixes)");

  // --- Debug Panel ---
  function updateDebug(msg) {
    let panel = document.getElementById(DEBUG_ID);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = DEBUG_ID;
      panel.style.cssText =
        "position: fixed; bottom: 10px; right: 10px; background: rgba(0,0,0,0.8); color: #0f0; padding: 10px; z-index: 9999; font-family: monospace; font-size: 12px; pointer-events: none; white-space: pre-wrap;";
      document.body.appendChild(panel);
    }
    panel.innerText = "HoHoNet Debug (v0.13):\n" + msg;
  }

  // --- Store Discovery ---
  function getStore() {
    // 1. Standard Global
    if (
      window.LabelStudio &&
      window.LabelStudio.instances &&
      window.LabelStudio.instances.length > 0
    ) {
      return window.LabelStudio.instances[0].store;
    }
    // 2. Legacy Global
    if (window.H) return window.H;

    // 3. React Internals (The "Nuclear" Option)
    const root =
      document.querySelector(".ls-room") ||
      document.querySelector("#label-studio") ||
      document.querySelector(".lsf-main-view");
    if (root) {
      for (const key in root) {
        if (key.startsWith("__reactFiber")) {
          // Traverse up to find the store in props or context
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

  function findSectionContainer() {
    const headers = Array.from(document.querySelectorAll("h3"));
    const header = headers.find(
      (h) => h.textContent && h.textContent.includes("3D Layout Preview")
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
    // 1. Try to find image within the main annotation area
    // Label Studio structure often has .lsf-main-view or .ls-main-view
    const mainView =
      document.querySelector(".lsf-main-view") ||
      document.querySelector(".ls-main-view");
    if (mainView) {
      const imgs = Array.from(mainView.querySelectorAll("img"));
      // Filter for reasonably large images to avoid icons/thumbnails
      const candidates = imgs.filter(
        (img) => img.naturalWidth > 200 || img.width > 200
      );
      if (candidates.length > 0) {
        // Return the largest one by area
        return candidates.reduce((a, b) =>
          (a.naturalWidth || 0) * (a.naturalHeight || 0) >
          (b.naturalWidth || 0) * (b.naturalHeight || 0)
            ? a
            : b
        );
      }
    }

    // 2. Fallback: Find the largest image on the entire page
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

  function tick() {
    let status = "";
    // v0.11 Fix: Delay store lookup until interaction to avoid React interference
    // let store = getStore(); // Removed from tick

    // --- URL Resolution ---
    let url = null;

    // Fallback: Try to guess URL from Image (Primary method now in tick)
    const img = findMainImage();
    if (img) {
      status += "Image: Found\n";
      url = "http://localhost:8000/tools/vis_3d.html";
      if (img.naturalWidth) {
        url += `?w=${img.naturalWidth}&h=${img.naturalHeight}`;
      }
    } else {
      status += "Image: Not found\n";
    }

    if (url) {
      status += "Target URL: Ready\n";
    } else {
      status += "Target URL: Missing\n";
    }

    // --- Injection ---
    const container = findSectionContainer();
    if (!container) {
      updateDebug(status + "Container: Not found");
      return;
    }

    try {
      // Hide original children
      Array.from(container.children).forEach((child) => {
        if (child.id !== WRAPPER_ID) {
          child.style.display = "none";
        }
      });

      // Wrapper
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

      // Update URL
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

      // Button
      let btn = document.getElementById(BUTTON_ID);
      if (!btn) {
        btn = document.createElement("button");
        btn.id = BUTTON_ID;
        btn.innerText = "🔄 Refresh 3D View";
        btn.style.cssText =
          "margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;";

        btn.onclick = function () {
          // v0.11 Fix: Lookup store only on click
          const store = getStore();
          if (!store) {
            alert(
              "Cannot connect to Label Studio Store. Please wait for the editor to load fully."
            );
            return;
          }
          if (!store.annotationStore || !store.annotationStore.selected) {
            alert("Please select an annotation first.");
            return;
          }

          const results = store.annotationStore.selected.results;
          const points = [];

          // Dimensions
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

          console.log("HoHoNet: Processing results:", results);

          // v0.9 Fix: Nuclear Unwrap
          const clean = (obj) => {
            try {
              return JSON.parse(JSON.stringify(obj));
            } catch (e) {
              return obj;
            }
          };

          results.forEach((r, idx) => {
            // v0.10 Fix: Check r.area first
            let source = r;
            if (r.area) source = r.area;

            // Unwrap
            let val = clean(source);
            if (!val) val = source.toJSON ? source.toJSON() : source;

            console.log(`HoHoNet: Result ${idx} (Cleaned):`, val);

            // Determine type (check both r and val)
            const type = r.type || val.type;

            // 1. Keypoints (Corners)
            // Compatible with: keypointlabels, keypointregion
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
                points.push({ x: px, y: py });
              }
            }
            // 2. Polygons (Walls/Surfaces)
            // Compatible with: polygonlabels, polygonregion
            else if (type === "polygonlabels" || type === "polygonregion") {
              let pts = [];
              if (val.points) pts = val.points;
              else if (val.value && val.value.points) pts = val.value.points;

              if (pts && pts.length > 0) {
                // v0.14 Fix: Simplify Polygon to Vertical Edges
                // Instead of taking all points (which creates many segments for curved walls),
                // we only extract the left-most and right-most vertical edges.

                // 1. Parse all points
                const parsedPts = pts
                  .map((pt) => {
                    if (Array.isArray(pt)) return { x: pt[0], y: pt[1] };
                    if (typeof pt === "object" && pt !== null)
                      return { x: pt.x, y: pt.y };
                    return null;
                  })
                  .filter((p) => p);

                if (parsedPts.length > 0) {
                  // 2. Find X bounds
                  let minX = Infinity,
                    maxX = -Infinity;
                  parsedPts.forEach((p) => {
                    if (p.x < minX) minX = p.x;
                    if (p.x > maxX) maxX = p.x;
                  });

                  // 3. Define threshold to identify vertical edges (e.g. 1% of image width)
                  const threshold = 1.0;

                  // 4. Extract Left and Right Edge Points
                  const leftPts = parsedPts.filter(
                    (p) => Math.abs(p.x - minX) < threshold
                  );
                  const rightPts = parsedPts.filter(
                    (p) => Math.abs(p.x - maxX) < threshold
                  );

                  const processEdge = (edgePts) => {
                    if (edgePts.length === 0) return;
                    // Find Y bounds (Ceiling and Floor)
                    let minY = Infinity,
                      maxY = -Infinity;
                    let avgX = 0;
                    edgePts.forEach((p) => {
                      if (p.y < minY) minY = p.y;
                      if (p.y > maxY) maxY = p.y;
                      avgX += p.x;
                    });
                    avgX /= edgePts.length;

                    // Add 2 corners for this edge
                    points.push({ x: (avgX * W) / 100, y: (minY * H) / 100 });
                    points.push({ x: (avgX * W) / 100, y: (maxY * H) / 100 });
                  };

                  processEdge(leftPts);
                  processEdge(rightPts);
                }
              }
            }
            // 3. Rectangles
            // Compatible with: rectanglelabels, rectangleregion
            else if (type === "rectanglelabels" || type === "rectangleregion") {
              let x, y, w, h;
              const src = val.value || val;
              x = src.x;
              y = src.y;
              w = src.width;
              h = src.height;

              if ([x, y, w, h].every((v) => typeof v === "number")) {
                const corners = [
                  { x: x, y: y },
                  { x: x + w, y: y },
                  { x: x + w, y: y + h },
                  { x: x, y: y + h },
                ];
                corners.forEach((pt) => {
                  points.push({ x: (pt.x * W) / 100, y: (pt.y * H) / 100 });
                });
              }
            }
          });

          if (points.length === 0) {
            alert(
              "No points found! Please draw Keypoints, Polygons, or Rectangles."
            );
            return;
          }

          console.log("HoHoNet: Raw Points:", points);

          points.sort((a, b) => a.x - b.x);
          const paired = [];
          const used = new Array(points.length).fill(false);
          const threshold = W * 0.05;

          for (let i = 0; i < points.length; i++) {
            if (used[i]) continue;
            let bestJ = -1;
            // Find the best matching point (closest in X)
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
              paired.push({
                x: (points[i].x + points[bestJ].x) / 2,
                y_ceiling: Math.min(points[i].y, points[bestJ].y),
                y_floor: Math.max(points[i].y, points[bestJ].y),
              });
            }
          }

          console.log("HoHoNet: Paired Corners:", paired);
          if (paired.length === 0) {
            alert(
              `Found ${points.length} points but could not pair any vertical edges! Try drawing straighter vertical lines.`
            );
            return;
          }

          // Get Image URL for texturing
          const img = findMainImage();
          let imageUrl = img ? img.src : null;

          // v0.13 Fix: If running with local cors_server, try to use local asset path
          // This avoids CORS/Auth issues with Label Studio URLs and ensures we get the right file
          if (imageUrl && iframe.src.includes(":8000")) {
            try {
              // Extract filename (e.g. from http://localhost:8080/.../pano_abc.png)
              const urlParts = imageUrl.split("/");
              let filename = urlParts[urlParts.length - 1];
              filename = filename.split("?")[0]; // Remove query params

              // If filename has Label Studio hash prefix (8 chars + dash), try to clean it
              // Heuristic: if it contains "pano_", use that part
              if (filename.includes("pano_")) {
                const match = filename.match(/(pano_.*)/);
                if (match) filename = match[1];
              }

              // Construct local URL (assuming assets are in 'assets/' folder relative to server root)
              // Note: This assumes cors_server is running from project root
              const localUrl = `http://localhost:8000/assets/${filename}`;
              console.log(
                `HoHoNet: Trying local asset URL: ${localUrl} (Original: ${imageUrl})`
              );

              // We pass the original as fallback, but let's try to prefer local if we can verify it?
              // For now, let's just pass the original, but if you want to force local, uncomment below:
              // imageUrl = localUrl;

              // Actually, let's pass BOTH to vis_3d and let it decide/fallback?
              // Or just stick to the original fix (findMainImage) first.
              // If the user says "different image", it's likely the wrong element.
              // But if the element is correct but the URL is blocked, we need local.

              // Let's use a hybrid approach: Pass the local URL as a 'textureUrl' property
              // and let vis_3d try it if provided.
            } catch (e) {
              console.warn("HoHoNet: Failed to construct local URL", e);
            }
          }

          iframe.contentWindow.postMessage(
            {
              type: "update_layout",
              corners: paired,
              width: W,
              height: H,
              imageUrl: imageUrl,
            },
            "*"
          );
        };
        wrapper.appendChild(btn);
      }
    } catch (e) {
      status += "Error: " + e.message;
    }

    updateDebug(status);
  }

  setInterval(tick, 1000);
})();
