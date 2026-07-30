<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260731_v9 SHA-256 de7d99f4d119a87a48cfaa4e5c30c9d11161da43f8c1c37e34a6550c8b68f86c -->
# Statistical Analysis Plan v1

> 瑙勮寖鎬ф柟娉曞瓧娈靛彧鏉ヨ嚜 `PAPER_A_METHOD_CONTRACT_CURRENT.json`锛堢増鏈?`paper_a_method_20260730_v6`锛汼HA-256 `bde2e7e20cb00fa4f67b377112fe6534e27e7938c34fb4f63b7987fd3c142e2b`锛夈€傛墽琛屾椂蹇呴』鏍稿鑷姩鐢熸垚 MD 鎵€鍒?JSON SHA锛涙湰鏂囦笉鍐嶇嫭绔嬪畾涔夊啿绐佸瓧娈点€?
## 0. 閫傜敤鑼冨洿涓庢浛浠ｅ０鏄?
鏈枃瑕嗙洊 P1/C1/C2銆乀1 鍜?V1 鐨勬寮忓垎鏋愩€傝鑼冩€у瓧娈靛彧鐢卞綋鍓?JSON 鏂规硶鍚堝悓瀹氫箟锛涘巻鍙叉彁绾蹭粎浣滆璁¤儗鏅紝骞舵浛鎹㈡棫鐨勶細

- Calibration_manual 涓?Random/Global/Full 绂荤嚎 replay 浣滀负 RQ3 涓绘瘮杈冿紱
- reserve-only C2锛?- 鍗曡噦 Full deployment V1锛?- Geometry LOO 鍗曠嫭鍐冲畾姝ｅ紡 Global銆?
Replay 鍙敤浜庡紑鍙戙€佹秷铻嶃€佽璁″拰鍔熸晥锛屼笉鏇夸唬鍓嶇灮 V1銆?
## 1. 閫氱敤鍘熷垯

### 1.1 闃舵闅旂

- P1锛歛dmission銆侀珮淇℃伅璇婃柇鍜岄娴嬪€欓€夛紱
- C1锛氬熀纭€鑳藉姏銆佷换鍔¤皟鏁淬€丆2/T1/V1 璁捐鍙傛暟锛?- C2锛氬叡鍚屾ˉ鎺ャ€佸眰绾ф敹缂┿€佺簿搴﹁ˉ榻愬拰鏈€缁堝喕缁擄紱
- T1锛歊Q1 Semi 鏉′欢鏁堝簲锛?- V1锛歊Q3 Strong Global vs Full-Integrated 鍓嶇灮鏀跨瓥鏁堝簲銆?
T1/V1 缁撴灉涓嶅緱淇敼浠讳綍 Calibration 鍙傛暟銆乸olicy銆乺isk銆乼hreshold銆乧apacity銆乻top rule 鎴栧垎鏋愯鍒掋€?
### 1.2 鍒嗘瀽璧勬牸

active-time銆丟T quality銆丩OO銆乻tructural failure銆乸redictive validity 鍜?routing feature 鍒嗗埆浣跨敤鑷繁鐨?eligibility銆備笉寰椾娇鐢ㄥ崟涓€ `valid` 杩囨护鍏ㄩ儴鍒嗘瀽銆?
### 1.3 Failure 涓?missingness

琛岀骇 failure attribution 涓?pair/task analysis disposition 鍒嗗紑銆?
- worker-caused structural failure锛氫繚鐣欏湪鍘?worker/condition/arm 鐨勭粨鏋勬満浼氫腑銆?- policy-caused failure锛氫繚鐣欏湪鍘熸斂绛栬噦 ITT銆?- external system failure锛氬彧鏈変笉鍙彉璇佹嵁銆丼HA銆佽寖鍥淬€佷簨鏁呯獥鍙ｅ拰缁撴灉鍙鍓嶇櫥璁板潎楠岃瘉閫氳繃鎵嶆垚绔嬨€?- not evaluable锛氳瘉鎹笉瓒虫垨鍏崇郴楠岃瘉澶辫触锛屼笉寰楅潤榛樻敼浣?complete case銆?
姣忛」鍒嗘瀽鍚屾椂鎶ュ憡鍘熷銆亀orker failure銆乸olicy failure銆乪xternal rerun銆佽鏀垮垹澶便€乶ot-evaluable 鍜屾渶缁堝彲鍒嗘瀽鏁伴噺鍙婁袱鑷?鏉′欢鍒嗗竷銆?
### 1.4 鍔熸晥涓?MDE

C1 closeout 鍚庝娇鐢?worker/image/building 鏂瑰樊銆佺粨鏋勬湁鏁堢巼銆乤ctive-time missingness銆乸olicy divergence銆乧apacity 鍜?timeout 妯℃嫙 C2銆乀1銆乂1銆侻DE銆乬ate 鍜屾牱鏈噺鍦?Main outcome 鍙鍓嶅喕缁撱€?
## 2. C1/C2 worker state 涓庨娴嬭瘉鎹?
### 2.1 涓夎酱鐘舵€?
姝ｅ紡鍩虹鐘舵€佷负锛?
```text
Q_u_GT_task_adjusted
R_u_peer
F_u_struct
```

GT quality 浣跨敤浜ゅ弶鍒嗙被妯″瀷鏍℃ worker 鐨勪换鍔＄粍鎴愶紝渚嬪锛?
```text
Q_GT(t,u) = mu + worker_u + task_t + error
```

鎶ュ憡 raw 涓綅鏁般€乼ask-adjusted estimate銆丆I/LCB銆乻upport 鍜?worker-task 鍥惧璁°€?
R_peer 浣跨敤 task-equal 鑱氬悎锛屽苟鎸夋柟娉曞悎鍚岀殑 support 闃堝€艰緭鍑?`not_evaluable/weak_descriptive/estimated`銆侺OO 浣跨敤鎺掗櫎宸ヤ汉鑷韩鐨?reference锛屾姤鍛?medoid/strict 鐘舵€佷笌 sensitivity锛汱OO 浠呮槸涓€鑷存€у璁″拰鍙敤鏃剁殑 tie-break锛屼笉灞炰簬姝ｅ紡涓夎酱锛屼篃涓嶆浛浠ｅ閮?GT quality銆?
C1-only 妯″瀷浣跨敤 task effect 涓斾笉鍚屾椂浼拌 stage effect銆傚悎骞?C1+C2 鏃朵娇鐢?building/task fixed effect 涓?stage fixed effect锛涜嫢娌℃湁璺ㄩ樁娈靛叡鍚?anchor 鎴栨敮鎸佽闅忔満鏁堝簲缁撴瀯鐨勬暟鎹紝stage effect 鏍囦负涓嶅彲璇嗗埆锛屼笉浠?task 涓?stage 瀹屽叏娣锋穯鐨勬暟鎹腑瑙ｉ噴銆?
缁撴瀯澶辫触鐜囦负锛?
```text
worker-caused invalid geometry
/
structural-evaluable opportunities
```

external銆乺eference failure銆丱OS 鍜屾湭鐭ュ綊鍥犱笉杩涘叆鍒嗘瘝銆?
### 2.2 P1 predictive chain

P1 component 鍒嗗埆璇勪及 `P1 -> C1`銆乣P1 -> C2-B` 鍜?`P1 -> T1`锛?
- Spearman/Kendall锛?- worker bootstrap CI锛?- 鏂瑰悜涓€鑷存€э紱
- discrepancy worker锛?- support锛?- range restriction銆?
鍙湁 C1 predictive validation 鍜?C2-B confirmation 鍧囬€氳繃銆乻upport 杈炬爣涓斿彲鐢辨爣娉ㄥ墠鐗瑰緛婵€娲荤殑 component 鎵嶈繘鍏?Full銆侰2-A-RP 鍙ˉ绮惧害锛屼笉鐢ㄤ簬鍙戠幇鎴栨寫閫夋柊 component銆?
### 2.3 C2-B simulation 涓庡眰绾фā鍨?
C1 鍚庢ā鎷?common anchor銆乨iverse bridge銆乽nique task銆佹瘡鍥?support銆亀orker-task 鍥捐繛閫氭€у拰椋庨櫓闊ф€у尯闂村搴︼紝浠ュ喕缁?C2-B 璁捐銆?
椋庨櫓闊ф€т娇鐢ㄥ眰绾ф敹缂╂ā鍨嬶細

```text
Q_GT(u,t)
= global_worker_u
+ route_risk_t
+ worker_specific_route_slope_u
+ stage
+ task_effect
+ error
```

杈撳嚭鏀剁缉 estimate銆乮nterval銆乴eave-one-task/block-out stability 鍜?routing eligibility銆傝揪鍒?C2-A-RP 涓婇檺浠嶄笉绋冲畾鏃讹紝璇ヨ皟鏁翠负 0 骞?fallback Strong Global銆?
## 3. Strong Global 涓?Full 閫夋嫨鍚堝悓

### 3.1 Strong Global

姝ｅ紡 Global 鐨?eligibility 鍩轰簬 process/independence銆丟T support銆佺粨鏋勫け璐?gate 鍜?task-adjusted GT quality floor銆傛帓搴忓垎鏁颁负锛?
```text
S_G(u) = z(Q_u_GT_EB)
```

LOO 浠呯敤浜庡喕缁?tie-break 鎴?compatibility 瀹¤銆?
### 3.2 Full-Integrated

Full 鍦?Global 鍩虹嚎涔嬩笂澧炲姞锛?
- `risk_route` 婵€娲荤殑鏀剁缉 worker risk-resilience锛?- 缁?P1鈫扖1鈫扖2-B 楠岃瘉銆佷笖鐢辨爣娉ㄥ墠浠诲姟 family 鍞竴婵€娲荤殑 P1 component銆?
鏉冮噸鍙湪 image/base-task 鍒?fold 鐨?nested cross-fitting 涓€夋嫨锛屼娇鐢ㄥ皬鍨嬬鏁ｉ泦鍚堛€佹€昏皟鏁翠笂闄愬拰 one-standard-error 鍘熷垯銆傝瘎浠?fold 涓嶅緱鍙備笌 feature銆亀eight銆乻upport銆乫allback 鎴?stopping 鐨勯€夋嫨銆?
### 3.3 鏀跨瓥宸紓鍙鎬?gate

Main 鍓嶆姤鍛?activation銆乫allback銆佹帹鑽愰閫変笉鍚岀巼銆佸垵濮?worker 闆嗕笉鍚岀巼銆乻upported candidate count 鍜?capacity 鍚庡樊寮傘€傝嫢鏈揪鍒伴娉ㄥ唽闃堝€硷紝V1 涓嶅惎鍔ㄥ苟鎶ュ憡鏀跨瓥涓嶅彲鍖哄垎锛涗笉寰楃敤 V1 outcome 鏀惧闃堝€笺€?
## 4. RQ1锛歍1 Semi-Auto 鏉′欢鏁堝簲

### 4.1 璁捐

```text
Manual / Semi
x
ordinary / stress_assist
```

姣忓浘 `2 Manual + 2 Semi`銆傚垎鏋?`pair_id` 鎭板ソ鍖呭惈涓€鏉?Manual 鍜屼竴鏉?Semi锛涘悓涓€鍥句袱鏉?pair 鍧囪繘鍏?image-level 姹囨€汇€傚伐浜轰笉寰楃湅鍒板悓鍥句袱绉嶆ā寮忥紝worker 鍐呭钩琛?mode/risk锛屽苟淇濆瓨 assignment probability銆?
### 4.2 Primary outcomes

submission-level delivery-adjusted quality锛?
```text
U(t,u) = I(structurally_valid) * IoU(annotation, GT)
```

worker-caused structural failure 鐨?`U=0`銆?
姣忎釜 image-condition 鐨勪袱鏉″悎娉?submission 鍙栧潎鍊硷細

```text
U_bar(t,c) = mean_u U(t,u,c)
D(t) = U_bar(t,Semi) - U_bar(t,Manual)
```

涓昏璐ㄩ噺 estimand 鏄?image-level paired `D(t)`銆備袱鍚嶅伐浜烘病鏈夊ぉ鐒跺鏁帮紱鏈喕缁撹瀺鍚堢畻娉曟椂锛屼笉鎶婂弻鏍囨敞鑱氬悎 IoU 浣滀负涓荤粨鏋溿€?
### 4.3 External pair resolver

鑻?pair 涓换涓€琛屾湁鍚堣 external incident锛?
- 鏈彈褰卞搷琛屼粛淇濇寔 `row_failure_attribution=none`锛?- 瀹屾暣 Manual/Semi pair 鍦ㄥ師鏉′欢銆佸師 freeze version 鍜?worker-image 闅旂涓嬫渶澶氶噸璺戜竴娆★紱
- resolver 浣跨敤鍚堟硶 rerun pair 鏇夸唬 original pair锛?- 鏃犳硶瀹屾暣閲嶈窇鏃舵暣瀵硅鏀垮垹澶憋紱
- 闈炴硶璇佹嵁/鍏崇郴鍒欐暣瀵?`not_evaluable`銆?
琛屾斂鍒犲け涓嶆槸闆跺€硷紝涓斾笉寰楀彧鍒犻櫎鏌愪竴鏉′欢銆傛墍鏈夊喅瀹氬湪鏉′欢 outcome 鍙鍓嶅喕缁撱€?
### 4.4 鎺ㄦ柇灞傜骇

1. 缁撴瀯鏈夋晥鐜囦笌 delivery-adjusted quality 鐨勯潪鍔?瀹夊叏闂紱
2. owner-valid active time锛?3. mode 脳 `risk_assist` interaction锛?4. blind trust銆乧orrection failure銆乷ver-correction銆丮odel Issue recognition銆?
涓绘帹鏂皧閲?image pairing锛屽苟鐢?worker/image/building 灞傜骇 bootstrap銆乸ermutation 鎴栫浉搴?mixed model锛涗笉寰楁妸 naive annotation-level 鐙珛鏍锋湰妫€楠屼綔涓哄敮涓€涓绘楠屻€?
### 4.5 Active-time downgrade

Primary 鍙娇鐢?owner-valid active time锛屼笉浣跨敤 Label Studio `lead_time`锛屼笉鍥哄畾鎵ｉ櫎浼扮畻鐨?Model Issue 鏃堕棿銆?
鑻ユ煇 mode/risk cell 鐨?owner-valid coverage 鏈揪鍒板喕缁撻槇鍊硷細

- active-time 浠庣‘璁ゆ€ч檷涓?descriptive/sensitivity锛?- 涓嶅奖鍝嶈川閲忎笌缁撴瀯涓诲垎鏋愶紱
- 鎶ュ憡 coverage銆佺己澶辨ā寮忓拰 downgrade 鍘熷洜銆?
## 5. RQ2锛歅1 璺ㄩ樁娈甸娴嬫晥搴?
RQ2 浠?worker-level 棰勬祴鍏宠仈銆佹晥搴旈噺銆佹柟鍚戜竴鑷存€у拰鏀寔涓轰富锛屼笉鎶?exploratory family 缁撴灉鍗囩骇涓哄洜鏋滅粨璁恒€?
濡傛灉淇濈暀棰勫厛鍐荤粨鐨?paired counterexample subset锛屼娇鐢?image-paired permutation/bootstrap锛涘弽渚嬬被鍨嬪垎甯冧娇鐢?paired/multilevel 鏂规硶锛屼笉鐢ㄦ櫘閫?chi-square 浣滀负鍞竴涓绘楠屻€?
鏀寔涓嶈冻銆乺ange restriction 鎴?multiple-testing 椋庨櫓蹇呴』鎶ュ憡銆傛湭缁?C1 鍜?C2-B 鍙岄噸楠岃瘉鐨?P1 component 淇濇寔 diagnostic-only銆?
## 6. RQ3锛歏1 鍓嶇灮鏀跨瓥璇曢獙

### 6.1 璁捐涓?ITT

V1 鍦?task/block 灞傚皢浠诲姟闅忔満鍒嗛厤鑷?Strong Global 鎴?Full-Integrated銆傚師濮嬮殢鏈哄寲浠诲姟鏄?ITT 鍗曚綅銆?
涓よ噦鍏变韩 worker pool銆佸€欓€?roster 鍜?availability snapshot锛屼娇鐢ㄥ绉?worker quota 涓庣嫭绔嬪閲忚处鏈€俹ffer銆乼imeout銆乺eplacement銆乧andidate exhaustion銆乨ynamic redundancy銆丟T-blind aggregation 瀹屽叏鐩稿悓锛涘敮涓€宸紓鏄帹鑽愭帓搴忋€?
### 6.2 Rerun resolver

external task 鍙湪鍚?policy arm銆佸悓 freeze version銆佸绉伴鐣欏閲忎笅鏈€澶氶噸璺戜竴娆°€傚繀椤诲叧绯婚獙璇?original/rerun task銆乺eservation ID銆乺eservation arm銆乻equence 鍜?capacity before/after銆?
- 鍚堟硶 rerun outcome 鏇夸唬 original outcome锛屼絾浠嶅綊鍘熼殢鏈哄寲鑷?ITT锛?- 鏃犳硶鍚堣 rerun 鏃惰鏀垮垹澶憋紝涓嶈繘鍏ヨ川閲忓垎姣嶏紱
- `external_system_failure_pending_disposition` 涓嶈兘浣滀负鏈€缁堟斂绛栫粓鎬侊紱
- policy-caused failure 淇濈暀鍘熻噦 ITT锛?- worker invalid 鍚庤嫢鎸夌浉鍚屾浛琛ヨ鍒?resolved锛屼笉鎶婃渶缁堜换鍔¤川閲忔敼涓?0銆?
### 6.3 Outcomes

鏈€缁堢粓鎬佷负 `resolved`銆乣unresolved`銆乣severe_failure`銆?
涓昏鎸囨爣锛?
```text
severe failure
unresolved + severe failure
delivery-adjusted quality
resolved-only GT quality
k_used
owner-valid active time
completion time
policy x risk_route interaction
```

delivery-adjusted quality锛?
```text
U_task = I(resolved) * IoU(policy_output, GT)
```

unresolved/severe failure 鐨?`U_task=0`锛岃〃绀烘湭浜や粯姝ｅ紡甯冨眬锛屼笉澹扮О鐪熷疄鍑犱綍 IoU 涓洪浂銆?
### 6.4 妫€楠屽眰绾?
1. severe failure 涓嶅姡锛?2. unresolved + severe failure 涓嶅姡锛?3. delivery-adjusted policy quality锛?4. resolved-only output quality锛?5. `k_used`銆乤ctive time銆乧ompletion time锛?6. policy 脳 `risk_route` interaction銆?
鍚屾椂鎶ュ憡 recommendation銆乷ffer銆乤ccept銆乼imeout銆乺eplacement銆乧andidate exhaustion銆亀orker failure銆乸olicy failure 鍜?capacity 娴佺▼銆備簨鍚庝笓瀹跺鏌ヤ笉寰楁浛鎹㈠喕缁撴斂绛栬緭鍑恒€?
## 7. 瀹為獙鍒嗗竷涓庣敓浜ф爣鍑嗗寲

ordinary/stress 鍒嗗眰鎶ュ憡鍚庯紝璁＄畻锛?
```text
V_design = 0.5 * V_ordinary + 0.5 * V_stress
```

璇ョ粨鏋滃彧浠ｈ〃 50:50 balanced experimental mixture銆?
鐢熶骇鏍囧噯鍖栦娇鐢ㄧ嫭绔嬭嚜鐒朵换鍔℃睜缁欏嚭鐨?`p_ordinary` 鍜?`p_stress`锛?
```text
V_prod = p_ordinary * V_ordinary + p_stress * V_stress
```

涓嶅緱浠?50:50 璇曢獙鏍锋湰浼拌鐢熶骇姣斾緥銆傛病鏈夊敮涓€姣斾緥鏃讹紝鎶ュ憡棰勬敞鍐屾儏鏅垎鏋愶紝渚嬪 80:20銆?0:40銆?0:50 鍜?30:70銆?
## 8. Replay銆佺己澶变笌绋冲仴鎬?
- Cross-fitted replay 鐢ㄤ簬 policy development銆佹秷铻嶃€丆2/T1/V1 鍔熸晥鍜屽彲琛屾€э紝涓嶆浛浠?V1銆?- 鎶ュ憡 complete-case 涓庡喕缁?missingness sensitivity锛涜鏀垮垹澶变笉鑳界紪鐮佷负闆躲€?- 瀵瑰眰绾?bootstrap/permutation 鍥哄畾 seed锛屽苟淇濆瓨 fold銆乧luster unit銆佹娊鏍锋鏁板拰浠ｇ爜 commit銆?- 瀵?worker pass-count 涓嶈冻浣跨敤棰勬敞鍐?contingency锛氱缉鍑?interaction/family 瑙ｉ噴鎴栧仠姝?V1锛岃€屼笉鏄檷浣庡噯鍏ュ悗瀹ｇО鍚岀瓑璇佹嵁銆?- 浠讳綍 schema drift銆佺己澶?manifest SHA銆乤ctive-time source mismatch 鎴栦簨鏁呰瘉鎹け璐ュ潎 fail closed銆?
## 9. 姝ｅ紡鎶ュ憡娓呭崟

姝ｅ紡琛ㄦ牸蹇呴』鑷冲皯鍖呭惈锛?
- 鍚勮疆 planned/actual task銆亀orker銆乻ubmission锛?- 涓夎酱 worker state 涓?support锛?- C2-B 璁捐鍜?C2-A-RP 鍋滄鎯呭喌锛?- P1 component validation/confirmation锛?- Global/Full activation銆乫allback 鍜屾斂绛栧樊寮傦紱
- T1 鍘熷銆乺erun銆佸垹澶便€乶ot-evaluable 鍜屾渶缁?pair锛?- V1 涓よ噦 ITT銆佺粓鎬併€佽川閲忋€佸閲忋€佹祦绋嬪け璐ュ拰 rerun锛?- external incident 鏁伴噺銆佸師鍥犲拰涓よ噦/鏉′欢鍒嗗竷锛?- 50:50 涓庣敓浜ф爣鍑嗗寲缁撴灉锛?- 鎵€鏈?downgrade銆乨eviation銆乫reeze version銆乵anifest SHA 鍜?code commit銆?
涓嶅緱铏氭瀯銆佹彃琛ユ垨鎻愬墠濉啓灏氭湭浜х敓鐨勬寮?C1/T1/V1 缁撴灉銆?
## 10. C1 variable-k 涓?Stage 3 鍒嗘瀽 amendment

Stage 1=P1锛孲tage 2=C1/C2-B/C2-A-RP锛孲tage 3=T1/V1銆侰1 姝ｅ紡鍒嗘瀽浠呬娇鐢?original銆丼HA-bound authorized replacement 鎴?registered late-entry calibration assignment 鐨?canonical evidence锛沷utside submission锛堝寘鎷?W034 B-004/B-022锛変繚鐣欏璁′絾鎺掗櫎 primary銆俉014 姘镐箙 excluded锛沇034=original+17銆乄001=original+3锛屽皻鏈舰鎴?canonical eligible submission 鐨勮ˉ鍏呬换鍔′笉寰楁彁鍓嶈础鐚瘉鎹€?
鎵€鏈?support銆乪ligibility 涓?k 鎸?`base_task_id 脳 condition 脳 estimand` 璁＄畻 final unique worker銆侴T銆乸eer銆丩OO銆乻tructural 涓?active-time 鍙湁涓嶅悓 k锛沝uplicate 涓嶉噸澶嶈鏁般€俻eer 鍏堣绠?task-level statistic锛屽啀瀵?task 绛夋潈姹囨€伙紱cluster 鍚屾椂鎶?absolute support銆乻hare銆乧luster_margin_all and cluster_margin_top2锛宻upported multimodal 涓嶈繘鍏?stable peer銆俛ctive-time 鐨?W034 琛ュ厖浠诲姟椤诲湪 sentinel 鍚?owner-valid锛涙棫缂哄け淇濇寔 timing ineligible锛屼笉寰楄ˉ闆舵垨褰卞搷鍏朵粬 capability estimand銆?
Strong Global 鐨勬寮?rank score 涓哄喕缁?cohort 鍐?`S_G=z(Q_GT_EB)`锛沗Q_GT_EB_LCB` 浠呬綔 quality gate銆佸尯闂村拰 sensitivity銆係tructural 姝ｅ紡瑙ｉ噴浣跨敤 EB 鍙婂叾鍖洪棿锛屼笉寰椾互 raw failure rate 鍐掑厖 EB銆侳ull/V1 蹇呴』鍦?Stage 3 global freeze 鍓嶅浐瀹?whitelist銆亀eights銆乻upport銆乧ap銆乼hreshold銆乵argin銆乸rofile/version銆乧omponent status/interval銆乮nput SHA 鍙?formal minimum worker/cluster rule锛汫T-blind medoid tie 涓嶈鍙?worker quality銆俽olling enrollment 榛樿鍏抽棴锛涙縺娲绘椂鏂颁汉鎸夋棦瀹?P1/C1/C2 瑙勫垯杩涘叆骞舵姤鍛?pooled 涓?original-only sensitivity銆傚涔犳晥搴斿彧鎶ュ憡椤哄簭/鐗堟湰/provenance锛屼笉鍔犲叆澶嶆潅涓绘ā鍨嬨€?
## v5 鏂规硶鍚堝悓闂幆

- `PAPER_A_METHOD_CONTRACT_CURRENT.json` 鏄敮涓€瑙勮寖鎬ф柟娉曠湡婧愶紱鏈?SAP 鍙В閲婂叾鍐荤粨鐨勫瓧娈典笌 SHA锛屼笉鑳借嚜琛屾柊澧炲悓涔夊瓧娈垫垨鍏紡銆?- C1-only 鐨?Q_GT 浣跨敤 worker 涓?task fixed effects锛屼笖涓嶄及璁?stage effect銆侰1+C2 final 鍙湪瀛樺湪鍐荤粨璺ㄩ樁娈?anchor 鎴栫瓑浠锋敮鎸佺粨鏋勬椂浣跨敤 building/task-within-building random intercept 涓?stage fixed effect锛涘惁鍒?stage effect 鐨勭姸鎬佹槸 `not_identifiable`銆?- `R_peer_task` 鍏堝湪 worker-task 鍐呭彇鍚岃鐩镐技搴︿腑浣嶆暟锛沗R_peer_all` 鍐嶅 eligible task 绛夋潈鍙栦腑浣嶆暟锛沗R_peer_stable` 鎺掗櫎 supported-multimodal task銆傛棫 `R_peer_median` 鍜?`R_peer_nonmultimodal` 涓嶅緱浣滀负姝ｅ紡瀛楁銆?- 琛岀骇 eligibility 鎸?GT銆乸eer銆丩OO medoid銆丩OO strict銆乻tructural銆乼ime銆丼emi correction銆乸redictive 涓?routing feature 鍒嗗紑娑堣垂锛屼笖鍏ㄩ儴鍏堥€氳繃 `formal_assignment_eligible`銆俹utside 姘镐笉杩涘叆涓昏 estimand銆?- reference registry 蹇呴』鍦?formal C1 Q_GT 鍓嶅喕缁擄紱鐢辨煇 submission 瑙﹀彂鐨?revision 涓嶈兘鍙嶈繃鏉ヤ负璇?submission 璁″垎锛汼tage 3 鍓嶅喕缁撴渶缁?registry銆?- V1 鐨勭‘璁ゅ眰绾у浐瀹氫负 severe failure銆乽nresolved+severe銆乨elivery-adjusted quality superiority銆乧ount/cost锛泀uality 涓嶄娇鐢ㄥ惈娣风殑 non-inferiority margin銆?
