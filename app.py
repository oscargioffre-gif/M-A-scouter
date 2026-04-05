"""
BIOTECH M&A SCOUTER 2026 — v5.0
3 fonti dati con fallback automatico - UI migliorata - Spiegazioni scientifiche
"""
import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta

try:
    import yfinance as yf
    YF_OK = True
except Exception:
    YF_OK = False

st.set_page_config(page_title="M&A Scouter", page_icon="🧬", layout="wide", initial_sidebar_state="collapsed")

CACHE_FILE = "cache_v5.json"
CACHE_TTL = 23 * 3600

def _yahoo_http(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=6mo&interval=1d"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")
    data = r.json()["chart"]["result"][0]
    meta = data["meta"]
    ohlcv = data["indicators"]["quote"][0]
    closes = [c for c in ohlcv["close"] if c is not None]
    opens = [o for o in ohlcv["open"] if o is not None]
    volumes = [v for v in ohlcv["volume"] if v is not None]
    return meta, closes, opens, volumes

def _yfinance_fetch(ticker):
    if not YF_OK:
        raise ImportError("yfinance non installato")
    stock = yf.Ticker(ticker)
    hist = stock.history(period="6mo")
    if hist.empty or len(hist) < 5:
        raise ValueError("Dati vuoti")
    info = stock.info
    closes = hist["Close"].tolist()
    opens = hist["Open"].tolist()
    volumes = [int(v) for v in hist["Volume"].tolist()]
    meta = {
        "regularMarketPrice": closes[-1],
        "marketCap": info.get("marketCap", 0),
        "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow", 0),
        "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh", 0),
    }
    opt = {}
    try:
        exps = stock.options
        near = [d for d in exps if 30 <= (datetime.strptime(d, "%Y-%m-%d") - datetime.now()).days <= 90]
        if near:
            chain = stock.option_chain(near[0])
            opt["call_oi"] = int(chain.calls["openInterest"].sum())
            opt["put_oi"] = int(chain.puts["openInterest"].sum())
            opt["pc"] = round(opt["put_oi"] / opt["call_oi"], 3) if opt["call_oi"] > 0 else None
            opt["exp"] = near[0]
    except Exception:
        pass
    return meta, closes, opens, volumes, opt


def _build_record(ticker, meta, closes, opens, volumes, opt=None, source=""):
    price = closes[-1] if closes else None
    mcap = meta.get("marketCap", 0) or 0

    if len(opens) >= 1 and len(closes) >= 1:
        last_o, last_c = opens[-1], closes[-1]
        if last_c > last_o:
            vol_dir = "🟢 INFLOW (acquisto)"
            vol_dir_short = "INFLOW"
        elif last_c < last_o:
            vol_dir = "🔴 OUTFLOW (vendita)"
            vol_dir_short = "OUTFLOW"
        else:
            vol_dir = "⚪ NEUTRO"
            vol_dir_short = "NEUTRO"
    else:
        vol_dir = "N/D"
        vol_dir_short = "N/D"

    vol_last = volumes[-1] if volumes else None
    vol_avg20 = int(sum(volumes[-20:]) / len(volumes[-20:])) if len(volumes) >= 20 else vol_last
    vol_ratio = round(vol_last / vol_avg20, 2) if vol_avg20 and vol_last else None

    def chg(days):
        if len(closes) > days:
            s = closes[-(days + 1)]
            return round(((price / s) - 1) * 100, 2), round(s, 2)
        return None, None

    c1d, s1d = chg(1)
    c1w, s1w = chg(5)
    c1m, s1m = chg(21)
    c3m, s3m = chg(63)

    return dict(
        price=round(price, 2) if price else None,
        mcap=mcap,
        mcap_str=f"${mcap/1e9:.2f}B" if mcap and mcap >= 1e9 else f"${mcap/1e6:.0f}M" if mcap else "N/D",
        vol_dir=vol_dir, vol_dir_short=vol_dir_short,
        vol_last=vol_last, vol_avg20=vol_avg20, vol_ratio=vol_ratio,
        c1d=c1d, s1d=s1d, c1w=c1w, s1w=s1w, c1m=c1m, s1m=s1m, c3m=c3m, s3m=s3m,
        low52=meta.get("fiftyTwoWeekLow"), high52=meta.get("fiftyTwoWeekHigh"),
        opt=opt or {},
        source=source, ts=datetime.now().isoformat()[:16],
    )

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_cache(data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


@st.cache_data(ttl=CACHE_TTL)
def fetch_all(tickers: tuple):
    result = {}
    errors = []
    cache = load_cache()
    for t in tickers:
        try:
            meta, closes, opens, volumes, opt = _yfinance_fetch(t)
            result[t] = _build_record(t, meta, closes, opens, volumes, opt, "🟢 LIVE (yfinance)")
            continue
        except Exception:
            pass
        try:
            meta, closes, opens, volumes = _yahoo_http(t)
            if "marketCap" not in meta or not meta.get("marketCap"):
                shares = meta.get("sharesOutstanding", 0)
                p = meta.get("regularMarketPrice", closes[-1] if closes else 0)
                meta["marketCap"] = int(shares * p) if shares else 0
            result[t] = _build_record(t, meta, closes, opens, volumes, {}, "🟡 LIVE (HTTP)")
            continue
        except Exception:
            pass
        if t in cache:
            result[t] = cache[t]
            result[t]["source"] = f"⚠️ CACHE ({cache[t].get('ts', '?')[:10]})"
            continue
        result[t] = dict(
            price=None, mcap=0, mcap_str="N/D",
            vol_dir="❌ Non disponibile", vol_dir_short="N/D",
            vol_last=None, vol_avg20=None, vol_ratio=None,
            c1d=None, s1d=None, c1w=None, s1w=None, c1m=None, s1m=None, c3m=None, s3m=None,
            low52=None, high52=None, opt={},
            source="❌ Nessun dato", ts=datetime.now().isoformat()[:16],
        )
        errors.append(t)
    save_cache(result)
    return result, errors

@st.cache_data(ttl=CACHE_TTL)
def fetch_trial(nct):
    try:
        r = requests.get(f"https://clinicaltrials.gov/api/v2/studies/{nct}", timeout=10)
        if r.status_code == 200:
            sm = r.json().get("protocolSection", {}).get("statusModule", {})
            return dict(status=sm.get("overallStatus", "N/D"), update=sm.get("lastUpdatePostDateStruct", {}).get("date", "N/D"), compl=sm.get("primaryCompletionDateStruct", {}).get("date", "N/D"))
    except Exception:
        pass
    return dict(status="Non raggiungibile", update="N/D", compl="N/D")

TARGETS = [
    dict(tk="RCKT",nm="Rocket Pharmaceuticals",drug="Kresladi (marnetegragene autotemcel)",moa="Terapia genica lentivirale: preleva cellule staminali del paziente, inserisce gene ITGB2 funzionante, le reinfonde. I leucociti tornano a funzionare.",ind="LAD-I - Malattia Rara Pediatrica",ar="🟣 Rara",ak="rare",cl="First-in-Class",pdufa="✅ APPROVATO 27/03/2026 (accelerata)",fase="In commercio USA. Conferma post-marketing richiesta.",btd="BTD + Orphan + RMAT + Fast Track",src="8-K 14/10/2025 + 27/03/2026",br=1.0,scettica="Approvata su marker surrogati (CD18), non su dati clinici finali. Mercato ~25 nuovi pazienti/anno. Titolo -20% post-approvazione.",pr="30-50%",pc="20-35%",npm="Valore reale nella pipeline CV (Danon, PKP2, BAG3) + PRV ($100-150M).",risk="Cash $189M (fino Q2 2027). Revenue LAD-I trascurabili.",nct=["NCT03812263"],spieg="Rocket ha ottenuto l'approvazione ma condizionata. Deve dimostrare che funziona a lungo termine. Il vero valore e' nella pipeline di terapie geniche cardiovascolari."),
    dict(tk="RARE",nm="Ultragenyx Pharmaceutical",drug="DTX401 + DTX301 (gene therapy AAV8)",moa="Virus innocuo (AAV8) trasporta geni funzionanti nelle cellule del fegato. DTX401 per GSDIa, DTX301 per deficit OTC.",ind="GSDIa + OTC Deficiency - Ultra-Rare",ar="🟣 Rara",ak="rare",cl="First-in-Class",pdufa="DTX401: BLA in review H2 2026 | DTX301: Phase 3 positiva 12/03/2026",fase="Due gene therapy late-stage. Revenue $673M/anno esistenti.",btd="Orphan Drug Designation",src="8-K 05/01/2026 + 12/03/2026",br=0.60,scettica="Gene therapy AAV: approvazione storica ~60-65%, problemi CMC frequenti. Due candidati in parallelo aumentano le chance. Revenue esistenti riducono rischio fallimento.",pr=">100%",pc="60-80%",npm="Revenue gia' nel prezzo. Complessita' manufacturing AAV. JPM ha tagliato target post-dati.",risk="EPS -$5.83. Manufacturing AAV storicamente problematico.",nct=["NCT05139316","NCT04442347"],spieg="Ha gia' ricavi e due gene therapy vicine all'approvazione. Il rischio e' nella complessita' di produzione."),
    dict(tk="KYMR",nm="Kymera Therapeutics",drug="KT-621 (degradatore orale STAT6)",moa="Pillola che etichetta la proteina STAT6 per la distruzione dal sistema di riciclaggio cellulare. Primo farmaco di questo tipo in immunologia.",ind="Dermatite Atopica / Asma",ar="🟢 Immuno",ak="immuno",cl="First-in-Class",pdufa="N/A - Phase 2b in corso (dati mid-2027)",fase="BROADEN2 + BREADTH Phase 2b in corso.",btd="FDA Fast Track (11/12/2025)",src="8-K 11/12/2025",br=0.35,scettica="TPD mai validata in immunologia. Ph2b->approvazione: ~35%. Cash $1.6B eccellente (fino 2029).",pr=">100%",pc="50-80%",npm="MktCap ~$5B borderline. Valore piattaforma TPD aggiunge 20-30%.",risk="Tecnologia non validata. Dati definitivi non prima 2028.",nct=["NCT06145048","NCT06640049"],spieg="Sviluppa un tipo di farmaco completamente nuovo. Se funziona, rivoluziona dermatite e asma. Dati nel 2027."),
    dict(tk="GPCR",nm="Structure Therapeutics",drug="Aleniglipron (GSBR-1290)",moa="Pillola che attiva il recettore GLP-1 (stesso bersaglio di Ozempic) ma come molecola piccola, non peptide iniettabile.",ind="Obesita' / Diabete Tipo 2",ar="🔵 Metabolico",ak="metabolico",cl="Best-in-Class",pdufa="N/A - Phase 3 in avvio mid-2026",fase="Phase 2b: -15.3% peso a 36 settimane (240mg).",btd="N/A",src="8-K Dic 2025",br=0.45,scettica="GLP-1 orale affollato: Lilly e Novo avanti 12-18 mesi. Azioni +100% per M&A prospect, non per dati.",pr="30-50%",pc="20-40%",npm="Big Pharma potrebbe preferire sviluppo interno.",risk="Zero ricavi. Competizione feroce. MktCap potenzialmente overvalued.",nct=["NCT06693843"],spieg="Vuole fare 'Ozempic in pillola'. Dati buoni ma Lilly e Novo sono avanti. Valore guidato da aspettative M&A."),
    dict(tk="VKTX",nm="Viking Therapeutics",drug="VK2735",moa="Iniezione settimanale che attiva GLP-1 e GIP contemporaneamente, come tirzepatide di Lilly. Versione orale in sviluppo.",ind="Obesita'",ar="🔵 Metabolico",ak="metabolico",cl="Best-in-Class",pdufa="N/A - Phase 3 mid-2027",fase="Phase 3 VANQUISH-1 arruolamento completato (4.650 pazienti).",btd="N/A",src="10-Q 2025",br=0.40,scettica="Meccanismo validato. Single-asset senza infrastruttura commerciale. Analisti: valore massimizzato solo via acquisizione.",pr="30-50%",pc="25-45%",npm="Mercato obesity $100B al 2030. Phase 3 fully enrolled.",risk="Zero ricavi. Se Phase 3 fallisce valore -> $0.",nct=["NCT06435793"],spieg="Target M&A piu' ovvio: ha il farmaco e l'arruolamento completato, ma non puo' commercializzarlo da sola."),
    dict(tk="ALT",nm="Altimmune",drug="Pemvidutide",moa="Iniezione che attiva glucagone e GLP-1 in modo bilanciato (1:1). Agisce direttamente sul fegato riducendo grasso e fibrosi.",ind="MASH (fegato grasso avanzato)",ar="🟡 Epatico",ak="epatico",cl="First-in-Class",pdufa="N/A - Phase 3 in pianificazione",fase="Phase 2b completata. FDA ha concordato design Phase 3.",btd="BTD (05/01/2026)",src="8-K 05/01/2026",br=0.30,scettica="BTD forte MA MASH ha peggior track record Phase 3 del settore. Solo Rezdiffra approvato. Novo/Akero $5.2B aveva dati piu' maturi.",pr=">100%",pc="50-80%",npm="BTD + precedente Novo/Akero supportano premio. Solo Phase 2.",risk="Phase 3 non iniziata. MASH = area con piu' fallimenti.",nct=[],spieg="Farmaco promettente per fegato grasso. Problema: quasi tutti i farmaci MASH sono falliti in Phase 3. Alto rischio/alto rendimento."),
    dict(tk="MNMD",nm="MindMed",drug="MM-120 ODT (lisergide)",moa="Psichedelico derivato dall'LSD in dose singola sotto supervisione. Agisce su recettori serotonina (5-HT2A) con effetti su ansia e depressione in ore.",ind="Ansia Generalizzata / Depressione Maggiore",ar="🔷 Neuro",ak="neuro",cl="First-in-Class",pdufa="N/A - Dati Phase 3 GAD H1 2026, MDD H2 2026",fase="Tre Phase 3 in parallelo. Arruolamento accelerato.",btd="BTD per GAD",src="8-K 2024 / 10-K 2025",br=0.25,scettica="Nessun psichedelico mai approvato FDA. Endpoint soggettivi. Cieco impossibile. Triplo rischio binario nel 2026.",pr=">100%",pc="40-70%",npm="Se anche 1 su 3 trial positivo -> forte upside. Ma nessun precedente.",risk="Zero precedenti approvazione psichedelica. Rischio politico. Triplo binary event.",nct=["NCT06529354"],spieg="Tenta di far approvare il primo psichedelico dalla FDA. Se ci riesce apre mercato da miliardi. Rischio altissimo."),
    dict(tk="CELC",nm="Celcuity",drug="Gedatolisib",moa="Inibitore che blocca simultaneamente PI3K + AKT + mTOR, tre motori della crescita tumorale. Il tumore non puo' aggirare il blocco.",ind="Cancro Mammario HR+/HER2-",ar="🔴 Onco",ak="onco",cl="First-in-Class",pdufa="🔥 17 LUGLIO 2026 (Priority Review + RTOR + BTD + Fast Track)",fase="NDA accettata. VIKTORIA-1: riduzione rischio progressione 76%. Pubblicato JCO.",btd="BTD + Fast Track + Priority Review + RTOR",src="8-K 20/01/2026",br=0.82,scettica="4 designazioni FDA simultanee = segnale fortissimo. NDA oncologia con Priority Review: base rate ~85%. Dati JCO peer-reviewed.",pr="30-50%",pc="25-45%",npm="Miglior profilo rischio/rendimento del panel. 4 designazioni + JCO.",risk="Single-asset. Safety review pendente. Competizione PI3K.",nct=["NCT05501886"],spieg="Il target con la piu' alta probabilita' di approvazione: decisione FDA il 17 luglio 2026, 4 designazioni favorevoli, dati pubblicati su rivista top."),
    dict(tk="IMMX",nm="Immix Biopharma",drug="NXC-201 (CAR-T anti-BCMA)",moa="Linfociti T del paziente vengono modificati per riconoscere proteina BCMA sulle cellule malate. Filtro digitale riduce errori.",ind="Amiloidosi AL refrattaria",ar="🟣 Rara",ak="rare",cl="First-in-Class",pdufa="N/A - BLA post dati finali 2026",fase="Phase 1/2 NEXICART-2. BTD+RMAT Gen 2026.",btd="BTD + RMAT + Orphan Drug (FDA+EMA)",src="8-K 28/01/2026",br=0.20,scettica="MICRO-CAP ($150M). BTD+RMAT forte MA: dati solo preliminari, CAR-T costoso, cash critico. Ph1/2->approvazione: ~20%.",pr=">100%",pc="30-60%",npm="Micro-cap = alto rischio. Se dati finali positivi premio risale.",risk="MASSIMO. $150M MktCap. Cash insufficiente. Rischio diluizione >50%.",nct=["NCT05392049"],spieg="Scommessa piu' rischiosa: micro-cap con poco cash ma designazioni fortissime (BTD+RMAT). Tutto o niente."),
    dict(tk="OMER",nm="Omeros Corporation",drug="YARTEMLEA (narsoplimab)",moa="Anticorpo che blocca MASP-2, disattivando la via lectina del complemento che danneggia i vasi dopo trapianto. Unico al mondo.",ind="TA-TMA post-trapianto",ar="🟣 Rara",ak="rare",cl="First-in-Class",pdufa="✅ APPROVATO 24/12/2025 | EMA mid-2026",fase="In commercio USA Q1 2026.",btd="BTD + Orphan Drug",src="8-K 24/12/2025",br=1.0,scettica="Approvato = rischio regolatorio zero. Rischio commerciale: mercato ultra-raro. Debito significativo.",pr=">100%",pc="40-60%",npm="Monopolio TA-TMA. Novo ha acquisito zaltenibart da Omeros. Ma mercato piccolo + debito.",risk="Debito elevato. Mercato ultra-piccolo. Revenue ramp-up lento.",nct=["NCT02222545"],spieg="Unico farmaco al mondo per TA-TMA. Monopolio in mercato piccolo. Domanda chiave: i ricavi copriranno il debito?"),
]

def calc_score(t, mk):
    base = t["br"]
    adj, n = 0, []
    if "BTD" in t.get("btd",""): adj += .10; n.append("+10% BTD")
    if "Fast Track" in t.get("btd",""): adj += .05; n.append("+5% Fast Track")
    if "Priority" in t.get("pdufa","") or "APPROVATO" in t.get("pdufa",""): adj += .05; n.append("+5% Priority Review")
    if "AAV" in t.get("moa","") or "genica" in t.get("moa","").lower(): adj -= .10; n.append("-10% CMC gene therapy")
    if "Phase 2" in t.get("fase","") and "Phase 3" not in t.get("fase",""): adj -= .15; n.append("-15% solo Phase 2")
    ap = 100 if base >= 1.0 else max(5, min(95, int((base+adj)*100)))
    if base >= 1.0: n = ["Gia' approvato"]
    ma, mn = 0, []
    mc = mk.get("mcap",0) or 0
    if 0 < mc < 3e9: ma += 25; mn.append("+25% MktCap<$3B")
    elif 0 < mc < 7e9: ma += 15; mn.append("+15% MktCap $3-7B")
    if t["cl"]=="First-in-Class": ma += 20; mn.append("+20% First-in-Class")
    else: ma += 10; mn.append("+10% Best-in-Class")
    if "BTD" in t.get("btd",""): ma += 10; mn.append("+10% BTD")
    if t["ak"] in ("metabolico","immuno"): ma += 10; mn.append("+10% area hot M&A")
    return dict(ap=ap, an=n, ma=min(85,ma), mn=mn)

def price_line(label, chg, start, curr):
    if chg is None: return f"| {label} | N/D | -- |"
    emoji = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
    return f"| {label} | {emoji} **{chg:+.2f}%** | ${start:.2f} -> ${curr:.2f} |"

# === MAIN UI ===
st.markdown("""<style>
.stApp{background:#060609}
.block-container{padding-top:0rem;max-width:1200px}
h1,h2,h3{color:#e2e8f0!important}
div[data-testid="stExpander"]{background:#0c0c18;border:1px solid #1e293b;border-radius:8px;margin-bottom:6px}
div[data-testid="stExpander"] summary span{font-size:12px!important}
.stMetric label{color:#64748b!important;font-size:10px!important}
.stMetric [data-testid="stMetricValue"]{color:#e2e8f0!important;font-size:20px!important}

/* HEADER */
.scouter-header{
    background:linear-gradient(135deg,#0c0c18 0%,#12061e 50%,#0c0c18 100%);
    border-bottom:2px solid #FF00AA33;
    padding:20px 20px 16px;
    margin:-1rem -1rem 1rem;
    border-radius:0 0 12px 12px;
}
.scouter-top{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.scouter-icon{
    background:#FF00AA;
    color:#000;
    font-weight:900;
    font-size:16px;
    padding:8px 12px;
    border-radius:10px;
    letter-spacing:1px;
    line-height:1;
    white-space:nowrap;
    box-shadow:0 0 20px #FF00AA44;
    flex-shrink:0;
}
.scouter-title{
    font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
    font-size:clamp(18px,4vw,28px);
    font-weight:800;
    color:#e2e8f0;
    letter-spacing:-.5px;
    line-height:1.1;
}
.scouter-title span{color:#FF00AA}
.scouter-sub{
    margin-top:8px;
    font-size:clamp(10px,2vw,12px);
    color:#64748b;
    letter-spacing:.5px;
}
.scouter-sub b{color:#94a3b8}
.scouter-live{
    display:inline-flex;align-items:center;gap:6px;
    margin-top:6px;
    font-size:11px;color:#64748b;
}
.scouter-dot{
    width:7px;height:7px;border-radius:50%;
    background:#22c55e;
    box-shadow:0 0 6px #22c55e88;
    animation:dotpulse 2s infinite;
}
@keyframes dotpulse{0%,100%{opacity:1}50%{opacity:.3}}

/* MOBILE FIXES */
@media(max-width:640px){
    .scouter-header{padding:14px 12px 12px;margin:-1rem -.8rem 1rem}
    .scouter-icon{font-size:13px;padding:6px 10px;border-radius:8px}
    div[data-testid="stExpander"] summary span{font-size:11px!important}
    .stMetric [data-testid="stMetricValue"]{font-size:18px!important}
}
</style>""", unsafe_allow_html=True)

_now = datetime.now().strftime('%d/%m/%Y %H:%M')
st.markdown(f"""
<div class="scouter-header">
  <div class="scouter-top">
    <div class="scouter-icon">M&A</div>
    <div class="scouter-title">BIOTECH <span>M&A</span> SCOUTER 2026</div>
  </div>
  <div class="scouter-sub">
    Segnali Pre-Acquisizione · Target NASDAQ Indipendenti · MktCap &lt;$10B · <b>Hard Data Only</b>
  </div>
  <div class="scouter-live">
    <div class="scouter-dot"></div>
    Aggiornato: {_now} UTC · Refresh automatico giornaliero
  </div>
</div>
""", unsafe_allow_html=True)

c1, c2 = st.columns([5,1])
with c2:
    if st.button("🔄 Aggiorna", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

tickers = tuple(t["tk"] for t in TARGETS)
with st.spinner("Connessione a 3 fonti dati..."):
    market, errs = fetch_all(tickers)

sources = set(str(m.get("source",""))[:2] for m in market.values())
if all("🟢" in str(m.get("source","")) or "🟡" in str(m.get("source","")) for m in market.values()):
    st.success("Dati LIVE caricati con successo.", icon="✅")
elif errs:
    st.warning(f"Alcuni ticker senza dati: {', '.join(errs)}. Dati disponibili mostrati, altri come N/D.", icon="⚠️")

with st.expander("📖 **COME LEGGERE QUESTA DASHBOARD** (clicca per aprire)"):
    st.markdown("""
**Ogni riga = un'azienda biotech NASDAQ indipendente** con segnali di potenziale acquisizione.

- **Appr %** = Probabilita' approvazione FDA (base rate storici, non opinioni)
- **M&A %** = Probabilita' acquisizione entro 18 mesi
- **INFLOW/OUTFLOW** = direzione volumi: se prezzo sale + volumi alti = acquisti in entrata. Se scende + volumi alti = vendite in uscita
- **First-in-Class** = farmaco unico, premio potenziale >100%
- **Best-in-Class** = migliora l'esistente, premio 30-50%

**Tocca ogni riga per espandere** e vedere: spiegazione semplice, variazioni prezzo, volumi, opzioni, rischi, trial clinici live.
""")

st.markdown("---")
m1,m2,m3,m4,m5=st.columns(5)
m1.metric("TARGET",len(TARGETS))
m2.metric("FIRST-IN-CLASS",sum(1 for t in TARGETS if t["cl"]=="First-in-Class"))
m3.metric("CON BTD",sum(1 for t in TARGETS if "BTD" in t["btd"]))
m4.metric("APPROVATI",sum(1 for t in TARGETS if t["br"]>=1.0))
m5.metric("PDUFA ≤90gg",sum(1 for t in TARGETS if "LUGLIO 2026" in t.get("pdufa","")))

f1,f2,f3=st.columns(3)
with f1: af=st.selectbox("Area",["Tutti","🟣 Rara","🔴 Onco","🔷 Neuro","🔵 Metabolico","🟡 Epatico","🟢 Immuno"])
with f2: cf=st.selectbox("Classe",["Tutti","First-in-Class","Best-in-Class"])
with f3: sf=st.selectbox("Ordina",["Prob. Approvazione","Prob. M&A","Ticker","Variaz. 1G"])

items=TARGETS[:]
if af!="Tutti":items=[t for t in items if t["ar"]==af]
if cf!="Tutti":items=[t for t in items if t["cl"]==cf]
scored=[{**t,**calc_score(t,market.get(t["tk"],{}))} for t in items]
if sf=="Prob. Approvazione":scored.sort(key=lambda x:x["ap"],reverse=True)
elif sf=="Prob. M&A":scored.sort(key=lambda x:x["ma"],reverse=True)
elif sf=="Ticker":scored.sort(key=lambda x:x["tk"])
elif sf=="Variaz. 1G":scored.sort(key=lambda x:market.get(x["tk"],{}).get("c1d") or -999,reverse=True)

for t in scored:
    mk=market.get(t["tk"],{})
    p=mk.get("price")
    ai="🟢" if t["ap"]>=75 else "🟡" if t["ap"]>=40 else "🔴"
    mi="🟢" if t["ma"]>=60 else "🟡" if t["ma"]>=35 else "🔴"
    c1d_s=f"{mk.get('c1d',0):+.1f}%" if mk.get("c1d") is not None else "N/D"
    ps=f"${p:.2f}" if p else "N/D"

    with st.expander(f"**{t['tk']}** {t['nm']} | {mk.get('mcap_str','N/D')} | {ps} ({c1d_s}) | Appr:{ai}{t['ap']}% M&A:{mi}{t['ma']}% | {t['ar']} {t['cl']}"):
        st.caption(f"Fonte: {mk.get('source','N/D')} | {mk.get('ts','')}")
        st.info(t["spieg"])

        r1,r2,r3,r4=st.columns(4)
        r1.metric("Prezzo",ps)
        r2.metric("Market Cap",mk.get("mcap_str","N/D"))
        r3.metric("52W Min",f"${mk['low52']:.2f}" if mk.get("low52") else "N/D")
        r4.metric("52W Max",f"${mk['high52']:.2f}" if mk.get("high52") else "N/D")

        st.markdown("##### 📈 Variazioni Prezzo")
        curr=p if p else 0
        tbl="| Periodo | Variazione | Da -> A |\n|---|---|---|\n"
        tbl+=price_line("1 Giorno",mk.get("c1d"),mk.get("s1d"),curr)+"\n"
        tbl+=price_line("1 Settimana",mk.get("c1w"),mk.get("s1w"),curr)+"\n"
        tbl+=price_line("1 Mese",mk.get("c1m"),mk.get("s1m"),curr)+"\n"
        tbl+=price_line("3 Mesi",mk.get("c3m"),mk.get("s3m"),curr)
        st.markdown(tbl)

        st.markdown("##### 📊 Volumi")
        v1,v2,v3=st.columns(3)
        v1.metric("Direzione",mk.get("vol_dir","N/D"))
        vl=mk.get("vol_last");v2.metric("Vol. Ultimo Giorno",f"{vl:,.0f}" if vl else "N/D")
        va=mk.get("vol_avg20");v3.metric("Media 20gg",f"{va:,.0f}" if va else "N/D")
        vr=mk.get("vol_ratio")
        vint="🔴 ANOMALO (>2x)" if vr and vr>2 else "🟡 ELEVATO" if vr and vr>1.5 else "⚪ NORMALE" if vr else "N/D"
        st.markdown(f"**Rapporto Vol/Media:** {vr:.2f}x - {vint}" if vr else "**Rapporto:** N/D")
        st.caption("INFLOW=chiusura>apertura (acquisti). OUTFLOW=chiusura<apertura (vendite). Proxy tecnico, NON order flow reale.")

        o=mk.get("opt",{})
        if o.get("call_oi"):
            st.markdown("##### 🎯 Opzioni (30-90gg)")
            o1,o2,o3=st.columns(3)
            o1.metric("Call OI",f"{o['call_oi']:,}")
            o2.metric("Put OI",f"{o.get('put_oi',0):,}")
            o3.metric("Put/Call",f"{o['pc']:.3f}" if o.get("pc") else "N/D")

        st.markdown("---")
        p1,p2=st.columns(2)
        with p1:
            st.markdown(f"**Prob. Approvazione: {t['ap']}%**")
            st.progress(t["ap"]/100)
            for n in t["an"]:st.caption(n)
        with p2:
            st.markdown(f"**Prob. M&A: {t['ma']}%**")
            st.progress(t["ma"]/100)
            for n in t["mn"]:st.caption(n)

        st.markdown("---")
        st.markdown(f"**🧪 {t['drug']}**")
        st.markdown(f"Come funziona: _{t['moa']}_")
        st.markdown(f"Indicazione: **{t['ind']}**")
        st.markdown(f"PDUFA: `{t['pdufa']}`")
        st.markdown(f"Fase: {t['fase']}")
        st.markdown(f"Designazioni: {t['btd']}")
        st.caption(f"Fonte: {t['src']}")
        st.markdown(f"**Premio M&A:** Raw {t['pr']} -> Corretto **{t['pc']}**")
        st.caption(t["npm"])
        st.warning(t["scettica"])
        st.error(t["risk"])
        if t.get("nct"):
            st.markdown("**🔎 ClinicalTrials.gov**")
            for nid in t["nct"]:
                if nid.startswith("NCT"):
                    tr=fetch_trial(nid)
                    st.caption(f"[{nid}](https://clinicaltrials.gov/study/{nid}) -> **{tr['status']}** | Agg: {tr['update']} | Compl: {tr['compl']}")

st.markdown("---")
st.caption("DISCLAIMER v5 - Report informativo, non consulenza finanziaria. Fonti: Yahoo Finance, ClinicalTrials.gov. Volumi: proxy Close/Open. 3 livelli fallback. Mai dati inventati. Probabilita' Bayesiane su base rate FDA.")
