"""Named explanation blocks from the existing frozen B8L2/D10 formula.

Verbatim formula source (the only changes are CSV numeric coercion and a frame
adapter): population_20261023/code/enrich_cached_geometry.py::score_blocks at
b9bcec809fbaec8ab055931a1abb7baa5db44dac. Never changes saved scores, geometry,
qualification or failure flags. Native old25/new26 scalars omit these optional
named blocks but retain all five raw quantities needed to recover them.
"""
import math

RAW=('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')
BLOCKS=('B8_floor_block','B8_direction_block','B8_global_height_block',
        'B8_local_height_block','B8_height_block','D10_direction_block')
VERSION='frozen_B8L2_D10_named_blocks_20261023_projected_20261026'
UNITS='dimensionless frozen loss terms, lower is better; not 0-100 points or additive percentage contributions'

def number(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None

def blocks_from_raw(row):
    v=[number(row.get(x)) for x in RAW]
    if any(x is None for x in v) or v[0]<=0:return {}
    iou,bottom,direction,hmean,hcenter=v
    floor=1/iou-1+bottom*bottom/32
    d8=1.5*direction*direction/(direction*direction+64)
    d10=1.5*direction*direction/(direction*direction+100)
    hg=(hmean/.8)**2;hl=(hcenter/.25)**2
    result=dict(zip(BLOCKS,(floor,d8,hg,hl,hg+hl,d10)))
    q=number(row.get('B8L2'))
    if q is not None:result['B8_formula_residual']=q-100/(1+math.hypot(floor,d8)+hg+hl)
    return result

def add_blocks_row(row,check_existing=True):
    result=dict(row);new=blocks_from_raw(row)
    for name,value in new.items():
        old=number(row.get(name))
        if old is not None and check_existing and abs(old-value)>1e-8:
            raise ValueError('Existing named component disagrees with frozen formula: '+str(row.get('team_key'))+' '+name)
        if old is None:result[name]=value
    return result

def add_blocks_frame(frame,check_existing=True):
    """Return a copy with missing named blocks filled; all main values preserved."""
    import numpy as np
    import pandas as pd
    out=frame.copy()
    raw={c:pd.to_numeric(out[c],errors='coerce') if c in out else pd.Series(np.nan,index=out.index) for c in RAW}
    valid=np.logical_and.reduce([np.isfinite(v) for v in raw.values()]) & raw['iou_2d'].gt(0)
    x=raw['dir'];floor=1/raw['iou_2d']-1+raw['S_bottom_deg']**2/32
    d8=1.5*x*x/(x*x+64);d10=1.5*x*x/(x*x+100)
    hg=(raw['Hmean']/.8)**2;hl=(raw['Hcenter']/.25)**2
    derived=dict(zip(BLOCKS,(floor,d8,hg,hl,hg+hl,d10)))
    if 'B8L2' in out:
        q=pd.to_numeric(out['B8L2'],errors='coerce')
        derived['B8_formula_residual']=q-100/(1+np.hypot(floor,d8)+hg+hl)
    for name,values in derived.items():
        values=values.where(valid)
        old=pd.to_numeric(out[name],errors='coerce') if name in out else pd.Series(np.nan,index=out.index)
        check=old.notna() & values.notna()
        if check_existing and ((old[check]-values[check]).abs()>1e-8).any():
            bad=out.loc[check & (old-values).abs().gt(1e-8),'team_key'].head(3).tolist() if 'team_key' in out else []
            raise ValueError('Existing '+name+' differs from frozen formula: '+repr(bad))
        out[name]=old.where(old.notna(),values)
    return out
