# Paper B Model Architecture Spec v1

> Status: Paper B / non-thesis-facing architecture planning.
>
> Scope: documentation/specification only. This document does not implement training code, does not define A-line protocol artifacts, and does not affect `P1 / C1 / C2 / T1 / V1`.

## 1. Model name

**HoHoNet-AE: HoHoNet with Enclosed Layout Supervision and Ambiguity-aware Auxiliary Heads**

HoHoNet-AE keeps HoHoNet as an enclosed-only predictor and uses Bi-Layout-style enclosed/extended disagreement to supervise auxiliary ambiguity and overextension-risk heads.

This is not Bi-Layout embedded inside HoHoNet. Bi-Layout-style data is used only as audited supervision for ambiguity, overextension risk, and target cleaning.

## 2. Architecture

Text-form architecture diagram:

```text
I
  -> HoHoNet encoder
      -> LHFeat H in R^{W x C}
          -> enclosed layout head
              -> P_enc
          -> ambiguity heatmap head
              -> A_amb(x)
          -> pool(H, A_amb)
              -> overextend-risk head
                  -> r_over
```

The shared HoHoNet trunk remains the only geometry feature extractor. The auxiliary heads are not allowed to produce a final extended layout output for annotation.

## 3. Input / output contract

Input:

- `I`: panoramic image or the standard HoHoNet input representation.
- Optional training-only metadata pointing to audited target records.

Training-time outputs:

- `P_enc`: enclosed layout prediction.
- `A_amb(x)`: 1D ambiguity / opening-region heatmap over panorama columns or aligned layout boundary positions.
- `r_over`: scalar overextension-risk score.

Inference-time Paper B outputs:

- `P_enc`
- `A_amb(x)`
- `r_over`

Forbidden inference outputs:

- final `P_ext`;
- automatic `scope`;
- automatic `model_issue`;
- automatic `difficulty`;
- formal A-line `g_t`;
- A-line routing bucket or V1 routing artifact.

## 4. Training targets

`Y_enc`:

- reliable enclosed layout target;
- accepted from B0 target-domain audit or B0-Z accepted ZInD mapping audit;
- valid for `L_layout_enc`.

`Y_ext_ref`:

- extended reference used only to derive disagreement, ambiguity, or auxiliary supervision;
- not a final Paper B annotation output;
- not exposed as the deployed prediction target.

`Y_amb(x)`:

- ambiguity heatmap or mask derived from audited enclosed/extended disagreement and/or manually confirmed opening regions;
- valid only when enc/ext paired supervision or audited opening-region evidence exists.

`Y_over`:

- audited overextend-risk label;
- valid only for samples where B0 or later expert audit has assigned overextension-risk evidence;
- not an OOS label and not a replacement for the A-line OOS gate.

## 5. Losses

Default B2 loss:

```text
L = L_layout_enc
  + lambda_amb * L_amb
  + lambda_over * L_over
```

`L_layout_enc`:

- supervised by `Y_enc`;
- applies to reliable enclosed targets only.

`L_amb`:

- supervised by `Y_amb(x)`;
- applies only to audited enc/ext paired samples or manually confirmed opening-region ambiguity.

`L_over`:

- supervised by `Y_over`;
- applies only to audited overextend-risk labels.

Optional later extensions:

- `L_policy_margin`: optional margin loss that encourages separation between enclosed boundary and extended reference near audited openings.
- `L_overextend_penalty`: optional penalty on predicted geometry that crosses audited enclosed stops.

The optional losses are later extensions, not required for the default Paper B model claim.

## 6. Prohibited claims

Do not claim:

- HoHoNet-AE embeds Bi-Layout inside HoHoNet;
- Bi-Layout relabel automatically replaces GT;
- `r_over` or `A_amb(x)` performs OOS classification;
- `P_ext` is a final annotation output;
- Paper B outputs can update A-line `P1 / C1 / C2 / T1 / V1`;
- Paper B outputs can enter formal A-line `g_t`, routing, OOS gate, Label Studio production UI, or Semi-Auto condition.

