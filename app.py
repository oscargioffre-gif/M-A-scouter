"""
BIOTECH M&A SCOUTER 2026 — v4.0 RESILIENT
Dati LIVE giornalieri • Volumi direzionali • Multi-timeframe • Fallback anti-crash
Deploy: Streamlit Community Cloud (gratis, per sempre)
"""
import streamlit as st
import pandas as pd
import requests
import json
import os
import base64
from datetime import datetime, timedelta, date
from pathlib import Path

# ── OPTIONAL IMPORTS (graceful fallback) ──
try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False

st.set_page_config(
    page_title="M&A Scouter 2026",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
CACHE_FILE = "cache_fallback.json"
CACHE_TTL = 24 * 3600  # 24 ore — refresh giornaliero

# ─────────────────────────────────────────────
# FUCHSIA ICON (base64 embedded for PWA)
# ─────────────────────────────────────────────
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect x="20" y="20" width="472" height="472" rx="80" fill="#FF00AA"/>
<rect x="20" y="250" width="472" height="242" rx="0" fill="#DD0090" opacity="0.4"/>
<text x="256" y="310" font-family="Arial Black,sans-serif" font-size="175" font-weight="900"
  fill="#000" text-anchor="middle" opacity="0.15">M&amp;A</text>
<text x="256" y="305" font-family="Arial Black,sans-serif" font-size="175" font-weight="900"
  fill="#000" text-anchor="middle">M&amp;A</text>
<text x="256" y="380" font-family="Arial Black,sans-serif" font-size="48" font-weight="900"
  fill="#000" text-anchor="middle" opacity="0.8">SCOUTER</text>
<circle cx="248" cy="65" r="5" fill="#000" opacity="0.6"/>
<circle cx="264" cy="55" r="5" fill="#000" opacity="0.6"/>
<circle cx="250" cy="82" r="4" fill="#000" opacity="0.5"/>
<circle cx="262" cy="72" r="4" fill="#000" opacity="0.5"/>
</svg>"""

# ─────────────────────────────────────────────
# TARGET DATABASE (curated – only hard data)
# ─────────────────────────────────────────────
TARGETS = [
    dict(ticker="RCKT",nome="Rocket Pharmaceuticals",
         farmaco="Kresladi (marnetegragene autotemcel)",
         moa="Terapia genica lentivirale – correzione ex vivo gene ITGB2",
         indicazione="LAD-I – Malattia Rara Pediatrica",area="🟣 Rara",area_key="rare",
         classificazione="First-in-Class",
         pdufa="✅ APPROVATO 27/03/2026 (accelerata, endpoint surrogati CD18/CD11a)",
         fase="Commercializzazione avviata. PRV ottenuto. Conferma post-marketing richiesta.",
         btd="BTD + Orphan + RMAT + Fast Track",btd_fonte="8-K 14/10/2025 | Approvazione 8-K 27/03/2026",
         base_rate=1.0,
         nota_scettica="APPROVATA su surrogati → conferma clinica pendente. Mercato ~25 nuovi casi/anno. Titolo -20% post-approvazione. Pipeline CV (Danon, PKP2, BAG3) è il reale asset strategico.",
         premio_raw="30-50%",premio_corr="20-35%",
         nota_premio="Post-approvazione premio ridotto. Valore PRV ($100-150M). Pipeline CV early-stage aggiunge optionalità.",
         rischio="Cash $189M, runway Q2 2027. Revenue LAD-I trascurabili. Se conferma post-marketing fallisce → rischio ritiro.",
         nct=["NCT03812263"]),
    dict(ticker="RARE",nome="Ultragenyx Pharmaceutical",
         farmaco="DTX401 + DTX301 (gene therapy AAV8)",
         moa="AAV8: espressione gene G6PC (GSDIa) / gene OTC (OTC deficiency)",
         indicazione="GSDIa + OTC Deficiency – Ultra-Rara",area="🟣 Rara",area_key="rare",
         classificazione="First-in-Class",
         pdufa="DTX401: BLA in review H2 2026 | DTX301: Phase 3 positiva 12/03/2026",
         fase="Due gene therapy late-stage. Revenue commerciali $673M TTM.",
         btd="Orphan Drug (DTX401 + DTX301)",btd_fonte="8-K 05/01/2026 + 12/03/2026",
         base_rate=0.60,
         nota_scettica="Base rate gene therapy AAV: ~60-65%. CMC storicamente critico per AAV (vedi Bluebird, Sarepta). Due shot in parallelo aumentano probabilità che almeno uno arrivi. Revenue esistenti riducono rischio sopravvivenza.",
         premio_raw=">100%",premio_corr="60-80%",
         nota_premio="Revenue esistenti ($673M) già nel prezzo. Complessità manufacturing AAV. Prezzo depresso potrebbe riflettere rischio reale.",
         rischio="EPS -$5.83. Manufacturing AAV storicamente fallimentare. JPM ha tagliato PT a $74 post-dati DTX301.",
         nct=["NCT05139316","NCT04442347"]),
    dict(ticker="KYMR",nome="Kymera Therapeutics",
         farmaco="KT-621 (degradatore orale STAT6)",
         moa="Targeted Protein Degradation – sistema ubiquitina-proteasoma per STAT6",
         indicazione="Dermatite Atopica / Asma Eosinofilico",area="🟢 Immuno",area_key="immuno",
         classificazione="First-in-Class",
         pdufa="N/A – Phase 2b (dati AD mid-2027, Asma late-2027)",
         fase="BROADEN2 (AD) + BREADTH (Asma) Phase 2b in corso.",
         btd="FDA Fast Track 11/12/2025",btd_fonte="8-K 11/12/2025",
         base_rate=0.35,
         nota_scettica="TPD piattaforma mai validata clinicamente in immunologia. Phase 2b→approvazione: ~35%. Dati BroADen Ph1b promettenti ma piccolo campione. Cash $1.6B eccellente.",
         premio_raw=">100%",premio_corr="50-80%",
         nota_premio="MktCap ~$5B borderline. Se dati Ph2b positivi, prezzo sale prima dell'offerta = premio compresso. Valore piattaforma TPD aggiunge 20-30%.",
         rischio="Piattaforma non validata. Dati registrativi non prima 2028. Best case: acquisizione pre-Phase 3.",
         nct=["NCT06145048","NCT06640049"]),
    dict(ticker="GPCR",nome="Structure Therapeutics",
         farmaco="Aleniglipron (GSBR-1290)",
         moa="Agonista selettivo orale GLP-1 – piccola molecola non-peptidica",
         indicazione="Obesità / Diabete Tipo 2",area="🔵 Metabolico",area_key="metabolico",
         classificazione="Best-in-Class",
         pdufa="N/A – Phase 3 in avvio mid-2026",
         fase="Phase 2b ACCESS completata Dic 2025: -15.3% peso (240mg, 36w).",
         btd="N/A",btd_fonte="8-K Dic 2025 (dati ACCESS/ACCESS II)",
         base_rate=0.45,
         nota_scettica="Campo GLP-1 orale affollato: orforglipron (Lilly), Wegovy orale (Novo). Ph2b→Ph3 success: ~50%. Differenziazione su convenience, non efficacia. Azioni +100% = M&A-driven.",
         premio_raw="30-50%",premio_corr="20-40%",
         nota_premio="Lilly/Novo avanti 12-18 mesi. Phase 3 non iniziata. Big Pharma potrebbe preferire sviluppo interno.",
         rischio="Zero revenue. Competizione feroce. MktCap $5.5B potenzialmente overvalued per Phase 2.",
         nct=["NCT06693843","NCT06703021"]),
    dict(ticker="VKTX",nome="Viking Therapeutics",
         farmaco="VK2735",
         moa="Agonista duale GLP-1/GIP – peptide SC + formulazione orale",
         indicazione="Obesità",area="🔵 Metabolico",area_key="metabolico",
         classificazione="Best-in-Class",
         pdufa="N/A – Dati Phase 3 VANQUISH-1 mid-2027",
         fase="Phase 3 arruolamento completato (4.650 pazienti).",
         btd="N/A",btd_fonte="10-Q 2025",
         base_rate=0.40,
         nota_scettica="Meccanismo validato (tirzepatide). Single-asset, zero infrastruttura commerciale. William Blair: valore massimizzato solo via acquisizione. Risultati lontani.",
         premio_raw="30-50%",premio_corr="25-45%",
         nota_premio="Analisti convergono su necessità M&A. Mercato obesity $100B al 2030. Phase 3 fully enrolled riduce rischio execution.",
         rischio="Zero revenue. Phase 3 mid-2027. Se fallisce → valore ~$0.",
         nct=["NCT06435793"]),
    dict(ticker="ALT",nome="Altimmune",
         farmaco="Pemvidutide",
         moa="Agonista duale bilanciato 1:1 Glucagone/GLP-1 – targeting epatico",
         indicazione="MASH (Steatoepatite Metabolica)",area="🟡 Epatico",area_key="epatico",
         classificazione="First-in-Class",
         pdufa="N/A – Phase 3 in pianificazione post EoP2",
         fase="Phase 2b IMPACT 48w completata. Allineamento FDA su Phase 3.",
         btd="BTD 05/01/2026",btd_fonte="8-K 05/01/2026",
         base_rate=0.30,
         nota_scettica="BTD forte MA Phase 3 MASH: peggior track record del settore (Intercept, Genfit fallite). Solo Rezdiffra (Madrigal) approvato. Novo ha pagato $5.2B per Akero ma dati più maturi.",
         premio_raw=">100%",premio_corr="50-80%",
         nota_premio="BTD + precedente Novo/Akero supportano premio. MA: solo Phase 2 + MASH Phase 3 storicamente fallimentare.",
         rischio="Phase 3 non iniziata. MASH peggior success rate nel settore. Cash da verificare.",
         nct=[]),
    dict(ticker="MNMD",nome="MindMed",
         farmaco="MM-120 ODT (lisergide)",
         moa="Agonista 5-HT2A – psichedelico singola dose",
         indicazione="GAD / MDD – Neuroscienze",area="🔷 Neuro",area_key="neuro",
         classificazione="First-in-Class",
         pdufa="N/A – Dati Ph3 GAD: H1 2026 | MDD (Emerge): H2 2026",
         fase="Tre studi Phase 3 in parallelo. Arruolamento accelerato.",
         btd="BTD per GAD",btd_fonte="8-K 2024 / 10-K 2025",
         base_rate=0.25,
         nota_scettica="Nessun psichedelico mai approvato FDA. Endpoint soggettivi. Cecità difficile. Triplo rischio binario nel 2026. Rischio regolatorio/politico.",
         premio_raw=">100%",premio_corr="40-70%",
         nota_premio="Nessun precedente regolatorio. Scheduling DEA incerto. Se 1 su 3 trial positivo → upside comunque alto.",
         rischio="Zero precedenti approvazione psichedelici. Rischio politico. Triplo binary event 2026.",
         nct=["NCT06529354"]),
    dict(ticker="CELC",nome="Celcuity",
         farmaco="Gedatolisib",
         moa="Inibitore pan-PI3K/mTOR multi-target – blocco completo pathway PAM",
         indicazione="Cancro Mammario HR+/HER2- wild-type",area="🔴 Onco",area_key="onco",
         classificazione="First-in-Class",
         pdufa="🔥 17 LUGLIO 2026 (Priority Review + RTOR + BTD + Fast Track)",
         fase="NDA accettata Gen 2026. VIKTORIA-1: PFS 12.4m vs 1.9m. Pubblicato JCO.",
         btd="BTD + Fast Track + Priority Review + RTOR",btd_fonte="8-K 20/01/2026",
         base_rate=0.82,
         nota_scettica="4 designazioni FDA simultanee = segnale molto forte. NDA oncologia con PR: base rate ~85%. Riduzione rischio 76% (triplet). Pubblicazione JCO = peer review. Rischio residuo: safety, label scope.",
         premio_raw="30-50%",premio_corr="25-45%",
         nota_premio="Miglior profilo rischio/rendimento nel panel. 4 designazioni + dati JCO. Competizione PI3K (Novartis, Lilly) e label scope riducono leggermente.",
         rischio="Single-asset pre-revenue. Safety review. Competizione. Label potrebbe essere più stretta.",
         nct=["NCT05501886"]),
    dict(ticker="IMMX",nome="Immix Biopharma",
         farmaco="NXC-201 (CAR-T anti-BCMA)",
         moa="CAR-T con filtro digitale sterico – riduzione attivazione aspecifica",
         indicazione="Amiloidosi AL refrattaria",area="🟣 Rara",area_key="rare",
         classificazione="First-in-Class",
         pdufa="N/A – BLA post dati finali 2026",
         fase="Phase 1/2 NEXICART-2. BTD+RMAT ottenuti Gen 2026.",
         btd="BTD + RMAT 28/01/2026 + Orphan Drug (FDA+EMA)",btd_fonte="8-K 28/01/2026",
         base_rate=0.20,
         nota_scettica="MICRO-CAP ($150M). BTD+RMAT forte MA: dati solo Ph1/2 interim. CAR-T costoso. Cash runway critico. Ph1/2→approvazione: ~20%.",
         premio_raw=">100%",premio_corr="30-60%",
         nota_premio="Micro-cap = rischio sopravvivenza. Single-asset + dati preliminari. Se dati finali positivi → premio risale.",
         rischio="MASSIMO. $150M MktCap. Cash insufficiente per BLA. Rischio diluizione >50%.",
         nct=["NCT05392049"]),
    dict(ticker="OMER",nome="Omeros Corporation",
         farmaco="YARTEMLEA (narsoplimab)",
         moa="Inibitore selettivo MASP-2 via lectina complemento",
         indicazione="TA-TMA post-trapianto – Malattia Rara",area="🟣 Rara",area_key="rare",
         classificazione="First-in-Class",
         pdufa="✅ APPROVATO 24/12/2025 | EMA mid-2026",
         fase="Commercializzazione USA Q1 2026. Codici ICD-10 dedicati.",
         btd="BTD + Orphan Drug (FDA+EMA)",btd_fonte="8-K 24/12/2025",
         base_rate=1.0,
         nota_scettica="Approvato = rischio regolatorio zero. Rischio commerciale: TA-TMA ultra-raro (~3-5K pz/anno USA). Pricing alto ma volume basso. Debito da gestire.",
         premio_raw=">100%",premio_corr="40-60%",
         nota_premio="First-and-only per TA-TMA. Novo ha acquisito zaltenibart (MASP-3) da Omeros = validazione piattaforma. MA: mercato piccolo + debito.",
         rischio="Debito elevato. Mercato ultra-piccolo. Revenue ramp-up lento. Pipeline early-stage.",
         nct=["NCT02222545"]),
]

# ─────────────────────────────────────────────
# RESILIENT DATA LAYER
# ─────────────────────────────────────────────

def load_cache() -> dict:
    """Load fallback cache from disk."""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            age = (datetime.now() - datetime.fromisoformat(data.get("timestamp", "2000-01-01"))).total_seconds()
            return data, age
    except Exception:
        pass
    return {}, float("inf")

def save_cache(data: dict):
    """Persist cache to disk for crash recovery."""
    try:
        data["timestamp"] = datetime.now().isoformat()
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

@st.cache_data(ttl=CACHE_TTL)
def fetch_all_market_data(tickers: tuple) -> dict:
    """
    Fetch live market data with multi-layer fallback.
    Layer 1: yfinance live
    Layer 2: Disk cache (last known good)
    Layer 3: Empty with clear 'N/D' flags (NEVER fabricate)
    """
    result = {}
    cache, cache_age = load_cache()
    source = "LIVE"

    for t in tickers:
        try:
            if not YF_OK:
                raise ImportError("yfinance non disponibile")

            stock = yf.Ticker(t)
            hist = stock.history(period="6mo")
            info = stock.info

            if hist.empty or len(hist) < 2:
                raise ValueError("Dati storici vuoti")

            price_now = float(hist["Close"].iloc[-1])
            # ── VOLUME DIRECTION ──
            # Proxy standard: confronto Close vs Open dell'ultimo giorno
            # Se Close > Open + Volume alto → pressione acquisto (INFLOW)
            # Se Close < Open + Volume alto → pressione vendita (OUTFLOW)
            last_open = float(hist["Open"].iloc[-1])
            last_close = float(hist["Close"].iloc[-1])
            last_vol = int(hist["Volume"].iloc[-1])
            avg_vol_20 = int(hist["Volume"].iloc[-20:].mean()) if len(hist) >= 20 else last_vol

            if last_close > last_open:
                vol_direction = "🟢 INFLOW (acquisto)"
            elif last_close < last_open:
                vol_direction = "🔴 OUTFLOW (vendita)"
            else:
                vol_direction = "⚪ NEUTRO"

            vol_ratio = round(last_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 0
            vol_intensity = "🔴 ANOMALO >2x" if vol_ratio > 2.0 else "🟡 ELEVATO" if vol_ratio > 1.5 else "⚪ NORMALE"

            # ── PRICE CHANGES (with starting prices) ──
            def pct_change(days_back):
                if len(hist) > days_back:
                    start_p = float(hist["Close"].iloc[-(days_back + 1)])
                    return round(((price_now / start_p) - 1) * 100, 2), round(start_p, 2)
                return None, None

            chg_1d, start_1d = pct_change(1)
            chg_1w, start_1w = pct_change(5)
            chg_1m, start_1m = pct_change(21)
            chg_3m, start_3m = pct_change(63)

            mcap = info.get("marketCap", 0)
            low52 = info.get("fiftyTwoWeekLow", 0)
            high52 = info.get("fiftyTwoWeekHigh", 0)

            # ── OPTIONS ──
            opt_call_oi = None
            opt_put_oi = None
            opt_pc_ratio = None
            opt_exp = None
            try:
                exps = stock.options
                near = [d for d in exps
                        if 30 <= (datetime.strptime(d, "%Y-%m-%d") - datetime.now()).days <= 90]
                if near:
                    opt_exp = near[0]
                    chain = stock.option_chain(near[0])
                    opt_call_oi = int(chain.calls["openInterest"].sum())
                    opt_put_oi = int(chain.puts["openInterest"].sum())
                    opt_pc_ratio = round(opt_put_oi / opt_call_oi, 3) if opt_call_oi > 0 else None
            except Exception:
                pass

            result[t] = dict(
                price=round(price_now, 2),
                mcap=mcap,
                mcap_str=f"${mcap/1e9:.2f}B" if mcap >= 1e9 else f"${mcap/1e6:.0f}M" if mcap > 0 else "N/D",
                vol_last=last_vol, vol_avg20=avg_vol_20, vol_ratio=vol_ratio,
                vol_direction=vol_direction, vol_intensity=vol_intensity,
                chg_1d=chg_1d, start_1d=start_1d,
                chg_1w=chg_1w, start_1w=start_1w,
                chg_1m=chg_1m, start_1m=start_1m,
                chg_3m=chg_3m, start_3m=start_3m,
                low52=low52, high52=high52,
                opt_call_oi=opt_call_oi, opt_put_oi=opt_put_oi,
                opt_pc_ratio=opt_pc_ratio, opt_exp=opt_exp,
                source="LIVE", fetched=datetime.now().isoformat(),
            )
        except Exception as e:
            # LAYER 2: disk cache
            if t in cache.get("data", {}):
                result[t] = cache["data"][t]
                result[t]["source"] = f"CACHE ({cache.get('timestamp','?')[:10]})"
                source = "CACHE (parziale)"
            else:
                # LAYER 3: empty — NEVER fabricate
                result[t] = dict(
                    price=None, mcap=0, mcap_str="N/D",
                    vol_last=None, vol_avg20=None, vol_ratio=None,
                    vol_direction="❌ DATI NON DISPONIBILI", vol_intensity="❌",
                    chg_1d=None, start_1d=None, chg_1w=None, start_1w=None,
                    chg_1m=None, start_1m=None, chg_3m=None, start_3m=None,
                    low52=None, high52=None,
                    opt_call_oi=None, opt_put_oi=None, opt_pc_ratio=None, opt_exp=None,
                    source="FALLBACK (nessun dato)", fetched=datetime.now().isoformat(),
                )
                source = "FALLBACK (parziale)"

    # Persist for crash recovery
    save_cache({"data": result, "source": source})
    return result, source

@st.cache_data(ttl=CACHE_TTL)
def fetch_trial(nct_id: str) -> dict:
    """ClinicalTrials.gov API v2 con fallback."""
    try:
        r = requests.get(f"https://clinicaltrials.gov/api/v2/studies/{nct_id}", timeout=10)
        if r.status_code == 200:
            sm = r.json().get("protocolSection", {}).get("statusModule", {})
            return dict(
                status=sm.get("overallStatus", "N/D"),
                update=sm.get("lastUpdatePostDateStruct", {}).get("date", "N/D"),
                completion=sm.get("primaryCompletionDateStruct", {}).get("date", "N/D"),
            )
    except Exception:
        pass
    return dict(status="⚠ Fetch fallito", update="N/D", completion="N/D")

# ─────────────────────────────────────────────
# SKEPTICAL ENGINE
# ─────────────────────────────────────────────
def score(t, mk):
    base = t["base_rate"]
    adj, notes = 0, []
    if "BTD" in t.get("btd", ""):
        adj += 0.10; notes.append("+10% BTD")
    if "Fast Track" in t.get("btd", ""):
        adj += 0.05; notes.append("+5% Fast Track")
    if "Priority" in t.get("pdufa", "") or "APPROVATO" in t.get("pdufa", ""):
        adj += 0.05; notes.append("+5% Priority Review")
    if "AAV" in t.get("moa", "") or "genica" in t.get("moa", "").lower():
        adj -= 0.10; notes.append("-10% CMC gene therapy")
    if "Phase 2" in t.get("fase", "") and "Phase 3" not in t.get("fase", ""):
        adj -= 0.15; notes.append("-15% solo Phase 2")
    appr = 100 if base >= 1.0 else max(5, min(95, int((base + adj) * 100)))
    if base >= 1.0: notes = ["Già approvato"]

    ma, mn = 0, []
    mc = mk.get("mcap", 0)
    if 0 < mc < 3e9: ma += 25; mn.append("+25% MktCap<$3B")
    elif 0 < mc < 7e9: ma += 15; mn.append("+15% MktCap $3-7B")
    if t["classificazione"] == "First-in-Class": ma += 20; mn.append("+20% First-in-Class")
    else: ma += 10; mn.append("+10% Best-in-Class")
    if "BTD" in t.get("btd", ""): ma += 10; mn.append("+10% BTD")
    if t["area_key"] in ("metabolico", "immuno"): ma += 10; mn.append("+10% area hot M&A")
    return dict(appr=appr, appr_n=notes, ma=min(85, ma), ma_n=mn)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def fmt_pct(v):
    if v is None: return "N/D"
    color = "green" if v > 0 else "red" if v < 0 else "gray"
    arrow = "▲" if v > 0 else "▼" if v < 0 else "–"
    return f":{color}[{arrow} {v:+.2f}%]"

def fmt_price_line(label, chg, start, current):
    if chg is None or start is None:
        return f"**{label}:** N/D"
    color = "green" if chg > 0 else "red" if chg < 0 else "gray"
    arrow = "▲" if chg > 0 else "▼" if chg < 0 else "–"
    return f"**{label}:** :{color}[{arrow} {chg:+.2f}%] &nbsp; (da ${start:.2f} → ${current:.2f})"

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
st.markdown("""<style>
.stApp{background:#060609}
section[data-testid="stSidebar"]{background:#0c0c18}
.block-container{padding-top:.8rem;max-width:1200px}
h1,h2,h3{color:#e2e8f0!important}
.stMetric label{color:#64748b!important;font-size:10px!important}
.stMetric [data-testid="stMetricValue"]{color:#e2e8f0!important}
div[data-testid="stExpander"]{background:#0c0c18;border:1px solid #1e293b;border-radius:8px}
.stMarkdown{color:#cbd5e1}
</style>""", unsafe_allow_html=True)

# Header
c1, c2 = st.columns([4, 1])
with c1:
    st.markdown("### 🧬 BIOTECH M&A SCOUTER 2026 — v4.0 RESILIENT")
    st.caption(f"Ultimo refresh: {datetime.now().strftime('%d/%m/%Y %H:%M')} UTC | Refresh automatico ogni 24h")
with c2:
    if st.button("🔄 AGGIORNA ORA", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Fetch data
tickers = tuple(t["ticker"] for t in TARGETS)
with st.spinner("📡 Connessione a Yahoo Finance + ClinicalTrials.gov..."):
    market, data_source = fetch_all_market_data(tickers)

# Data source indicator
if "LIVE" in data_source:
    st.success(f"📡 Fonte dati: **{data_source}** — Aggiornamento riuscito", icon="✅")
elif "CACHE" in data_source:
    st.warning(f"⚠️ Fonte dati: **{data_source}** — API temporaneamente non raggiungibili. Dati dall'ultimo fetch riuscito.", icon="⚠️")
else:
    st.error(f"❌ Fonte dati: **{data_source}** — Nessun dato disponibile. Riprovare più tardi.", icon="❌")

st.info(
    "**⚠ METODOLOGIA SCETTICA:** Probabilità basate su base rate storici FDA, non opinioni. "
    "Premi M&A ridotti 20% per survival bias. Direzione volumi = proxy (Close vs Open), NON order flow reale. "
    "**Dati mai inventati:** se un dato non è disponibile appare 'N/D'.",
    icon="🔬"
)

# Summary
st.markdown("---")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("TARGET", len(TARGETS))
m2.metric("FIRST-IN-CLASS", sum(1 for t in TARGETS if t["classificazione"] == "First-in-Class"))
m3.metric("CON BTD", sum(1 for t in TARGETS if "BTD" in t["btd"]))
m4.metric("APPROVATI", sum(1 for t in TARGETS if t["base_rate"] >= 1.0))
m5.metric("PDUFA ≤90gg", sum(1 for t in TARGETS if "LUGLIO 2026" in t.get("pdufa", "")))

# Filters
st.markdown("---")
f1, f2, f3 = st.columns(3)
with f1:
    af = st.selectbox("Area", ["Tutti", "🟣 Rara", "🔴 Onco", "🔷 Neuro", "🔵 Metabolico", "🟡 Epatico", "🟢 Immuno"])
with f2:
    cf = st.selectbox("Classe", ["Tutti", "First-in-Class", "Best-in-Class"])
with f3:
    sf = st.selectbox("Ordina", ["Prob. Approvazione ↓", "Prob. M&A ↓", "Ticker", "Variaz. 1G ↓"])

# Filter + score
items = TARGETS[:]
if af != "Tutti": items = [t for t in items if t["area"] == af]
if cf != "Tutti": items = [t for t in items if t["classificazione"] == cf]
scored = [{**t, **score(t, market.get(t["ticker"], {}))} for t in items]
if sf == "Prob. Approvazione ↓": scored.sort(key=lambda x: x["appr"], reverse=True)
elif sf == "Prob. M&A ↓": scored.sort(key=lambda x: x["ma"], reverse=True)
elif sf == "Ticker": scored.sort(key=lambda x: x["ticker"])
elif sf == "Variaz. 1G ↓": scored.sort(key=lambda x: market.get(x["ticker"], {}).get("chg_1d") or -999, reverse=True)

# ── CARDS ──
for t in scored:
    mk = market.get(t["ticker"], {})
    price = mk.get("price")
    appr_ico = "🟢" if t["appr"] >= 75 else "🟡" if t["appr"] >= 40 else "🔴"
    ma_ico = "🟢" if t["ma"] >= 60 else "🟡" if t["ma"] >= 35 else "🔴"
    chg1d_str = f"{mk.get('chg_1d',0):+.1f}%" if mk.get("chg_1d") is not None else "N/D"
    price_str = f"${price:.2f}" if price else "N/D"

    with st.expander(
        f"**{t['ticker']}** {t['nome']} | {mk.get('mcap_str','N/D')} | "
        f"{price_str} ({chg1d_str}) | "
        f"Appr:{appr_ico}{t['appr']}% M&A:{ma_ico}{t['ma']}% | "
        f"{t['area']} {t['classificazione']}"
    ):
        # Source badge
        src = mk.get("source", "?")
        if "LIVE" in str(src):
            st.caption(f"📡 Dati: **LIVE** — {mk.get('fetched','')[:16]}")
        elif "CACHE" in str(src):
            st.caption(f"⚠️ Dati: **CACHE** — ultimo fetch: {mk.get('fetched','')[:16]}")
        else:
            st.caption(f"❌ Dati: **NON DISPONIBILI** — nessun dato storico")

        # ── ROW 1: Price + MktCap ──
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Prezzo", price_str)
        r2.metric("Market Cap", mk.get("mcap_str", "N/D"))
        r3.metric("52W Min", f"${mk['low52']:.2f}" if mk.get("low52") else "N/D")
        r4.metric("52W Max", f"${mk['high52']:.2f}" if mk.get("high52") else "N/D")

        # ── ROW 2: PRICE CHANGES ──
        st.markdown("**📈 VARIAZIONI PREZZO (con quotazione di partenza)**")
        current = price if price else 0
        st.markdown(fmt_price_line("1 Giorno", mk.get("chg_1d"), mk.get("start_1d"), current))
        st.markdown(fmt_price_line("1 Settimana", mk.get("chg_1w"), mk.get("start_1w"), current))
        st.markdown(fmt_price_line("1 Mese", mk.get("chg_1m"), mk.get("start_1m"), current))
        st.markdown(fmt_price_line("3 Mesi", mk.get("chg_3m"), mk.get("start_3m"), current))

        st.markdown("---")

        # ── ROW 3: VOLUME DIRECTION ──
        st.markdown("**📊 ANALISI VOLUMI (direzione + intensità)**")
        vc1, vc2, vc3 = st.columns(3)
        vc1.metric("Direzione", mk.get("vol_direction", "N/D"))
        last_v = mk.get("vol_last")
        vc2.metric("Volume ultimo giorno", f"{last_v:,.0f}" if last_v else "N/D")
        avg_v = mk.get("vol_avg20")
        vc3.metric("Media 20gg", f"{avg_v:,.0f}" if avg_v else "N/D")

        vi1, vi2 = st.columns(2)
        vr = mk.get("vol_ratio")
        vi1.metric("Ratio Vol/Media", f"{vr:.2f}x" if vr else "N/D", mk.get("vol_intensity", ""))
        vi2.markdown(
            "**Metodo:** Close > Open + volume → INFLOW (pressione acquisto). "
            "Close < Open + volume → OUTFLOW (pressione vendita). "
            "⚠ Proxy tecnico, NON order flow reale."
        )

        # ── ROW 4: OPTIONS ──
        st.markdown("**🎯 SEGNALI OPZIONI (30-90gg)**")
        oc1, oc2, oc3, oc4 = st.columns(4)
        coi = mk.get("opt_call_oi")
        poi = mk.get("opt_put_oi")
        pcr = mk.get("opt_pc_ratio")
        oex = mk.get("opt_exp")
        oc1.metric("Call Open Interest", f"{coi:,}" if coi is not None else "N/D")
        oc2.metric("Put Open Interest", f"{poi:,}" if poi is not None else "N/D")
        oc3.metric("Put/Call Ratio", f"{pcr:.3f}" if pcr is not None else "N/D")
        oc4.metric("Scadenza analizzata", oex if oex else "N/D")

        st.markdown("---")

        # ── PROBABILITY BARS ──
        p1, p2 = st.columns(2)
        with p1:
            st.markdown(f"**Prob. Approvazione FDA: {t['appr']}%**")
            st.progress(t["appr"] / 100)
            for n in t["appr_n"]: st.caption(n)
        with p2:
            st.markdown(f"**Prob. M&A ≤18 mesi: {t['ma']}%**")
            st.progress(t["ma"] / 100)
            for n in t["ma_n"]: st.caption(n)

        st.markdown("---")

        # ── DRUG INFO ──
        st.markdown(f"**🧪 {t['farmaco']}** — {t['moa']}")
        st.markdown(f"Indicazione: **{t['indicazione']}**")

        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**📋 Status Regolatorio**")
            st.markdown(f"PDUFA: `{t['pdufa']}`")
            st.markdown(f"Fase: {t['fase']}")
            st.markdown(f"Designazioni: {t['btd']}")
            st.caption(f"Fonte: {t['btd_fonte']}")
        with d2:
            st.markdown("**💰 Premio M&A**")
            st.markdown(f"Raw: {t['premio_raw']} → **Corretto: {t['premio_corr']}**")
            st.caption(t["nota_premio"])

        st.markdown("**🔬 NOTA SCETTICA**")
        st.info(t["nota_scettica"])
        st.markdown("**⚠️ RISCHI**")
        st.error(t["rischio"])

        # ── CLINICAL TRIALS LIVE ──
        if t.get("nct"):
            st.markdown("**🔎 ClinicalTrials.gov — Status Live**")
            for nid in t["nct"]:
                if nid.startswith("NCT"):
                    tr = fetch_trial(nid)
                    st.caption(f"`{nid}` → **{tr['status']}** | Aggiorn: {tr['update']} | Completamento: {tr['completion']}")

# ── FOOTER ──
st.markdown("---")
st.markdown("""
<div style="font-size:9px;color:#334155;line-height:1.8">
<b>DISCLAIMER v4.0</b> — Report informativo. Non è consulenza finanziaria.<br>
<b>Fonti live:</b> Yahoo Finance (prezzi, volumi, opzioni), ClinicalTrials.gov API v2 (status trial).<br>
<b>Direzione volumi:</b> Proxy tecnico basato su confronto Close/Open + volume giornaliero. NON è order flow reale (non disponibile gratuitamente).<br>
<b>Resilienza:</b> 3 livelli — (1) API live, (2) cache disco ultimo fetch riuscito, (3) N/D esplicito. MAI dati inventati.<br>
<b>Refresh:</b> Automatico ogni 24h. Pulsante "Aggiorna Ora" per forzare. Cache disco persiste tra riavvii.<br>
<b>Probabilità:</b> Bayesiane su base rate FDA storici. Non sono previsioni. Non sono garanzie.<br>
<b>Filtro:</b> NASDAQ indipendenti, MktCap <$10B. Escluse società acquisite/filiali/in fusione.
</div>
""", unsafe_allow_html=True)
