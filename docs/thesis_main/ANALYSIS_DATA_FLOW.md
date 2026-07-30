<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260730_v7 SHA-256 e2621e20af8afeb31139b0da81cfb8f740de065d83f5f4d587586d041256dc1a -->
# Paper A 姝ｅ紡鍒嗘瀽鏁版嵁娴?
  鏇存柊锛?026-07-18
  鐪熸簮锛歅aper A vFinal銆佹寮?protocol/SOP/SAP 涓庡瓧娈靛悎鍚屻€?  `export_label/`銆乣import_json/`銆乣active_logs/` 鏄緭鍏ョ湡婧愶紱`analysis_results/` 浠呭瓨娲剧敓鍜屽璁°€?
## 1. 涓嶅彉鐨?C1 鍘熷灞?
宸茬粡寮€濮嬬殑 C1 涓嶈繑宸ワ細

```text
Label Studio assignment/import
Label Studio raw export
active_time raw logs
```

涓嶈姹傛爣娉ㄥ憳琛ュ～ failure銆乮ncident銆丟T銆丩OO銆乺isk 鎴?routing 瀛楁銆傛墍鏈夋柊瀛楁鐢卞悗澶勭悊鐢熸垚銆?
## 2. C1 娲剧敓閾?
```text
raw export
+ assignment manifest
+ active logs
-  selected annotation registry
-  c1_canonical_annotations.csv

canonical roster
+ sparse incident_registry.csv
+ structural/policy adjudication
+ frozen failure rule manifest
-  complete failure_disposition.csv

canonical annotations
+ complete disposition
+ external GT/reference registry
-  Q_u_GT_raw / Q_u_GT_task_adjusted / CI / LCB

canonical geometry
+ worker-excluded LOO reference
-  R_u_LOO / compatibility / stability audit

canonical submissions
+ complete disposition
-  F_u_struct numerator / structural-evaluable denominator
```

涓夋潯娴嬮噺閾句笉寰椾簰鐩镐唬濉細

- GT 缂哄け涓嶈兘鐢?LOO 浠ｆ浛銆?- LOO support 涓嶈冻涓嶈兘鍐欎綔 GT failure銆?- external/policy/not-evaluable 涓嶈兘鍐欎綔 worker structural failure銆?- missing disposition 涓嶈兘榛樿涓烘甯搞€?
## 3. P1銆丆1 涓?C2

```text
P1 candidate components
-  C1 predictive validation
-  C1 variance/graph/power simulation
-  freeze C2-B design
-  C2-B common anchor + diverse bridge
-  C2-B confirmation + hierarchical shrinkage B_u
-  C2-B submissions -  post-C2-B worker profile -  profile manifest -  C2-B closeout SHA
-  C2-A-RP precision-adaptive completion
-  C2 final worker/policy freeze
```

C1 simulation 鍐冲畾锛?
```text
n_common_anchor
n_diverse_bridge
n_unique_tasks
per-task support
worker-task graph connectivity
expected Q/B interval width
budget
```

C2-A-RP 鍙缉绐勫凡瀹氫箟 component 鐨勪笉纭畾鎬э紱涓嶆悳绱㈡柊椋庨櫓鎴栨柊 P1 family銆?
鏈€缁?worker state锛?
```text
Q_u_GT_task_adjusted
R_u_peer
F_u_struct
R_u_LOO_medoid / R_u_LOO_strict  # sensitivity only
B_u_risk_shrunk
P1 supported components
d_cal_F
```

`d_cal_A` 鍙敤浜?C1 鍚庤璁?C2锛沗d_cal_F` 鍙敤浜?C2 鍚庣殑 V1 eligibility/fallback銆?
## 4. T1 娴?
```text
frozen T1 pair manifest
-  Manual/Semi 脳 ordinary/stress_assist execution
-  canonical row outcomes
-  row_failure_attribution
-  pair_analysis_disposition
-  original/rerun pair resolver
-  final analysis pair
-  RQ1 paired analysis
```

姣忎釜 `pair_run_id` 蹇呴』鎭板ソ涓€鏉?Manual銆佷竴鏉?Semi銆俥xternal 褰卞搷涓€琛屾椂锛屽彟涓€琛屼粛鍙负 `none`锛沺air 鏁翠綋鏈€澶氶噸璺戜竴娆°€備笉鑳藉悎娉曞畬鏁撮噸璺戝垯鏁村琛屾斂鍒犲け锛涘叧绯绘垨璇佹嵁澶辫触鍒?`not_evaluable`銆?
涓昏緭鍑猴細

```text
structurally_valid
delivery_adjusted_quality
valid_only_GT_quality
owner_valid_active_time
mode_x_risk_assist
blind_trust / correction failure / over-correction
```

## 5. V1 鏀跨瓥鎵ц娴?
```text
C2 frozen worker profile
+ frozen task pre-annotation features
+ availability snapshot
+ shared worker roster
-  block randomization: Strong Global vs Full-Integrated
-  independent symmetric capacity ledgers
-  recommendation
-  offer / accept / timeout / replacement
-  dynamic redundancy
-  GT-blind aggregation
-  resolved | unresolved | severe_failure
-  original/rerun ITT resolver
-  RQ3 analysis
```

Strong Global锛?
```text
鍦ㄥ喕缁撶殑 administratively eligible銆丵_GT-estimable cohort 涓婏細
S_u_G = z(Q_u_GT_EB)
```

`Q_GT_EB_LCB` 浠呯敤浜?safety gate銆佷笉纭畾鎬у拰 sensitivity锛屼笉鑳戒綔涓烘寮忔帓搴忋€係tructural 娴佸繀椤诲尯鍒?raw銆丒B 鍜?interval銆?
Full锛?
```text
S_u,t_F = S_u_G
          + risk_route * lambda_B * B_u_risk_shrunk
          + activated_supported_P1_component
```

涓よ噦鍏变韩鍊欓€夋睜銆乤vailability銆乹uota 瑙勫垯銆乷ffer/timeout銆乺eplacement銆佸姩鎬佸啑浣欏拰 GT-blind aggregation锛涘敮涓€瀹為獙宸紓鏄帹鑽愭帓搴忋€侳ull 鐨勬暣浣?fallback 蹇呴』绮剧‘鍥炲埌 Strong Global銆?
鏃?Random/Global/Full offline replay 浠呬负 `legacy_diagnostic`锛屼笉鑳芥浛浠ｄ笂杩板墠鐬?V1銆?
## 6. V1 failure 涓?rerun

```text
worker-caused invalid submission
-  worker event
-  鎸変袱鑷傜浉鍚?replacement rule 缁х画
-  鑻ユ渶缁?resolved锛屼笉鎶婁换鍔℃渶缁堣川閲忓己鍒剁疆 0

policy-caused failure
-  淇濈暀鍘熼殢鏈哄寲鑷?ITT
-  policy failure
-  鏃犱氦浠樻椂 delivery-adjusted quality = 0

verified external incident
-  鍚岃噦銆佸悓 freeze version銆佸绉伴鐣欏閲忎笅鏈€澶氶噸璺戜竴娆?-  resolver 浠ュ悎娉?rerun outcome 鏇夸唬 original
-  浠嶅綊 original randomized arm

external 鏃犳硶鍚堟硶閲嶈窇
-  administrative censor
```

蹇呴』鍏崇郴楠岃瘉锛?
```text
original_task_id
rerun_task_id
policy_arm
freeze_version
rerun_sequence
reservation_id
reservation_arm
reservation_capacity_before
reservation_capacity_after
```

`external_system_failure_pending_disposition` 鍙槸杩愯涓姸鎬侊紝涓嶅緱杩涘叆鏈€缁堟斂绛栫粓鎬併€?
## 7. 杈撳嚭涓庡璁?
姣忔 formal materialization 淇濆瓨锛?
```text
schema/rule/freeze version
input path + SHA-256
reference registry SHA-256
incident registry SHA-256
failure rule manifest SHA-256
code commit
random seed
dependency bundle
formal readiness
downgrade / warning / not-evaluable counts
```

鏈€缁堝垎鏋愬悓鏃舵姤鍛婏細

- C1/C2 涓夎酱銆乻upport銆丆2-B 鍥剧粨鏋勫拰 C2-A-RP stop锛?- P1 璺ㄩ樁娈?validation/confirmation锛?- Strong Global/Full activation銆乫allback 鍜屾斂绛栧樊寮傦紱
- T1 original/rerun/censor/not-evaluable/final pair锛?- V1 涓よ噦 ITT銆佺粓鎬併€佽川閲忋€佸閲忋€佹祦绋嬪拰 rerun锛?- external incident 鐨勬潯浠?鑷傚垎甯冿紱
- V1 50:50 design estimand 涓庣嫭绔嬬敓浜у垎甯冩爣鍑嗗寲 estimand銆?
浠讳綍 schema drift銆乵issing required field銆乤ctive-time source mismatch銆丼HA 澶遍厤銆佽法鑷?璺ㄧ増鏈?rerun 鎴?capacity 閫忔敮鍧?fail closed锛屼笉寰楅潤榛樺垹琛屻€?
## 8. 鍏煎璇存槑

鏃?`quality_report_*.csv`銆乣reliability_report_*.csv`銆乣r_u_calib`銆乣T_u/U_u` 鍙户缁綔涓哄吋瀹?璇婃柇瀛楁璇诲彇锛涙寮忚В閲婂垎鍒槧灏勫埌 task-level quality銆丩OO compatibility 鍜?raw diagnostic risk銆傛棫 notebook 涓€滄寜 r_u 閲嶅垎閰嶅苟涓庨殢鏈烘瘮杈冣€濈殑绀轰緥涓嶆槸褰撳墠 RQ3 姝ｅ紡鏁版嵁娴併€?
## 9. C1 provenance銆乿ariable-k 涓庢粴鍔ㄦ嫑鍕熸祦

`original_assignment`銆丼HA-bound `authorized_replacement_assignment` 涓?registered `late_entry_calibration_assignment` 鍏堢粡 canonicalization銆乨uplicate resolution 鍜?estimand eligibility锛屽啀鍒嗗埆杩涘叆 GT/peer/LOO/structural/time锛沗outside_assignment_submission` 浠呮祦鍚?raw/export銆乪xposure 涓?process audit銆俉014 姘镐箙鍦?primary 鍒嗘敮鍓嶆帓闄わ紱W034 鐨?17 鏉′笌 W001 鐨?3 鏉″彧鍦ㄦ巿鏉冦€佹彁浜ゅ強璧勬牸鍧囬綈澶囧悗鍔犲叆锛學034 B-004/B-022 浠嶅仠鐣?outside 鍒嗘敮銆傛瘡涓垎鏋愬垎鏀寜 task-condition-estimand 褰㈡垚 final unique-worker k锛宲eer 鍏?task-level 鍚庣瓑鏉冩眹鎬伙紝骞惰緭鍑?crowd support/share/cluster_margin_all and cluster_margin_top2銆?
W034 active-time 鍒嗘敮蹇呴』鍏堟秷璐?owner-valid sentinel validation manifest锛涙湭閫氳繃銆佹棭浜庨獙璇佹垨缂哄け鐨勮鍙爣涓?timing not-evaluable锛屼笉寰楁薄鏌撳叾浠?capability 鍒嗘敮銆俽olling enrollment 榛樿鍏抽棴锛涘惎鐢ㄦ椂浠?P1 pass 鍜屽喕缁?workload template 鐢熸垚鐙珛 late-entry branch锛屼笉淇敼鍘?roster锛屽苟杈撳嚭 original-only 涓?pooled profile銆傛渶缁堝皢 quality銆乸eer銆丩OO銆乺ow eligibility銆乻tructural EB銆乧ompletion銆乥uilding銆乸rovenance銆乤ctive-time銆乪nrollment 鐨?SHA 涓€骞惰緭鍏?Stage 3 freeze锛沄1 浠呮秷璐硅鍐荤粨 roster/parameters锛孏T-blind aggregation 涓嶈鍙栨斂绛栬川閲忓垎鏁般€?
## v5 瑙勮寖鎬ф暟鎹祦

鍞竴鏂规硶鐪熸簮鏄?`PAPER_A_METHOD_CONTRACT_CURRENT.json`锛涘巻鍙?outline 鍙綔闈炶鑼冩€у啓浣滆儗鏅€傛寮忔祦涓?canonical export -  assignment evidence (estimand-specific eligibility) -  frozen reference registry -  Q_GT / peer / geometry LOO / structural EB -  `worker_profile_v2` -  frozen Global `global_rank_S_G` -  Full -  Stage 3/V1銆備换浣曠己灏?formal assignment gate銆乺egistry/reference/contract SHA 鎴栧喕缁?Global rank 鐨勮緭鍏ュ潎鍦ㄥ搴旀寮忚竟鐣?fail closed銆?

