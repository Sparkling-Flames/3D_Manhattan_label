# 29张完整参考待核的逐图原因

已确认41图43空间的点位处理，不再要求重复画范围。此处待核仅指完整三维参考；不改原B8L2、标签、坐标或资格。

面积单位为相机高度平方(h²)，不是平方米；百分比为越界面积/新范围面积。位移为新边每段101点到源多边形最近点的ERP投影距离采样最大值（1024×512，考虑横向环缝），不是严格连续上界。

另从源JSON的coords、xyz半径及cameraHeight重新执行既定转换但不保留两位小数，检验越界是否仍存在。与原JSON逐值转换相等检查通过后才进行比较，不直接把JSON的xyz轴当ERP坐标。

诊断分组：两种源表示的采样位移均≤0.01像素，列为数值/存储误差候选；均>1像素列为相对已有源域的实际扩展；其余证据不足。0.01来自现有存储尺度，1像素只用于分开明显扩展；二者均不是参考准入阈值。候选不等于已证明唯一成因，扩展不等于用户范围错误。

|图片|原因组|越界h²|占新范围%|原GT位移px|未舍入源位移px|未舍入越界h²|
|---|---|---:|---:|---:|---:|---:|
|[B6ByNegPMKs-37](D:/Work/HOHONET/data/mp3d_layout/test/img/B6ByNegPMKs_c946db5792df4f90bea20f06a0030c37.png)|仅数值/存储误差候选|0.0004151406|0.0062166|0.00429906|0.004592235806166539|0.00011856908453415995|
|[S9hNv5qa7GM-09](D:/Work/HOHONET/data/mp3d_layout/valid/img/S9hNv5qa7GM_625eb179629b45f280c01d3f6ec74b4f.png)|仅数值/存储误差候选|7.842598e-06|0.00056574|0.00201485|0.0009380402500551377|1.820528390035224e-05|
|[UwV83HsGsw3-10](D:/Work/HOHONET/data/mp3d_layout/test/img/UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596.png)|仅数值/存储误差候选|6.658471e-06|0.00047031|0.0031413|0.0012624067200251044|8.38535523037283e-06|
|[b8cTxDM8gDG-18](D:/Work/HOHONET/data/mp3d_layout/test/img/b8cTxDM8gDG_f3748786c3704532abb2358581488f3f.png)|仅数值/存储误差候选|4.855226e-05|0.0011674|0.0032417|0.0005067620356995573|1.1212643536562002e-06|
|[e9zR4mvMWw7-09](D:/Work/HOHONET/data/mp3d_layout/test/img/e9zR4mvMWw7_1d316dfbe35f41dd9203eaf88be5aae8.png)|实际范围扩展（相对已有源域）|0.3027387|4.0155|26.3389|26.342586745899464|0.3026446574780314|
|[e9zR4mvMWw7-17](D:/Work/HOHONET/data/mp3d_layout/test/img/e9zR4mvMWw7_4273c4dd97974531b5256f96204fee47.png)|仅数值/存储误差候选|0.0003334252|0.0025621|0.0085559|0.007547542376018514|0.00017294435933487575|
|[pRbA3pwrgk9-02](D:/Work/HOHONET/data/mp3d_layout/valid/img/pRbA3pwrgk9_03de6e2562bb4f56a88db3ceb681af78.png)|仅数值/存储误差候选|4.403901e-06|0.00070199|0.00200356|0.0|0.0|
|[pa4otMbVnkk-11](D:/Work/HOHONET/data/mp3d_layout/valid/img/pa4otMbVnkk_4fbdfc08c934474ea9a04977f9081d0e.png)|仅数值/存储误差候选|0.0001086898|0.0010219|0.00501819|0.0|0.0|
|[q9vSo1VnCiC-11](D:/Work/HOHONET/data/mp3d_layout/test/img/q9vSo1VnCiC_830eb252ae01401a8fe55f9538e627dd.png)|仅数值/存储误差候选|8.111662e-05|0.0007128|0.00149544|0.003591728687045325|9.54446257043078e-05|
|[q9vSo1VnCiC-12](D:/Work/HOHONET/data/mp3d_layout/test/img/q9vSo1VnCiC_9ba6cd412cb04c5c9beb15ef9e6d22c5.png)|仅数值/存储误差候选|7.338213e-05|0.00074321|0.00326812|0.005081877886599365|0.0005518403327737786|
|[q9vSo1VnCiC-16](D:/Work/HOHONET/data/mp3d_layout/test/img/q9vSo1VnCiC_a424533651804a38a55b1252daccc81e.png)|仅数值/存储误差候选|0.0001596047|0.0014024|0.00398189|0.0|0.0|
|[q9vSo1VnCiC-29](D:/Work/HOHONET/data/mp3d_layout/test/img/q9vSo1VnCiC_dc320b1236f741a98303db9f89bc68a2.png)|仅数值/存储误差候选|6.770772e-06|0.00065662|0.00229006|0.00501266421566849|3.975530186484111e-05|
|[q9vSo1VnCiC-34](D:/Work/HOHONET/data/mp3d_layout/test/img/q9vSo1VnCiC_f7452776f0604b508bb2b0263238deb0.png)|仅数值/存储误差候选|0.0002970814|0.0025273|0.00573549|0.0026226613509788854|0.00014128661810336554|
|[uNb9QFRL6hY-18](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_2ed0e171a7c34f17a85363923a26ab98.png)|实际范围扩展（相对已有源域）|0.8648106|8.7439|73.2972|73.29452238539251|0.8650563869512661|
|[uNb9QFRL6hY-26](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_5b62816d9cf94f17ae166291822ea9ab.png)|实际范围扩展（相对已有源域）|0.7683477|7.8803|34.6641|34.66635525523883|0.7685235144496746|
|[uNb9QFRL6hY-41](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_76ba70b55bde4313939a4a0cd78a49d3.png)|实际范围扩展（相对已有源域）|0.8789629|8.9366|48.5334|48.534771379639054|0.8791671790365354|
|[uNb9QFRL6hY-44](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_85e7a14905bd44648061e3eb7f79cf13.png)|仅数值/存储误差候选|8.808355e-05|0.0013217|0.00605806|0.005351863668494952|0.0001801721597956809|
|[uNb9QFRL6hY-54](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_a7ab19b1a9f044f0905592de1414e8b3.png)|实际范围扩展（相对已有源域）|0.01605127|0.51383|12.8639|12.85994193552119|0.0160149188626469|
|[uNb9QFRL6hY-55](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_ab84a27288034713b2c24e41b31acc78.png)|仅数值/存储误差候选|0.0001575778|0.0021926|0.00572852|0.0022700124758970454|8.695332201372075e-05|
|[uNb9QFRL6hY-59](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_b98c9460586e4f138658181461df9f51.png)|实际范围扩展（相对已有源域）|0.7758046|8.7258|97.7128|97.70905858158213|0.7761200148925662|
|[uNb9QFRL6hY-66](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449.png)|实际范围扩展（相对已有源域）|0.7483485|8.2363|54.7044|54.706330187540885|0.748561179775661|
|[uNb9QFRL6hY-67](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_ca08ebfb2da647f68db41630637e400b.png)|实际范围扩展（相对已有源域）|0.03165148|3.0172|17.1025|17.102314956918462|0.03164902371338421|
|[uNb9QFRL6hY-68](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_cdca0a1a2fc343bb94bacdc3045b2d8d.png)|仅数值/存储误差候选|0.0001297802|0.0019493|0.00501811|0.0019293564478058882|0.00010232307956830545|
|[uNb9QFRL6hY-81](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_e8fcf8c5bd324655a25186117151ccbd.png)|仅数值/存储误差候选|0.0001153361|0.001538|0.00368439|0.0013705939106014714|9.616362857167715e-05|
|[uNb9QFRL6hY-86](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_fd10460fd2bc4c52af84e36e89357269.png)|仅数值/存储误差候选|3.052309e-05|0.00045276|0.00231855|0.004797235353307181|0.00031989671864258865|
|[uNb9QFRL6hY-88](D:/Work/HOHONET/data/mp3d_layout/test/img/uNb9QFRL6hY_fd8d4da92ec14b668ed3d2986616bd14.png)|实际范围扩展（相对已有源域）|0.8338373|7.5927|36.349|36.35260249863263|0.8344036993614815|
|[wc2JMjhGNzB-22](D:/Work/HOHONET/data/mp3d_layout/test/img/wc2JMjhGNzB_3a035012369c4eb58295238d946fbc66.png)|其它/证据不足|0.0001386088|0.0018205|0.0120958|0.0027354798097042918|0.0002177026091048479|
|[wc2JMjhGNzB-29](D:/Work/HOHONET/data/mp3d_layout/test/img/wc2JMjhGNzB_52ed6a0219e84a0bb6db8037ae700366.png)|仅数值/存储误差候选|8.701367e-05|0.001065|0.00202448|0.001144373878210601|3.0803582166175215e-05|
|[zsNo4HB9uLZ-13](D:/Work/HOHONET/data/mp3d_layout/valid/img/zsNo4HB9uLZ_aabf649f606a48a1b16d5bdcd5970602.png)|仅数值/存储误差候选|0.0001207184|0.0017743|0.00439111|0.0|0.0|

逐图全部源对象、回执路径、原JSON成员及原图链接见 [pending_scope_audit.json](pending_scope_audit.json)。未重新肉眼检查全部原图；本表结论是来源与几何差异诊断，不能认证照片中的天花板延续。

分组数量：{"仅数值/存储误差候选": 19, "实际范围扩展（相对已有源域）": 9, "其它/证据不足": 1}
