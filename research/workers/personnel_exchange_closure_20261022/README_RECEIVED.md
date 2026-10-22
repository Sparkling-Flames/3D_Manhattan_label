# 接收状态与既有来源案例记录（2026-10-22）

**当前更新：** 43条件研究的报告代码包和101092端点三表已补齐，Manual主方向已独立复算、两条Semi元数据已修复，见[完整端点验收](LOCAL_ACCEPTANCE.md)。下文保留较早案例和首批接收时的来源判断，不代表当前仍只收到三件。

## 较早接收记录：既有案例包阶段归属待核

**用户已明确确认：Downloads中的这份案例ZIP是此前文件，不是此次Pro返回。** 此目录只保存既有来源案例，不能作为本次总体报告、43条件、新事件、端点或机制研究已经交付的证据。本次整体研究尚未独立验收。

## 来源身份与本地保存

- 来源：`HOHONET_20261022_实际原图叠图与票账案例.zip`，30,367,102字节。
- 123个来源文件在用户澄清前已安全展开，展开后31,155,793字节；没有覆盖已有文件，原下载ZIP保留。
- 121个主题文件保留ZIP中的仓库相对路径。路径名`personnel_exchange_closure_20261022`只用于追溯原包目录，**不证明本次研究阶段**；阶段归属待核。
- ZIP根部`PACKAGE_CONTENTS.csv`与`HOHONET_DELIVERY_README.txt`保存在`delivery/received_case_zip/`，避免写到仓库根及覆盖未来交付清单。
- 实际来源映射：[RECEIVED_MEMBERS.csv](delivery/received_case_zip/RECEIVED_MEMBERS.csv)。
- 当前仅本地保存，由统筹提交；未公开推送、未上传长期文件库。

## 包内既有材料

- [Manual联合案例说明](manual_joint/mechanism_case/MANUAL_JOINT_CASE_ZH.md)。
- [机制说明](mechanisms/机制解释_原答到融合.md)。
- 原图、叠图、成员、票账和端点JSON/CSV沿原相对目录保留。

以上为作者原件，其措辞、日期、链接及“完成”声明不等于本次实际交付状态，也不代表已通过本线程独立复算。

## 用户明确的本次返回

此次实际返回以下三份现已另行收到，保存于[本次阶段01与首批端点](received_stage01_manual001_20261022/README.md)，不与本页此前案例混合：

1. `阶段01_接续依据与实验范围.md`。
2. `HOHONET_公开分类基线_当前main.zip`。
3. `HOHONET_新端点_manual_001.zip`。

实际三件只支持计划、旧分类与首批3489个Manual端点，尚缺最终汇总和ABC关联。此前粘贴总体报告、43条件表和完整事件／端点的sandbox链接不能作为本机已收到或长期保存的证据。旧native/cross事件也不能替代本次新事件。

## 本次来源检查边界

展开前拒绝绝对路径、父目录越界、盘符、反斜杠路径、符号链接、重复目标和已有文件冲突。逐文件读取并检查长度，未计算SHA，未执行包内代码，未重新评分、融合或统计。

RECEIVED_MEMBERS字段：source_zip是源包名；source_member_path是包内原路径；archive_path是本地仓库相对路径；bytes是未压缩长度；status=prior_download_source_case_stage_unconfirmed表示既有来源案例、阶段待核，不表示本次收到或结论通过验收。
