# 返回研究包与权威 Stage2 快照的独立对照

核验时间：2026-09-30 UTC。权威对象仅为 Sparkling-Flames/3D_Manhattan_label 的提交 `10a0fe54608f62668f73d705d6a0cf50a9179f21` 内 `research/pro_layout_metric_response_20261001`，不是根目录历史实现，也不是 `pro_layout_20260929`。

## 结论

返回包的“独立重实现＋摘录”说明准确。现有数值有可靠原始对照支持，不能只因没有复用原源码就判为不可信。此次补核完成原官方嵌入验证（74 合成、15 真实、9 缺参考、1 个加密边界诊断），原快照的 4 项测试也通过。返回包交付的 77 行主要指标与权威结果全部吻合；把返回核心额外用于原快照全部 15 项真实比较，也未发现共同数值指标的实质偏差。

需要分清两项限制：

1. 返回核心不是原输入／身份／错误状态协议的可直接替换实现。已构造 8 个边界反例，存在非法坐标产出正常数值、未知 phase 默认为 C、身份不校验等行为。返回报告已明确不承诺替代这些协议，因此这是后续接入的修复关口，不能反推现有合法输入上的实验失效。
2. 权威快照本身有发布库存缺件：MANIFEST 声称包含 63 字节 `requirements.txt`，但该提交目录没有这个文件。严格官方入口因此报 `bundle_inventory_mismatch`。这是原快照的打包缺陷，不是返回包的问题；本核验没有补造文件来制造全通过。

## 1. 来源取得与真实性

先阅读 README、研究方向、坐标来源说明、机器合同及字段合同，再检查算法。通过 GitHub 阅读接口取得限定目录中的 28 个文件（含 MANIFEST、嵌入结果、相关源码／测试、4 张图）；全部按 Git blob 规则 `SHA1("blob <bytes>\0"+bytes)` 校验，与 API 返回的 blob SHA 完全相同；同时生成 SHA-256 清单。原始换行与 BOM 被保留，所有实际存在的清单文件字节数也相符。

没有克隆全仓库、下载原图、原始身份映射或原始评论。额外读取的唯一外部代码来源为坐标说明直接引用的 HoHoNet 官方数据准备文档，用于核查 GT 生产公式。

主要源文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| README.md | `914008f71aef53e7bd0d5adb8e79f7027dd3a619467f64206f064d92d3dc5387` |
| MANIFEST.json | `489a9f4b4361ac5e8d54b4b5006cb8019e1c989038ad1a38f5cff5f31c5adefa` |
| 嵌入 results.json | `ae5d7f0f024d03d37621409d96119a7111b91685039ff00e34a0cb4ee51376fe` |
| 官方复算入口 | `dc2867bab12e205ff07054a20ebd2fefe1d033ff7c14e69bb5c9eeb0f802ec1a` |
| 当前指标编排源码 | `842a145edcf2abd9c841ee9f5c40861af17235f795acd9e11e2be517b172b616` |

完整逐文件来源、Git blob SHA 与 SHA-256 见 `source_hashes.json`。

## 2. 原验证缺口此次补到了哪里

| 核验 | 实际结果 | 解释 |
|---|---|---|
| 严格原 `verify_layout_metric_snapshot_20261001` 命令 | 库存检查失败 | 唯一缺文件是 requirements.txt；没有额外文件或错误大小 |
| 未改动官方 `verify_embedded` | 通过 | 74 合成全部指标、状态、原因、重建诊断；15 真实完整比较；9 缺参考 null/状态；8192 点加密诊断 |
| 原快照 pytest | 4 passed | 只指快照自带的两份测试文件，不是整仓库全部测试 |
| PLAN 与实验计划 JSON | 完全相同 | 使用原比较函数 |
| 合成 CSV 与字段合同／嵌入结果 | 74 行×59 列全部匹配 | 按原 `_flat` 与原序列化规则逐字段检查 |
| 真实 CSV 与字段合同／嵌入结果 | 24 行×58 列全部匹配 | 包含缺参考行 |

官方浮点容差为相对 `1e-9`、绝对 `1e-10`；身份、字段、整数像素及状态严格比较。上游选样和源表绑定仍未重建，原图内容、GT 视觉正确性和人员资格仍未重新裁定。快照本来就不包含足以独立复核这些事项的全量输入。

补核使“未验证全部原始嵌入结果”的数值覆盖缺口得到补充，但不把返回包变成全量官方协议实现，也没有增加新真人或多人方法效果证据。

## 3. 输入摘录是否忠实

### 三张真实图

下列 6 份记录的全部点坐标、数组环序、点对源索引、记录 ID、人员别名（适用时）及环确认状态都与原嵌入对象相符；浮点坐标是逐值完全相同，而非近似比较。

| 图片 | 人员记录 | 原始参考 | 点对数 a/b |
|---|---|---|---|
| jtcxE69GiFV-12 | R03398 | R02614 | 7 / 6 |
| yqstnuAEVhm-31 | R00236 | R02780 | 7 / 8 |
| 7y3sRwLe3Va-12 | R00705 | R02512 | 8 / 6 |

三个 a 都是已确认人员环，三个 b 都是未人工确认的原始 GT 环；不是同图多名人员作答。原完整面板核对为 12 张图、每图 1 个选中人员记录，24 个参考版本行，其中 12 个原始参考＋3 个人工修订参考可比较，9 个人工修订参考缺失。15 次比较不等于 15 个独立人员样本。

摘录确有元数据缩减：人员审核／资格 gate、场景、完整点标签等未复制；参考的 `version` 等也未复制。三份参考原本的 `source_point_indices=[0,…,2n−1]` 被写成 null，而不是逐字段保留。记录 ID、点对索引和顺序仍足以对照本次计算，但建议下版恢复参考源点索引及版本，避免把“来源保留”误读为完整证据链。这些摘录不可直接当人员质量分析入口。

### 74 个合成对照

74 组 family/case/amplitude、点数、点序和 C/P 声明相符。148 个 a/b 侧中 143 个坐标数组逐值相同，其余 5 侧的最大差为 `1.1368683772161603e-13` 像素，属于独立投影公式的浮点舍入。

20 侧把说明性合成标签改名，如 south_midpoint/east_midpoint 变为 mid、detail_start 变为 start；逐对检验的 a/b 身份相等关系完全不变。这是有意转写，不能称字节级或完整身份字符串的副本，也没有证据显示造成对应关系错误。返回输入还省略了原 amplitude_unit 等非计算字段。

## 4. 核心公式及数值的直接交叉验证

两套代码在当前有效输入上使用相同的共同相机框架：Y 向上、floor Y=−1、长度单位 h、连续坐标射线或显式 P→C 偏移；不分别对齐 layout。BEV 使用声明底环精确交并／面积质心；边界以每侧 512 等弧长样本到对方连续边界的距离计算；列式墙带按输出像素中心方向，选择声明底环最近正射线交点，并在对应边线性插值墙顶高度。这些均不是未知真实屋顶体积的估计。

交叉核验结果：

- 直接将原快照 74 合成＋15 真实输入交给返回实现，共 89 组，1228 个可用共同数值字段全在原容差内
- 356 个“记录侧×ERP尺寸”mask 条件中，352 个可计算，逐像素完全一致；另 4 个两边都不可计算
- 交付 CSV 的 74 合成＋3 真实共 77 行，1060 个可用共同字段同样全在容差内
- 两种分辨率的列式 IoU 与差异像素计数均精确相等
- 最大 BEV IoU 差为 `5.56e-16`；最大面积差 `9.10e-13 h²`；最大边界 sampled-max 差 `2.85e-14 h`

这里“共同字段”指返回包确实输出的 BEV IoU、双方面积／coverage、质心、边界 pooled mean/p95/sampled max及采样上界、两种ERP IoU和差异像素。返回包没有完整复刻原对称差面积、边界方向均值／步长、mask面积、合成身份RMSE、原Manhattan诊断、全部状态和元数据；不要把此次共同字段一致扩写成“返回实现所有字段与原协议一致”。

## 5. 已复现的边界协议差异

反例均从原快照的有效四角基准复制，仅作下列指定更改。索引从 0 开始；这些是审计构造的非法／边界输入，不是返回包已有实验输入。

| 更改 | 原实现 | 返回实现 |
|---|---|---|
| `points[0][1]=NaN`（第一 top 的 y） | invalid_point_array，BEV/墙带 N/A | BEV=1；1024墙带IoU=0.5 |
| `points[0][1]=−1` | 越界，BEV/墙带 N/A | BEV=1；墙带≈0.705586 |
| `points[0][1]=0`（top 极点） | BEV=1；墙带 pole_ray/N/A | 墙带≈0.700270 |
| 两个 source_pair_indices 重复 | invalid_source_pair_identity | BEV=墙带=1 |
| coordinate_convention=unknown | 明确 ValueError | 当 continuous 接受，BEV=墙带=1 |
| 第一 top/bottom 的 x 同加1024，超过声明图像界 | 越界，BEV/墙带 N/A | 周期射线给正常值 |
| points=None | pairing_unavailable/N/A | reshape异常 |
| 删除最后一个点，变奇数端点 | invalid_point_array/N/A | reshape异常 |

建议在正式接入前复用／恢复原完整记录校验、phase枚举、身份唯一性、pole_ray和状态传播；随后将这些反例作为 fail-closed 测试。此问题与多数、分簇或局部匹配有效性是不同层面，不应借它否定当前已对照通过的主要数值。

## 6. 当前 C 坐标声明是否站得住

当前快照不是旧版“GT来源phase未知”的状态。README、机器合同和坐标来源说明明确记录：259 份本地原始 GT 与官方 JSON、官方生产公式按两位小数（含原行序）逐项核对一致，从而将这一批原始 GT 的生产坐标确定为 C。返回报告对此的陈述符合这份权威快照。

此次独立查看 HoHoNet 官方准备文档，确认公式为 x=1024u，y=512(1/2−纬度/π)，没有 −0.5，并交替保存 top/bottom、两位小数。这个公式确实是连续坐标。官方文档记录的 Git blob 为 `c636fb4c01cdc114e6b0faeb296310e746c71494`。

证据层级不能混写：本次检查了快照的来源记录及官方生产代码，没有重新取全量 259 GT 和原始 JSON 重做逐值绑定。因此“259全匹配”是原快照已记录的上游核验结果，而本轮独立重算范围是打包嵌入输入。C 生产phase也不证明实际 ERP 批次采样、skybox面序、重力调平、真实尺度或历史 LS 初始化phase；原文保留这些限制，返回报告没有证据将它们抹掉。

## 7. 复现文件与命令

- `compare_original.py`：完整只读交叉检查；再次运行会写本审计结果，不改原快照或返回包
- `comparison_summary.json`：输入差异、计数、原CSV检查、数值摘要、8个边界反例
- `cross_implementation_details.json`：89组数值与356项mask逐项检查
- `source_hashes.json`：28个固定提交源文件的URL、Git blob SHA、SHA-256及字节数
- `strict_validator.log`、`original_embedded.log`、`original_pytest.log`：原入口／子入口／测试的实际输出

运行环境：Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、Shapely 2.1.2、GEOS 3.13.1，测试使用 pytest 9.1.1。原／返回方法无需 GPU。依赖目录只读共享，pytest安装于单独目录。

从本审计目录执行：

```sh
PYTHONPATH=../audit-oct1-deps python -B compare_original.py
cd ../audit-oct1-original
PYTHONPATH=../audit-oct1-deps:../audit-oct1-testdeps python -B -m pytest tests -q -p no:cacheprovider -W error::RuntimeWarning
PYTHONPATH=../audit-oct1-deps python -B -m tools.thesis_main.analysis.verify_layout_metric_snapshot_20261001
```

最后一条仍应因公开快照缺 requirements.txt 而失败；不要把前两项通过表述成严格库存入口通过。

目录结构变化时，比较脚本也接受 `--original <原快照目录> --returned <返回包目录> --out <审计输出目录>`，不依赖本机绝对路径。

## 权威链接

- [本轮快照 README](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/10a0fe54608f62668f73d705d6a0cf50a9179f21/research/pro_layout_metric_response_20261001/README.md)
- [固定提交 MANIFEST](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/10a0fe54608f62668f73d705d6a0cf50a9179f21/research/pro_layout_metric_response_20261001/MANIFEST.json)
- [官方嵌入结果](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/10a0fe54608f62668f73d705d6a0cf50a9179f21/research/pro_layout_metric_response_20261001/analysis_results/layout_metric_response_20261001/results.json)
- [官方当前编排与 measure](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/10a0fe54608f62668f73d705d6a0cf50a9179f21/research/pro_layout_metric_response_20261001/tools/thesis_main/analysis/layout_metric_response_20261001.py)
- [坐标生产与实际来源证据](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/10a0fe54608f62668f73d705d6a0cf50a9179f21/research/pro_layout_metric_response_20261001/docs/thesis_main/布局表示地基与坐标核验_20260930.md)
- [HoHoNet 官方 GT 转换公式](https://github.com/sunset1995/HoHoNet/blob/master/README_prepare_data_mp3d_layout.md)
