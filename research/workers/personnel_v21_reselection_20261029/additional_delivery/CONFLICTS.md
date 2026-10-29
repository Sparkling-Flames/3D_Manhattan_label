# 同名文件差异

逐字节比较，不计算额外哈希。新包按来源目录分别保存，差异不触发覆盖。

## 03B_01: `PACKAGE_MANIFEST.json`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_core\PACKAGE_MANIFEST.json`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_01\PACKAGE_MANIFEST.json`
- 首个不同字节：14；双方内容分别保存。

## 03B_02: `PACKAGE_MANIFEST.json`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_core\PACKAGE_MANIFEST.json`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_02\PACKAGE_MANIFEST.json`
- 首个不同字节：14；双方内容分别保存。

## 03B_03: `PACKAGE_MANIFEST.json`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_core\PACKAGE_MANIFEST.json`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_03\PACKAGE_MANIFEST.json`
- 首个不同字节：14；双方内容分别保存。

## 03B_04: `PACKAGE_MANIFEST.json`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_core\PACKAGE_MANIFEST.json`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_04\PACKAGE_MANIFEST.json`
- 首个不同字节：14；双方内容分别保存。

## 03B_05: `PACKAGE_MANIFEST.json`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_core\PACKAGE_MANIFEST.json`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_05\PACKAGE_MANIFEST.json`
- 首个不同字节：14；双方内容分别保存。

## 03C: `PACKAGE_MANIFEST.json`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03B_core\PACKAGE_MANIFEST.json`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\03C\PACKAGE_MANIFEST.json`
- 首个不同字节：14；双方内容分别保存。

## 05A: `experiment/run_registered.py`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\experiment\run_registered.py`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\05A\experiment\run_registered.py`
- 首个不同字节：5297；双方内容分别保存。

```diff
--- existing

+++ 05A

@@ -89,12 +89,5 @@

             flush()
     # A scalar shard is complete and independently consumable as soon as a pool finishes.
-    scalars=[]
-    for r in done.values():
-        scalar_input=dict(r)
-        # Historical caches also store these fields as pipe-delimited strings.
-        for field in ('member_workers','member_object_ids'):
-            if isinstance(scalar_input[field],str):scalar_input[field]=scalar_input[field].split('|')
-        scalars.append(native.native.scalar_row(scalar_input))
-    sdir=Path(output)/'scalar_shards';sdir.mkdir(exist_ok=True)
+    scalars=[native.native.scalar_row(r) for r in done.values()];sdir=Path(output)/'scalar_shards';sdir.mkdir(exist_ok=True)
     save_frame(sdir/(pid+'.csv.gz'),pd.DataFrame(scalars))
     result=dict(pool_id=pid,requested=len(wanted),previous=original,reused=reused,new_native=new,total=len(done),
```

## 05B: `STAGE05_PACKAGE_MANIFEST.json`

- 保留左侧：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\05A\STAGE05_PACKAGE_MANIFEST.json`
- 新来源：`D:\Work\HOHONET\research\workers\personnel_v21_reselection_20261029\additional_delivery\packages\05B\STAGE05_PACKAGE_MANIFEST.json`
- 首个不同字节：28；双方内容分别保存。

## 2026-10-29其余来源ZIP的差异成员

阶段06及07A—07D的ZIP成员均已在本研究树中逐项对照。07A的`experiment/run_registered.py`、07B的`experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz`、07C的`experiment/fixed_A_m_endpoints/ENDPOINT_SCALARS.csv.gz`与当前同路径文件不同；差异来源版本逐字节另存于`packages/07A/`、`packages/07B/`、`packages/07C/`，并已加到`PATH_MAP.csv`。07A代码源版本与05A原始来源相同。主路径内容没有被覆盖。

阶段06中的原始全景照片及07A中的`*_original.png`在本机保留，Git忽略规则排除上传；其余原始ZIP成员均已在仓库研究树中找到。
