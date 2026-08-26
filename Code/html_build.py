import json, re, pandas as pd
from pathlib import Path
SRC = Path('/root/work/Riyadh_4G_Network_Dashboard.html')
P2  = Path('/root/work/part2/part2_outputs')
OUT = Path('/root/work/v6/Riyadh_4G_Network_Dashboard_v5.html')
h = SRC.read_text(encoding='utf-8')

# ── 1. swap the data blob ────────────────────────────────────────────────────
D = Path('/root/work/v6/data_v5.json').read_text(encoding='utf-8')
i = h.index('const D = {'); j = h.index('\n', i)
shim = """
Object.keys(D.slices).forEach(k=>{const s=D.slices[k]; if(typeof s==='string')return;
  const d=s.density; if(d&&d.pts){const out=[]; for(const hh in d.h){for(const pr of d.h[hh]){const p=d.pts[pr[0]];
    out.push({h:+hh,la:p[0],lo:p[1],n:pr[1]});}} s.density=out;}});
Object.keys(D.slices).forEach(k=>{ if(typeof D.slices[k]==='string') D.slices[k]=D.slices[D.slices[k]]; });
"""
h = h[:i] + 'const D = ' + D + ';' + shim + h[j:]

# ── 2. part-2 payload ────────────────────────────────────────────────────────
rd = lambda f: pd.read_csv(P2/f)
P = {
 'fc':   rd('q2_forecast.csv').rename(columns={'operator':'op','direction':'d','forecast_mb':'y',
            'lo80_mb':'lo','hi80_mb':'hi'}).assign(op=lambda x:x.op.str[-1],
            d=lambda x:x.d.str[0], ts=lambda x:x.ts.str[-8:-6].astype(int))
            [['op','d','ts','y','lo','hi']].round(1).to_dict('records'),
 'hist': rd('q2_series.csv').rename(columns={'RadioOperatorName':'op','TrafficDirection':'d',
            'tv_samsung':'y'}).assign(op=lambda x:x.op.str[-1], d=lambda x:x.d.str[0])
            [['op','d','Date','Hour','y']].round(1).to_dict('records'),
 'trend': rd('q2_trend.csv').assign(op=lambda x:x.operator.str[-1], d=lambda x:x.direction.str[0])
            [['op','d','pct_per_day','ci_lo','ci_hi','p']].to_dict('records'),
 'eff':  rd('q1_effects.csv').to_dict('records'),
 'scen': rd('q1_scenario.csv').assign(op=lambda x:x.operator.str[-1], d=lambda x:x.metric.str[0])
            [['op','d','uplift_dB','pct_change','ci_lo','ci_hi']].to_dict('records'),
 'poly': rd('q1_polygon_summary.csv').assign(op=lambda x:x.RadioOperatorName.str[-1])
            [['op','rsrp_mean','rsrp_samples','downlink_gb','uplink_gb']].to_dict('records'),
 'score': rd('q2_model_scores.csv').groupby(['test','model'],as_index=False).MASE.mean()
            .round(3).to_dict('records'),
}
h = h.replace('const D = ', 'const P2 = ' + json.dumps(P, separators=(',',':')) + ';\nconst D = ', 1)

# ── 3. hex → cell wording (identifiers protected) ────────────────────────────
prot = {'hexshape':'\x01','hexPath':'\x02','HexMap':'\x03','hexagonal':'\x04'}
for k,v in prot.items(): h = h.replace(k, v)
h = re.sub(r'\bhexes\b','cells',h); h = re.sub(r'\bhex\b','cell',h)
h = re.sub(r'\bHexes\b','Cells',h); h = re.sub(r'\bHex\b','Cell',h)
for k,v in prot.items(): h = h.replace(v, k)

for a,b in [
 ('1.4&nbsp;km cell grid','1&nbsp;km grid'),('530&nbsp;m cell grid','500&nbsp;m grid'),
 ('530&nbsp;m cells coloured','1&nbsp;km cells coloured'),('1.4&nbsp;km cell with','1&nbsp;km cell with'),
 ('Top 1.4&nbsp;km cells','Top 1&nbsp;km cells'),('1.4&nbsp;km tile','1&nbsp;km cell'),
 ("{0:['6','3.7 km cell'],1:['7','1.4 km cell'],2:['8','530 m cell']}",
  "{0:['6','2 km bin'],1:['7','1 km bin'],2:['8','500 m bin']}"),
 ('>1.4 km cell<','>1 km bin<'),
 ('Full window &middot; 1&ndash;4 Nov 2019','Full window &middot; 2&ndash;4 Nov 2019'),
 ('Weekend &middot; Fri 1 &ndash; Sat 2 Nov','Weekend &middot; Sat 2 Nov'),
 ('Friday 1 Nov has only 64 readings in the whole file, so it has no single-day entry of its own — it is folded into the weekend option.',
  'The file spans Sat 2 – Mon 4 Nov 2019. Saturday is the Saudi weekend, so only two weekdays are represented.'),
 ('Spatial aggregation uses H3 hexagonal bins at resolutions 6 / 7 / 8 (3.7 km, 1.4 km, 0.53 km edge). Cell centroids are plotted on an equirectangular projection anchored at 24.70&deg;N; distances are accurate to &lt;0.5% across this extent.',
  'Spatial aggregation uses equal-degree bins of 2 km, 1 km and 500 m, identical to the grids driving the Tableau workbook. Bin centroids are plotted on an equirectangular projection anchored at 24.70&deg;N; distances are accurate to &lt;0.5% across this extent.'),
 ('RSRP.csv (2,725,353 rows) and TrafficVolume.csv (138,469 rows)',
  'RSRP.csv (2,725,353 rows) and TrafficVolume.csv (138,469 rows), processed by the v5 pipeline'),
 ('Dashboard Mockup','Dashboard'),
 ('every chart on all three pages follows the filter row above','every chart on all four pages follows the filter row above'),
 ('1&ndash;4 Nov 2019 &middot; 2.06M validated RSRP samples','2&ndash;4 Nov 2019 &middot; 1.98M validated RSRP samples'),
 ('1&ndash;4 Nov 2019, timestamps in UTC+03:00.','2&ndash;4 Nov 2019, timestamps in UTC+03:00.'),
 ('1&ndash;4 Nov 2019','2&ndash;4 Nov 2019'),
 ('1.4 km cells','1 km cells'),('1.4 km cell','1 km cell'),('530 m cell','500 m cell'),
 ('2.06M crowdsourced','1.98M crowdsourced'),
]:
    h = h.replace(a,b)

# ── 3b. square bins: shape loop must follow the array length, and the basemap
#        footprint is built from 1 km cells, so use that grid for it
h = h.replace("for(let i=0;i<6;i++){ const [x,y]=this.px(la+sh[i][0], lo+sh[i][1]);",
              "for(let i=0;i<sh.length;i++){ const [x,y]=this.px(la+sh[i][0], lo+sh[i][1]);")
h = h.replace("const sh = D.hexshape['8'];\n    for(const c of BASE)", "const sh = D.hexshape['7'];\n    for(const c of BASE)")
# heat map draws the 1 km RSRP grid, not the 500 m density grid
h = h.replace("heatMap.draw = m=>{\n    m.clear(); m.basemap();\n    const ctx=m.ctx, sh=D.hexshape['8'];",
              "heatMap.draw = m=>{\n    m.clear(); m.basemap();\n    const ctx=m.ctx, sh=D.hexshape['7'];")

# ── 4. mobile CSS ────────────────────────────────────────────────────────────
mob = """
/* ============================================================
   MOBILE  — single column, scrollable tabs, touch-sized controls
   ============================================================ */
@media(max-width:820px){
  .wrap,main{padding-left:12px;padding-right:12px}
  .tabs{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .tabs::-webkit-scrollbar{display:none}
  .tab{flex:0 0 auto;white-space:nowrap}
  .grid,.g2,.g3,.g23,.g32{grid-template-columns:1fr !important}
  .g4{grid-template-columns:repeat(2,minmax(0,1fr)) !important}
  .span2{grid-column:auto !important}
  .stat.hero{grid-column:1 / -1}
  .filterbar{position:static;flex-wrap:wrap;gap:10px}
  .fgroup{flex:1 1 46%;min-width:0}
  .fgroup select,.fgroup input[type=range]{width:100%;min-width:0}
  .ctrlrow{flex-wrap:wrap;gap:10px}
  .ctrl{flex:1 1 100%;min-width:0}
  .mapwrap{aspect-ratio:4/3 !important}
  .card{padding:14px}
  h2{font-size:19px}h3{font-size:14.5px}
  .val{font-size:28px}
  .tableview{overflow-x:auto}
  table{min-width:520px}
  .chart{overflow-x:hidden}
  .maplegend{transform:scale(.85);transform-origin:bottom left}
  .playbtn,.tbtn,.seg button{min-height:38px}
  .footer{font-size:11px}
}
@media(max-width:480px){
  .g4{grid-template-columns:1fr !important}
  .val{font-size:26px}
  .brand-title{font-size:15px}
}
"""
h = h.replace('</style>', mob + '</style>', 1)

# ── 5. fourth tab ────────────────────────────────────────────────────────────
h = h.replace('<button class="tab" role="tab" aria-selected="false" data-page="p3">Device &amp; Data Quality</button>',
 '<button class="tab" role="tab" aria-selected="false" data-page="p3">Device &amp; Data Quality</button>\n'
 '      <button class="tab" role="tab" aria-selected="false" data-page="p4">Forecast &amp; Impact</button>')

PAGE4 = """
<!-- =========================================================== PAGE 4 -->
<section class="page" id="p4">
  <div class="pagehead">
    <h2>Forecast &amp; Impact</h2>
    <p>Two forward-looking questions answered on the cleaned feed: what next-day traffic looks like, and what a coverage
       improvement would actually buy. Both are reported with the uncertainty attached, because at this sample size the
       uncertainty <em>is</em> the finding.</p>
  </div>

  <div class="grid g4" id="p4bans"></div>

  <div class="divider"></div>
  <p class="sectionlab">Next 24 hours &mdash; traffic forecast</p>
  <div class="grid g23 top">
    <div class="card">
      <div class="card-head"><div>
        <h3>Observed 72 hours, forecast next 24</h3>
        <div class="sub">SARIMA(1,0,0)(1,0,0,24) on log traffic, fitted per operator and direction. Shaded band is the
          80% prediction interval &mdash; it is wide on purpose.</div></div></div>
      <div class="chart" id="fcChart"></div>
      <div class="legend" id="fcLegend"></div>
      <div class="insight info" id="fcInsight"><div class="ic">i</div><p></p></div>
    </div>
    <div class="card">
      <div class="card-head"><div><h3>Is traffic actually growing?</h3>
        <div class="sub">Daily percentage change with a 95% confidence interval, per operator and direction.</div></div></div>
      <div class="tableview on" id="tblTrend" style="max-height:none"></div>
      <div class="insight warn" id="trendInsight"><div class="ic">!</div><p></p></div>
    </div>
  </div>

  <div class="divider"></div>
  <p class="sectionlab">Would better coverage carry more traffic?</p>
  <div class="grid g23 top">
    <div class="card">
      <div class="card-head"><div><h3>Coverage-uplift effect, measured within cells</h3>
        <div class="sub">Elasticity of traffic to RSRP, estimated with cell and hour fixed effects so the comparison is
          the same place at the same time of day &mdash; not one neighbourhood against another.</div></div></div>
      <div class="tableview on" id="tblEff" style="max-height:none"></div>
      <div class="insight crit" id="effInsight"><div class="ic">!</div><p></p></div>
    </div>
    <div class="card">
      <div class="card-head"><div><h3>Scenario &mdash; lift the study area to the best operator's signal</h3>
        <div class="sub">Applying the measured elasticity to the RSRP gap each operator would have to close.</div></div></div>
      <div class="chart" id="scenChart"></div>
      <div class="tableview on" id="tblScen" style="max-height:none"></div>
    </div>
  </div>

  <div class="divider"></div>
  <p class="sectionlab">What this means</p>
  <div class="grid g3" id="p4cards"></div>
</section>
"""
h = h.replace('</main>', PAGE4 + '</main>', 1)

# ── 6. page-4 renderers ──────────────────────────────────────────────────────
JS = r"""
/* ============================================================
   PAGE 4 — FORECAST & IMPACT
   ============================================================ */
let fcDir='D';
function p4dir(){ return fcDir; }
function renderP4(){
  const o=HOME, d=p4dir();
  const fc=P2.fc.filter(r=>r.op===o&&r.d===d).sort((a,b)=>a.ts-b.ts);
  const hist=P2.hist.filter(r=>r.op===o&&r.d===d);
  const fcGB=fc.reduce((s,r)=>s+r.y,0)/1024;
  const days={}; hist.forEach(r=>{days[r.Date]=(days[r.Date]||0)+r.y;});
  const lastGB=(days[Object.keys(days).sort().pop()]||0)/1024;
  const chg=lastGB? (fcGB-lastGB)/lastGB*100 : 0;
  const mase=(P2.score.find(s=>s.model==='SARIMA'&&s.test==='24-step ahead')||{}).MASE;
  const sn=(P2.score.find(s=>s.model==='Seasonal naive'&&s.test==='24-step ahead')||{}).MASE||1;
  $('#p4bans').innerHTML=[
    ['Forecast next 24 h', num(fcGB,1), 'GB', 'Sum of the hourly SARIMA forecast for '+OPNAME[o]+' downlink'],
    ['vs last observed day', (chg>=0?'+':'')+num(chg,1), '%', 'Change against the final complete day in the window'],
    ['Forecast error &middot; MASE', num(mase,2), '', 'Mean absolute scaled error over a full day ahead. Below 1 beats the seasonal-naive baseline'],
    ['Skill vs seasonal naive', num((1-mase/sn)*100,0), '%', 'How much of the naive benchmark&rsquo;s error the model removes']
  ].map(([lab,v,u,t],i)=>`<div class="stat${i===0?' hero':''}"><div class="lab">${lab} <span title="${t}">&#9432;</span></div>
      <div class="val">${v} <small>${u}</small></div></div>`).join('');

  // ---- forecast chart -------------------------------------------------------
  const host=$('#fcChart'); host.innerHTML='';
  const W=chartW(host),H=300,L=58,Rp=16,T=14,B=40;
  const obs=hist.sort((a,b)=>a.Date.localeCompare(b.Date)||a.Hour-b.Hour).map((r,i)=>({x:i,y:r.y/1024}));
  const f0=obs.length;
  const fpt=fc.map((r,i)=>({x:f0+i,y:r.y/1024,lo:r.lo/1024,hi:r.hi/1024}));
  const all=[...obs.map(p=>p.y),...fpt.map(p=>p.hi)];
  const ymax=Math.max(...all)*1.05, xmax=f0+fpt.length-1;
  const X=v=>L+v/xmax*(W-L-Rp), Y=v=>H-B-v/ymax*(H-T-B);
  const svg=svgRoot(W,H); svg.setAttribute('aria-label','Observed and forecast hourly traffic');
  [0,.25,.5,.75,1].forEach(f=>{const v=ymax*f;
    svg.appendChild(S('line',{x1:L,y1:Y(v),x2:W-Rp,y2:Y(v),stroke:cssv('--grid'),'stroke-width':1}));
    const t=S('text',{x:L-8,y:Y(v)+3.5,'text-anchor':'end','font-size':10.5,fill:cssv('--text-muted')});
    t.textContent=num(v,1)+' GB'; svg.appendChild(t);});
  svg.appendChild(S('rect',{x:X(f0),y:T,width:W-Rp-X(f0),height:H-B-T,fill:cssv('--seq-450'),opacity:.05}));
  const band=fpt.map(p=>`${X(p.x).toFixed(1)},${Y(p.hi).toFixed(1)}`).join(' ')+' '+
             fpt.slice().reverse().map(p=>`${X(p.x).toFixed(1)},${Y(p.lo).toFixed(1)}`).join(' ');
  svg.appendChild(S('polygon',{points:band,fill:opColor(o),opacity:.13}));
  const line=pts=>pts.map((p,i)=>`${i?'L':'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join('');
  svg.appendChild(S('path',{d:line(obs),fill:'none',stroke:opColor(o),'stroke-width':2,'stroke-linejoin':'round'}));
  svg.appendChild(S('path',{d:line([obs[obs.length-1],...fpt]),fill:'none',stroke:opColor(o),
    'stroke-width':2.2,'stroke-dasharray':'5 3'}));
  svg.appendChild(S('line',{x1:X(f0),y1:T,x2:X(f0),y2:H-B,stroke:cssv('--axis'),'stroke-width':1,'stroke-dasharray':'3 3'}));
  const fl=S('text',{x:X(f0)+6,y:T+11,'font-size':10,'font-weight':600,fill:cssv('--text-secondary')});
  fl.textContent='forecast →'; svg.appendChild(fl);
  for(let i=0;i<=xmax;i+=12){ const t=S('text',{x:X(i),y:H-14,'text-anchor':'middle','font-size':10.5,fill:cssv('--text-muted')});
    t.textContent=(i%24).toString().padStart(2,'0')+':00'; svg.appendChild(t); }
  const xl=S('text',{x:(L+W-Rp)/2,y:H-1,'text-anchor':'middle','font-size':10,fill:cssv('--text-muted')});
  xl.textContent='72 observed hours (2–4 Nov) then 24 forecast hours (5 Nov)'; svg.appendChild(xl);
  host.appendChild(svg);
  $('#fcLegend').innerHTML=
    `<span class="item"><span class="key" style="background:${opColor(o)}"></span>${OPNAME[o]} observed</span>`+
    `<span class="item"><span class="key" style="background:${opColor(o)};opacity:.45"></span>Forecast &middot; 80% interval</span>`+
    `<span class="item" style="cursor:pointer" id="fcToggle"><span class="key sq" style="background:var(--seq-450)"></span>${d==='D'?'Downlink':'Uplink'} &mdash; click to switch</span>`;
  $('#fcToggle').onclick=()=>{ fcDir = fcDir==='D'?'U':'D'; renderP4(); };
  const width=(fpt[0].hi-fpt[0].lo)/Math.max(fpt[0].y,1e-9);
  $('#fcInsight').querySelector('p').innerHTML =
    `<b>${OPNAME[o]} is forecast to carry ${num(fcGB,1)} GB of ${d==='D'?'downlink':'uplink'} over the next 24 hours</b>, `+
    `${chg>=0?'up':'down'} ${num(Math.abs(chg),1)}% on the last observed day. The 80% interval spans roughly `+
    `${num(width,1)}× the central estimate at the first forecast hour &mdash; three days of history cannot support a tighter claim, `+
    `and a forecast that hid that would be worse than useless for capacity planning.`;

  // ---- trend table ----------------------------------------------------------
  buildTable('#tblTrend',['Operator','Direction','Change / day','95% CI','p'],
    P2.trend.map(r=>[OPNAME[r.op], r.d==='D'?'Downlink':'Uplink',
      (r.pct_per_day>=0?'+':'')+num(r.pct_per_day,1)+'%',
      num(r.ci_lo,1)+'% to '+num(r.ci_hi,1)+'%', num(r.p,3)]));
  const sig=P2.trend.filter(r=>r.p<0.05).length;
  $('#trendInsight').querySelector('p').innerHTML = sig===0
    ? `<b>Not one of the six series shows a statistically significant trend.</b> Every confidence interval spans zero, and the
       smallest p-value is ${num(Math.min(...P2.trend.map(r=>r.p)),3)}. Over three days that is the expected result: what looks
       like growth or decline is the day-of-week pattern, not a trajectory. Any capacity plan that extrapolates a trend from
       this window is extrapolating noise.`
    : `<b>${sig} of 6 series show a significant daily trend.</b> Treat with care — three days is a very short base.`;

  // ---- coverage-uplift effects ---------------------------------------------
  buildTable('#tblEff',['Metric','Specification','Cells','Effect per 10 dB','95% CI','p'],
    P2.eff.map(r=>[r.metric, r.spec, int(r.n),
      (r.pct_per_10dB>=0?'+':'')+num(r.pct_per_10dB,1)+'%',
      num(r.ci_lo*10*100,1)+'% to '+num(r.ci_hi*10*100,1)+'%', num(r.p,3)]));
  $('#effInsight').querySelector('p').innerHTML =
    `<b>Within a given cell and hour, better RSRP does not produce more traffic.</b> Every point estimate is negative or
     indistinguishable from zero, and the one nominally significant coefficient (uplink, ${num(P2.eff[2].pct_per_10dB,1)}% per 10 dB,
     p&nbsp;=&nbsp;${num(P2.eff[2].p,3)}) points the <em>wrong way</em> for a coverage business case. The positive correlation visible
     on the explorer page is population density counted twice: busy places attract both traffic and capacity investment.
     Fixed effects remove that, and the relationship goes with it.`;

  // ---- scenario -------------------------------------------------------------
  const host2=$('#scenChart'); host2.innerHTML='';
  const rows=P2.scen.filter(r=>r.d==='D');
  const W2=chartW(host2),H2=150,L2=96,R2=64;
  const mx=Math.max(...P2.scen.map(r=>Math.abs(r.ci_lo)),...P2.scen.map(r=>Math.abs(r.ci_hi)),1)*1.15;
  const X2=v=>L2+(v+mx)/(2*mx)*(W2-L2-R2);
  const svg2=svgRoot(W2,H2); svg2.setAttribute('aria-label','Predicted traffic change from closing the RSRP gap');
  svg2.appendChild(S('line',{x1:X2(0),y1:8,x2:X2(0),y2:H2-24,stroke:cssv('--axis'),'stroke-width':1}));
  rows.forEach((r,i)=>{
    const y=22+i*34;
    const lab=S('text',{x:L2-10,y:y+4,'text-anchor':'end','font-size':11.5,fill:cssv('--text-primary')});
    lab.textContent=OPNAME[r.op]+' · +'+num(r.uplift_dB,1)+' dB'; svg2.appendChild(lab);
    svg2.appendChild(S('line',{x1:X2(r.ci_lo),y1:y,x2:X2(r.ci_hi),y2:y,stroke:opColor(r.op),'stroke-width':3,opacity:.35}));
    svg2.appendChild(S('circle',{cx:X2(r.pct_change),cy:y,r:5,fill:opColor(r.op)}));
    const v=S('text',{x:X2(r.ci_hi)+8,y:y+4,'font-size':10.5,'font-weight':650,fill:cssv('--text-secondary')});
    v.textContent=(r.pct_change>=0?'+':'')+num(r.pct_change,1)+'%'; svg2.appendChild(v);
  });
  [-mx,0,mx].forEach(v=>{const t=S('text',{x:X2(v),y:H2-8,'text-anchor':'middle','font-size':10.5,fill:cssv('--text-muted')});
    t.textContent=num(v,0)+'%'; svg2.appendChild(t);});
  host2.appendChild(svg2);
  buildTable('#tblScen',['Operator','Metric','Uplift needed','Predicted change','95% CI'],
    P2.scen.map(r=>[OPNAME[r.op], r.d==='D'?'Downlink':'Uplink', '+'+num(r.uplift_dB,2)+' dB',
      (r.pct_change>=0?'+':'')+num(r.pct_change,2)+'%', num(r.ci_lo,2)+'% to '+num(r.ci_hi,2)+'%']));

  // ---- takeaway cards -------------------------------------------------------
  const cards=[
    ['info','A usable next-day forecast exists',
     `SARIMA beats the seasonal-naive benchmark by <b>${num((1-mase/sn)*100,0)}%</b> (MASE ${num(mase,2)}) over a full day ahead,
      and beats naive, Holt-Winters, gradient boosting and Prophet on both horizons. The daily shape is strong and stable —
      that is what the model is capturing.`],
    ['warn','But only the shape, not the level',
     `The 80% interval is roughly ${num(width,1)}× the central estimate. With 72 observations there is no way to narrow it
      honestly. Use the forecast for <em>when</em> the peak lands, not for <em>how big</em> it will be.`],
    ['crit','The coverage business case does not survive fixed effects',
     `Comparing the same cell at the same hour, a 10 dB RSRP improvement changes traffic by
      ${num(P2.eff[0].pct_per_10dB,1)}% (p&nbsp;=&nbsp;${num(P2.eff[0].p,3)}) on downlink. The scenario analysis puts every
      operator's predicted gain within a couple of percent of zero, with intervals straddling it. Coverage spend must be
      justified by quality of experience and churn, not by a traffic uplift this data cannot demonstrate.`],
    ['good','What the study area does show',
     `Across the polygon the three networks differ by <b>${num(Math.max(...P2.poly.map(r=>r.rsrp_mean))-Math.min(...P2.poly.map(r=>r.rsrp_mean)),1)} dB</b>
      in mean RSRP on ${int(P2.poly.reduce((s,r)=>s+r.rsrp_samples,0))} samples. That gap is real and measurable — it is the
      <em>consequence</em> of the gap for traffic that the data cannot pin down.`],
    ['warn','Three days is the binding constraint',
     `No weekly seasonality, no trend identification, no holiday effects. Every limitation on this page traces back to the
      window length, not to the method. A four-week feed would change all of it.`],
    ['info','What we would instrument next',
     `Per-cell throughput and RRC-connected counts alongside RSRP, so the outcome variable is quality of experience rather
      than volume. Volume is dominated by how many people are present; experience is what coverage actually moves.`]
  ];
  $('#p4cards').innerHTML = cards.map(([sev,t,b])=>
    `<div class="card" style="border-top:3px solid ${sev==='crit'?cssv('--critical'):sev==='warn'?cssv('--warning'):sev==='good'?cssv('--good'):cssv('--seq-450')}">
       <div class="card-head"><div><h3>${t}</h3></div></div>
       <p style="margin:8px 0 0;font-size:13px;color:var(--text-secondary);line-height:1.55">${b}</p></div>`).join('');
}
"""
h = h.replace('function initBasemap(){', JS + '\nfunction initBasemap(){', 1)
h = h.replace("renderTrafficHour(); renderDlUl(); renderOutlier(); renderQuant(); renderDupes(); renderFunnel(); renderDqList(); renderTakeaways();",
              "renderTrafficHour(); renderDlUl(); renderOutlier(); renderQuant(); renderDupes(); renderFunnel(); renderDqList(); renderTakeaways(); renderP4();")
OUT.write_text(h, encoding='utf-8')
print('written', round(OUT.stat().st_size/1e6,2), 'MB')
