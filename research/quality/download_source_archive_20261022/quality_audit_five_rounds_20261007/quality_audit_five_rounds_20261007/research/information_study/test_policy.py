from round_e import choose
import numpy as np
s={'L0':.2,'C':.02,'U':2,'D3':.15};a={'id':'anchor','loss':{'L0':.2,'C':.02,'U':1.,'D3':.1}};b={'id':'changed','loss':{'L0':.1,'C':.01,'U':1.05,'D3':.2}}
assert choose([a,b],a,'LC',s)[0]['id']=='changed'
assert choose([a,b],a,'guard_angular_strict',s)[0]['id']=='changed'
assert choose([a,b],a,'guard_full_strict',s)[0]['id']=='anchor'
z={'id':'missing_upper','loss':dict(a['loss'],U=np.nan)}
assert choose([z],z,'guard_full_strict',s)[1]=='abstain_anchor_metric_NA'
assert choose([z],z,'guard_spatial_strict',s)[1]=='retain_anchor'
print('5 policy tests passed: compensation, extra 3D constraint, NA is not zero')
