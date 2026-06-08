import json
import os
import argparse
import numpy as np
import cv2
from collections import defaultdict
from shapely.geometry import Polygon

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def extract_corners(result, width, height):
    """提取并配对角点"""
    corners = []
    for r in result:
        if r.get('type') in ['keypointlabels', 'keypointregion']:
            val = r.get('value', {})
            x = val.get('x')
            y = val.get('y')
            if x is not None and y is not None:
                corners.append({
                    'x': x * width / 100.0,
                    'y': y * height / 100.0
                })
    
    # 配对逻辑 (简化版 HoHoNet 逻辑)
    # 1. 按 x 排序
    corners.sort(key=lambda p: p['x'])
    
    paired_columns = []
    used = [False] * len(corners)
    threshold = width * 0.02 # 2% 宽度的容差
    
    for i in range(len(corners)):
        if used[i]: continue
        
        # 找同一列的另一个点
        best_j = -1
        min_diff = float('inf')
        
        for j in range(i + 1, len(corners)):
            if used[j]: continue
            diff = abs(corners[j]['x'] - corners[i]['x'])
            if diff < threshold:
                if diff < min_diff:
                    min_diff = diff
                    best_j = j
        
        if best_j != -1:
            used[i] = True
            used[best_j] = True
            p1 = corners[i]
            p2 = corners[best_j]
            
            # 确定哪个是天花板，哪个是地板
            # y 越小越靠上 (Ceiling)，越大越靠下 (Floor)
            y_ceil = min(p1['y'], p2['y'])
            y_floor = max(p1['y'], p2['y'])
            avg_x = (p1['x'] + p2['x']) / 2
            
            paired_columns.append([avg_x, y_ceil, y_floor])
            
    return sorted(paired_columns, key=lambda x: x[0])

def draw_masks(result, width, height):
    """绘制语义分割 Mask"""
    # 0: Background, 1: Wall
    mask = np.zeros((height, width), dtype=np.uint8)
    
    polygons = []
    for r in result:
        if r.get('type') in ['polygonlabels', 'polygonregion']:
            val = r.get('value', {})
            points = val.get('points', [])
            if points:
                # 转换坐标
                pts = np.array([[p[0] * width / 100.0, p[1] * height / 100.0] for p in points], dtype=np.int32)
                polygons.append(pts)
                
                # 填充多边形 (Wall = 1)
                cv2.fillPoly(mask, [pts], color=1)
                
    return mask

def main():
    parser = argparse.ArgumentParser(description="Convert Label Studio JSON to Dual-Stream Dataset")
    parser.add_argument('json_file', help="Path to Label Studio JSON export")
    parser.add_argument('--out_dir', default="data/dual_stream_data", help="Output directory")
    args = parser.parse_args()

    # 目录结构
    # data/dual_stream_data/
    #   layout_txt/  (HoHoNet 格式: x y_ceil y_floor)
    #   semantic_mask/ (PNG 图像)
    #   vis/ (可视化检查)
    
    dir_layout = os.path.join(args.out_dir, "layout_txt")
    dir_sem = os.path.join(args.out_dir, "semantic_mask")
    dir_vis = os.path.join(args.out_dir, "vis")
    
    ensure_dir(dir_layout)
    ensure_dir(dir_sem)
    ensure_dir(dir_vis)
    
    print(f"Loading {args.json_file}...")
    with open(args.json_file, 'r', encoding='utf-8') as f:
        tasks = json.load(f)
        if isinstance(tasks, dict): tasks = [tasks]

    count = 0
    for task in tasks:
        # 获取文件名 (从 data.image url 中提取)
        img_url = task['data'].get('image', '')
        if not img_url: continue
        
        # 提取文件名: "http://.../img/abc.png" -> "abc"
        basename = os.path.splitext(os.path.basename(img_url))[0]
        
        # 获取最新的标注
        anns = task.get('annotations', [])
        if not anns: continue
        ann = anns[0] # 假设第一个是最新的，或者根据 updated_at 排序
        
        result = ann.get('result', [])
        
        # 1. 处理 Layout (Corners)
        # 假设图像尺寸 1024x512 (HoHoNet 标准)
        W, H = 1024, 512
        columns = extract_corners(result, W, H)
        
        if len(columns) < 2:
            print(f"Skipping {basename}: Not enough corners paired.")
            # 即使没有配对成功的角点，如果有 Mask 也应该保存 Mask？
            # 为了双流训练，最好两者都有。
        
        # 保存 Layout TXT
        # 格式: 每行一个角点 x y (HoHoNet 原始格式通常是 x y_ceil, x y_floor 交替，或者 x y_ceil y_floor)
        # 这里我们保存为: x y_ceil y_floor，方便后续 DataLoader 读取
        txt_path = os.path.join(dir_layout, f"{basename}.txt")
        with open(txt_path, 'w') as f_txt:
            for col in columns:
                f_txt.write(f"{col[0]:.2f} {col[1]:.2f} {col[2]:.2f}\n")
                
        # 2. 处理 Semantic (Masks)
        mask = draw_masks(result, W, H)
        mask_path = os.path.join(dir_sem, f"{basename}.png")
        # 保存为 8-bit PNG (0, 1, 2...)
        # 为了可视化方便，我们也可以保存一份乘以 50 的版本在 vis 里，但训练数据要原始 ID
        cv2.imwrite(mask_path, mask)
        
        # 3. 可视化验证
        vis_img = np.zeros((H, W, 3), dtype=np.uint8)
        # 绘制 Mask (绿色通道)
        vis_img[:, :, 1] = mask * 100 
        
        # 绘制 Layout 线条 (红色)
        for i in range(len(columns)):
            curr = columns[i]
            next_col = columns[(i + 1) % len(columns)]
            
            pt1_ceil = (int(curr[0]), int(curr[1]))
            pt1_floor = (int(curr[0]), int(curr[2]))
            pt2_ceil = (int(next_col[0]), int(next_col[1]))
            pt2_floor = (int(next_col[0]), int(next_col[2]))
            
            # 垂直线
            cv2.line(vis_img, pt1_ceil, pt1_floor, (0, 0, 255), 2)
            # 天花板线
            cv2.line(vis_img, pt1_ceil, pt2_ceil, (0, 0, 255), 2)
            # 地板线
            cv2.line(vis_img, pt1_floor, pt2_floor, (0, 0, 255), 2)
            
        vis_path = os.path.join(dir_vis, f"{basename}_vis.jpg")
        cv2.imwrite(vis_path, vis_img)
        
        count += 1
        
    print(f"Successfully processed {count} tasks.")
    print(f"Output directory: {args.out_dir}")

if __name__ == "__main__":
    main()
