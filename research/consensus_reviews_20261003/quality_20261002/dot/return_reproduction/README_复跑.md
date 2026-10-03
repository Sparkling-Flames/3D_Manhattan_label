# 返回包复现与独立方程检查

这两份脚本仅核对返回包的1图6作答1GT实验，不运行原仓库195作答/390参考行验证器。

## 依赖

Python 3.12或3.13。本次已验证版本：

```sh
python -m pip install numpy==2.3.5 scipy==1.17.0 shapely==2.1.2 pandas==2.2.3 matplotlib==3.10.8
```

安装命令供使用者在自己的独立环境执行；审计脚本本身不安装软件、不访问网络。

## 运行

先审阅源码。将原始返回ZIP解压到全新的目录，以避免已有`__pycache__`或重新生成的结果污染收到清单。替换以下路径：

```sh
python portable_reproduce.py \
  --source /path/layout_quality_audit_20261002 \
  --out /path/new-reproduction-output

python independent_checks.py \
  --package /path/layout_quality_audit_20261002 \
  --out /path/independent-output
```

如依赖放在独立目录，第一条命令追加`--dependency-path /path/packages`；第二条命令前加`PYTHONPATH=/path/packages`。没有写死的外部路径依赖。

`portable_reproduce.py`要求输出目录尚不存在且不在来源目录内。它验证32条manifest及清单自身，复制输入，在副本中调用原`reproduce.py`，比较全部保存JSON/CSV和图像，再验证原始字节没有改变。SVG比较仅忽略生成日期与随机元素ID。进程失败或结果不符会触发断言，不应仅凭原程序退出0判定成功。

`independent_checks.py`不导入返回包实现，以另写的几何、Simpson矩积分、分段全局轴优化、射线线性方程和解析模型重新核对。它只读取包、写入指定输出目录。

## 本次期望结果

- 32/32个清单条目大小和SHA256通过，收到文件合计33个
- 原`reproduce.py`退出0，8项局部检查通过
- 9份数值/检查结果文件及controlled_inputs逐字节一致；858个保存数值单元最大差0
- environment.json只差Python版本；3个PNG字节一致，SVG规范化后相同
- 独立35项数值单元全部通过，最大绝对差约1.49e−14
- 17组模型对照；5份列式有效记录、10个作答对；2个体积次序反转、1个列式次序反转

这些结果不证明指标效度或元数据来源正确。R03288人员别名与原点索引，以及未参与实验的R03280来源问题，见中文技术报告及原交接核验分项。

## 文件

- `返回包复现审核.txt`：中文技术报告
- `portable_reproduce.py`：隔离执行、清单与保存结果比较
- `independent_checks.py`：独立方程、数值和计数检查
- `portable_validation_clean/machine_comparison.json`：机器比较结果
- `portable_validation_clean/reproduce.log`：复跑日志
- `independent/independent_checks.json`、`independent_common_fields.csv`：独立复核明细

主交付包如已附原始返回ZIP，无需再次附本目录中的`clean_received`或重复执行副本。两个Python脚本、README及上述结果文件可以放在任意目录使用。
