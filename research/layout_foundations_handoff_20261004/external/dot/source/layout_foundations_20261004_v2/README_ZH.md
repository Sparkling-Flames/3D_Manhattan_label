# 连线、质量与全员共识：独立可复算包

冻结仓库：Sparkling-Flames/3D_Manhattan_label @ 080949f5971000a32310d4e4ebf9028dab831a91。

先看 `REPORT_ZH.md` 或 `REPORT_ZH.html`。完整上下点对及来源展示在 `EVIDENCE_VIEWER_ZH.html`（数据内嵌，无远程依赖）。原图没有传入，空白ERP画布不是原始照片。

核心增量：明确ERP墙带投票与BEV投票的阈值对偶；将全员顺序统计曲线按解析事件序列化为完整上下点对；以单独误差预算压缩新表示；用带采样误差说明的声明球面边界距离检验窄事件，并区分高度／体积的假设。

## 复算

依赖版本见 `environment.json`；不必强行降级本地环境。通常需要NumPy、SciPy和Shapely；重建HTML无需浏览器库。绘图另用Matplotlib。

```bash
python -m unittest discover -s tests -v
python run_research.py --out /path/to/NEW_results --stage all
```

也可按 `construct`、`evaluate`、`controls`、`synthetic` 顺序运行；构造阶段不打开隔离GT。`--stage all/construct`拒绝已有非空目录。生成、评价和验算记录全部独立，不写仓库源数据。

## 当前选中人员接口

```bash
python run_local.py --input inputs/real24_points.json --out /path/to/NEW_result.json --epsilon 0.5
```

输入为一个图／同条件／同证据人口的明确records名单。每份记录必须有唯一id、worker、points、independent=true和consensus_eligible=true；人口用`human_observed`或显式`synthetic_control`区分，不混合。顶层必须给出image、condition、evidence_kind（也可每条提供并保持一致）。不进行隐式资格筛选、排序、修点或失败成员删除。

0.5px只是演示预算，不是已校准的人类容差。原型精确结果是配对边界节点，不是认证物理墙角；n=1只表示一份观测。任何当前选中人不满足单值域时，返回全组选中名单及失败，不能使用成功子集替代全体。复杂合法环仍可进行单独BEV研究。

## 本地源输入验收

```bash
python verify_local_inputs.py --repo /path/to/full_repo --out /path/to/NEW_source_check.json
```

该脚本先核对两个固定源文件的Git blob SHA，再逐条核对坐标和来源索引／资格。云端未取得完整源文件，未在完整仓库上执行该命令。部分元数据是计算摘录，所有读取／缺失状态见 `SOURCES_ZH.md`。

## 工件

`results/final/`保存主结果。`real24_fusion.json`含两规则精确点、弧段、节点和来源；`real24_compressed_*.json`为单独压缩副本；`real_quality.csv`与details为预测冻结后的固定原GT评价。`failure_nonmonotone.json`保留当前确认环不适用。`synthetic_validation.csv`、`narrow_feature.json`、`roof_nonidentifiability.json`、`height_coupling.json`是针对性控制。

`logs/tests_final.log`、`logs/final_run.log`、`logs/final_replay.log`和 `results/final_replay_checks.json`记录回归与二次计算。`logs/viewer_checks.json`记录系统Chromium页面检查；这不是用户环境验收。`logs/development_failures.json`保留开发中的数值／环境失败。`MANIFEST.sha256`供文件完整性检查，不代替方法效度。

没有更新GT、源环、资格、正式阈值、人员类型或难度，也没有执行整个仓库测试。该研究包未推送到GitHub。
