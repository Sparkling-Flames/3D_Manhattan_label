# HOHONET v2.1 全链路下游分析（2026-10-30）

已完成按v2研究链的五项实际下游分析。当前来源提交：`13a7861334749805a86dc19e9ea79fcaa71020c0`。TARGET K3/K2等仅为冻结工作分类，最终选型尚未由用户决定。

## 阅读顺序

1. [中文综合报告](REPORT_ZH.md)；离线排版版为 `REPORT_ZH.html`。
2. [32项v2→v2.1对照](stage06_synthesis/V2_TO_V21_CROSSWALK.csv) 与 [缺口登记](stage06_synthesis/GAP_REGISTER.csv)。
3. [最新半队全部36图与机制](stage01_half_team/README.md)，包括21张对称非正、其他数值反例和局部不可评图。
4. [同房换人、均值、个人预测及构成方差](stage02_same_room/REPORT_ZH.md)。
5. [同类近Q快慢×难度](stage03_speed_difficulty/README.md)。
6. [选队、停止与历史成本](stage05_selection_stop/REPORT_ZH.md)。 四个既定政策案例的原图与完整原答见 [直接查看入口](stage06_synthesis/selection_case_exhibits/index.html)。
7. [复现说明](REPRODUCE.md)、[仓库增量更新及并行保护](repository_update/README_ZH.md)。

## 文件合并与下载

六个研究ZIP（00、01、02A、02B、03、05）保留相同根目录名。将代码/源表/综合包、半队包、同房02A及02B两包、快慢包、选队停止包解压到同一父目录即可组成完整研究目录。不要改成每个ZIP各套一层同名子目录。阶段02病例HTML需与其 `images/` 文件夹一起使用；最终下载目录另提供嵌入真实原图的独立HTML版本。

最终精确文件清单、完整性回执和持久下载链接见 `DOWNLOAD_INDEX.html` / `DOWNLOAD_INDEX.csv`。每个ZIP内部含逐文件SHA256清单，包外另有逐成员完整读检回执。

## 实际工作边界

五项科学分析已完成。文档更新以 `repository_update/overlay/` 和 `UPDATE.patch` 交付，没有写入本会话不可达的 `D:\Work\HOHONET`，也未推送远端。7个旧入口完整保留旧内容，只追加本轮验收；新worker入口拟为 `research/workers/personnel_full_chain_v21_20261030/`。

原v2、现有直接AC/整类、并行严格9/10人ABC均不覆盖。缺Q保留缺失；现有半队185个三队Q共同事件与187个BC事件不混用。旧同房8,904是双视角物理替换事件，不是8,904张图。本轮没有新增分类拟合、人员、房间事实或256条自然曲线。
