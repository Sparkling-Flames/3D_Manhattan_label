# Paper A manuscript migration audit v3

版本日期：2026-07-16  
状态：v5 收口审计；Overleaf-only compile target。  
不回写边界：本审计不修改历史预注册、ROUND_BASED protocol/SOP、SAP v1、assignment、routing、C1 XML、tools、tests、data 或 raw artifacts。

## 1. 兼容性分类

### 完全兼容

- `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)` 与 `P1 -> C1 -> C2 -> T1 -> V1`；
- C2 reserve-only 与两类合法补派理由；
- Calibration-only `R_u`、worker-excluded LOO、T1/V1 隔离；
- RQ3b task/image unit 与 image-level cross-fitting；
- 三状态 `+/-/0/NA` 与 failure outcome `true/false/not_evaluable` 的层次区分。

### 仅分析澄清

- Manual 基础能力与 Semi correction evidence 的角色分离；
- objective task condition、worker Difficulty、task×model Model Issue 三层 map；
- global/family-specific Semi profile 与 support fallback；
- worker-state version、domain、refresh 和 validity 字段；
- counterexample 四层用途和 prevalence 禁止解释。

### Pending implementation / closeout

- formal C1 three-state sidecar 与 thesis-facing evidence ledger；
- formal seam-aware Geometry LOO result 与 integrated (G_u) component；
- online routing evidence table 的正式运行产物；
- RQ3a predictive artifact、C2 frozen worker state 和 RQ3b replay 数值；
- frozen challenge/regression bank 与 future relabel/retraining pool。

### Requires explicit amendment

- 实际执行 C2b-Semi；
- 将动态冗余候选参数写入当前冻结 V1 执行；
- 改变 C2 assignment reason；
- 改写 SAP v1 primary estimand 或将 Semi evidence 回流 primary (R_u)。

## 2. 实现状态核对

当前代码存在三状态、seam-aware Geometry 和 temporal replay 的代码/候选脚手架；这不等于 formal thesis artifact。旧 majority materializer 保留为 legacy descriptive proxy；本次未修改 tools 或 tests。

## 3. 计数与单位核对

P1 eligible=23、C1 launched workers=23、每 worker 约 33 张 manual 任务和 core target (k\approx5) 仍是当前 accounting。P1 Semi planned opportunity 或 (23\times18) 不作为正式独立样本量；结果必须由 closeout registry 报告 planned/received/valid/correction-evaluable 与 task/image support。

## 4. 结构与排版核对

v5 standalone outline 使用 `description` 的独立“名词 + 冒号”条目；active manuscript 将内部五项卡片保留为注释，正文使用自然段。`\\` 只保留在受控的短结构块中；数学符号、下划线和引用需由 Overleaf XeLaTeX 检查。

## 5. 修改前后 SHA-256

| 文件 | 修改前 SHA-256 | 修改后 SHA-256 |
|---|---|---|
| `main.tex` | `7D873A2EC1F093F88C9026024BC8773ED8776B6C3D29B59BF51763F0B581177A` | `B5AAD36697A032110A8C6016044438D49346E18AB398500FA8731AEAA3F3E189` |
| `01_引言.tex` | `8F426196C50D4B4B78A2B68F6303D86C6A47E8CBBCCCFA7D9C7CFAD4DF73E310` | `65D6AAF580E653340710B30A9153C63677EDB9342493F24F463C6B681264C20A` |
| `02_相关工作.tex` | `F3D2F80C03205244DD191B4014DB8E3F80845DB7EEE45445B7E07AD10D6265A9` | `7B0FC1933818E87B8A2B5198051A519DB294ADCEEAD54528067D8D17194216F6` |
| `03_研究协议与数据生命周期.tex` | `D457D46358034D3EF3C57FF2AC1FEE5D2B7ED75A757B6B3C89A94BE26E94C066` | `C999B2E9DEE4093F480820C7D07110CF0224E71A7AC982574AB7CE387DBEB014` |
| `04_测量模型与双链路工人画像.tex` | `B70DF80A6148D7DB08AD2FD27DA9377869A3EC6942FEA735A831544DD65AEF75` | `37C832BB2CDBFBF6F54F66715B75E7E35D41CDE5A4EDE44F878B48B7AF22844A` |
| `05_路由策略与统计分析.tex` | `91D906F0471BD3B169226C6DD5A0196EDF1EC342B6E743954A9B7B24740E9D70` | `AC862D3891356F09860C63BE08D3EDEDEEE09C37163A3E4D7628A9BFEFB0A8E0` |
| `06_实验结果.tex` | `E8F619B6BE742C7A129BEFEFE353234019A73D8E9DB9C73B9A611D160D0CC1CF` | `3C358B81FD4E6A151176A57DC96C89B64F32F37A1E8F64B009937432E196EC8C` |
| `07_讨论与局限.tex` | `D00EEF0CBAC07F4C94EB1F128F1744513BEDA0577319587ADBCEE7A397E39502` | `328E17B7552B3F2276907F25106D5D8422F320B406B6CF792CD17D5838734AD4` |
| `08_结论.tex` | `63C20808B6477FB4D4C35811DE7ABBD5FAB6F3344CD8738E742D7009389C223A` | `2EF9B241D5DF8C33DE1D9E0EEF8E0DD1409F5C7645F288F8DC44E54953875745` |
| `A2_数据集汇总表.tex` | `9C199421D388D037180539E87B7CD268239B83F7E625809D5988EF9AB29B2CC8` | `FE3360794EAA7164EBC7C7CF552F77BD0543AFC49AB86C95722642E5A331738` |
| `A4_测度与统计方法速查.tex` | `1159010216F877210B60D0BE0C986FB56EF863080E2A2DC1DBA09D561D7819B7` | `5A26BC874209B679740C66638A9E85D0F04C5EFF6C5B23A2B1C002E0797BEA35` |

仓库当前没有可用论文 PDF，且本地 `xelatex`、`pdflatex`、`latexmk`、`tectonic` 均缺失；PDF SHA、页数、目录和 broken-reference 状态记为 `unavailable; compile in Overleaf`，不得声称本地编译成功。
