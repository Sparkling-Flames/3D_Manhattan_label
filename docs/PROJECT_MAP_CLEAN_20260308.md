<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260802_v17 SHA-256 5068e08ade8d1f2013b5ed66af04761c210acf74ef522229ffd39ad8f6b17b4c -->
# HOHONET 椤圭洰鍦板浘

> 2026-07-18 vFinal 鏇存柊锛歅aper A 姝ｅ紡涓荤嚎宸叉敼涓?C1 璁捐 C2-B
>锛坈ommon anchor + diverse bridge锛夈€丆2-A-RP 绮惧害琛ユ祴銆乀1 2脳2 鏉′欢璇曢獙锛?> 浠ュ強 Strong Global 瀵?Full-Integrated 鐨?V1 鍓嶇灮鍙岃噦鏀跨瓥璇曢獙銆?> `docs/thesis_main/manuscript/overleaf_project/main.tex` 鏄敮涓€璁烘枃鍏ュ彛锛?> 宸插垹闄よ宸ョ▼鍐呮湭寮曠敤鐨勬棫鐗堥噸澶嶇珷鑺傘€侰1 鍘熷 export銆乤ssignment 鍜屾爣娉ㄧ晫闈㈡湭鏀瑰彉銆?> 鏂版寮忓疄鐜颁綅浜?`tools/thesis_main/analysis/materialize_main_failure_outcomes.py`銆?> `build_c2_assignment_manifest_from_c1_gaps.py`銆乣c1_materialize_c2_gap_audits.py`
> 鍜?`routing/v1_policy.py`锛涘垎鍒礋璐ｅ畬鏁翠簨鏁呭缃笌 resolver銆丆2-B銆丆2-A-RP
> 浠ュ強 Strong Global/Full-Integrated 鐨?V1 鍓嶇灮鎵ц銆?> `tools/thesis_main/analysis/materialize_vfinal_main_analysis.py` 鍙秷璐?resolver
> 鏈€缁堣〃锛岀敓鎴?T1 pair estimand 涓?V1 ITT/璁捐鍜岀敓浜ф爣鍑嗗寲缁撴灉銆?
鏇存柊鏃堕棿锛?026-06-08

鏈湴鍥捐褰曞綋鍓嶄粨搴撶殑涓昏鐩綍杈圭晫銆傛柊澧炪€佸垹闄ゃ€佺Щ鍔ㄦ枃浠跺悗蹇呴』妫€鏌ユ湰鏂囨。鏄惁闇€瑕佸悓姝ャ€?
## 椤跺眰鐩綍

- `tools/`锛氳剼鏈拰杩愯璧勬簮锛屾寜璁烘枃绾夸笌鍏变韩杩愯灞傛媶鍒嗐€?- `docs/`锛氬崗璁€丼OP銆佸瓧娈靛悎鍚屻€佽鏂囩嚎鏂囨。鍜?agent 瑙勫垯锛涜鏂囨ā鏉?鍙傝€冭祫鏂欑瓑澶у潡鍐欎綔璧勪骇榛樿鎸?`.gitignore` 鐣欏湪鏈湴銆?- `import_json/`锛歱lanned import / planned split 鐪熸簮銆?  - `stage1_prescreen_foreign_https_20260609/`锛歋tage 1 / P1 澶栧浗鏍囨敞鍛?HTTPS Label Studio 瀵煎叆鍖咃紱浠呭皢姝ｅ紡涓枃鍖呯殑 `data.vis_3d` base URL 鏀逛负 `https://label.sparkle0825.top`锛屼换鍔℃睜銆侀『搴忋€乵etadata銆乸roposal 涓庡浘鐗?URL 淇濇寔涓嶅彉銆?- `export_label/`锛歀abel Studio 杩愯鏃舵爣娉ㄥ鍑虹湡婧愶紝涓嶄綔涓鸿剼鏈啓鍏ョ洰鏍囥€?- `active_logs/`锛氬師濮?`active_time` 鏃ュ織鐪熸簮锛沗operational_incidents/` 淇濆瓨 C1 璧蜂笉鍙彉鐨勮繍琛屼簨鏁呰瘉鎹紝涓嶄笌鍒嗘瀽杈撳嚭娣风敤銆?- `analysis_results/`锛氱敓鎴愮粨鏋溿€佸璁°€乵anifest銆佸浘琛ㄥ拰涓棿鍒嗘瀽浜х墿銆?- `tests/`锛歵ools 涓庡瓧娈靛悎鍚岀殑 pytest 瑕嗙洊锛汸aper A 姝ｅ紡閾炬柊澧炴寜 `contracts/`銆乣c1/`銆乣c2b/`銆乣e2e/` 鍒嗙被锛屾湭鍒嗙被鍘嗗彶娴嬭瘯缁х画淇濈暀鍦ㄦ牴鐩綍銆?- `data/`锛氭暟鎹祫浜с€?- `output/`锛欻oHoNet 鎺ㄧ悊涓庝腑闂翠骇鐗┿€?- `trap闆?`锛歵rap / manual 鍊欓€夌礌鏉愬眰銆?
## tools 甯冨眬

- `tools/thesis_main/data_prep/prepare_c2b_validation_inputs.py`: builds the validation-only C2-B input bundle; C1 and legacy rows remain support-only.

- `tools/README.md`锛歵ools 鎬诲叆鍙ｏ紱鏍圭洰褰曚笉鍐嶄繚鐣欐棫鑴氭湰 wrapper銆?- `tools/thesis_main/`
  - 璁烘枃涓荤嚎宸ュ叿銆?  - `analysis/`锛氳川閲忓垎鏋愩€乤ctive-time audit銆乻tage-aware 鍒嗘瀽銆佸浘琛ㄣ€佺粺璁℃眹鎬汇€?    - `c1_live_collection_monitor.py`銆乣c1_canonicalize_exports.py`銆乣failure_disposition.py`銆乣materialize_main_failure_outcomes.py`銆乣c1_materialize_quality_table.py`銆乣c1_materialize_worker_state.py`銆乣c1_materialize_worker_profile_sidecar.py`銆乣c1_materialize_c2_gap_audits.py`銆乣build_c2_assignment_manifest_from_c1_gaps.py`銆乣materialize_c2b_task_eligibility.py`銆乣materialize_p1_post_closeout_evidence_correction.py` 涓?`materialize_p1_post_closeout_geometry_scores.py`锛欳1 live 鐩戞帶銆乧anonicalization銆佸け璐ュ綊鍥犮€侀€愯酱璇佹嵁銆丆2-B 涓ユ牸浠诲姟璧勬牸銆佸€欓€夎璁′笌鍐荤粨 assignment 娑堣垂锛屼互鍙婂彧璇?P1 post-closeout evidence/geometry correction銆?    - `rebuild_stage1_chinese_completion_excel.py`锛氭寜鏈€鏂?`鏍囨敞浜哄憳.xlsx`銆乣閫€鍑烘爣娉?xlsx`銆丼tage 1 涓枃 LS JSON 瀵煎嚭鍜?active logs 閲嶇畻涓枃 P1 瀹屾垚鎯呭喌宸ヤ綔绨裤€?  - `registry/`锛歳egistry銆乵anifest銆乫reeze銆乫inal-gold銆乼rap/materialization銆乺isk-rule銆丆2 failure-disposition manifest銆乣d_t/g_t` dry-run銆乪xport inventory銆?  - `data_prep/`锛氭暟鎹泦鍑嗗鍜?MP3D smoke/import 鐢熸垚銆?  - `foreign_recruitment/`锛歅1/PreScreen 澶栧浗鏍囨敞鍛?HTTPS 鑻辨枃閫傞厤鍖呫€?- `tools/paper_b/`
  - Paper B 宸ュ叿銆傚綋鍓嶅寘鎷?`validate_b0_relabel_audit.py`锛涘悗缁?B0/B1/B2 璁粌銆乧ue銆乥ilayout銆佸璁¤剼鏈彧杩涙湰鐩綍銆?- `tools/label_studio/`
  - 涓夋潯绾垮叡浜殑 Label Studio XML銆?D viewer銆乻erver/CORS銆丆OS/upload銆乮mport/build helper 鍜?`official/`銆傚巻鍙?C1 XML 淇濇寔鍘熻涔夛紱C2/Stage3 鏈潵璇箟浣跨敤 `label_studio_view_config_c2_future.xml` 涓庤嫳鏂囧搴旀枃浠讹紱鍐荤粨 SHA 璁板綍鍦?`tools/label_studio/label_studio_c1_xml_freeze_manifest_v1.json`銆?  - `vis_3d_pre_m15_19_2_backup.html`锛歝ommit `f6d53b0` 鐨?viewer 鍘熸牱澶囦唤锛屼粎鐢ㄤ簬鍥炴粴/瀵圭収锛屼笉鏄繍琛屾椂鍏ュ彛銆?  - 浜戞湇鍔″櫒杩愯鏃?URL `/tools/vis_3d.html` 淇濇寔鍏煎锛岃繖鏄儴缃茶矾鐢憋紝涓嶄唬琛ㄦ簮鐮佷粛鍦?`tools/` 鏍圭洰褰曘€?- `tools/legacy/`銆乣tools/legacy_server/`銆乣tools/backups/`
  - 鍘嗗彶鎴栧浠界洰褰曪紝榛樿涓嶈縼绉汇€佷笉淇銆?
## docs 甯冨眬

- `docs/README_INDEX.md`锛歞ocs 鎬荤储寮曘€?- `docs/PROJECT_MAP_CLEAN_20260308.md`锛氭湰鏂囦欢锛屼粨搴撳湴鍥俱€?- `docs/thesis_main/`
  - 姝ｅ紡鎵ц涓荤嚎鏂囨。銆?  - 鍖呮嫭 protocol銆乤ssignment SOP銆丳reScreen銆丆alibration銆丮ain(Test + Validation)銆佺粺璁¤鍒掋€佸瓧娈靛悎鍚屻€亀orker-profile sidecar contract銆乫inal-gold銆乺egistry銆佽鏂囦富绾垮啓浣滄潗鏂欍€?  - Paper A 鍞竴瑙勮寖鏂规硶鐪熸簮涓?`PAPER_A_METHOD_CONTRACT_CURRENT.json`锛沗Paper_A_鏂扮増瀹屾暣璁烘枃鎻愮翰_vFinal_Draft.md` 宸叉爣涓?superseded 鐨勯潪瑙勮寖鎬у啓浣滆儗鏅€倂3-v5 鎻愮翰銆佽縼绉?map/audit 涓?standalone `.tex` 宸插綊妗ｅ埌 `docs/legacy/paper_a_pre_vfinal_20260724/`锛沗WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md` 绛夊瓧娈靛悎鍚岀户缁繚鐣欍€?  - `manuscript/` 鍙繚瀛?Overleaf 椤圭洰鍜屼富绾胯鏂囧啓浣滆祫浜э紝浣嗘寜鐜版湁 `.gitignore` 榛樿涓嶆彁浜ゃ€?  - `tools/thesis_main/analysis/materialize_c2b_closeout.py` 缁戝畾 C2-B submissions銆乸ost-C2-B profile銆乸rofile manifest 涓?design summary锛屽舰鎴?C2-A-RP formal 鎵€闇€鐨勭湡瀹?SHA closeout銆?  - `tools/thesis_main/analysis/materialize_frozen_routing_profiles.py` 浠?Manual GT submission銆佸喕缁?worker state 鍜岃法闃舵 component evidence 鐢熸垚 Strong Global 涓?Full component 鍐荤粨琛ㄣ€?  - Paper A vFinal 浠ｇ爜杩佺Щ鍚堝悓銆佸洓涓€欓€?rule manifest 涓庡璁¤褰曚繚瀛樺湪璇ョ洰褰曪紱杩欎簺鏂囦欢鍙畾涔夊彲瀹¤鐨勭粨鏋勫拰鍊欓€夎鍒欙紝涓嶆妸 dry-run 浜х墿鍗囩骇涓烘寮?C1 鏁版嵁銆傚搴旂殑 canonical鈫抍oncrete-tag銆丟eometry LOO 涓?temporal replay 浠ｇ爜浣嶄簬 `tools/thesis_main/analysis/`锛屼笖鏃犳寮?export 鏃跺彧鑳借緭鍑?dry-run/not-evaluable銆?  - Paper A vFinal 浠ｇ爜杩佺Щ鍚堝悓銆佸洓涓€欓€?rule manifest 涓庡璁¤褰曚繚瀛樺湪璇ョ洰褰曪紱杩欎簺鏂囦欢鍙畾涔夊彲瀹¤鐨勭粨鏋勫拰鍊欓€夎鍒欙紝涓嶆妸 dry-run 浜х墿鍗囩骇涓烘寮?C1 鏁版嵁銆?- `docs/paper_b/`
  - Paper B 鏀嚎鏂囨。銆?  - 鍖呮嫭 ambiguity-aware HoHoNet銆乑InD mapping銆丅-line freeze/audit銆佹ā鍨嬫灦鏋勫拰鍚庣画璁粌璁″垝銆?- `docs/label_studio/`
  - Label Studio CE-only銆乤ctive-time銆佷簯绔儴缃层€丆OS銆佹爣娉ㄥ憳/寮€鍙戣€呰鏄庛€?- `docs/agent/`
  - Agent 涓婁笅鏂囥€乸laybook銆佸啓鍏ヨ鍒欏拰缁?Codex 鐨勮ˉ鍏呰鏄庛€?  - 鍏抽敭鍏ュ彛锛歚AGENT_CONTEXT_INDEX.md`銆乣REPO_PATH_MAP.md`銆乣WRITE_RULES.md`銆乣playbooks/`銆?- `docs/shared/`
  - 璁烘枃妯℃澘銆佸弬鑰冭祫鏂欍€佸叡浜啓浣滆祫浜э紱鎸夌幇鏈?`.gitignore` 榛樿涓嶆彁浜ゃ€?- `docs/legacy/`
  - 鍘嗗彶鏉愭枡锛岄粯璁や笉杩佺Щ銆佷笉淇銆?
## 鐪熸簮涓庤緭鍑哄眰

- `import_json/` 鏄?planned import / planned split 鐪熸簮銆?- `export_label/` 鏄?Label Studio 杩愯鏃跺鍑虹湡婧愶紱鏈 tools/docs 杩佺Щ涓嶅啓鍏ャ€佷笉绉诲姩銆佷笉閲嶅懡鍚嶃€?- `active_logs/` 鏄師濮?active-time 鏃ュ織鐪熸簮锛沗active_logs/operational_incidents/` 鏄?C1 璧峰閮ㄧ郴缁熶簨鏁呯殑鍘熷璇佹嵁婧愩€?  - 浜戞湇鍔″櫒绔粛搴斾綅浜庝粨搴撴牴涓嬶紝渚嬪 `/home/ubuntu/workspace/HoHoNet/active_logs/`銆?  - 鑻ヤ簯绔缃?`ACTIVE_LOG_DIR="active_logs/new_server"`锛屾柊鏃ュ織搴旇繘鍏?`/home/ubuntu/workspace/HoHoNet/active_logs/new_server/`銆?  - `tools/label_studio/cors_server.py` 鐨勬簮鐮佽縼绉讳笉搴旀敼鍙樻棩蹇楀瓨鍌ㄦ牴鐩綍銆?- `analysis_results/` 鏄緭鍑恒€佸璁″拰鍥捐〃钀界洏鍖猴紝涓嶆槸杈撳叆鐪熸簮銆?
## 鍐欏叆涓庤縼绉昏鍒?
- 鏂板 `tools/` 鑴氭湰蹇呴』杩涘叆瀵瑰簲璁烘枃绾挎垨鍏变韩 Label Studio 鐩綍锛屼笉寰楃洿鎺ユ斁鍦?`tools/` 鏍圭洰褰曘€?- 鏂板 `docs/` 涓婚鏂囨。蹇呴』杩涘叆瀵瑰簲鍒嗙被鐩綍锛屼笉寰楃洿鎺ユ斁鍦?`docs/` 鏍圭洰褰曘€?- 涓荤嚎宸ュ叿鍜屾枃妗ｅ垎鍒繘鍏?`tools/thesis_main/` 涓?`docs/thesis_main/`銆?- Paper B 宸ュ叿鍜屾枃妗ｅ垎鍒繘鍏?`tools/paper_b/` 涓?`docs/paper_b/`銆?- Label Studio 鍏变韩璧勬簮鍜岃鏄庡垎鍒繘鍏?`tools/label_studio/` 涓?`docs/label_studio/`銆?- Agent 瑙勫垯鍜?playbook 杩涘叆 `docs/agent/`銆?- legacy 榛樿涓嶈縼绉汇€佷笉淇銆?- 涓嶆敼鍙?protocol銆乻chema銆乺outing銆丼OP 璇箟銆?## 2026-07-24 Paper A 鍒嗘瀽閾炬敹鍙ｈˉ鍏?
  鍒嗗眰鐗╁寲锛涚己 C2-B 鏃?Full 鑷姩绂佺敤銆?- `tools/thesis_main/analysis/materialize_main_inference.py`锛歍1 image-level 涓?V1 ITT 鐨?manifest/SHA 缁戝畾

`docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json` 鏄敮涓€瑙勮寖鏂规硶鐪熸簮锛涘悓鐩綍淇濆瓨鐢熸垚 MD 鍜屼簲涓?v2 schema銆傚叡浜獙璇併€乬eometry銆丼tage 3銆乀1/V1 online/replay 宸ュ叿浣嶄簬 `tools/thesis_main/analysis/`銆?
- docs/thesis_main/PAPER_A_REFERENCES_NEEDED_CHECKLIST.md锛氱浉鍏冲伐浣滀笌寮曠敤鏍搁獙寰呭姙锛涗笉鏋勬垚鏂规硶鍚堝悓銆?

## 2026-08-02 C2-B pre-dispatch amendment

- `docs/thesis_main/C2B_PREDISPATCH_METHOD_AMENDMENT_v1.json`：v17 绑定的 D8/D10/D12 统一候选生成与 gate 语义修订；不改变数值阈值。

## 2026-07-30 Paper A C1-A/C2-B batch boundary

- un_c1_closeout_launch.py 统一提供 reeze-c1-batch、design-c2b、uild-c2b --assignment-batch 和 ind-c2b-runtime-mapping；它们不连接 Label Studio API。
- PAPER_A_C1_BATCH_SCOPE.template.json 定义 C1-A scope：original cohort、W034 17 张、W001 3 张，以及如 W011 漏交任务的显式 completion exception。
- Stage 3 只读取全局 enrollment closed、all terminal 和 final pooled profile 状态；C1-A snapshot 不可替代该门。
