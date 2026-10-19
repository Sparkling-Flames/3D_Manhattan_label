# 最终 7 个案例的 6 张 Release 原图

当前最终案例共 **7 个，使用 6 张不同原图、来自 4 栋建筑**。C01、C02 共用 yqstnuAEVhm-27；其余案例各用一张图。6 个本地 PNG 均已重新核对 SHA256、ZIP 条目 CRC32、字节数、2048×1024 尺寸，并完成 PNG 解码检查；原图覆盖无缺口。精确图号、图片 ID、案例 JSON 路径、case 中的相对图片路径与来源字段、Release asset URL 和 ZIP 内部路径完整保存在 `SELECTED_ORIGINALS.json`。

| 图号 | 案例 | ZIP 分包 | 字节数 | CRC32 | 本地 SHA256 |
|---|---|---|---:|---|---|
| yqstnuAEVhm-27 | C01, C02 | 03/03 | 1,919,397 | `ff4d7fdd` | `bc2c9b272e213e8a00c374ebeeb081527a530693a958fbb46314434579c3ca85` |
| UwV83HsGsw3-22 | C03 | 02/03 | 1,642,317 | `9e1e7914` | `58fd930f2c3239901efc9f166bf27221088f075b59006ce19fbfce5e633b7425` |
| X7HyMhZNoso-07 | C04 | 03/03 | 1,962,633 | `272eff09` | `ecf78f290dff4e2030d60915fc0f11add92284e9bf91234e3b2cf3a1738cdc0b` |
| UwV83HsGsw3-09 | C05 | 03/03 | 1,909,331 | `33e5e169` | `bdf425702aee4d28cf8b71d25feeecb71679d18c673fe0c8a1fca0c71f6c1b28` |
| q9vSo1VnCiC-03 | C06 | 02/03 | 2,170,027 | `559a4c58` | `9d6c7e36c5d7f4c0628a57a9133ca6b6932e51a164e954639e7700518ea0032b` |
| yqstnuAEVhm-25 | C07 | 02/03 | 2,107,617 | `da32d3b9` | `04a66b95b8ecfdfb4d596848a22c4c7aec8abe7f5321fb7659c18cbd8db32801` |

## 来源核对口径

- 逐例读取 `analysis/representative_cases/cases/` 中最终案例的 `image_source`、`image_path` 和 `image_sha256`，再对齐 `release_IMAGE_INDEX.csv` 和 `zip_directories.json`。共 7 个案例全部一致。
- Release 索引本身已与元数据发布者 SHA256 核对。索引未提供逐图发布者 SHA256；表中逐图 SHA256 是本次对本地原始 PNG 字节重新计算的值，且与案例已存摘要一致。
- 所需原图通过 HTTP Range 按 ZIP 条目提取。条目 CRC32、未压缩大小、索引字节数与尺寸全部一致；这不等于下载并验证整个 ZIP。JSON 保留 Release 元数据中的整个 ZIP 发布者 digest，并明确 `whole_archive_sha256_verified=false`。
- `analysis/selected_originals/extraction_manifest.json` 仅含最后提取的 UwV83HsGsw3-09、q9vSo1VnCiC-03 两图，属于单次提取日志。本清单覆盖全部 6 图，不以该日志的两条记录当作最终总量。

## 精简交付与重取

按本次成果包打包规则，**Release 原图全集和这 6 张原始 PNG 均不重复放入精简 ZIP**。保留精确提取代码 `range_zip.py`、Release 元数据、图片索引与 ZIP 条目目录、本清单，以及最终 ERP／BEV／3D 对照图和可重建案例几何。需要原始 PNG 时，使用 JSON 中的 6 个图号及精确 asset／内部路径重新提取；现有代码每次可传入多个 `--image-id`。

本文件只补齐最终原图来源与覆盖记录；没有新增科研实验，也不把当前案例图上的结构观感改写成新的参考、范围资格或选人验证结果。
