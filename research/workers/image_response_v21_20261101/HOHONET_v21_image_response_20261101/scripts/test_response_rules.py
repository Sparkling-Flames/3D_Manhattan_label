"""Scientific boundary checks for retrospective response rules (no fusion)."""
import unittest
import numpy as np
import pandas as pd
import analyze_response as ar


def curve(N,values,valid=256,rate=1.):
    rows=[]
    for k,x in zip(range(3,N+1),values):
        r=dict(k=k,unique_teams=1 if k==N else 100)
        for q in ar.QUALITY:
            for stat in ['mean','p10','sd']:
                r[q+'_'+stat]=x if stat!='sd' else 0.
            r[q+'_valid_n']=valid if np.isfinite(x) else 0
        for st in ['complete_evaluable','quality_available','geometry_formed']:
            r[st+'_rate']=rate;r[st+'_valid_n']=256
        rows.append(r)
    return pd.DataFrame(rows)


def meta(N):
    return dict(pool_id='test',image='test-image',building='test-building',condition='manual',
                domain='test',target_id='target',reference_id='reference',reference_version='frozen',
                N=N,difficulty='中等',difficulty_en='medium')


def main_row(onsets,metric='B8L2_mean'):
    return onsets[onsets.metric.eq(metric)&onsets.primary_rule].iloc[0]


class ResponseRules(unittest.TestCase):
    def test_early_flat_then_late_change_is_not_early_plateau(self):
        values=[50.]*8+[56.]*10 # k3..10 then k11..20
        _,p,t,_=ar.tail_analysis(curve(20,values),meta(20),{})
        self.assertEqual(main_row(p).onset_k,11)
        q=t[t.metric.eq('B8L2_mean')]
        self.assertTrue((q.first_later_change_k==11).any())

    def test_very_late_jump_prevents_adequate_tail_onset(self):
        values=[50.]*18;values[-3]=56. # k18
        _,p,_,_=ar.tail_analysis(curve(20,values),meta(20),{})
        q=main_row(p)
        self.assertTrue(np.isnan(q.onset_k))
        self.assertEqual(q.reason,'small_range_only_with_short_remaining_followup')

    def test_missing_full_Q_is_not_zero_or_plateau(self):
        values=[50.]*17+[np.nan]
        _,p,_,_=ar.tail_analysis(curve(20,values),meta(20),{})
        q=main_row(p)
        self.assertTrue(np.isnan(q.onset_k));self.assertTrue(np.isnan(q.actual_full_value))
        self.assertEqual(q.reason,'actual_full_metric_unavailable')

    def test_stable_failure_rate_is_not_reliable_output(self):
        _,p,_,_=ar.tail_analysis(curve(20,[np.nan]*18,rate=0.),meta(20),{})
        q=main_row(p,'complete_evaluable_rate')
        self.assertEqual(q.onset_k,3)
        self.assertEqual(q.tail_rate_level,'consistently_low_le5pct')

    def test_path_support_threshold_is_separate(self):
        _,p,_,_=ar.tail_analysis(curve(20,[50.]*18,valid=64),meta(20),{})
        q=p[p.metric.eq('B8L2_mean')&p.tolerance.eq(2.)]
        self.assertEqual(q[q.minimum_valid_paths.eq(64)].iloc[0].onset_k,3)
        self.assertTrue(np.isnan(q[q.minimum_valid_paths.eq(128)].iloc[0].onset_k))

    def test_band_uncertainty_does_not_erase_point_estimate_onset(self):
        bands={('test','B8L2_mean',k):dict(estimate=50.,low=48.,high=52.,cohort='pooled256',source='test',complete_bootstrap_draws=2000) for k in range(3,21)}
        _,p,_,_=ar.tail_analysis(curve(20,[50.]*18),meta(20),bands)
        q=main_row(p)
        self.assertEqual(q.onset_k,3)
        self.assertEqual(q.onset_MC_class,'band_crosses_tolerance')

    def test_single_valid_observation_does_not_have_sample_SD_zero(self):
        self.assertTrue(np.isnan(ar.finite_stats([4.])['sd']))
        self.assertEqual(ar.finite_stats([4.]*256)['sd'],0.)

    def test_duplicate_team_path_frequency_is_preserved(self):
        d=pd.DataFrame({'k':[3]*3,'replicate_id':['r1','r2','r3'],
          'team_key':['same','same','other'],'B8L2':[0.,0.,100.],
          'complete_evaluable':[True]*3,'origin_stratum':['stratum']*3})
        d=ar.prepare_frame(d,meta(5));c,_=ar.per_k_statistics(d,meta(5))
        self.assertAlmostEqual(c.iloc[0].B8L2_mean,100./3)
        self.assertEqual(c.iloc[0].unique_teams,2)

    def test_two_endpoint_support_and_real_zero_are_separate(self):
        rows=[]
        for rep,x,y in [('r1',0.,1.),('r2',np.nan,2.),('r3',3.,np.nan),('r4',np.nan,np.nan)]:
            for k,z in [(3,x),(4,y)]:rows.append(dict(k=k,replicate_id=rep,team_key=rep+str(k),B8L2=z,complete_evaluable=np.isfinite(z),origin_stratum='stratum'))
        d=ar.prepare_frame(pd.DataFrame(rows),meta(6));r,_=ar.paired_response(d,meta(6),False)
        q=r[r.k_from.eq(3)&r.k_to.eq(4)&r.metric.eq('B8L2')].iloc[0]
        self.assertEqual([q.both_valid_n,q.from_only_valid_n,q.to_only_valid_n,q.neither_valid_n],[1,1,1,1])
        self.assertEqual(q.mean_delta,1.)


if __name__=='__main__':unittest.main()
