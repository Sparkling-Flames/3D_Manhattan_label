from round_d import OUT
import pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=OUT;d=pd.read_csv(p/'D_controls.csv');fig,ax=plt.subplots(1,2,figsize=(11,4))
s=d[d.family=='same_floor_matched_upper_mae_different_depth'];ax[0].bar(['Near 0','Near 1','Far 2','Far 3'],s.top3d_symmetric_mean_h,color=['#2b6cb0','#2b6cb0','#dd6b20','#dd6b20']);ax[0].set_title('Same floor, all upper MAE = 0.25 deg');ax[0].set_ylabel('Conditional top 3D mean distance / h')
s=d[d.family=='global_depth_scale_equal_upper_angular'];ax[1].plot(s.scale,s.top3d_symmetric_mean_h,'o-');ax[1].set_xlabel('Scale in camera-height units');ax[1].set_title('All upper MAE = 1.613238 deg');ax[1].set_ylabel('Conditional top 3D mean distance / h');fig.tight_layout();fig.savefig(p/'D_information_controls.png',dpi=170)
