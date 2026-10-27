#!/usr/bin/env python3
"""Refresh official publicly downloadable FRED CSV data into a static dashboard JSON.
Standard library only. Maintains human-curated metrics and source dates. No fake fallbacks.
"""
import csv, io, json, math, os, pathlib, time, urllib.request, hashlib
from datetime import datetime, timezone
from collections import deque
ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "snapshot.json"
DATA = json.loads(PATH.read_text(encoding="utf-8"))
HISTORY_PATH = ROOT / "data" / "history.json"
BEFORE_METRICS = json.dumps(DATA["metrics"], sort_keys=True, ensure_ascii=False)
SERIES = {
    'DCOILBRENTEU': ('brent', 1.0),
    'DGS2': ('dgs2', 1.0), 'DGS10': ('dgs10', 1.0), 'DGS30': ('dgs30', 1.0),
    'DFII10': ('tips10', 1.0), 'T10YIE': ('breakeven10', 1.0),
    'BAMLH0A0HYM2': ('hy', 100.0), 'UNRATE': ('unemployment', 1.0),
}
def read_fred(series):
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
    req = urllib.request.Request(url, headers={'User-Agent':'MacroScenarioRadar/1.0 public-financial-data-research'})
    with urllib.request.urlopen(req, timeout=25) as response:
        body = response.read().decode('utf-8-sig')
    items=[]
    for row in csv.DictReader(io.StringIO(body)):
        date=row.get('observation_date') or row.get('DATE')
        raw=row.get(series)
        if not date or raw is None or raw.strip() in ('', '.'):
            continue
        try: v=float(raw)
        except ValueError: continue
        if math.isfinite(v): items.append((date, v))
    if not items: raise ValueError(f'No valid observations for {series}')
    return items

def update(key, date, value, series, multiplier=1.0):
    rec = DATA['metrics'].get(key)
    if not rec: return
    prevdate=rec.get('asof')
    # Prevent replacing a newer verified source observation with an older release.
    if prevdate and date < prevdate: return
    rec['value']=round(value*multiplier, 3)
    rec['asof']=date
    rec['source']=f'FRED / {series}'
    rec['url']=f'https://fred.stlouisfed.org/series/{series}'


def observation_signature():
    items = {k: {'value': r.get('value'), 'asof': r.get('asof')} for k,r in DATA['metrics'].items()}
    body = json.dumps(items, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(body).hexdigest()[:16]

# Keep the historical weights consistent with the browser's transparent rules.
# These are signal-fit weights, never statistically calibrated probabilities.
def regime_weights():
    metrics = DATA['metrics']
    def val(key):
        x = metrics.get(key, {}).get('value')
        try: return float(x) if x is not None else None
        except (TypeError, ValueError): return None
    raw = [math.log(x) for x in [10,30,20,15,15,10]]
    def add(i, cond, w):
        if cond: raw[i] += w
    oil,pce,p3,orders,prices,tips,hy,unemp,prod,capex,cuts,tp = (
        val(k) for k in ('brent','corepce','corepce3m','ismnew','ismprices','tips10','hy','unemployment','productivity','capexgrowth','capexcuts','term_premium')
    )
    if oil is not None:
        add(1,oil<=95,.65);add(1,oil>105,-.25);add(2,oil>=105,.33);add(5,oil>=135,.9);add(4,oil<80,.4)
    if pce is not None:
        add(0,pce<=2.3,.4);add(1,pce<=2.7,.38);add(2,pce>=2.8,.3);add(5,pce>=3.8,.55);add(4,pce<2.4,.35)
    if p3 is not None:
        add(0,p3<=2.5,.55);add(1,p3<=2.5,.45);add(2,p3>=3.1,.42);add(5,p3>=4,.6)
    if orders is not None:
        add(0,orders>=53,.24);add(1,orders>=50,.18);add(2,orders>=52,.47);add(4,orders<48,.72);add(5,orders<48,.46);add(3,orders<50,.25)
    if prices is not None:
        add(1,prices<60,.43);add(2,prices>70,.53);add(5,prices>70,.44)
    if tips is not None:
        add(1,tips<=2.2,.35);add(2,tips>=2.5,.4);add(3,tips>=2.8,.48);add(4,tips<=2.0,.4);add(5,tips>=2.8,.22)
    if hy is not None:
        add(1,hy<350,.3);add(2,hy<375,.20);add(3,hy>=450,.67);add(4,hy>=600,.95);add(5,hy>=600,.7)
    if unemp is not None:
        add(4,unemp>=5.2,.66);add(5,unemp>=5.1,.6);add(1,unemp<=4.5,.18)
    if prod is not None:
        add(0,prod>=3,.9);add(0,prod<2,-.28);add(1,prod>=2,.18)
    if capex is not None:
        add(0,capex>=15,.36);add(1,capex>=10,.28);add(2,capex>=15,.38);add(3,capex<0,.48);add(4,capex<=-15,.65);add(5,capex<=-20,.58)
    if cuts is not None:
        add(3,cuts>=2,.6);add(4,cuts>=3,.67);add(5,cuts>=3,.49)
    if tp is not None:
        add(3,tp>=1.2,.54)
    mx=max(raw)
    exps=[math.exp(x-mx) for x in raw]
    probs=[100*x/sum(exps) for x in exps]
    floored=[math.floor(x*10)/10 for x in probs]
    rem=round((100-sum(floored))*10)
    for i in sorted(range(6), key=lambda k: probs[k]-floored[k], reverse=True)[:rem]: floored[i]+=0.1
    return [round(x,1) for x in floored]

errors=[]; successes=0
for series, (key, mult) in SERIES.items():
    try:
        rows=read_fred(series)
        update(key,*rows[-1],series,mult)
        successes+=1
    except Exception as exc:
        errors.append(f'{series}: {str(exc)[:100]}')
    time.sleep(0.2)
try:
    rows=read_fred('PCEPILFE')
    # Match exact year and month, not an arbitrary number of row positions.
    months={d[:7]:v for d,v in rows}
    latestdate, latestvalue=rows[-1]
    year,month=map(int,latestdate[:7].split('-'))
    lastyr=f'{year-1:04d}-{month:02d}'
    prevyear=months.get(lastyr)
    if prevyear and prevyear>0:
        update('corepce',latestdate,(latestvalue/prevyear-1)*100,'PCEPILFE')
    m0=(year*12+month)-3
    ym=f'{(m0-1)//12:04d}-{(m0-1)%12+1:02d}'
    prev3=months.get(ym)
    if prev3 and prev3>0:
        update('corepce3m',latestdate,((latestvalue/prev3)**4-1)*100,'PCEPILFE')
    successes+=1
except Exception as exc:
    errors.append(f'PCEPILFE: {str(exc)[:100]}')
try:
    rows=read_fred('OPHNFB')
    lastdate,lastval=rows[-1]
    q={(int(d[:4]),(int(d[5:7])-1)//3+1):v for d,v in rows}
    y,quarter=int(lastdate[:4]),(int(lastdate[5:7])-1)//3+1
    old=q.get((y-1,quarter))
    if old and old>0: update('productivity',lastdate,(lastval/old-1)*100,'OPHNFB')
    successes+=1
except Exception as exc:
    errors.append(f'OPHNFB: {str(exc)[:100]}')
# If all sources are blocked, don't silently redate the snapshot.
if successes == 0:
    raise SystemExit('All official data pulls failed; retain last verified snapshot. ' + '; '.join(errors))
now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
changed = BEFORE_METRICS != json.dumps(DATA['metrics'], sort_keys=True, ensure_ascii=False)
mode_changed = DATA.get('mode') != 'fred_synced_plus_manual_ism_capex'
if changed or mode_changed:
    DATA['generated_at'] = now
    DATA['mode']='fred_synced_plus_manual_ism_capex'
    DATA['refresh_stats']={'successful_sources':successes,'attempted_sources':len(SERIES)+2,'errors':errors}
    PATH.write_text(json.dumps(DATA,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    history=json.loads(HISTORY_PATH.read_text(encoding='utf-8')) if HISTORY_PATH.exists() else []
    sig=observation_signature()
    if not history or history[-1].get('sig')!=sig:
        history.append({'date':now,'weights':regime_weights(),'tag':'公开数据与经核验的研究输入更新（规则信号拟合）','sig':sig})
        history=history[-800:]
        HISTORY_PATH.write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if not (changed or mode_changed):
    history=json.loads(HISTORY_PATH.read_text(encoding='utf-8')) if HISTORY_PATH.exists() else []
    sig=observation_signature()
    if not history or history[-1].get('sig')!=sig:
        history.append({'date':now,'weights':regime_weights(),'tag':'GitHub手动核验指标变更（规则信号拟合）','sig':sig})
        HISTORY_PATH.write_text(json.dumps(history[-800:],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Checked {successes}/{len(SERIES)+2} feeds. New macro observations={changed}; warnings={len(errors)}; snapshot={DATA.get("generated_at")}')
for e in errors: print('WARN',e)
