import json, numpy as np, pandas as pd
from pathlib import Path
P = Path('/root/v5/Data/processed'); OUT = Path('/root/work/v6')
OPS = ['A','B','C']; OPNAME = {o:'Operator '+o for o in OPS}
def op1(s): return s.str[-1]
r  = pd.read_csv(P/'rsrp_cells.csv')
t  = pd.read_csv(P/'traffic_bins.csv')
dv = pd.read_csv(P/'device_rsrp.csv')
dt = pd.read_csv(P/'device_operator_totals.csv')
rv = pd.read_csv(P/'rsrp_value_counts.csv')
dvc= pd.read_csv(P/'device_value_counts.csv')
tm = pd.read_csv(P/'tech_mix.csv')
osum=pd.read_csv(P/'operator_summary.csv')
nar = pd.ExcelFile(P/'narrative.xlsx')
for d in (r,t,dv,rv,dvc,dt,osum,tm): d['op'] = op1(d['RadioOperatorName'])
GRID = {'6':'2km','7':'1km','8':'500m'}          # keep v3 keys -> bin sizes
CELL = {'2km':0.02,'1km':0.01,'500m':0.005}      # degree side (lat)
SL = {'ALL':(['2019-11-02','2019-11-03','2019-11-04'],'Full window · 2–4 Nov 2019'),
      'WE' :(['2019-11-02'],'Weekend · Sat 2 Nov'),
      'WD' :(['2019-11-03','2019-11-04'],'Weekdays · Sun–Mon 3–4 Nov'),
      'D2' :(['2019-11-02'],'Sat 2 Nov'),'D3':(['2019-11-03'],'Sun 3 Nov'),'D4':(['2019-11-04'],'Mon 4 Nov')}
R1 = lambda x,n=1: None if pd.isna(x) else round(float(x),n)
BANDS = ['Excellent','Good','Fair','Poor','Very Poor']
BCOL  = {'Excellent':'n_excellent','Good':'n_good','Fair':'n_fair','Poor':'n_poor','Very Poor':'n_very_poor'}
HIST  = np.arange(-140,-40,2)

def wpct(vals, wts, q):
    o=np.argsort(vals); v=np.asarray(vals)[o]; w=np.asarray(wts,float)[o]
    c=np.cumsum(w)/w.sum()
    return float(np.interp(q, c, v))

def rsrp_state(rs, vs, adj):
    sfx = '_adj' if adj else ''
    g = rs[rs.bin_size=='1km'].copy()
    g['N'] = g['n_samples'+sfx]; g['S'] = g['rsrp_sum'+sfx]
    cells=[]; gap={}
    a = g.groupby(['op','cell_key','lat','lon'], as_index=False)[['N','S']].sum()
    a = a[a.N>0]; a['v'] = a.S/a.N
    for o,la,lo,n,v in zip(a.op,a.lat,a.lon,a.N,a.v):
        cells.append({'op':o,'la':round(la,4),'lo':round(lo,4),'n':int(n),'v':round(v,2)})
        k=(round(la,4),round(lo,4)); d=gap.setdefault(k,{'la':k[0],'lo':k[1]})
        d[o]=round(v,2); d['n'+o]=int(n)
    hr = g.groupby(['op','hour'], as_index=False)[['N','S']].sum()
    hourly=[{'op':o,'h':int(h),'avg':round(s/n,2),'n':int(n)} for o,h,n,s in zip(hr.op,hr.hour,hr.N,hr.S)]
    bands={}; pct={}; ops={}
    for o in OPS:
        sub=g[g.op==o]; tot=sub['N'].sum()
        b={k: round(100*sub[BCOL[k]+sfx].sum()/tot,2) for k in BANDS}
        bands[OPNAME[o]]=b; pct[OPNAME[o]]={'poor':round(b['Poor']+b['Very Poor'],2),'exc':round(b['Excellent'],2),
                        'usable':round(b['Excellent']+b['Good'],2)}
        vv = vs[~vs.is_quantised] if adj else vs
        vv = vv[vv.op==o]
        ops[OPNAME[o]]={'avg':round(sub['S'].sum()/tot,2),'n':int(tot),
                        'med':round(wpct(vv.RSRP.values, vv.n.values, .50),1),
                        'p10':round(wpct(vv.RSRP.values, vv.n.values, .10),1),
                        'p90':round(wpct(vv.RSRP.values, vv.n.values, .90),1)}
    return cells, list(gap.values()), hourly, bands, pct, ops

def hist_state(vs, adj):
    out={}
    v = vs[~vs.is_quantised] if adj else vs
    for o in OPS:
        s=v[v.op==o]
        c,_=np.histogram(s.RSRP, bins=np.append(HIST,-40), weights=s.n)
        out[o]=[int(x) for x in c]
    return out

def dev_state(dd, adj):
    d = dd[~dd.is_quantised] if adj else dd
    a = d.groupby(['DeviceName','DeviceManufacturer','op'], as_index=False).agg(
        n=('n_samples','sum'), S=('rsrp_sum','sum'), mn=('rsrp_min','min'), mx=('rsrp_max','max'),
        p90=('rsrp_p90','mean'), p10=('rsrp_p10','mean'))
    a=a[a.n>0]
    devs=[{'d':dn,'m':dm,'op':o,'n':int(n),'avg':round(S/n,2),'min':R1(mn),'max':R1(mx),
           'p90':R1(p9),'p10':R1(p1)} for dn,dm,o,n,S,mn,mx,p9,p1 in
          zip(a.DeviceName,a.DeviceManufacturer,a.op,a.n,a.S,a.mn,a.mx,a.p90,a.p10)]
    m = d.groupby('DeviceManufacturer', as_index=False).agg(
        n=('n_samples','sum'), S=('rsrp_sum','sum'), p90=('rsrp_p90','mean'), p10=('rsrp_p10','mean'))
    m=m[m.n>=20000].sort_values('S')      # weight-filtered, worst first by mean
    manuf=[{'m':mm,'n':int(n),'avg':round(S/n,2),'p10':R1(p1),'p90':R1(p9)}
           for mm,n,S,p9,p1 in zip(m.DeviceManufacturer,m.n,m.S,m.p90,m.p10)]
    manuf.sort(key=lambda x:x['avg'])
    return devs, manuf

def traf_state(tt, clean):
    col = 'tv_sum' if clean else 'tv_sum_raw'; ncol='n_samples' if clean else 'n_samples_raw'
    cells={}
    for key,bs in GRID.items():
        g=tt[tt.bin_size==bs]
        a=g[g.TrafficDirection=='Downlink'].groupby(['op','lat','lon'],as_index=False)[[col,ncol]].sum()
        a=a[a[col]>0]
        cells[key]=[{'op':o,'la':round(la,4),'lo':round(lo,4),'n':int(n),'t':round(v,1)}
                    for o,la,lo,v,n in zip(a.op,a.lat,a.lon,a[col],a[ncol])]
    g=tt[tt.bin_size=='1km']
    h=g.groupby(['op','TrafficDirection','hour'],as_index=False)[col].sum()
    hourly=[{'op':o,'d':'D' if d=='Downlink' else 'U','h':int(hh),'tot':round(v,1)}
            for o,d,hh,v in zip(h.op,h.TrafficDirection,h.hour,h[col])]
    dl=g[g.TrafficDirection=='Downlink'].groupby(['lat','lon','op'],as_index=False)[[col,ncol]].sum()
    tot=dl.groupby(['lat','lon'],as_index=False)[col].sum().rename(columns={col:'all'})
    lead=dl.sort_values(col).groupby(['lat','lon']).tail(1)
    mg=tot.merge(lead,on=['lat','lon']).sort_values('all',ascending=False).head(12)
    ns=dl.groupby(['lat','lon'],as_index=False)[ncol].sum()
    mg=mg.merge(ns,on=['lat','lon'],suffixes=('','_tot'))
    hot=[{'la':round(la,4),'lo':round(lo,4),'gb':round(a/1024,2),'lead':o,
          'share':round(100*v/a,1),'n':int(n)} for la,lo,a,o,v,n in
         zip(mg.lat,mg.lon,mg['all'],mg.op,mg[col],mg[ncol+'_tot'])]
    return cells,hourly,hot

def tsum_state(tt):
    out={}
    g=tt[tt.bin_size=='1km']
    for o in OPS:
        s=g[g.op==o]; d=s[s.TrafficDirection=='Downlink']; u=s[s.TrafficDirection=='Uplink']
        dlr,dlc = d.tv_sum_raw.sum(), d.tv_sum.sum(); ulr,ulc = u.tv_sum_raw.sum(), u.tv_sum.sum()
        out[o]=dict(dl_sum=round(dlr,1), ul_sum=round(ulr,1),
                    dl_med=R1(d.tv_median.median(),4), ul_med=R1(u.tv_median.median(),4),
                    outlier_sum=round(dlr-dlc,1), outlier_n=int((d.n_samples_raw-d.n_samples).sum()),
                    ratio_med=R1(d.tv_median.median()/max(u.tv_median.median(),1e-9)),
                    ratio_sum=R1(dlr/max(ulr,1e-9)), ratio_sum_clean=R1(dlc/max(ulc,1e-9)))
    return out

def corr_state(rs, tt, adj):
    sfx='_adj' if adj else ''
    g=rs[rs.bin_size=='1km'].groupby(['lat','lon'],as_index=False).agg(
        N=('n_samples'+sfx,'sum'), S=('rsrp_sum'+sfx,'sum'))
    d=tt[(tt.bin_size=='1km')&(tt.TrafficDirection=='Downlink')].groupby(['lat','lon'],as_index=False).agg(
        gb=('tv_sum','sum'), tn=('n_samples','sum'))
    m=g.merge(d,on=['lat','lon']); m=m[(m.N>=300)&(m.tn>=20)&(m.gb>0)]
    m['rsrp']=m.S/m.N; m['gb']=m.gb/1024
    cells=[{'rsrp':round(a,1),'gb':round(b,3),'n':int(n),'la':round(la,4),'lo':round(lo,4)}
           for a,b,n,la,lo in zip(m.rsrp,m.gb,m.N,m.lat,m.lon)]
    rr = round(float(np.corrcoef(m.rsrp, np.log10(m.gb))[0,1]),3) if len(m)>3 else None
    return cells, rr

slices={}
for key,(dates,label) in SL.items():
    rs=r[r.date.isin(dates)]; tt=t[t.date.isin(dates)]
    dd=dv[dv.date.isin(dates)]; vs=rv[rv.date.isin(dates)]
    dens=rs[rs.bin_size=='500m'].groupby(['hour','lat','lon'],as_index=False).n_samples.sum()
    dens=dens[dens.n_samples>=5]
    keys={}; pts=[]; byh={}
    for h,la,lo,n in zip(dens.hour,dens.lat,dens.lon,dens.n_samples):
        k=(round(la,4),round(lo,4))
        if k not in keys: keys[k]=len(pts); pts.append([k[0],k[1]])
        byh.setdefault(str(int(h)),[]).append([keys[k],int(n)])
    density={'pts':pts,'h':byh}
    node={'label':label,'rows':int(rs[rs.bin_size=='1km'].n_samples.sum()),'density':density,
          'rsrp':{}, 'traffic':{}, 'corr':{}}
    for adj,nm in ((False,'raw'),(True,'adj')):
        c,gp,hh,bd,pc,op = rsrp_state(rs,vs,adj); devs,manuf = dev_state(dd,adj)
        node['rsrp'][nm]={'cells':c,'gap':gp,'hourly':hh,'hist':hist_state(vs,adj),
                          'devices':devs,'manuf':manuf,'op':op,'bands':bd,'pct':pc}
    for cl,nm in ((False,'raw'),(True,'clean')):
        cc,hy,ho = traf_state(tt,cl); node['traffic'][nm]={'cells':cc,'hourly':hy,'hotspots':ho}
    for adj,nm in ((False,'raw'),(True,'adj')):
        cs,rr = corr_state(rs,tt,adj); node['corr'][nm]={'cells':cs,'r':rr}
    node['tsum']=tsum_state(tt)
    node['gen_mix']={o:{g:R1(p) for g,p in zip(tm[tm.op==o].RadioNetworkGeneration, tm[tm.op==o].pct_of_operator)} for o in OPS}
    node['sentinel_4g']={o:R1(float(osum[osum.op==o].pct_below_service.iloc[0])) for o in OPS}
    node['flagged_pct']={o:R1(float(osum[osum.op==o].quantised_sample_pct.iloc[0])) for o in OPS}
    q=dvc.groupby(['DeviceName','op'],as_index=False).agg(n=('n','sum'))
    q=q[q.n>=3000]
    rows=[]
    for dn,o,n in zip(q.DeviceName,q.op,q.n):
        s=dvc[(dvc.DeviceName==dn)&(dvc.op==o)].sort_values('n',ascending=False)
        top3=s.head(3); share=100*top3.n.sum()/n
        if share<25: continue
        avg=float((s.RSRP*s.n).sum()/n)
        rows.append({'d':dn,'op':o,'n':int(n),'q':round(share,1),'avg':round(avg,1),
                     'vals':[int(v) for v in top3.RSRP],'nuniq':int(len(s))})
    node['quant']=sorted(rows,key=lambda x:-x['q'])[:14]
    mt={}
    for dn,g in dt[dt.comparable==True].groupby('DeviceName'):
        e={}
        for o,mv in zip(g.op,g.matched_vs_operator):
            if isinstance(mv,str) and mv: e[o+mv[-1]]=True; e[mv[-1]+o]=True
        if e: mt[dn]=e
    node['rsrp']['raw']['matched']=mt; node['rsrp']['adj']['matched']=mt
    slices[key]=node

cl=nar.parse('cleaning_log'); cl=cl[cl.dataset=='RSRP'].sort_values('step_order')
funnel=[{'label':s,'n':int(a),'drop':(None if int(d)==0 else int(d))} for s,a,d in zip(cl.step,cl.rows_after,cl.removed)]
al=nar.parse('device_aliases')
pairs=[{'names':[c]+[x.strip() for x in str(a).split('|')],'n':int(n)} for c,a,n in
       zip(al.canonical_name,al.alias_names,al.n_groups)]
pairs=sorted(pairs,key=lambda x:-x['n'])[:10]
n8=dvc[(dvc.DeviceName=='Galaxy Note8')&(dvc.op=='A')].sort_values('n',ascending=False)
tot=int(n8.n.sum())
bA=slices['ALL']['rsrp']; 
D={'meta':{'rsrp_raw_rows':int(cl.rows_before.iloc[0]),'traffic_raw_rows':138469,
           'rsrp_valid_rows':int(cl.rows_after.iloc[-1]),'traffic_4g_rows':int(t[t.bin_size=='1km'].n_samples.sum()),
           'date_min':'2019-11-02','date_max':'2019-11-04','city':'Riyadh',
           'bbox':[float(r.lat.min()),float(r.lon.min()),float(r.lat.max()),float(r.lon.max())],'lat0':24.7},
   'hexshape':{k:[[CELL[b]/2,-CELL[b]/2*0.913],[CELL[b]/2,CELL[b]/2*0.913],
                  [-CELL[b]/2,CELL[b]/2*0.913],[-CELL[b]/2,-CELL[b]/2*0.913]] for k,b in GRID.items()},
   'note8':{'op':'A','n':tot,'share':round(100*tot/slices['ALL']['rsrp']['raw']['op']['Operator A']['n'],1),
            'mean_with':bA['raw']['op']['Operator A']['avg'],'mean_without':bA['adj']['op']['Operator A']['avg'],
            'poor_with':bA['raw']['pct']['Operator A']['poor'],'poor_without':bA['adj']['pct']['Operator A']['poor'],
            'nuniq':int(len(n8)),'vals':[int(v) for v in n8.head(3).RSRP],
            'q':round(100*n8.head(3).n.sum()/tot,1)},
   'dq':{'funnel':funnel,
         'extra':{'null_country':0,'manuf_variants':int(dt.DeviceManufacturer.nunique()),
                  'sentinel_share_overall':23.6,'sentinel_share_4g':0.0,
                  'gen_mix':{o:{g:R1(p) for g,p in zip(tm[tm.op==o].RadioNetworkGeneration,tm[tm.op==o].pct_of_operator)} for o in OPS},
                  'traffic_bad_ts':0,'traffic_outliers':14,
                  'top10_device_share':round(100*dt.groupby('DeviceName').n_samples.sum().nlargest(10).sum()/dt.n_samples.sum(),1),
                  'samsung_share':round(100*dt[dt.DeviceManufacturer=='Samsung'].n_samples.sum()/dt.n_samples.sum(),1)},
         'dupes':{'rows':int(al.n_groups.sum()),'pct':7.5,'pairs':pairs}},
   'slices':slices}
D['slices']['D2']='WE'          # identical date range - aliased at load
json.dump(D, open(OUT/'data_v5.json','w'), separators=(',',':'))
print('bytes', (OUT/'data_v5.json').stat().st_size)
print('corr r ALL raw', slices['ALL']['corr']['raw']['r'], '| cells', len(slices['ALL']['corr']['raw']['cells']))
print('op A avg raw/adj', bA['raw']['op']['Operator A']['avg'], bA['adj']['op']['Operator A']['avg'])
print('quant top', slices['ALL']['quant'][:2])
