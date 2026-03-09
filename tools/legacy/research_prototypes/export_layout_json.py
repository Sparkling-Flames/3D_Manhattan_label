import glob, json, os
from PIL import Image
import numpy as np
# ========== 以下是必须补加的代码（放在脚本第1行开始）==========
import argparse  # 解析命令行参数
import glob
import os
import json
from PIL import Image  # 如果你需要读图片尺寸，必须导入
import yaml  # 解析--cfg配置文件（和你命令中的--cfg对应）

# 解析命令行参数（和你命令中的--xxx参数一一对应，一个都不能少）
parser = argparse.ArgumentParser(description="Convert layout txt to JSON")
# 对应你命令中的每个--参数
parser.add_argument("--layout_glob", required=True, help="Glob pattern for txt files")
parser.add_argument("--image_root", required=True, help="Image root directory")
parser.add_argument("--out_dir", required=True, help="Output JSON directory")
parser.add_argument("--source_tag", required=True, help="Source tag for meta")
parser.add_argument("--cfg", required=True, help="Config yaml file")
args = parser.parse_args()  # 这行是核心！定义args变量，让脚本识别命令行参数

for layout_path in glob.glob(args.layout_glob):
    basename = os.path.splitext(os.path.basename(layout_path))[0]
    image_path = os.path.join(args.image_root, f"{basename}.png")
    img = Image.open(image_path)
    W, H = img.size

    cor = np.loadtxt(layout_path, dtype=np.float32)    # shape (2N, 2)
    cor = cor.reshape(-1, 2)
    assert len(cor) % 2 == 0, "layout txt must have even rows"

    corners = []
    for idx in range(0, len(cor), 2):
        corners.append({
            "id": idx // 2,
            "x": float(cor[idx][0]),
            "y_ceiling": float(cor[idx][1]),
            "y_floor": float(cor[idx + 1][1]),
        })

    payload = {
        "image_filename": f"{basename}.png",
        "image_size": [W, H],
        "layout": {
            "corners": corners,
            "num_corners": len(corners),
            "order": "sorted_x_cyclic"
        },
        "meta": {
            "source": args.source_tag,
            "config": args.cfg,
        }
    }

    out_path = os.path.join(args.out_dir, f"{basename}.json")
    json.dump(payload, open(out_path, "w"), indent=2)
