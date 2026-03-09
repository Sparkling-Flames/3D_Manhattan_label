import json
import os
import glob
import numpy as np
import argparse

# 配置（支持两种模式）
# 1) 旧模式（本地/云主机静态服务）:
#    image = {HOHONET_BASE_URL}/{IMAGE_DIR_REL}/{basename}
#    vis_3d = {HOHONET_VIS_BASE_URL}/tools/vis_3d.html?... 
# 2) COS 模式（推荐）:
#    设置 HOHONET_IMAGE_BASE_URL，例如:
#    https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/test/img
#    此时 image 直接走 COS，不占用旧服务器带宽。
# 新服务器默认值（可被环境变量覆盖）
DEFAULT_BASE_URL = os.environ.get("HOHONET_BASE_URL", "http://175.178.71.217:8000")
DEFAULT_VIS_BASE_URL = os.environ.get("HOHONET_VIS_BASE_URL", DEFAULT_BASE_URL)
DEFAULT_IMAGE_BASE_URL = os.environ.get("HOHONET_IMAGE_BASE_URL", "")
OUTPUT_JSON = "label_studio_import_docker.json"
LAYOUT_TXT_DIR = "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34"
IMAGE_DIR_REL = "data/mp3d_layout/test/img"

# 图像尺寸 (HoHoNet 默认)
W, H = 1024, 512

import urllib.parse

# Three.js 3D 预览 HTML 模板 (使用 Iframe 隔离)
# 我们将数据编码到 URL 中，避免脚本注入问题
IFRAME_TEMPLATE = """
<div style="width: 100%; height: 400px; background: #000;">
    <iframe id="iframe-{id}" 
            src="{iframe_url}" 
            style="width: 100%; height: 100%; border: none;"
            allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen>
    </iframe>
</div>
<div style="margin-top: 5px;">
    <button onclick="
        (function(){{
            var iframe = document.getElementById('iframe-{id}');
            if(!iframe) return;
            
            // Try to find Label Studio store
            var store = null;
            if (window.LabelStudio && window.LabelStudio.instances && window.LabelStudio.instances.length > 0) {{
                store = window.LabelStudio.instances[0].store;
            }} else if (window.H) {{
                store = window.H;
            }}

            if (store && store.annotationStore && store.annotationStore.selected) {{
                var results = store.annotationStore.selected.results;
                var points = [];
                var W = {width};
                var H = {height};
                
                results.forEach(function(r) {{
                    if (r.type === 'keypointlabels' && r.value) {{
                        var px = r.value.x * W / 100;
                        var py = r.value.y * H / 100;
                        points.push({{ x: px, y: py }});
                    }}
                }});

                if(points.length === 0) {{
                    alert('No points found!');
                    return;
                }}

                // Pairing logic
                points.sort(function(a, b) {{ return a.x - b.x; }});
                var paired = [];
                var used = new Array(points.length).fill(false);
                var threshold = W * 0.05; 

                for (var i = 0; i < points.length; i++) {{
                    if (used[i]) continue;
                    var bestJ = -1;
                    for (var j = i + 1; j < points.length; j++) {{
                        if (!used[j] && Math.abs(points[j].x - points[i].x) < threshold) {{
                            bestJ = j;
                            break;
                        }}
                    }}
                    if (bestJ !== -1) {{
                        used[i] = true; used[j] = true;
                        var p1 = points[i]; var p2 = points[bestJ];
                        paired.push({{ 
                            x: (p1.x + p2.x)/2, 
                            y_ceiling: Math.min(p1.y, p2.y), 
                            y_floor: Math.max(p1.y, p2.y) 
                        }});
                    }}
                }}
                
                // Send to iframe
                iframe.contentWindow.postMessage({{
                    type: 'update_layout',
                    corners: paired,
                    width: W,
                    height: H
                }}, '*');
                
            }} else {{
                alert('Cannot find Label Studio data. Make sure you are in labeling mode.');
            }}
        }})()
    ">🔄 Refresh 3D View</button>
    <span style="font-size: 12px; color: #666;">(Click after modifying 2D points)</span>
</div>
"""

def _join_url(base_url, suffix):
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def create_import_json(
    output_json,
    layout_txt_dir,
    image_dir_rel,
    image_ext,
    legacy_base_url,
    image_base_url,
    vis_base_url,
    disable_vis3d=False,
):
    tasks = []
    
    # 1. 查找 output/mp3d_layout/... 下的所有 txt 文件
    txt_pattern = os.path.join(layout_txt_dir, "*.txt")
    txt_files = glob.glob(txt_pattern)
    
    print(f"Found {len(txt_files)} TXT files in {layout_txt_dir}")

    for idx, txt_file in enumerate(txt_files):
        try:
            # 读取 txt 内容
            # 格式: x y (每行一个点, 顺序: Ceiling0, Floor0, Ceiling1, Floor1, ...)
            with open(txt_file, 'r') as f:
                lines = [l.strip().split() for l in f if l.strip()]
            
            if not lines:
                continue

            # 解析坐标
            coords = [] # [(x, y), ...]
            for l in lines:
                coords.append((float(l[0]), float(l[1])))
            
            # 构造 Label Studio Predictions
            predictions = []
            result = []
            
            # 1. KeyPoints (所有角点)
            for i, (x, y) in enumerate(coords):
                result.append({
                    "id": f"kp_{i}",
                    "from_name": "kp", # 对应 Label Studio XML 中的 KeyPointLabels name
                    "to_name": "img",
                    "type": "keypointlabels",
                    "original_width": W,
                    "original_height": H,
                    "value": {
                        "x": x / W * 100,
                        "y": y / H * 100,
                        "width": 0.5, # 点的大小
                        "keypointlabels": ["Corner"]
                    }
                })

            # 2. Polygon (墙面轮廓)
            # HoHoNet 输出顺序是 [C0, F0, C1, F1, ...]
            # 我们需要构建一个闭合多边形: C0 -> C1 -> ... -> Cn -> Fn -> ... -> F1 -> F0
            ceil_pts = coords[0::2] # 偶数索引: 天花板点
            floor_pts = coords[1::2] # 奇数索引: 地板点
            
            # 按照 x 排序 (HoHoNet 输出通常已经排序，但为了保险)
            pairs = list(zip(ceil_pts, floor_pts))
            pairs.sort(key=lambda p: p[0][0]) # 按 Ceiling x 排序
            
            sorted_ceil = [p[0] for p in pairs]
            sorted_floor = [p[1] for p in pairs]

            # 插值函数: 在全景图上正确连接两点 (模拟 3D 直线投影)
            def interpolate_points(p1, p2, num_steps=10):
                # p1, p2 are [x, y] in image coordinates
                # Convert to spherical/3D direction
                def to_3d(p):
                    u, v = p[0], p[1]
                    # map u, v to theta, phi
                    # u: 0~W -> -pi ~ pi
                    # v: 0~H -> -pi/2 ~ pi/2
                    lon = (u / W - 0.5) * 2 * np.pi
                    lat = -(v / H - 0.5) * np.pi # distinct from standard definition, check coordinate system
                    # Standard equirectangular:
                    # x = cos(lat) * sin(lon)
                    # y = sin(lat)
                    # z = cos(lat) * cos(lon)
                    # But we need to align with the assumption that walls are straight lines.
                    # Let's assume standard conversion first.
                    x = np.cos(lat) * np.sin(lon)
                    y = np.sin(lat)
                    z = np.cos(lat) * np.cos(lon)
                    return np.array([x, y, z])

                def to_uv(vec):
                    x, y, z = vec
                    norm = np.sqrt(x*x + y*y + z*z)
                    if norm == 0: return [0, 0]
                    x, y, z = x/norm, y/norm, z/norm
                    lat = np.arcsin(y)
                    lon = np.arctan2(x, z)
                    
                    u = (lon / (2 * np.pi) + 0.5) * W
                    v = (-lat / np.pi + 0.5) * H
                    return [u, v]

                vec1 = to_3d(p1)
                vec2 = to_3d(p2)
                
                # Recover 3D position on a horizontal plane (y=1 or y=-1)
                # We assume ceiling/floor are horizontal planes.
                # If vec[1] (y-component) is 0, it's on horizon, cannot project to plane.
                if abs(vec1[1]) < 1e-6 or abs(vec2[1]) < 1e-6:
                    # Fallback to linear interpolation in 2D if points are on horizon (unlikely for ceiling/floor)
                    return np.linspace(p1, p2, num_steps, endpoint=False).tolist()

                # Project to y=1 plane (for ceiling) or y=-1 (for floor)
                # Actually sign doesn't matter as long as we are consistent
                # P = vec / |vec.y|
                P1 = vec1 / abs(vec1[1])
                P2 = vec2 / abs(vec2[1])

                new_points = []
                for t in np.linspace(0, 1, num_steps, endpoint=False):
                    Pt = P1 * (1 - t) + P2 * t
                    uv = to_uv(Pt)
                    new_points.append(uv)
                return new_points

            # 构建插值后的多边形
            dense_poly_points = []
            
            # Ceiling: C0 -> C1 -> ... -> Cn
            for i in range(len(sorted_ceil)):
                p_curr = sorted_ceil[i]
                p_next = sorted_ceil[(i + 1) % len(sorted_ceil)]
                
                # Check for boundary crossing (e.g. x goes from 1000 to 10)
                if abs(p_curr[0] - p_next[0]) > W / 2:
                    # Boundary crossing, do not interpolate or handle specially
                    # For now, just add current point. 
                    # In valid layout, the last point connects to first point usually via boundary.
                    # But Label Studio polygon is a single closed loop.
                    # If we just add points, it will draw a line across the image.
                    # We'll just add the point itself.
                    dense_poly_points.append(p_curr)
                else:
                    # Interpolate to next point
                    # Only interpolate if it's not the last segment connecting back to start (which might be across image)
                    if i < len(sorted_ceil) - 1:
                        pts = interpolate_points(p_curr, p_next)
                        dense_poly_points.extend(pts)
                    else:
                        # Last point connecting to first point. 
                        # If they are far apart (boundary), don't interpolate.
                        if abs(p_curr[0] - p_next[0]) < W / 2:
                             pts = interpolate_points(p_curr, p_next)
                             dense_poly_points.extend(pts)
                        else:
                             dense_poly_points.append(p_curr)

            # Floor: Fn -> ... -> F1 -> F0 (Reverse order)
            # We need to connect from last Ceiling point to last Floor point (Vertical wall)
            # Then traverse Floor points in reverse
            
            # Vertical connection (Ceiling Last -> Floor Last) is straight in 2D (same x), no need to interpolate much
            
            reversed_floor = sorted_floor[::-1]
            for i in range(len(reversed_floor)):
                p_curr = reversed_floor[i]
                p_next = reversed_floor[(i + 1) % len(reversed_floor)]
                
                if abs(p_curr[0] - p_next[0]) > W / 2:
                    dense_poly_points.append(p_curr)
                else:
                    if i < len(reversed_floor) - 1:
                        pts = interpolate_points(p_curr, p_next)
                        dense_poly_points.extend(pts)
                    else:
                        if abs(p_curr[0] - p_next[0]) < W / 2:
                             pts = interpolate_points(p_curr, p_next)
                             dense_poly_points.extend(pts)
                        else:
                             dense_poly_points.append(p_curr)

            # 转换为百分比
            poly_points_pct = [[p[0]/W*100, p[1]/H*100] for p in dense_poly_points]
            
            result.append({
                "id": "poly_1",
                "from_name": "poly", # 对应 Label Studio XML 中的 PolygonLabels name
                "to_name": "img",
                "type": "polygonlabels",
                "original_width": W,
                "original_height": H,
                "value": {
                    "points": poly_points_pct,
                    "polygonlabels": ["Wall"]
                }
            })

            predictions.append({
                "model_version": "HoHoNet_v1",
                "score": 0.99,
                "result": result
            })

            # 构造 3D View URL 数据
            # 需要传递给 vis_3d.html 的格式: [{x, y_ceiling, y_floor}, ...]
            vis_corners = []
            for c, f in pairs:
                vis_corners.append({
                    "x": c[0],
                    "y_ceiling": c[1],
                    "y_floor": f[1]
                })
            
            corners_json = json.dumps(vis_corners)
            encoded_data = urllib.parse.quote(corners_json)
            iframe_url = ""
            if not disable_vis3d and vis_base_url:
                iframe_url = _join_url(vis_base_url, f"tools/vis_3d.html?w={W}&h={H}&data={encoded_data}")

            # 获取图片文件名
            # txt 文件名: ID_hash.txt -> 图片文件名: ID_hash.<ext>
            basename = os.path.basename(txt_file).replace('.txt', image_ext)
            if image_base_url:
                img_url = _join_url(image_base_url, basename)
            else:
                img_url = _join_url(legacy_base_url, f"{image_dir_rel}/{basename}")

            task = {
                "data": {
                    "image": img_url,
                    "vis_3d": iframe_url,
                    "title": basename
                },
                "predictions": predictions
            }
            tasks.append(task)
            
        except Exception as e:
            print(f"Error processing {txt_file}: {e}")

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, indent=2)
    
    print(f"生成了 {len(tasks)} 个任务到 {output_json}")
    print(f"请确保在 Label Studio 项目配置中包含:")
    print(f"<KeyPointLabels name=\"kp\" toName=\"img\">...</KeyPointLabels>")
    print(f"<PolygonLabels name=\"poly\" toName=\"img\">...</PolygonLabels>")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Label Studio import JSON for MP3D layout tasks.")
    parser.add_argument("--output-json", default=OUTPUT_JSON, help="Output JSON file path.")
    parser.add_argument("--layout-txt-dir", default=LAYOUT_TXT_DIR, help="Directory with HoHoNet .txt predictions.")
    parser.add_argument("--image-dir-rel", default=IMAGE_DIR_REL, help="Relative image path for legacy base URL mode.")
    parser.add_argument("--image-ext", default=".png", help="Image extension used to build image filename, e.g. .png or .jpg")
    parser.add_argument("--legacy-base-url", default=DEFAULT_BASE_URL, help="Legacy static server base URL.")
    parser.add_argument("--image-base-url", default=DEFAULT_IMAGE_BASE_URL, help="COS/CDN image prefix URL ending at image directory.")
    parser.add_argument("--vis-base-url", default=DEFAULT_VIS_BASE_URL, help="Base URL serving tools/vis_3d.html.")
    parser.add_argument("--disable-vis3d", action="store_true", help="Do not generate vis_3d URL field.")
    args = parser.parse_args()

    print("[Config]")
    print(f"  output_json    : {args.output_json}")
    print(f"  layout_txt_dir : {args.layout_txt_dir}")
    print(f"  image_ext      : {args.image_ext}")
    print(f"  image_base_url : {args.image_base_url or '(legacy mode)'}")
    print(f"  vis_base_url   : {args.vis_base_url or '(disabled)'}")

    create_import_json(
        output_json=args.output_json,
        layout_txt_dir=args.layout_txt_dir,
        image_dir_rel=args.image_dir_rel,
        image_ext=args.image_ext,
        legacy_base_url=args.legacy_base_url,
        image_base_url=args.image_base_url,
        vis_base_url=args.vis_base_url,
        disable_vis3d=args.disable_vis3d,
    )
