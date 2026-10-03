from itertools import combinations

import numpy as np
import pytest

from tools.thesis_main.analysis.audit_worker_returns_20261003 import parent_evidence, replacement_audit, paired_radius


def test_parent_lineage_does_not_depend_on_coordinate_equality():
    def ann(i, author, parent=None, x=10):
        return dict(id=i, completed_by=author, parent_annotation=parent,
                    result=[dict(id='point', type='keypointlabels', original_width=100,
                                 original_height=100, value=dict(x=x, y=20))])
    task=dict(annotations=[ann(1, 2), ann(2, 3, 1), ann(3, 4, 2, 12), ann(4, 5, 99)])
    same=parent_evidence(task, 2); changed=parent_evidence(task, 3)
    assert same['cross_author_parent'] and same['same_parent_points'] and same['root_annotation']==1
    assert changed['cross_author_parent'] and not changed['same_parent_points'] and changed['ancestor_ids']==[2,1]
    assert parent_evidence(task,4)['lineage_status']=='missing_parent'
    task['annotations'][0]['parent_annotation']=3
    with pytest.raises(ValueError,match='parent_cycle'):
        parent_evidence(task,1)


def test_paired_means_cannot_show_interaction_but_backgrounds_can():
    members=np.array(list(combinations(range(6),3)))
    weights=np.array([0,1,2,3,4,5.])
    score=weights[members].sum(1)/15
    got=replacement_audit(members,score,np.array([False]*3+[True]*3))
    assert got['pair_identity_max_error']<1e-14
    assert got['residual_fraction']==pytest.approx(0,abs=1e-12)
    score=score+.1*((members==0).any(1)&(members==1).any(1))
    got=replacement_audit(members,score,np.array([False]*3+[True]*3))
    assert got['pair_identity_max_error']<1e-14 and got['residual_fraction']>0
    with pytest.raises(ValueError,match='integer_members_required'):
        replacement_audit(members.astype(float)+.1,score,np.array([False]*3+[True]*3))
    expected=np.sqrt(np.log(4/.05)*102/(2*16384*33**2))
    assert paired_radius([1]*10+[2]*23,16384)==pytest.approx(expected)
