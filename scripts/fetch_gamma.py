#!/usr/bin/env python3
"""Daily logger: QQQ prices (Yahoo chart API), ZeroGEX main source (NQ, NDX, QQQ, SPX, SPY), GEXBoard second source (NDX, QQQ).
Never writes a guessed number: if a page cannot be read, that item is skipped and the run is marked failed."""
import csv, os, re, sys, json, urllib.request, datetime as dt
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
DATA = Path(__file__).resolve().parent.parent / 'data'
LOG, PX = DATA / 'gamma_log.csv', DATA / 'qqq_daily.csv'
HEAD = ['id','date','time_et','session','instrument','regime','net_gex','unit','gamma_flip','call_wall','put_wall','spot','source','notes']
SYMS = ['NDX', 'QQQ', 'SPX', 'SPY', 'ES', 'NQ']
problems = []

class T(HTMLParser):
    def __init__(s):
        super().__init__(); s.out = []; s.skip = 0
    def handle_starttag(s, t, a):
        if t in ('script', 'style'): s.skip += 1
    def handle_endtag(s, t):
        if t in ('script', 'style') and s.skip: s.skip -= 1
    def handle_data(s, d):
        if not s.skip and d.strip(): s.out.append(d.strip())

def clean(t): return t.replace('−', '-').replace('–', '-')
def text_of(html):
    p = T(); p.feed(html); return clean('\n'.join(p.out))
def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (personal gamma logger)'})
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')

NUM = r'\$?\s*(-?\d[\d,]*\.?\d*)'
def num(pat, txt):
    m = re.search(pat, txt, re.I)
    return float(m.group(1).replace(',', '')) if m else None
def levels(w):
    return dict(net=num(r'Net GEX[\s:|]*' + NUM + r'\s*B', w),
                flip=num(r'(?:Gamma flip|Zero gamma)[\s:|]*' + NUM, w),
                call=num(r'Call wall[\s:|]*' + NUM, w),
                put=num(r'Put wall[\s:|]*' + NUM, w),
                spot=num(r'(?:Closed at|Spot)[\s:|]*' + NUM, w))
def windows(txt, sym, size=1500):
    for m in re.finditer(r'\b' + sym + r'\b', txt):
        w = txt[m.end():m.end() + size]
        cut = [x.start() for o in SYMS if o != sym for x in [re.search(r'\b' + o + r'\b', w)] if x]
        yield w[:min(cut)] if cut else w
def full(lv): return all(lv[k] is not None for k in lv)
def regime(net): return 'Positive' if net > 0 else 'Negative' if net < 0 else 'Mixed'
def fmt(x): return ('%g' % x) if x is not None else ''

def row(date, time, session, inst, reg, net=None, flip=None, call=None, put=None, spot=None, source='', notes=''):
    return dict(date=date.isoformat(), time_et=time, session=session, instrument=inst, regime=reg,
                net_gex=fmt(net), unit='$B/1%' if net is not None else '', gamma_flip=fmt(flip), call_wall=fmt(call),
                put_wall=fmt(put), spot=fmt(spot), source=source, notes=notes)

def prices(target):
    d = json.loads(fetch('https://query1.finance.yahoo.com/v8/finance/chart/QQQ?range=10d&interval=1d'))['chart']['result'][0]
    q = d['indicators']['quote'][0]
    for i, ts in enumerate(d['timestamp']):
        if dt.datetime.fromtimestamp(ts, NY).date() == target:
            v = [q[k][i] for k in ('open', 'high', 'low', 'close', 'volume')]
            if None in v: break
            return [target.isoformat()] + ['%.2f' % x for x in v[:4]] + [str(int(v[4]))]
    return None

def gexboard(target):
    txt = text_of(fetch('https://gexboard.com/learn/nasdaq-gamma-levels'))
    m = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})\s*close', txt)
    if not m:
        problems.append('GEXBoard: page date not found'); print(txt[:2500]); return []
    page = dt.datetime.strptime(m.group(1), '%B %d, %Y').date()
    if page != target:
        print(f'NOTE: GEXBoard page is for {page}, not {target}; skipped (second source, not an error)')
        return []
    out = []
    for inst in ('NDX', 'QQQ'):
        hit = next((w for w in windows(txt, inst) if full(levels(w))), None)
        if not hit:
            problems.append(f'GEXBoard {inst}: could not read levels'); print(txt[:2500]); continue
        lv = levels(hit)
        r = re.search(r'Regime at the open\D{0,80}?(short|long|mixed)', hit, re.I)
        if r:
            out.append(row(target, '', 'Open', inst, {'short': 'Negative', 'long': 'Positive', 'mixed': 'Mixed'}[r.group(1).lower()],
                           source='GEXBoard', notes='Regime at the open per GEXBoard'))
        else:
            problems.append(f'GEXBoard {inst}: open regime not found')
        out.append(row(target, '16:00', 'Close', inst, regime(lv['net']), lv['net'], lv['flip'], lv['call'], lv['put'], lv['spot'], 'GEXBoard'))
    return out

def zblock(txt, sym):
    m = re.search(r'\n' + sym + r'\n[A-Z ]*GAMMA', txt)
    if not m: return None
    end = txt.find(sym + ' gamma levels', m.end())
    return txt[m.start():end if end > 0 else m.start() + 900]

def zlevels(b):
    def one(pat):
        m = re.search(pat, b)
        return float(m.group(1).replace(',', '')) if m else None
    n = re.search(r'Net GEX[^\n]*\n\s*(-?)\$\s*(-?[\d,]*\.?\d+)\s*B', b)
    net = None
    if n:
        net = float(n.group(2).replace(',', ''))
        if n.group(1): net = -abs(net)
    return dict(net=net,
                flip=one(r'Gamma flip\s*\n\s*([\d,]+\.?\d*)'),
                call=one(r'Call wall\s*\n\s*([\d,]+\.?\d*)'),
                put=one(r'Put wall\s*\n\s*([\d,]+\.?\d*)'),
                spot=one(r'Reference spot[^\n]*\n\s*([\d,]+\.?\d*)'))

def zerogex(target, morning=False):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.goto('https://zerogex.io/gex-levels', wait_until='networkidle', timeout=60000)
        pg.wait_for_timeout(5000)
        txt = clean(pg.inner_text('body')); b.close()
    out = []
    for inst in (('NQ', 'NDX', 'QQQ') if morning else ('NQ', 'SPX', 'SPY', 'NDX', 'QQQ')):
        blk = zblock(txt, inst)
        lv = zlevels(blk) if blk else None
        if not lv or not full(lv):
            problems.append(f'ZeroGEX {inst}: could not read levels'); continue
        a = re.search(r'As of\s+([A-Z][a-z]{2,8} \d{1,2},? \d{4}),?\s*(\d{1,2}):(\d{2})\s*([AP]M)', blk)
        if not a:
            problems.append(f'ZeroGEX {inst}: as-of date/time not found'); continue
        d = dt.datetime.strptime(a.group(1).replace(',', ''), '%b %d %Y' if len(a.group(1).split()[0]) <= 3 else '%B %d %Y').date()
        h = int(a.group(2)) % 12 + (12 if a.group(4).upper() == 'PM' else 0)
        t = f'{h:02d}:{a.group(3)}'
        note = 'Morning snapshot' if morning else 'After-close snapshot'
        if 'temporarily delayed' in blk: note += '; page marked data temporarily delayed'
        if morning:
            if d != target or t < '09:30':
                problems.append(f'ZeroGEX {inst}: no fresh morning reading (page as-of {d} {t})'); continue
            out.append(row(target, t, 'Open', inst, regime(lv['net']), lv['net'], lv['flip'], lv['call'], lv['put'], lv['spot'], 'ZeroGEX', note))
            continue
        if d != target or t < '15:59':
            problems.append(f'ZeroGEX {inst}: page is as of {d} {t}, not after the {target} close yet'); continue
        out.append(row(target, t, 'Close', inst, regime(lv['net']), lv['net'], lv['flip'], lv['call'], lv['put'], lv['spot'], 'ZeroGEX', note))
    if not out: print(txt[:2500])
    return out

def main():
    now = dt.datetime.now(NY)
    target = dt.date.fromisoformat(os.environ['TARGET_DATE']) if os.environ.get('TARGET_DATE') else now.date()
    if target.weekday() >= 5: print('weekend'); return 0
    morning = os.environ.get('MODE') == 'morning'
    if morning and not os.environ.get('FORCE') and not ('09:30' <= now.strftime('%H:%M') <= '10:30'):
        print('outside the morning window (New York time), skipping'); return 0
    log = list(csv.DictReader(open(LOG)))
    new = []
    if morning:
        try: new += zerogex(target, morning=True)
        except Exception as e: problems.append(f'zerogex failed: {e}')
    else:
        px = list(csv.reader(open(PX)))
        try: p = prices(target)
        except Exception as e: p = None; problems.append(f'price fetch failed: {e}')
        if p is None: problems.append(f'no QQQ price for {target} (holiday or not out yet)')
        elif not any(r[0] == p[0] for r in px[1:]):
            px.append(p); csv.writer(open(PX, 'w', newline='')).writerows(px)
        for fn in (gexboard, zerogex):
            try: new += fn(target)
            except Exception as e: problems.append(f'{fn.__name__} failed: {e}')
    print(f'READ {len(new)} rows from the pages for {target}:')
    for r in new: print('  ', r['instrument'], r['session'], r['regime'], r['net_gex'], r['gamma_flip'], r['source'])
    nid = max(int(r['id']) for r in log) + 1
    have = {(r['date'], r['instrument'], r['source'], r['session']) for r in log}
    for r in new:
        k = (r['date'], r['instrument'], r['source'], r['session'])
        if k in have: print('   (already in log, skipped):', k); continue
        r['id'] = nid; nid += 1; log.append(r); have.add(k)
    with open(LOG, 'w', newline='') as f:
        w = csv.DictWriter(f, HEAD); w.writeheader(); w.writerows(log)
    for x in problems: print('PROBLEM:', x)
    return 2 if problems else 0

if __name__ == '__main__': sys.exit(main())
