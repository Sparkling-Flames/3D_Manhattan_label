# 离线复现与数据身份

## 1. 先合并结果包

六个ZIP都保留研究根 `HOHONET_v21_full_chain_20261030/`。解压到同一父目录。`source/`保存当前与v2对照所需源表、冻结引擎；每个stage保存最低输入、精确成员/端点及汇总。没有完整旧21GB仓库仍可从随包缓存重聚合。

`ENVIRONMENT_LOCK.json`记录实际Python、NumPy、pandas、SciPy、Shapely、matplotlib、Pillow、scikit-learn版本及来源提交。`requirements.txt`给出这些运行依赖版本。本轮没有重新拟合分类。图表字体如本机无中文字体，可安装Noto Sans CJK；这不改变任何科学表格或保存几何。

## 2. 汇总与案例的推荐重建顺序

```bash
python scripts/prepare_half_team.py
python scripts/complete_half_traces.py
python scripts/analyze_half_mechanisms.py
python scripts/finalize_half_report.py
python scripts/build_half_case_viewer.py
node scripts/validate_half_viewer.js
```

半队已提供全部348轨迹。`complete_half_traces.py`发现本地完整文件时只验证；旧仓库缓存只是可选来源。837个精确选取标量即为最小输入，没有旧三大端点包时使用随包 `SAVED_ENDPOINT_SCALARS.csv.gz`。原图均已完整保存，`fetch_half_originals.py`先本地校验，缺失才定点请求公开release字节范围。

同房复现命令详见 `stage02_same_room/README.md`。优先使用完整已有事件、状态、几何及84案例缓存；`same_room_extract_events.py`等是可选一次性采集器，缓存齐全不需要旧Git对象库。`MINIMUM_REPRODUCTION_INPUTS.csv`给出34项精确输入。

快慢人员复现与31项指标在 `stage03_speed_difficulty/README.md`。主脚本为 `scripts/speed_difficulty.py`、`speed_difficulty_explain.py`、`report_speed_difficulty.py`。输入是已有合法原答结构、当前Q、楼外Q/T与冻结类标签；不触发新融合或评分。

选队停止从现成端点重汇总可直接运行：

```bash
python scripts/selection_stop_analyze.py all
python scripts/selection_stop_validate.py
python scripts/selection_stop_finalize.py
python scripts/selection_stop_report.py
```

若确需从设计重新生成端点，先 `selection_stop_prepare.py`，再 `selection_stop_endpoints.py plan` 与 `run --jobs 4`。随包25,826完整端点已经齐全，通常不必重新融合。停止原顺序及124,924条前缀保持不变，仅按request_id应用受影响参考补丁。

## 3. 追溯和验证

每个方法、条件、空间、来源、人数、替换块和事件阶段保留字段。最短追溯路径为：正文→`V2_TO_V21_CROSSWALK.csv`的精确源表/筛选→逐图/图对→逐事件→team_key/原答object_id→参考/楼外标签。原样保存的源文件与新输出分目录，不把旧结果换个版本标签。

`scripts/package_delivery.py`生成阶段ZIP与逐文件SHA256，并读取每个成员到结尾，核查内层gzip、JSON/JSONL、CSV列数及图像解码。HTML全组合执行验证用Node VM模拟DOM/Canvas；真实浏览器验收另用Chrome 156检查四个页面的脚本、原图、画布、版式与中文截图。两项验证分开记录在相应阶段回执及stage06_synthesis/browser_acceptance/BROWSER_EXECUTION_CHECKS.json中。

`repository_update/apply_update.py`默认只检查。应用之前需读取本地仓库自身的AGENTS.md，并按说明传入本研究目录。脚本会检查原文件字节与导入文件冲突；不会覆盖并行改动。当前会话未直接修改Windows仓库或推送远端。

## 中文图形再生成

全部成品图与案例页面已经随包提供。重新生成静态中文图时，脚本优先使用 `HOHONET_CJK_FONT` 指定的字体文件，再查找Noto Sans CJK SC、Microsoft YaHei等系统中文字体；数值、几何与票账重聚合不依赖字体或浏览器。
