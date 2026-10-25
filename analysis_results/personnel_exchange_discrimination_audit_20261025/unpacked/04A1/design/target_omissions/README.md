# 固定原队的7人目标块留一研究登记

使用真实v2、既有楼外标签、screen与confirm登记的n10/m7严格ABC。只从最大人数历史类→困难转折最高历史类选锚点，不读取效果选锚点。

实际登记：286个锚点，2002个m6事件，90图、22楼，去重需要3146个端点（包括已登记m7端点以支持配对差）。这里只登记，尚未声称完成融合。

每锚点把X7的一人留到共同D，固定A不变；Y7固定删一人；原Z7完整枚举7个留一Z6。三队n=10、实际m=6，D/X/Y/Z仍两两不交叠。原目标七人面板内7选6已经完整登记；全池若有其它目标类成员，它们明确列在ANCHORS中，此设计不称全类穷举。

核心文件：EVENTS_EXACT.csv.gz、REQUESTS.json.gz、ANCHORS.csv.gz、PAIR_LINKS.csv.gz、CAPACITY_AND_ATTEMPTS.csv.gz、FROZEN_LABELS.csv.gz、FOLD_ROLE_CENTERS.csv.gz。PAIR_LINKS定位原m7事件、原B7/C7和遗漏者。

评价应同时看C7−C6、B7−B6及两者净差，不能把净优势变化直接称C队升质。C7与C6、B7与B6各只换1个实际成员；m6三队之间各换6人。失败、缺分不补零。此有限面板用于找出效果是否依赖某个成员，以及少换1人是否改变结构、质量、几何与风险。

复现：python exchange_research_20261025/design_advice/register_target_omissions.py
