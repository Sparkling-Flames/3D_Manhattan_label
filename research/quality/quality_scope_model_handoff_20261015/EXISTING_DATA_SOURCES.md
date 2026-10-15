# 精简包的外部资料入口与核验边界

## 重新打包原图（2026-10-15）

用户报告旧Library下载失败，已从本地原图库重建263张原图：当前登记261张，另补q9vSo1VnCiC-21与q9vSo1VnCiC-25。三个独立ZIP包含88、88、87张，原字节保留。新入口：https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015

三个ZIP及索引已全部上传，远端大小已核对一致。用户随后明确授权公开上传，已完成发布并核实`isDraft=false`、五个附件均为`uploaded`。此前草稿及自动审批阻塞描述只属于发布前状态，不再是当前限制。图片查找使用Release中的IMAGE_INDEX.csv；原图包不含人员作答或评论，不替代旧expanded_data研究数据包。

- [原图01：88张](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/quality_original_images_20261015_01_of_03.zip)
- [原图02：88张](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/quality_original_images_20261015_02_of_03.zip)
- [原图03：87张](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/quality_original_images_20261015_03_of_03.zip)
- [图片索引](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/IMAGE_INDEX.csv)


2026-10-15。本次通过GitHub连接器实际读取main上的统一输入目录、manifest、坐标文件及四包索引。命令行Git受本机代理影响失败，连接器读取成功。

## 作答与参考：从GitHub读取，不重复随包上传

仓库：https://github.com/Sparkling-Flames/3D_Manhattan_label

入口：`analysis_results/research_input_20260929/manifest.json`；使用 `tools/thesis_main/data_prep/consolidate_research_input.py` 中 `load_current_bundle()`，不要单读冻结的preprocessed_source。manifest明确列出quality_update增量、最终环序和评论入口。

实际读取的preprocessed_source.json是Git LFS指针，指向59,490,666字节的数据；comments.json目录项也仅134字节。必须取得真实LFS内容，不能把指针当JSON解析或宣称数据已读完。本轮确认远端入口与LFS对象声明存在，没有重新下载全部LFS实体，也没有宣称逐条重新核验全部3152份。原始导出来源由loader对象的source路径追溯。

**后续下载入口核验：** `https://media.githubusercontent.com/media/Sparkling-Flames/3D_Manhattan_label/main/analysis_results/research_input_20260929/preprocessed_source.json` 与同目录`comments.json`的匿名分段请求均返回206，前256字节为真实JSON，声明完整长度分别为59,490,666与108,396,834字节。只核实入口及文件开头，不冒称重新下载全体；消费方仍应完整取得实体并应用manifest/loader增量。可以先使用这些既有数据入口，不必重传全库。

36份相关作答和2个GT的本地快照仍留在仓库交接目录，精简上传包不再重复携带；从原始导出直接解析不能替代当前预处理、环序与审核增量。历史1145表和模型源码优先读取仓库已有归档；新版不重复附全量结果表。

## 图片：使用已有Library资料

以下索引已与GitHub main实际返回一致。当前会话没有Library文件读取工具，未重新下载四包、核验内部图片覆盖或确认新Pro自动获得访问权限。Pro应先按精确名称/ID访问已有包；若不可访问，只说明需要关联哪个现有文件，不重新制作原图副本。

# 用户指定的四个基础资料包

确认日期：2026-10-11。用户明确纠正第四个包为扩展数据包。本表作为后续质量研究固定索引，优先按精确名称或Library ID查找，无需每次重新猜文件名。

|文件名|Library ID|字节数|已核实/用途边界|
|---|---|---:|---|
|pro_quality_original_images_01_of_03.zip|libfile_79227978f15881918d63e4ed16e83e46|184403061|原图包01；本轮核实可定位元数据，内容与覆盖由消费环境检查|
|pro_quality_original_images_02_of_03.zip|libfile_be25334b519c8191a28f3347d944baf3|124304472|原图包02；同上|
|pro_quality_original_images_03_of_03.zip|libfile_d9d00e38c898819192834e424722b2c4|182549824|原图包03；同上|
|pro_quality_expanded_data_20261007.zip|libfile_71977790d08c81918700d41c91aec899|24016602|扩展数据包；不要未解压就断言含有哪些原图或字段|

这4个文件是用户指定的基础资料集合，不是4份都已验证为图片的归档。首次使用应核对包内清单、图像ID、分辨率、重复、缺失和版本，并把实际覆盖与哈希结果记到新研究报告。Library存在不代表任何Pro对话自动获得读取权限；若当前研究环境不可访问，请用户在该对话附对应文件，不假称已读取。

另有 Pro质量研究七张原图_20261008.zip（libfile_55c26716d6e8819184feece8f7679018，13157304 bytes）是补充材料，不属于此次指定四包。此前提示词把它列为第四包是错误，现已更正；文件不删除、不作内容猜测。

近期46MB交接包的定位见 LIBRARY_FILES.json；它包括本轮30份作答的24张不同原图与视图，以及原始回执、代码、计算材料。不要将它与以上基础资料集合混同。后续有更新版本时重新核对文件元数据，不悄悄把旧坐标或资格混入新计算。

## 本精简包独有内容

只带两图新范围原件及增量、核验说明、44份本次人工回执和绑定、固定分项诊断、选样表及任务说明。不包含照片、查看器、重复当前作答坐标、1145全量结果表或历史大ZIP。

精简包是补充材料，不是可脱离GitHub和Library独立运行的全量研究环境。旧65.5 MiB交付ZIP已删除；本地原图、作答数据及用户上传原件不删。
