# 🧬 Biotech M&A Scouter 2026 — v4.0 RESILIENT

Dashboard LIVE di monitoraggio segnali pre-M&A nel settore biotech.

## 📊 Funzionalità
- **Dati LIVE giornalieri** da Yahoo Finance + ClinicalTrials.gov
- **Volumi direzionali**: INFLOW (acquisto) / OUTFLOW (vendita) con intensità
- **Variazioni prezzo**: 1G, 1 settimana, 1 mese, 3 mesi con quotazione di partenza
- **Opzioni**: Call/Put Open Interest, Put/Call ratio (30-90gg)
- **Probabilità Bayesiane**: approvazione FDA + M&A con base rate storici
- **3 livelli fallback**: Live → Cache disco → N/D esplicito (MAI dati inventati)

## 🚀 Deploy GRATUITO (5 minuti)

### 1. Crea Repository GitHub
- Vai su https://github.com/new
- Nome: `biotech-scouter` → Public → Create

### 2. Carica i File
Carica TUTTI questi file/cartelle:
```
app.py
requirements.txt
README.md
icon-512.png
icon-192.png
.streamlit/config.toml
```

### 3. Deploy su Streamlit Cloud
- Vai su https://share.streamlit.io
- Login con GitHub → "New app"
- Seleziona il tuo repo → Main file: `app.py` → Deploy!
- URL permanente: `https://tuonome-biotech-scouter.streamlit.app`

## 📱 Installare l'Icona Fuxia sul Telefono

### Android (Chrome):
1. Apri l'URL della tua app in **Chrome**
2. Tocca i **tre puntini** in alto a destra
3. Tocca **"Aggiungi a schermata Home"**
4. **PRIMA di confermare**: tocca l'icona per cambiarla
5. Seleziona l'immagine `icon-512.png` dalla galleria
6. Se Chrome non permette di cambiare l'icona:
   - Scarica **"Shortcut Maker"** dal Play Store (gratis)
   - Apri Shortcut Maker → "Web page" → incolla URL
   - Tocca l'icona → "Gallery" → seleziona `icon-512.png`
   - Crea collegamento

### iPhone (Safari):
1. Apri l'URL in **Safari**
2. Tocca l'icona di **condivisione** (quadrato con freccia)
3. Tocca **"Aggiungi alla schermata Home"**
4. L'icona sarà uno screenshot della pagina
5. Per l'icona personalizzata:
   - Scarica l'app **"Shortcuts"** (Comandi Rapidi, preinstallata)
   - Crea nuovo comando → "Apri URL" → incolla URL
   - Tocca i tre puntini → "Aggiungi alla Home" → tocca l'icona → "Scegli foto"
   - Seleziona `icon-512.png`

## ⚠️ Disclaimer
Non è consulenza finanziaria. Dati mai inventati: se non disponibili → "N/D".
