// tools/ls_3d_logic.js

(function () {
  if (window.LS3D) return; // 防止重复定义

  console.log("[LS3D] Logic loaded.");

  window.LS3D = {
    threeLoaded: false,

    loadThree: function (callback) {
      if (window.THREE) {
        this.threeLoaded = true;
        callback();
        return;
      }
      console.log("[LS3D] Loading Three.js...");
      var script = document.createElement("script");
      script.src =
        "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
      script.onload = function () {
        console.log("[LS3D] Three.js loaded.");
        window.LS3D.threeLoaded = true;
        callback();
      };
      document.head.appendChild(script);
    },

    init: function (id, corners, width, height) {
      this.loadThree(function () {
        window.LS3D.startScene(id, corners, width, height);
      });
    },

    startScene: function (id, corners, W, H) {
      const containerId = "vis-3d-" + id;
      const container = document.getElementById(containerId);
      const statusEl = document.getElementById("status-" + id);

      if (!container) {
        console.error("[LS3D] Container not found: " + containerId);
        return;
      }

      if (container.getAttribute("data-initialized") === "true") {
        console.log("[LS3D] Already initialized: " + id);
        return;
      }
      container.setAttribute("data-initialized", "true");

      if (statusEl) statusEl.innerText = "Running";

      // --- Three.js Setup ---
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x111111);

      const camera = new THREE.PerspectiveCamera(
        75,
        container.clientWidth / container.clientHeight,
        0.1,
        1000
      );
      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(container.clientWidth, container.clientHeight);
      container.innerHTML = ""; // Clear status text
      container.appendChild(renderer.domElement);

      // Helpers
      const gridHelper = new THREE.GridHelper(10, 10, 0x444444, 0x222222);
      scene.add(gridHelper);

      // Materials
      const matCeil = new THREE.LineBasicMaterial({
        color: 0xff0000,
        linewidth: 2,
      });
      const matFloor = new THREE.LineBasicMaterial({
        color: 0x0088ff,
        linewidth: 2,
      });
      const matVert = new THREE.LineBasicMaterial({
        color: 0x00ff00,
        linewidth: 1,
      });

      let meshObjects = [];

      function draw(drawCorners) {
        meshObjects.forEach((o) => scene.remove(o));
        meshObjects = [];

        if (!drawCorners || drawCorners.length === 0) return;

        // Sort by x
        drawCorners.sort((a, b) => a.x - b.x);

        const ceilPoints = [];
        const floorPoints = [];

        drawCorners.forEach((c) => {
          // Mapping: x(0..W) -> -PI..PI
          const theta = (c.x / W) * 2 * Math.PI - Math.PI;
          const R = 4;
          const x3 = R * Math.sin(theta);
          const z3 = -R * Math.cos(theta);

          const h_ceil = (0.5 - c.y_ceiling / H) * 5;
          const h_floor = (0.5 - c.y_floor / H) * 5;

          const pCeil = new THREE.Vector3(x3, h_ceil, z3);
          const pFloor = new THREE.Vector3(x3, h_floor, z3);

          ceilPoints.push(pCeil);
          floorPoints.push(pFloor);

          const vGeo = new THREE.BufferGeometry().setFromPoints([
            pCeil,
            pFloor,
          ]);
          const vLine = new THREE.Line(vGeo, matVert);
          scene.add(vLine);
          meshObjects.push(vLine);
        });

        // Close loop
        if (ceilPoints.length > 0) {
          ceilPoints.push(ceilPoints[0]);
          floorPoints.push(floorPoints[0]);
        }

        const cGeo = new THREE.BufferGeometry().setFromPoints(ceilPoints);
        const fGeo = new THREE.BufferGeometry().setFromPoints(floorPoints);

        scene.add(new THREE.Line(cGeo, matCeil));
        scene.add(new THREE.Line(fGeo, matFloor));
        meshObjects.push(
          scene.children[scene.children.length - 1],
          scene.children[scene.children.length - 2]
        );
      }

      draw(corners);

      camera.position.set(0, 0, 0.1);
      camera.lookAt(0, 0, -1);

      function animate() {
        requestAnimationFrame(animate);
        renderer.render(scene, camera);
      }
      animate();

      // Resize handler
      const resizeObserver = new ResizeObserver(() => {
        if (container.clientWidth > 0) {
          camera.aspect = container.clientWidth / container.clientHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(container.clientWidth, container.clientHeight);
        }
      });
      resizeObserver.observe(container);

      // --- Sync Logic ---
      window["sync3D_" + id] = function () {
        console.log("[LS3D] Syncing " + id);

        // Try to find Label Studio store
        let store = null;
        if (
          window.LabelStudio &&
          window.LabelStudio.instances &&
          window.LabelStudio.instances.length > 0
        ) {
          store = window.LabelStudio.instances[0].store;
        } else if (window.H) {
          store = window.H;
        }

        if (store && store.annotationStore && store.annotationStore.selected) {
          const results = store.annotationStore.selected.results;
          const points = [];

          results.forEach((r) => {
            if (r.type === "keypointlabels" && r.value) {
              const px = (r.value.x * W) / 100;
              const py = (r.value.y * H) / 100;
              points.push({ x: px, y: py });
            }
          });

          if (points.length === 0) {
            alert("No points found!");
            return;
          }

          // Pairing logic
          points.sort((a, b) => a.x - b.x);
          const paired = [];
          const used = new Array(points.length).fill(false);
          const threshold = W * 0.05;

          for (let i = 0; i < points.length; i++) {
            if (used[i]) continue;
            let bestJ = -1;
            for (let j = i + 1; j < points.length; j++) {
              if (!used[j] && Math.abs(points[j].x - points[i].x) < threshold) {
                bestJ = j;
                break;
              }
            }
            if (bestJ !== -1) {
              used[i] = true;
              used[j] = true;
              const p1 = points[i];
              const p2 = points[bestJ];
              paired.push({
                x: (p1.x + p2.x) / 2,
                y_ceiling: Math.min(p1.y, p2.y),
                y_floor: Math.max(p1.y, p2.y),
              });
            }
          }
          console.log("[LS3D] Paired: ", paired);
          draw(paired);
        } else {
          alert(
            "Cannot find Label Studio data. Make sure you are in labeling mode."
          );
        }
      };
    },
  };
})();
