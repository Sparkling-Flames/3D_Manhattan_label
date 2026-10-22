"""Score-hidden review outputs and frozen prediction keys; no photos repackaged."""
from pathlib import Path
import json,sys,argparse
import pandas as pd
ROOT=Path(__file__).resolve().parent

def write_viewer(cards,dest,mode='scope'):
 payload=dict(panel_id='quality_AB_20261015_'+mode,mode=mode,title='两图范围与顶界待核验' if mode=='scope' else '普通作答核验：模型身份与分数隐藏',
              intro='现有几何及参考并列；新增顶部为空。局部标记和顶点建议另存，不修改原始数据。' if mode=='scope' else '对固定作答与固定参考判断总体五档或指出不能容忍的部位。无需每例精确命中，不显示模型分数。',
              exposure='known_developmental' if mode=='scope' else 'not_used_current_parameter_selection_historical_exposure_unknown',cards=cards)
 text=(ROOT/'review/viewer_template.html').read_text(encoding='utf-8');dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(text.replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')

def build(results,review):
 review.mkdir(parents=True,exist_ok=True);views=json.loads((results/'two_image_geometry.json').read_text(encoding='utf-8'));ledger=pd.read_csv(results/'TWO_IMAGE_CHANGELOG_36.csv');cards=[]
 for v in views:
  cards.append(dict(display_id=v['image_code']+' / '+v['record_id'],record_id=v['record_id'],image_id=v['image_id'],condition=v['condition'],cleaning=v['cleaning_disposition'],
             floor=v['a'],height=v['ah'],original_floor=v['original'],original_height=v['original_heights'],new_floor=v['new_floor'],crop_center_x=0 if v['image_code'].startswith('Uw') else 805))
 for v in ledger[ledger.execution_status.eq('unavailable_pairing')].to_dict('records'):
  cards.append(dict(display_id=v['image_code']+' / '+v['record_id'],record_id=v['record_id'],image_id=v['image_id'],condition=v['condition'],cleaning=v['cleaning_disposition'],floor=None))
 cards.sort(key=lambda c:(c['image_id'],c['record_id']));write_viewer(cards,review/'TWO_IMAGE_REVIEW.html')
 scores=pd.read_csv(results/'SCORES_1145.csv');sel=pd.read_csv(ROOT/'inputs/next_review_bindings.csv')
 # Same frozen 20, without selecting a more favourable reference or model.
 key=sel.merge(scores,on=['record_id','object_id','image_id','image_code','reference_id','condition'],how='left',validate='one_to_one')
 assert len(key)==20 and key.Q_WQ.notna().all()
 key[['blind_id','record_id','object_id','image_id','reference_id','Q_WQ','Q_A10','Q_B8L2','Q_IoU3D','used_for_current_calibration','historically_unexposed_certified']].to_csv(review/'PRIVATE_NEXT20_MODEL_KEY.csv',index=False)
 sel.to_csv(review/'NEXT20_BINDINGS.csv',index=False)
 # Balanced targeted follow-up: known concerns + substantive reversal + zero-D omission.
 sample=scores[scores.record_id.isin(['R01288','R03034','R00655','R03274','R01030','R00215','R01496','R01536','R00502','R02422'])].copy()
 reasons={'R01288':'direction burden / previously good qualitative judgement','R03034':'N18 endpoint sensitivity and mixed geometry','R00655':'N19 high IoU moderate intrinsic D','R03274':'J04 local projection versus wide shape consequence',
 'R01030':'N13 omission: near-zero direction should not be automatically rewarded','R00215':'N29 omission / boundary position contribution',
 'R01496':'B substantive reversal pair: lower D but worse remaining components','R01536':'B substantive reversal pair: higher D but better remaining components',
 'R00502':'N24 challenge: direction-dominant error with high footprint fidelity','R02422':'N27 challenge: retain useful direction distinction against N13'}
 sample['selection_reason']=sample.record_id.map(reasons);sample['development_not_blind']=True
 sample.to_csv(review/'TARGETED_CHALLENGE_BINDINGS.csv',index=False)
 audit=dict(scope_cards=len(cards),geometric_cards=len(views),new_top_arrays=0,scope_scores_embedded=False,
            frozen_ordinary_bindings=len(sel),ordinary_full_cards_generated_in_this_run=0,
            ordinary_reuse='Use the existing local Codex hydration_check/NEXT_ORDINARY_REVIEW.html unchanged, or materialize_review.py with its payload; no new geometry/photo availability is claimed.')
 (review/'REVIEW_GENERATION_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
 print(audit)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--review',type=Path,required=True);a=p.parse_args();build(a.results,a.review)
