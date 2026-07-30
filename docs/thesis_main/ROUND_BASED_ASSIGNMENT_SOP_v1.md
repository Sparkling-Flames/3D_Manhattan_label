<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260730_v8 SHA-256 a74ea709ec4a0a3a35f724521b8b2deb0f69f6b0e36191bac8b99c3517ae30df -->
# Round-Based Assignment SOP v1

> 鏈?SOP 鍙秷璐?`PAPER_A_METHOD_CONTRACT_CURRENT.json`锛堢増鏈?`paper_a_method_20260730_v6`锛汼HA-256 `bde2e7e20cb00fa4f67b377112fe6534e27e7938c34fb4f63b7987fd3c142e2b`锛夈€傛棫 Global銆丆2銆丩OO 鎴?rolling 璇箟鍧囦负 superseded銆?
## 0. 閫傜敤鑼冨洿

鏈枃鎶?`ROUND_BASED_EXECUTION_PROTOCOL_v1.md` 杞垚鍙墽琛岀殑鍒嗗彂銆佸喕缁撳拰钀界洏姝ラ銆傞樁娈佃竟鐣屽浐瀹氫负锛?
```text
Pilot -> P1 -> C1 -> C2-B -> C2-A-RP -> T1 -> V1
```

鎵€鏈夐樁娈甸伒瀹?Label Studio CE-only 杩愯惀绾︽潫銆俻lanned assignment 浠?`import_json/` 涓虹湡婧愶紝raw submission 浠?`export_label/` 涓虹湡婧愶紝active-time 浠?`active_logs/` 涓虹湡婧愶紝`analysis_results/` 鍙瓨娲剧敓涓庡璁＄粨鏋溿€?
C1 宸插紑濮嬩笖涓嶈繑宸ワ細涓嶅緱閲嶅缓鏃㈡湁 C1 project銆佹敼鍙?assignment 鎴栬姹傚伐浜鸿ˉ瀛楁銆傚悗缁彧浠庢棦鏈?raw export 閲嶈窇 canonicalization 鍜屾淳鐢熼摼銆?
## 1. 閫氱敤鎵ц瑙勫垯

### 1.1 姣忚疆寮€濮嬪墠

蹇呴』鍐荤粨骞朵繚瀛橈細

```text
round_id
assignment_manifest
eligible_worker_roster
task_roster
seed
code_commit
rule_manifest
input SHA
```

娑夊強浜嬫晠銆侀噸璺戝拰鍒犲け鏃惰繕蹇呴』鍔犺浇鍐荤粨鐨?incident/failure rule manifest锛屼笉寰楀湪缁撴灉鍙鍚庝慨鏀广€?
### 1.2 瀹屾暣 failure disposition

鍏堢敓鎴?canonical annotation roster锛屽啀涓?sparse incident registry銆乻tructural validator 鍜?adjudication 鎷兼帴锛岃緭鍑烘瘡鏉?annotation 涓€琛岀殑瀹屾暣 disposition锛?
```text
annotation_id
row_failure_attribution
structurally_valid
incident_id
failure_reason
evidence_status
```

姝ｅ父璁板綍鏄惧紡鍐?`none`锛涘紓甯镐笉鑳介潤榛樹涪寮冦€俥xternal 鍙湁鍦ㄤ互涓嬮獙璇佸叏閮ㄩ€氳繃鏃舵垚绔嬶細

- incident registry 涓瓨鍦紱
- evidence file SHA 鍖归厤锛?- project/task 浣嶄簬褰卞搷鑼冨洿锛?- annotation 鏃堕棿浣嶄簬 `occurred_at` 鑷?`recovered_at`锛?- `recorded_at` 鏃╀簬 outcome review锛?- `recorded_before_outcome_review=true`銆?
鍚﹀垯鍐?`not_evaluable`銆?
## 2. P1 鈥?PreScreen

### 杈撳叆

Pilot 鍐荤粨浠诲姟銆丟T/reference銆丆E-only user/project銆乸lanned assignment 鍜?owner-valid active-time 閰嶇疆銆?
### 鍒嗗彂

- 鍙悜棰勬敞鍐屽伐浜哄垎鍙戯紱
- worker 涓嶅緱鎺ヨЕ GT銆佷粬浜虹粨鏋滄垨姝ｅ紡璺敱鐢诲儚锛?- 淇濆瓨 task-worker 鏄犲皠銆佹ā寮忋€侀『搴忋€乻eed 鍜屾毚闇茶瘉鎹€?
### Closeout

钀界洏 admission銆乸ass-count contingency銆乸rocess integrity銆乫ailure-family evidence銆丳1鈫扖1/C2-B/T1 棰勬祴鍊欓€夊拰 freeze manifest銆?
P1 component 姝ゆ椂鍙兘鏍囦负 candidate锛屼笉鑳借繘鍏?Full銆?
## 3. C1 鈥?Calibration 涓绘牎鍑嗚疆

### 杈撳叆涓庝笉杩斿伐瑙勫垯

缁х画浣跨敤宸茬粡鍐荤粨鐨?C1 import銆乤ssignment銆丩abel Studio 椤圭洰鍜?raw export銆傜姝㈤噸鏂板垎閰嶅凡缁忓畬鎴愭垨姝ｅ湪鎵ц鐨?C1 鏍囨敞銆?
### 娲剧敓澶勭悊椤哄簭

```text
raw export
-> canonical annotation roster
-> complete failure disposition
-> task-adjusted GT quality
-> Geometry LOO audit
-> worker structural profile
-> predictive validation
-> C2 design simulation
```

姣忎竴姝ヤ繚瀛樿緭鍏?杈撳嚭 SHA銆佷唬鐮?commit銆乺ule manifest 鍜?schema validation銆?
### Closeout

蹇呴』钀界洏锛?
- `Q_u_GT_raw`銆乣Q_u_GT_task_adjusted`銆丆I/LCB 鍜?support锛?- `R_u_peer`銆乸eer support/status锛涘彟鍒?LOO medoid/strict state 涓庡彲鐢ㄦ椂鐨?tie-break evidence锛?- `F_u_struct` 鍙婂彲璇勪环鏈轰細鏁帮紱
- P1 predictive validation锛?- `risk_assist`銆乣risk_route` 鍊欓€夛紱
- worker/task/building 鏂瑰樊锛?- C2-B 鍊欓€夎璁°€佸姛鏁堜笌棰勭畻妯℃嫙銆?
## 4. C2-B 鈥?Common anchor + diverse bridge

### 4.1 璁捐鍐荤粨

浠?C1 simulation 閫夋嫨涓€涓璁★紝鏄庣‘锛?
```text
per_worker_count
common_anchor_count
diverse_bridge_count
unique_task_count
support_per_task
worker_task_graph_rule
ordinary_stress_balance
```

涓嶅緱鏈烘浣跨敤鏃?reserve 閰嶉銆俢ommon anchor 鐢辨墍鏈夌洰鏍囧伐浜哄叡鍚屽畬鎴愶紱diverse bridge 浣跨敤鍐荤粨鐨勫钩琛′笉瀹屽叏鍖虹粍鍒嗗彂銆?
### 4.2 鍒嗗彂妫€鏌?
- 姣忎釜 worker 婊¤冻鍐荤粨鐨?ordinary/stress 閰嶆瘮锛?- common anchor 瑕嗙洊瀹屾暣锛?- bridge 鎻愬崌 unique task 瑕嗙洊涓旀弧瓒冲浘杩為€氳鍒欙紱
- 涓嶄緷鎹伐浜哄綋鍓嶇粨鏋滄湁鍒╀笌鍚︽洿鎹换鍔★紱
- 淇濆瓨 planned split銆佸疄闄呴鍙栥€佸畬鎴愬拰鍋忓樊鍘熷洜銆?
### 4.3 Closeout

鏇存柊 task-adjusted GT quality銆丩OO/structural 瀹¤銆佸眰绾ф敹缂╅闄╅煣鎬с€丳1 component confirmation銆乣risk_route` confirmation 鍜?`d_cal^F` support銆?
## 5. C2-A-RP 鈥?Precision-adaptive completion

### 5.1 瑙﹀彂

鍙湪鍐荤粨瑙勫垯鍒ゅ畾鍖洪棿杩囧涓斿皯閲忎换鍔″彲鑳芥敼鍙?routing eligibility 鏃惰Е鍙戙€俻rocess/independence blocker 瀛樺湪鏃朵笉寰楅€氳繃琛ラ鈥滀慨澶嶁€濄€?
### 5.2 鍒嗗彂

姣忎釜 block 鍥哄畾涓猴細

```text
1 ordinary + 1 stress
```

姣忎汉 0鈥? 涓?block锛屽叿浣撲笂闄愪娇鐢?C1 鍚庡喕缁撳€笺€傛瘡娆¤拷鍔犲彧渚濇嵁棰勬湡鍖洪棿缂╃獎閲忥紝涓嶄緷鎹?component 鏂瑰悜鎴栧 Full 鏄惁鏈夊埄銆?
### 5.3 鍋滄

- 杈惧埌绮惧害鐩爣锛氬仠姝㈠苟鍐荤粨锛?- 杈惧埌涓婇檺浠嶄笉绋冲畾锛氳 component 璁句负 unsupported锛岃皟鏁撮噺涓?0锛?- 涓嶅厑璁告悳绱㈡柊椋庨櫓鎴栨柊 P1 family銆?
## 6. Main freeze

T1/V1 import 鍓嶅繀椤荤敓鎴愪竴涓増鏈竴鑷寸殑 freeze bundle锛?
```text
reference registry
worker_state_version
Strong Global policy
Full-Integrated policy
risk_assist / risk_route
support / activation / fallback
T1 allocation and pair contract
V1 block randomization
availability / quota / capacity ledger
offer / timeout / replacement
dynamic redundancy
GT-blind aggregation
terminal states
incident / rerun / censor rules
analysis plan
code and input SHA
```

杩愯鏀跨瓥宸紓鍙鎬?gate銆傝嫢 activation銆侀閫夊樊寮傛垨瀹归噺鍚庡樊寮傛湭杈惧埌鍐荤粨闃堝€硷紝鍋滄 V1 鍒涘缓骞惰惤鐩樷€滄斂绛栦笉鍙尯鍒嗏€濆璁★紱涓嶅緱涓轰簡鍚姩璇曢獙浜嬪悗璋?Full銆?
## 7. T1 鈥?Main-Test

### 7.1 鍒嗗彂

鎸?`Manual/Semi 脳 ordinary/stress_assist` 鎵ц銆?
姣忓浘寤虹珛鍥涗釜 slot锛?
```text
Manual pair A
Semi   pair A
Manual pair B
Semi   pair B
```

鍥犳姣忓浘涓?`2 Manual + 2 Semi`锛屼絾姣忎釜 `pair_id` 蹇呴』鎭板ソ鍖呭惈涓€鏉?Manual 鍜屼竴鏉?Semi銆傚垎閰嶅繀椤绘弧瓒筹細

- 鍚屼竴宸ヤ汉涓嶇湅鍚屽浘涓ょ妯″紡锛?- worker 鍐?Manual/Semi 涓?ordinary/stress 灏介噺骞宠　锛?- workload cap锛?- 淇濆瓨 candidate set銆乻eed銆乤ssignment probability 鍜?freeze version銆?
### 7.2 杩愯涓紓甯?
琛岀骇鍙褰曡 submission 鐨?`row_failure_attribution`銆備竴琛?external 涓嶅緱鎶婂悓 pair 鐨勫彟涓€琛屾敼鏍?external銆?
pair-level disposition锛?
1. external 璇佹嵁楠岃瘉閫氳繃鍚庯紝灏嗗畬鏁?pair 鏍囦负 pending锛?2. 鍦ㄥ師鏉′欢銆佸師 freeze version 鍜?worker-image 闅旂涓嬫渶澶氬畬鏁撮噸璺戜竴娆★紱
3. 閲嶈窇 pair 浠嶉』鎭板ソ涓€ Manual銆佷竴 Semi锛?4. 鎴愬姛鏃?resolver 鐢ㄩ噸璺?pair 鏇夸唬 original pair锛?5. 涓嶈兘瀹屾暣閲嶈窇鏃舵暣瀵硅鏀垮垹澶憋紱
6. 璇佹嵁鎴栧叧绯讳笉鍚堟硶鏃舵暣瀵?`not_evaluable`銆?
### 7.3 Closeout

淇濆瓨 original/rerun pair銆佽绾у綊鍥犮€乸air disposition銆佽鏀垮垹澶卞師鍥犮€乷wner-valid active-time 鍜屾渶缁?analysis pair銆俆1 outcome 涓嶅緱淇敼浠讳綍 Calibration/V1 freeze銆?
## 8. V1 鈥?Main-Validation

### 8.1 Block 鍒涘缓

姣忎釜 block 鍦ㄩ殢鏈哄寲鍓嶅喕缁撳悓涓€涓細

```text
availability_snapshot_id
candidate_roster
worker_total_capacity
global_quota_per_worker
full_quota_per_worker
offer_timeout
completion_timeout
max_offer_attempts
replacement_rule
dynamic_redundancy_rule
freeze_version
```

鎸夊喕缁?seed 灏?task/block 鍒嗛厤鍒?Strong Global 鎴?Full-Integrated銆傚叡浜€欓€夋睜浣嗗缓绔嬩袱濂楃嫭绔嬭处鏈紝绂佹璺ㄨ噦鍊熷閲忋€?
### 8.2 鎺ㄨ崘涓?offer

涓よ噦鍙厑璁告帹鑽愭帓搴忎笉鍚屻€傛墽琛岄『搴忕粺涓€涓猴細

```text
recommend
-> offer
-> accept/decline/timeout
-> complete/incomplete
-> validate
-> replace or aggregate
```

姣忔浜嬩欢淇濆瓨 candidate set銆佹帹鑽?rank銆乷ffered/accepted/completed worker銆乷ffer sequence銆乺eplacement reason銆乧apacity before/after 鍜?candidate exhaustion銆?
### 8.3 鍔ㄦ€佸啑浣欎笌 GT-blind 鑱氬悎

鍒濆 `k`銆佽拷鍔犳潯浠躲€乻tandard/exceptional cap 浣跨敤鍚屼竴涓喕缁撹鍒欍€傝仛鍚堜笉寰楄鍙?GT锛屽彧鑳借鍙栧悎娉曟彁浜ゃ€佸喕缁撳嚑浣曠浉浼煎害銆佺粨鏋勬湁鏁堟€с€乴argest/second cluster銆乵edoid margin 鍜屽宄扮姸鎬併€?
- 绋冲畾鍗曚竴杈撳嚭锛歚resolved`锛?- 鏈夊悎娉曟彁浜や絾鍒颁笂闄愪粛澶氬嘲/涓嶇ǔ瀹氾細`unresolved`锛?- 鍒颁笂闄愪粛鏃犲彲浜や粯鍚堟硶杈撳嚭锛歚severe_failure`銆?
### 8.4 External rerun

`external_system_failure_pending_disposition` 鍙槸杩愯涓姸鎬併€傚悎娉曢噸璺戝繀椤伙細

- original task 瀛樺湪锛?- rerun 涓?original 鍚?policy arm銆佸悓 freeze version锛?- `rerun_sequence=1` 涓旀瘡涓?original 鏈€澶氫竴娆★紱
- reservation arm 涓?policy arm 鐩稿悓锛?- reservation ID 鍞竴涓斿閲忓彉鍖栧悎娉曪紱
- 浣跨敤棰勫厛瀵圭О棰勭暀瀹归噺銆?
鎴愬姛鍚?resolver 鐢?rerun outcome 鏇夸唬 original锛屽悓鏃朵繚鎸?original randomization arm 鐨?ITT銆備笉鑳藉悎瑙勯噸璺戝垯琛屾斂鍒犲け锛涗笉寰楄法鑷傘€佽法鐗堟湰鎴栦簩娆￠噸璺戙€?
### 8.5 Closeout

钀界洏 recommendation/offer/completion 鍏ㄤ簨浠躲€佺嫭绔嬪閲忚处鏈€亀orker/policy failure銆乷riginal/rerun chain銆佹渶缁堜换鍔＄粓鎬併€丟T-blind 杈撳嚭鍜?analysis-ready ITT 琛ㄣ€?
## 9. 鍋忓樊涓庡璁?
浠讳綍 schema drift銆乵issing field銆乤ctive-time source mismatch銆乧apacity 閫忔敮銆佽法鐗堟湰 rerun 鎴栫己澶?manifest SHA 蹇呴』 fail closed锛屼笉寰楅潤榛樺拷鐣ャ€?
姣忚疆 closeout 淇濆瓨锛?
```text
鎵ц鍛戒护
娴嬭瘯鎽樿
code commit
杈撳叆/杈撳嚭 SHA
鍐荤粨瑙勫垯鐗堟湰
璁″垝涓庡疄闄呭亸宸?澶勭疆浜哄拰鏃堕棿
```

Main 寮€濮嬪悗鐨勪换浣曚慨鏀瑰彧鑳戒綔涓轰笉鏀瑰彉涓昏鍚堝悓鐨勫嫎璇垨鍦?outcome 涓嶅彲瑙佹椂鐧昏鐨?amendment锛涗笉寰楀洖娴?P1/C1/C2銆?
## 杩藉姞锛欳1 assignment provenance 涓?rolling enrollment

C1 roster 鐨勬寮?assignment provenance 鍥哄畾涓?`original_assignment`銆乣authorized_replacement_assignment`銆乣late_entry_calibration_assignment`銆乣outside_assignment_submission`銆傛巿鏉?replacement 蹇呴』缁戝畾 original manifest/row銆佹巿鏉冭褰曘€佸垎鍙戣瘉鎹拰 SHA锛沷utside submission 鍙繘鍏?raw/exposure ledger锛屼笉鑳藉洜 generic authorized exception 杩涘叆 GT銆乸eer銆丩OO銆乻tructural 鎴?time銆俉014 涓嶇敓鎴?replacement锛沇034 浠呮帴鏀?17 鏉?non-anchor 鎺堟潈琛ュ厖浠诲姟锛學001 浠呮帴鏀?3 鏉℃巿鏉冭ˉ鍏呬换鍔★紝W034 鐨?B-004/B-022 姘镐笉鍐嶆鍒嗛厤銆?
姣忎釜 task-condition 鎸?estimand 璁＄畻 final unique-worker support锛沝uplicate revision 鍙繚鐣欏喕缁?canonical row銆俛ctive-time 浠呭湪 owner-valid sentinel 鍜屾棩蹇楃粦瀹氶€氳繃鍚庢爣璁?expected/eligible锛屼笉鍥炲～鏃㈠線缂哄け銆俽olling enrollment 鏃犺鍚敤涓庡惁閮藉繀椤诲喕缁?`calibration_enrollment_registry.csv`锛涘叧闂椂鏄庣‘璁板綍 `rolling_activated=false`銆乣N_late=0`锛屽惎鐢ㄦ椂鐧昏鍏ㄩ儴 original/late-entry worker 鍙?terminal status銆俛ssignment manifest 鍙瘉鏄庝换鍔℃潵婧愶紝绂佹鐢ㄥ畠鎺ㄦ柇 enrollment batch銆係tage 3 roster freeze 鍚庡仠姝竴鍒囨嫑鍕熶笌 assignment 鍙樻洿銆?
## v5 鏂规硶鍚堝悓鎵ц绾︽潫

`policy_candidate_v2.global_rank_S_G` 鏄?V1 鍞竴鍙秷璐圭殑闈欐€?Global 鍚嶆銆傚惎鍔ㄥ墠蹇呴』鍚屾椂 SHA 缁戝畾鏂规硶鍚堝悓銆丼trong Global policy manifest銆乧andidate roster 涓?profile version锛沷nline engine 鍙鍙栧綋鏃跺彲瑙佺姸鎬佸苟 append-only 鍐?ledger锛宐atch 妯″潡鍙仛 replay/audit銆傚閲忓拰 availability 鍙兘鏀瑰彉 scheduler offer锛屼笉鑳芥敼鍐欒闈欐€?rank銆?
