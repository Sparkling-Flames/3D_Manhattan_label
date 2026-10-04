# 输入绑定复算

本次实跑已先核对两份完整源文件Git blob，并运行作者verify_local_inputs.py及更宽的独立共有字段检查。495字段涵盖29标注、2原GT；26个gate对象是已披露的metadata摘录，status一致。

为避免搬运整个研究池，此目录只附实际用到的源记录。本总包解压后，运行 python source_binding/recheck.py，即可复算495字段。若另有冻结完整仓库，追加 --repo /path/to/repo 将同时重新验证整个输入Git blob；未给出时明确只重验已提供源摘录。

原始实跑机器结果为independent_source_fields.json、author_verifier_result.json。strict_comparison_initial.json保留最初整个gate对象相等检查的失败，原因只是省略reasons/scope_policy，已核实不改变status或名单。完整分母对应验证在原实跑结果rosters字段。
