"""Package real quality-masked MODIS matrices in recorded photo coordinates.
No inference or fitted values; nearest source sample with a finite gap threshold.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib, json, sys
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import xarray as xr
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
sys.path.insert(0, str(WORK/'johann_geolocated_20261021'))
from extract_labels import subset_indices, SAMMY_FLAG_BITS
MASK = sum(1 << b for b in SAMMY_FLAG_BITS.values())
OUT = ROOT/'public/satellite-maps'; OUT.mkdir(exist_ok=True)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def project(points, matrix):
    h = np.c_[points, np.ones(len(points))] @ matrix.T
    return h[:,:2]/h[:,2:]
def build(pid, corners, subset, match, source):
    corners = np.asarray(corners,float); assert corners.shape == (4,2) and np.isfinite(corners).all()
    lat,lon = corners.mean(0)
    def xy(a): return np.c_[((a[:,1]-lon+180)%360-180)*np.cos(np.deg2rad(lat)), a[:,0]-lat]
    rows=[]; values=[]
    for (x,y),(u,v) in zip(xy(corners),[(0,0),(1,0),(1,1),(0,1)]):
        rows += [[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]]; values += [u,v]
    matrix=np.r_[np.linalg.solve(rows,values),1].reshape(3,3)
    assert np.max(np.abs(project(xy(corners),matrix)-[[0,0],[1,0],[1,1],[0,1]])) < 1e-8
    uv=project(xy(subset[['lat','lon']].to_numpy()),matrix)
    inside=(uv>=0).all(1)&(uv<=1).all(1)
    assert inside.mean()>.95
    tree=cKDTree(uv[inside]); pitch=float(np.median(tree.query(uv[inside],k=2)[0][:,1])); assert 0<pitch<.5
    # Display grid only: retain MODIS resolution and do not invent native photo pixels.
    side=32; x,y=np.meshgrid((np.arange(side)+.5)/side,(np.arange(side)+.5)/side)
    distances,nearest=tree.query(np.c_[x.ravel(),y.ravel()])
    good=(subset.l2_flags.to_numpy(dtype='uint32')&MASK)==0
    layers={}
    for target,column in [('chlor_a','chlor_a'),('kd_490','Kd_490')]:
        a=subset[column].to_numpy(float); valid=good & np.isfinite(a)&(a>0)
        expected=match['targets'][target]
        assert int(valid.sum())==int(expected['valid_pixels']), (pid,target,'mask count')
        mean=float(np.exp(np.log(a[valid]).mean())); np.testing.assert_allclose(mean,expected['value'],rtol=2e-6)
        retained=valid[inside][nearest] & (distances<=1.5*pitch)
        picked=a[inside][nearest]; grid=np.full(side*side,np.nan);grid[retained]=np.log10(picked[retained])
        layers[target]={'grid_log10':[[float(v) if np.isfinite(v) else None for v in line] for line in grid.reshape(side,side)],
            'units':expected['units'],'valid_pixels':int(valid.sum()),'display_coverage':float(retained.mean()),'geomean':mean}
    payload={'photo_id':pid,**source,'layers':layers,'granule_id':match['granule_id'],'delta_minutes':match['delta_minutes'],
        'granule_sha256':match.get('granule_sha256'),'mask_flags':match['mask_flags'],
        'method':'Nearest quality-masked MODIS sample projected to a 32 × 32 display grid; distant gaps and rejected samples remain blank.',
        'registration':'Approximate projection using recorded photo corners. Independent pixel alignment and sub-MODIS accuracy are not validated.'}
    raw=json.dumps(payload,allow_nan=False,separators=(',',':')).encode(); digest=hashlib.sha256(raw).hexdigest()
    filename=f'{pid}-{digest[:16]}.json';(OUT/filename).write_bytes(raw)
    return {'url':'/satellite-maps/'+filename,'sha256':digest,**source}

records=json.loads((ROOT/'runtime/pilot-calibrated-records.json').read_text())
assets={a['photo_id']:a for a in records['input_assets']}; index={}
for match in records['satellite_matchups']:
    pid=match['photo_id'];a=assets[pid];path=WORK/'mediterranean_20261102/results/subsets'/f'{pid}.parquet'
    index[pid]=build(pid,a['provenance']['metadata']['corners_latlon'],pd.read_parquet(path),match['data'],
        {'input_asset_id':a['id'],'source_sha256':a['image_sha256'],'subset_sha256':sha(path)})
    print('Packaged',pid,flush=True)
native=json.loads((ROOT/'src/native-maps.json').read_text())
catalog=json.loads((ROOT/'src/native-photo-catalog.json').read_text())
rows=pd.read_csv(WORK/'high_density_pixel_20261109/results/selected_photos.csv').set_index('image_id')
for entry in native['photos']:
    pid=entry['image_id'];row=rows.loc[pid];path=WORK/'high_density_20261109/raw/granules'/row.granule_file
    assert sha(path)==row.granule_sha256
    with xr.open_dataset(path,group='navigation_data',engine='h5netcdf') as nav: lat,lon=nav.latitude.values,nav.longitude.values
    lines,pixels=subset_indices(SimpleNamespace(corners_latlon=row.corners_latlon,center_lon=row.longitude),lat,lon)
    with xr.open_dataset(path,group='geophysical_data',engine='h5netcdf') as geo: chl,kd=geo.chlor_a.values[lines,pixels],geo.Kd_490.values[lines,pixels]
    with xr.open_dataset(path,group='geophysical_data',engine='h5netcdf',mask_and_scale=False) as geo:
        attrs=geo.l2_flags.attrs;actual=dict(zip(attrs['flag_meanings'].split(),map(int,attrs['flag_masks'])))
        for name,bit in SAMMY_FLAG_BITS.items(): assert actual[name]==1<<bit
        flags=geo.l2_flags.values[lines,pixels].astype('uint32')
    subset=pd.DataFrame({'lat':lat[lines,pixels],'lon':lon[lines,pixels],'chlor_a':chl,'Kd_490':kd,'l2_flags':flags})
    match=catalog[pid]['predictions']['chlor_a']['satellite']
    index[pid]=build(pid,entry['corners_latlon'],subset,{**match,'granule_sha256':row.granule_sha256},
        {'photo_url':entry['assets']['photo'],'source_sha256':entry['sha256'][pid+'_photo.jpg']})
    print('Packaged',pid,flush=True)
(ROOT/'src/satellite-maps.json').write_text(json.dumps(index,indent=2)+'\n')
print(f'Verified and packaged {len(index)} satellite comparisons')
