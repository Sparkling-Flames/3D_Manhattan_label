<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260730_v7 SHA-256 e2621e20af8afeb31139b0da81cfb8f740de065d83f5f4d587586d041256dc1a -->
# Paper A C1鈫扖2-B 姝ｅ紡杩愯鎵嬪唽

## 1. 闅旂鐜

```powershell
D:\anaconda\python.exe -m venv .venv-paper-a-gpu
.\.venv-paper-a-gpu\Scripts\python.exe -m pip install -r config\paper_a_analysis_requirements.lock.txt
.\.venv-paper-a-gpu\Scripts\python.exe -m pip install -r config\paper_a_torch_requirements.lock.txt --index-url https://download.pytorch.org/whl/cu128
```

姝ｅ紡鐜涓?Python 3.11銆丆UDA PyTorch銆乫loat32銆乣cuda:0`銆乸hysical batch 4銆傜壒寰佹帹鐞嗕笉鍏佽鑷姩 CPU銆丄MP 鎴?batch fallback銆?
## 2. C1 缁撴潫鍓嶅畬鎴愮殑闈欐€佸噯澶?
```powershell
$py = ".\.venv-paper-a-gpu\Scripts\python.exe"
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py prepare-c2b-static `
  --p1-closeout-dir analysis_results/prescreen_closeout_final_gold_v2_20260701 `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --legacy-manifest import_json/paper_a_c2b/legacy_reverse_v3_1_manifest.csv `
  --reference-dir data/mp3d_layout/train/img `
  --layout-dir output/layout_json `
  --c1-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --c1-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv `
  --p1-initialization-import import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json `
  --p1-initialization-import import_json/stage1_prescreen_foreign_https_20260609/stage1_prescreen_semi_import_v5_foreign_https.json `
  --building-registry <evidence-root>/authoritative_building_registry.csv `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --config config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml `
  --feature-audit-threshold-manifest docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json `
  --output-dir analysis_results/c2b_static_<sha> `
  --device cuda:0
```

棣栨灏氭棤姝ｅ紡 building registry 鏃剁渷鐣?`--building-registry`銆傚叆鍙ｅ彧鐢熸垚鏈€澶?15 涓?scene key 鐨?`authoritative_building_scene_mapping_pilot.review_queue.csv`锛沨istory 鐩存帴浠?P1/C1 鐪熸簮鎺ㄥ锛?scope/reference 鍙负缂哄け鎴栧啿绐侀」鐢熸垚鏈€灏忛槦鍒椼€備汉宸ユ壒鍑?scene 鏄犲皠鍚庡啀鎵归噺灞曞紑锛?
```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py expand-building-registry `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --approved-scene-mapping <evidence-root>/approved_scene_mapping.csv `
  --output-csv <evidence-root>/authoritative_building_registry.csv
```

鍙湁 `formal_registry_ready=true` 鐨勫睍寮€缁撴灉鍙敤浜庨噸鏂拌繍琛?`prepare-c2b-static`銆傞潤鎬佸喕缁撲骇鐗╀负
`c2b_static_freeze_manifest.json`锛屽苟缁戝畾 P1 integrity銆乫eature cache銆乺eference/candidate image/layout
娓呭崟銆乴eakage audit銆乻plit proposals銆佺幆澧冧笌浠ｇ爜 SHA銆俿plit proposals 姘歌繙淇濇寔 `candidate_only`锛?浠ｇ爜涓嶅緱鑷姩閫夋嫨鎴栫敓鎴?approval锛涘€欓€夋憳瑕佸浐瀹氫负 `c2b_source_holdout_split_proposals.summary.json`銆?
鍚屼竴璺緞鍐嶆杩愯鏃讹紝鍏ュ彛浼氬厛鏍￠獙 reference listing銆乧andidate inventory銆乧heckpoint銆乧onfig銆乧ache 鍜?audit SHA锛涘叏閮ㄥ尮閰嶆椂鍙埛鏂板鎵圭姸鎬佷笌鐜 manifest锛屼笉閲嶅杩愯 HoHoNet銆?
review queue 涓嶆槸姝ｅ紡璇佹嵁锛屼笉寰楃洿鎺ユ敼鍚嶅啋鍏?approval銆俠uilding_id 鍙兘鐢变汉宸ユ壒鍑嗙殑 scene mapping
绮剧‘灞曞紑锛涚姝粠 image/task 鍓嶇紑鎺ㄦ柇銆俿ource/holdout 蹇呴』鐢遍潤鎬佸€欓€夋柟妗堢粡浜哄伐閫夊畾鍚庣敓鎴愶紝骞剁敱涓や釜鐙珛
approval 鏂囦欢鍒嗗埆缁戝畾鍚屼竴 `selected_proposal_id`銆乸roposal summary SHA 涓庡悇鑷?evidence SHA銆?
闅忓悗杩愯闈欐€?preflight锛?
```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py preflight-calibration `
  --static-dir analysis_results/c2b_static_<sha> `
  --threshold-manifest docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json `
  --feature-audit-threshold-manifest docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json `
  --output analysis_results/c2b_static_<sha>/preflight_calibration.json
```

姝ゅ鐨?`C2B_DESIGN_SELECTION_THRESHOLDS.json` 鏄?C1 缁撴潫鍓嶅喕缁撶殑鍏紡銆佸父鏁般€佽緭鍏ュ瓧娈典笌鏂瑰悜鍚堝悓锛?涓嶆槸鏈€缁堟暟鍊?manifest銆俧eature audit 鐨勬暟鍊奸槇鍊笺€佹渶灏?audit support 涓?missing/nonfinite fail-closed
瑙勫垯涔熷凡鍦?C1 缁撴潫鍓嶅喕缁擄紱浠讳綍鍚堝悓缂洪」鏃?preflight 蹇呴』澶辫触銆?
feature audit 闃堝€艰幏鎵瑰悗锛屽厛鐢ㄥ悓涓€ `prepare-c2b-static` 鍛戒护澶嶇敤缂撳瓨骞跺埛鏂?manifest锛屽啀浠庣紦瀛樼敓鎴?C1 浠诲姟渚х壒寰侊細

```powershell
& $py tools/thesis_main/analysis/materialize_c1_preannotation_task_features.py `
  --assignment-csv analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --assignment-csv analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --building-registry-csv <evidence-root>/authoritative_building_registry.csv `
  --layout-dir output/layout_json `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --config config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml `
  --feature-freeze-manifest <static-root>/c2_feature_freeze_manifest.json `
  --output-dir <static-root> `
  --device cuda:0
```

璇ュ懡浠ゅ彧璇诲彇缂撳瓨鍜屾ā鍨嬭緭鍑猴紝涓嶈鍙?crowd geometry锛涜緭鍑?`<static-root>/c1_preannotation_task_features.csv`銆?
## 3. C1 collection freeze

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py freeze-c1 `
  --source-live-root active_logs/new_server `
  --frozen-root active_logs/c1/<cutoff>_<aggregate-sha> `
  --collection-cutoff-server-time <ISO-8601-server-time> `
  --operator <operator> `
  --late-submission-policy reject_post_cutoff `
  --active-log-freeze-manifest <formal-root>/c1_active_log_freeze_manifest.json `
  --collection-closure-manifest <formal-root>/c1_collection_closure_manifest.json `
  --export-dir export_label/stage2_Chinese `
  --export-dir export_label/stage2_English `
  --manual-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --semi-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv
```

## 4. 浜旀姝ｅ紡閾?
浠ヤ笅鍛戒护涓殑 `<formal-root>`銆乣<static-root>`銆乣<audit-root>`銆乣<c2b-design-root>` 鍜屽鎵规枃浠跺繀椤绘浛鎹负鍐荤粨鍚庣殑鐪熷疄璺緞銆俙audit-c1` 鍙兘璇诲彇 `freeze-c1` 鐢熸垚鐨?frozen root 鍜?manifest銆?
```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py audit-c1 `
  --export-dir export_label/stage2_Chinese `
  --export-dir export_label/stage2_English `
  --active-log active_logs/c1/<cutoff>_<aggregate-sha> `
  --manual-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --semi-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv `
  --worker-distribution analysis_results/calibration_rebuild_20260702/worker_distribution_internal_manifest_v3_1.csv `
  --gt-export export_label/groudTruth.json `
  --p1-closeout-dir analysis_results/prescreen_closeout_final_gold_v2_20260701 `
  --p1-integrity-dir <static-root>/p1_integrity `
  --c1-preannotation-feature-csv <static-root>/c1_preannotation_task_features.csv `
  --c1-active-log-freeze-manifest <formal-root>/c1_active_log_freeze_manifest.json `
  --collection-closure-manifest <formal-root>/c1_collection_closure_manifest.json `
  --authorized-reassignment-manifest <formal-root>/authorized_reassignment_manifest.csv `
  --calibration-enrollment-registry <formal-root>/calibration_enrollment_registry.csv `
  --w034-active-time-validation-manifest <formal-root>/w034_active_time_validation_manifest.json `
  --building-registry <evidence-root>/authoritative_building_registry.csv `
  --duplicate-adjudication <review-root>/duplicate_adjudication.csv `
  --structural-disposition <review-root>/structural_disposition.csv `
  --project-independence-disposition <review-root>/project_independence_disposition.csv `
  --scope-adjudication <review-root>/scope_adjudication.csv `
  --reference-amendment <review-root>/reference_amendment.csv `
  --outside-assignment-disposition <review-root>/outside_assignment_disposition.csv `
  --completion-disposition <review-root>/completion_disposition.csv `
  --output-root analysis_results

& $py tools/thesis_main/analysis/run_c1_closeout_launch.py finalize-c1 `
  --output-dir <audit-root> `
  --adjudication-manifest <review-root>/c1_adjudication_manifest.json

& $py tools/thesis_main/analysis/run_c1_closeout_launch.py design-c2b `
  --c1-closeout-summary <audit-root>/c1_evidence_freeze_manifest.json `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --layout-dir output/layout_json `
  --c1-task-feature-csv <static-root>/c1_preannotation_task_features.csv `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --building-registry <evidence-root>/authoritative_building_registry.csv `
  --source-split-evidence <evidence-root>/source_split_evidence.csv `
  --source-split-approval <approval-root>/source_split_approval.json `
  --future-holdout-evidence <evidence-root>/future_holdout_evidence.csv `
  --future-holdout-approval <approval-root>/future_holdout_approval.json `
  --history-overlap-audit <evidence-root>/history_overlap_audit.csv `
  --scope-registry <evidence-root>/scope_registry.csv `
  --reference-registry <evidence-root>/reference_registry.csv `
  --feature-freeze-manifest <static-root>/c2_feature_freeze_manifest.json `
  --static-freeze-manifest <static-root>/c2b_static_freeze_manifest.json `
  --threshold-formula-contract docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json `
  --threshold-input-approval <approval-root>/c2b_threshold_input_approval.json `
  --threshold-manifest <c2b-design-root>/c2b_design_selection_thresholds.derived.json `
  --capacity-manifest <approval-root>/c2b_capacity_manifest.csv `
  --output-dir <c2b-design-root> `
  --device cuda:0

# 绗竴娆¤繍琛岃嫢灏氭棤 threshold input approval锛屽彧鐗╁寲 C1 design parameters 鍜屼笅鍒楀鏍歌姹傦紝缁濅笉鏋氫妇鍊欓€夛細
# <c2b-design-root>/c2b_threshold_input_review_request.json
# reviewer 浠呮牳瀵瑰叾涓?formula contract銆丆1 design parameters銆乧apacity 涓変釜 SHA锛屾寜
# paper_a_c2b_threshold_input_approval_v1 鍐欏叆 approval 鍚庯紝鍘熸牱閲嶈窇 design-c2b銆?
# 浜哄伐瀹℃壒鍚庢墠鍏佽鎵ц锛涘鎵规枃浠跺繀椤荤粦瀹氬疄闄?selected design/task set SHA銆?& $py tools/thesis_main/analysis/run_c1_closeout_launch.py build-c2b `
  --c1-closeout-summary <audit-root>/c1_evidence_freeze_manifest.json `
  --risk-summary <c2b-design-root>/c2_task_risk.summary.json `
  --task-pool <c2b-design-root>/c2_task_risk_inventory.csv `
  --task-eligibility-evidence <c2b-design-root>/c2b_task_eligibility_evidence.csv `
  --candidate-dir <c2b-design-root>/c2_candidates `
  --design-manifest <c2b-design-root>/c2b_candidate_design_manifest.json `
  --threshold-manifest <c2b-design-root>/c2b_design_selection_thresholds.derived.json `
  --source-split-evidence <evidence-root>/source_split_evidence.csv `
  --source-split-approval <approval-root>/source_split_approval.json `
  --future-holdout-evidence <evidence-root>/future_holdout_evidence.csv `
  --future-holdout-approval <approval-root>/future_holdout_approval.json `
  --reference-registry <evidence-root>/reference_registry.csv `
  --selected-task-reference-manifest <approval-root>/selected_task_reference_approval.json `
  --selected-design-approval <approval-root>/selected_design_approval.json `
  --capacity-manifest <approval-root>/c2b_capacity_manifest.csv `
  --output-dir <c2b-build-root>
```

姝ｅ紡浜х墿鎵€鏈夋潈鍥哄畾濡備笅锛歚audit-c1` 鍙啓 `formal_audit_summary.json`銆?`c1_measurement_freeze_manifest.json` 涓庡緟鍐荤粨 worker state锛涘彧鏈?`finalize-c1` 鍙互鍐?`c1_evidence_freeze_manifest.json`銆俙design-c2b` 鍐?`c2_task_risk.summary.json`銆?`c2b_evidence_freeze_envelope.json`銆乣c2b_threshold_input_review_request.json`銆?`c2b_design_selection_thresholds.derived.json`銆乣c2b_candidate_design_manifest.json`锛屽苟鍦?`c2_candidates/c2b_design.summary.json` 淇濆瓨鍊欓€夎璁℃憳瑕併€俙build-c2b` 浠呭湪 threshold銆乻plit銆?feature銆佹満姊版淳鐢?threshold銆乻elected-task/reference銆乻elected-design 涓?capacity 瀹℃壒鍧囨湁鏁堟椂鍐?`assignment_manifest_C2B.csv`锛涘惁鍒?assignment 蹇呴』涓?0 琛屻€?鎴愬姛鏋勫缓鍚庣殑鐙珛鍚姩瀹¤涓?`c2b_launch_ready_report.json`銆傚彧鏈夎鎶ュ憡鍚屾椂婊¤冻鏂规硶鍚堝悓 SHA銆乤ssignment/distribution identity銆亀orker-facing GT 闅旂銆佸浘鐗囪矾寰勩€乧apacity銆佸鎵瑰拰鍏ㄩ儴渚濊禆 SHA 鏍￠獙鏃讹紝`C2B_LAUNCH_READY=true`锛涙湰鍏ュ彛鍙敓鎴愬惎鍔ㄥ寘锛屼笉杩炴帴鎴栧啓鍏?Label Studio銆?
浜や粯鍓嶈繍琛屽懡浠ゅ悎鍚屾鏌ワ紝闃叉鎵嬪唽杈撳叆寮曠敤涓嶅瓨鍦ㄧ殑涓婃父浜х墿锛?
```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py check-command-contract `
  --runbook docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md
```

淇濈暀涓婅堪缁嗙矑搴﹀懡浠ょ敤浜庡璁°€傛寮忔搷浣滆€呬篃鍙噯澶?`paper_a_close_c1_plan_c2b_run_config_v1` JSON锛堜粠
`PAPER_A_CLOSE_C1_PLAN_C2B_RUN_CONFIG.template.json` 澶嶅埗骞舵浛鎹㈠崰浣嶇锛夊悗浣跨敤鍙仮澶嶈杽鍏ュ彛锛涘畠浼氫緷娆￠獙璇?collection銆?杩愯 formal audit銆佸喕缁?C1 evidence銆佹牎楠?static/evidence envelope銆佺敓鎴?C2-B candidate designs锛?骞跺湪 C1 adjudication銆乻plit approval 鎴?threshold input approval 缂哄け鏃跺仠姝紝鍙繑鍥炰竴鏉￠噸璺戝懡浠わ細

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py close-c1-and-plan-c2b `
  --run-config <formal-root>/close_c1_and_plan_c2b_run_config.json `
  --state-output <formal-root>/close_c1_and_plan_c2b_state.json
```

璇ュ叆鍙ｅ皢鐘舵€佷笌杩愯閰嶇疆 SHA 缁戝畾锛氬湪 C1 瀹℃壒鎴?split 瀹℃壒缂哄け鏃跺彧杩斿洖鍚屼竴鏉″彲閲嶅叆鍛戒护锛涘€欓€夎璁℃寮忓氨缁悗锛宍next_command` 鍙繑鍥炰竴鏉′娇鐢ㄥ綋鍓?Python 瑙ｉ噴鍣ㄧ殑 `build-c2b` 鍛戒护銆?
## 5. Fail-closed 鍙ｅ緞

- PreScreen active time 鍙粦瀹?`active_logs/prescreen` 鎴?P1 immutable snapshot锛涗笉寰楃敤 C1 鏃ュ織鏇夸唬銆?- rehearsal 鍙互璇诲彇 live C1 鏃ュ織浣?`collection_window_closed=false`锛涙寮忓垎鏋愬彧鑳借鍙?`active_logs/c1/<cutoff>_<sha>`銆?- 鍘熷 `v3_1` assignment/distribution 涓嶅洖鍐欙紱W034 17 琛屼笌 W001 3 琛屽彧閫氳繃鐙珛 `authorized_reassignment_manifest.csv` 澧為噺鎵胯銆?- `audit-c1` 濮嬬粓瑕佹眰 `--calibration-enrollment-registry <...>/calibration_enrollment_registry.csv`銆俽olling 鏈縺娲绘椂 registry 蹇呴』鏄庣‘ `rolling_activated=false` 涓旀棤 late-entry 琛岋紱婵€娲绘椂 registry 瑕嗙洊鍏ㄩ儴鍘熷/鏂板 worker锛屽苟涓?completion terminal status 瀹屽叏涓€鑷淬€俙--late-entry-assignment-manifest` 鍙瘉鏄庢柊澧炰换鍔℃潵婧愶紝涓嶅啀鍐冲畾 enrollment batch銆?- W034 sentinel 鏈€氳繃鎴栭獙璇佹櫄浜庝换鍔″紑濮嬫椂锛岀浉搴旇ˉ鍏呬换鍔?timing fail closed锛屼絾涓嶅奖鍝嶅悎璧勬牸 capability evidence銆?- `valid_authorized_exception` 鍙敼鍙?process audit disposition锛屼笉鑳芥妸鏅€?outside submission 鎻愬崌涓烘寮忓垎鏋愯瘉鎹€?- `VALIDATION_ROSTER_FROZEN=true` 鍚庯紝鏂板 worker 鎴?enrollment/roster SHA 鍙樺寲蹇呴』鎷掔粷鍚姩 Stage 3銆?- `support_limited` 涓嶆槸澶辫触锛屼篃涓嶆槸鎴愬姛浼拌锛涘畠鍙〃绀鸿 estimand 宸茬粓姝絾璇佹嵁涓嶈冻銆?- threshold 鍏紡鍚堝悓銆丼HA 缁戝畾 input approval銆佹満姊版淳鐢熸暟鍊?manifest銆乫eature銆乻ource/holdout銆乻elected design 鎴?selected task approval 浠讳竴缂哄け鏃讹紝assignment 蹇呴』涓?0銆?- `P1_INTEGRITY_BUNDLE_FROZEN=true` 鍙〃绀烘枃浠跺強 SHA 宸插喕缁擄紱`P1_PREDICTIVE_EVIDENCE_READY=false` 鏃剁鐢?P1 predictive component锛屼絾涓嶉樆鏂?risk-only C2-B銆?> Formal run 鍓嶅繀椤绘牎楠?`PAPER_A_METHOD_CONTRACT_CURRENT.json`锛堢増鏈?`paper_a_method_20260730_v6`锛汼HA-256 `bde2e7e20cb00fa4f67b377112fe6534e27e7938c34fb4f63b7987fd3c142e2b`锛夈€俙close-c1-and-plan-c2b` 鏄鍒掑叆鍙ｏ紝鍙敓鎴愬€欓€変笌 `build-c2b` 鍛戒护锛沗build-c2b` 鎵嶆槸鏈€缁堝惎鍔ㄥ寘鏋勫缓鍏ュ彛銆傛棫瀛楁鎴栫敓鎴?MD銆丼AP銆丼OP 涓?JSON 涓嶄竴鑷存椂涓€寰?fail closed銆?
## v5 closeout 涓嶅彉閲?
rehearsal 鍙湪 `collection_window_closed=false` 鏃朵繚鐣?registry 涓殑 `in_progress` 绛夐潪缁堟€侊紝骞惰緭鍑?`status=provisional` 涓?`all_registered_workers_terminal=false`锛涜繖涓嶆槸 closeout銆俧ormal `audit-c1`銆乣finalize-c1` 涓?C1 closure 鍙帴鍙楃粓鎬?registry锛屽苟閫掑綊缁戝畾鍏?SHA銆乺eference registry freeze銆亀orker profile銆乄034 sensitivity 鍜屾柟娉曞悎鍚?SHA銆?

## C1-A batch snapshot and manual runtime binding

reeze-c1-batch writes c1_a_analysis_snapshot.json. It may be provisional while W034/W001 repairs are unfinished; only ormal_design_eligible opens design-c2b and does not close rolling enrollment. uild-c2b --assignment-batch C2B_BATCH_A writes the Batch A package. uild-c2b --assignment-batch C2B_BATCH_B only appends P1-passed, C1-B-completed workers under the Batch A selected_design_sha. After manual import, ind-c2b-runtime-mapping writes c2b_runtime_task_mapping.csv and c2b_worker_task_binding_audit.json; no task may be opened until this audit passes.

## Batch commands

freeze-c1-batch writes c1_a_analysis_snapshot.json. A provisional snapshot supports analysis only; formal_design_eligible opens design-c2b without closing rolling enrollment. build-c2b --assignment-batch C2B_BATCH_A writes the current-worker package. build-c2b --assignment-batch C2B_BATCH_B only appends P1-passed, C1-B-completed workers under the frozen selected_design_sha. bind-c2b-runtime-mapping writes c2b_runtime_task_mapping.csv and c2b_worker_task_binding_audit.json after manual import; no task may be opened before this audit passes.
