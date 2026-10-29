# pa4-11：已有目标裁定与八角人群输出

2026-10-30。当前规则足以说明本轮评分对象，无需因为七组合低Q重新问一次同样的范围问题。

`reference_bindings.csv`中该图35份Manual原答全部为`sole_admitted_space`，唯一允许且实际绑定的目标是`user_floor_20261015:pa4otMbVnkk-11`。35份均保留原答、未裁切、未修改，Q未用于空间选择。`reference_catalog.json`保留两条记录：历史原GT八角仅作历史版本，`is_admitted_space_candidate=false`；当前四角空间为`confirmed_scope`，是用户已确认的主目标。全体八角原答不存在被自动路由到另一个已准入八角空间的选项。

采用来源可追溯到`analysis_results/research_input_20260929/floor_scope_update_20261015.json`的records/2、`scope_receipt_20261015_1.json`的records/50/space_regions/regions/0，后续参考更新使用`adopted_references_20261028/USER_ADOPTION_RECEIPT.json`。10月28日将该图难度改为中等，不改变目标归属。

原答及七队输出均保留右侧外伸轮廓，与四角参考在范围上不同。已保存底面图能直观看到外伸，同时不同队的主矩形定位也有差异。这解释了“全员较一致却相对当前目标低Q”的现象；它没有证明35份原答在所有可能目标下都错误。

**当前可采用的描述：** 七种完整类别组合均形成八节点完整输出，但相对已指定四角目标有共同范围偏离；类别组合改变了定位、尺度和高度，未消除这项共同偏离。完整输出和准确对应目标是不同观察。

本轮只回查35条绑定与两条目录身份，并目视检查保存底面图，没有重放路由、重算Q或更改参考。证据见[绑定核对](SCOPE_PA4_11_BINDINGS.csv)和[检查记录](SCOPE_PA4_11_CHECKS.json)。

## 可查看的材料

- 完整原答、参考、七组合及票账见[病例报告](stage06_cases/alliance_pa4_11/REPORT_ALLIANCE_PA4_11_ZH.md)和逐图票账；嵌入高清原图的HTML查看器仅本机保留，不上传。
- [统一坐标下的七组合底面](stage06_cases/alliance_pa4_11/figures/SEVEN_ALLIANCES_BEV.png)。黑虚线为当前参考；各队未单独缩放。
- [作者病例分项](stage06_cases/alliance_pa4_11/REPORT_ALLIANCE_PA4_11_ZH.md)。其“需要人工判断”的部分在本地回查后收窄为下面的条件问题。

只有用户希望新增八角空间为合法目标时，才需要明确判断：ERP横坐标约525–1010、四角参考r2→r3闭合段之外的入口/过渡范围，是否作为另一个独立目标准入？已有原答u约553/711/832/947的路径可作观察材料；全员一致或更高Q不替代该语义判断。这不是本轮尚未完成的评分修复，也不阻断已有实验采用。
