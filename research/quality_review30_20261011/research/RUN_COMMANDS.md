# 云端运行与验收入口

在独立云端目录运行，不使用用户本地电脑执行数据整理/计算。所有来源只读；最终用户页供人工填写。

1. 将既有完整云端计算工件解压为`cloud_compute`，包含results/inputs和blind_sample；解压本目录`results/selected_original_photos_private.zip`为`photo_input`（其下有originals）。
2. 若只核对选样，执行：

```bash
python code/freeze_selection.py --frozen-root /path/to/cloud_compute --photo-root /path/to/photo_input/originals --out /path/to/selection_replay
```

比较selection_private.json/csv、boundary_coverage_private.json和selection_audit.json：交付版重跑逐字节相同。清单JSON SHA256固定`bf1c3265184fe21d313c96415c80741a65ce6f531f1141aa7ff79ea1e40d2bf8`。

3. 完整渲染入口（代码与results处在同一个研究目录；已冻结清单/几何/顺序需完整）：

```bash
python code/freeze_display_order.py
MPLCONFIGDIR=/tmp/quality_review30_mpl python code/render_review30.py --photo-root /path/to/photo_input/originals
python code/build_review30_page.py
```

种子2026101130，发现已冻结不同顺序时拒绝覆盖。此步骤不重算Q、不改选择、不产生B top。

4. 用户ZIP内已有user目录。如只测试交付页面，将ZIP解压在一个独立研究副本根目录，而不是覆盖旧8例。测试脚本参数：

```bash
python code/test_review30_receipt.py --review-root /path/to/review30_copy --old-user /path/to/old8_user
```

review-root中须有user目录及results/receipt_schema_anonymous.json。old-user是旧8例ZIP解压后的user目录，只读旧responses.json/csv检验拒绝；不会写入它。测试使用预装/usr/bin/chromium和Python Playwright，本地回环HTTP，无外部服务或浏览器下载。该云端环境阻止file://，不声称验证Windows双击路径。

5. 测试通过后打包：

```bash
python code/package_final_review30.py --review-root /path/to/review30_copy
```

其校验选样哈希、30唯一/成对分离、默认空白、图片哈希、同图尺度、用户数据去身份及14组测试结果，然后输出两个互相独立的ZIP。复打包保留固定ZIP条目时间以便哈希比较。所有测试合成回答仅存在临时浏览器上下文。

环境：Python版本及numpy 2.3.5、matplotlib 3.10.8、Pillow 12.3.0、playwright 1.62.0、字体SHA及具体图像/回执参数见results/render_and_receipt_parameters.json。选样使用冻结数值结果；新的适配与Pro/官方IoU原件分开保存。
