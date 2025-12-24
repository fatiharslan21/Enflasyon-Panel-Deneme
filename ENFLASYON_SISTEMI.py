import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
import re
import calendar
from datetime import datetime, timedelta
import time
import json
from github import Github
from io import BytesIO
import zipfile
import base64
import google.generativeai as genai
import requests
from prophet import Prophet
import feedparser
from fpdf import FPDF
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import streamlit.components.v1 as components

# --- 1. AYARLAR VE TEMA YÖNETİMİ ---
st.set_page_config(
    page_title="Enflasyon Monitörü",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# --- SADECE KOYU TEMA (Dark Mode Fixed) ---
st.session_state.theme = 'dark' 

# --- CSS MOTORU ---
def apply_theme():
    # Sadece Dark Mode Renkleri
    colors = {
        "bg": "#0E1117",
        "sidebar": "#262730",
        "text": "#FAFAFA",
        "input_bg": "#1A1C24",
        "input_border": "#4A4A4A",
        "card_bg": "#1A1C24",
        "border_color": "#414141"
    }
    st.session_state.plotly_template = "plotly_dark"

    final_css = f"""
    <style>
        /* --- SIDEBAR AYARLARI --- */
        section[data-testid="stSidebar"] {{
            width: 400px !important;
            min-width: 400px !important;
            max-width: 400px !important;
            background-color: {colors['sidebar']};
            border-right: 1px solid {colors['border_color']};
        }}

        /* --- KESİN GİZLEME KODLARI --- */
        div[class*="viewerBadge"] {{ display: none !important; }}
        footer {{ visibility: hidden !important; display: none !important; height: 0px !important; }}
        #MainMenu {{ visibility: hidden !important; display: none !important; }}
        header {{ visibility: hidden !important; }}
        header[data-testid="stHeader"] {{ display: none !important; }}
        [data-testid="stDecoration"] {{ display: none !important; }}
        [data-testid="collapsedControl"] {{ display: none !important; }}
        .stDeployButton {{ display: none !important; }}

        .block-container {{ padding-top: 1rem !important; }}

        /* --- GENEL RENKLER --- */
        .stApp {{ background-color: {colors['bg']}; color: {colors['text']}; }}
        h1, h2, h3, h4, h5, h6, p, li, label, .stMarkdown, .stRadio label {{ color: {colors['text']} !important; }}

        /* Input Alanları */
        .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {{
            background-color: {colors['input_bg']} !important;
            color: {colors['text']} !important;
            border: 1px solid {colors['input_border']} !important;
        }}
        
        /* Slider Rengi */
        div[data-baseweb="slider"] div {{ background-color: #3b82f6 !important; }}

        /* Tablolar */
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
            background-color: {colors['card_bg']} !important;
            border: 1px solid {colors['border_color']} !important;
        }}
        [data-testid="stDataFrame"] td, [data-testid="stDataEditor"] td {{ color: {colors['text']} !important; }}
        [data-testid="stDataFrame"] th, [data-testid="stDataEditor"] th {{
            color: {colors['text']} !important;
            background-color: {colors['sidebar']} !important;
        }}

        /* Butonlar */
        div.stButton > button, 
        div.stFormSubmitButton > button,
        [data-testid="stDownloadButton"] button {{
            background-color: #ffffff !important;   
            color: #000000 !important;              
            border: 2px solid #000000 !important;   
            border-radius: 8px !important;
            font-weight: bold !important;
        }}
        div.stButton > button p, div.stFormSubmitButton > button p {{ color: #000000 !important; }}
        
        div.stButton > button:hover {{
            background-color: #f0f0f0 !important;
            border-color: #3b82f6 !important;
        }}
        
        /* Primary Buton (Mavi) */
        div.stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: white !important;
            border: none !important;
        }}
        div.stButton > button[kind="primary"] p {{ color: white !important; }}

        .metric-card {{ background: {colors['card_bg']} !important; border: 1px solid {colors['border_color']} !important; }}
        .metric-val, div[data-testid="stMetricValue"] {{ color: {colors['text']} !important; }}
    </style>
    """
    st.markdown(final_css, unsafe_allow_html=True)


# Temayı Uygula
apply_theme()

if "gemini" in st.secrets:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])


# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"


# --- PDF RAPOR MOTORU ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'ENFLASYON DURUM RAPORU', 0, 1, 'C')
        self.set_y(10)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(0, 0, 0)
        self.ln(5)
        self.line(10, 25, 200, 25)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Enflasyon Monitoru - Sayfa {self.page_no()}', 0, 0, 'C')


def create_pdf_report(text_content, filename="Rapor.pdf"):
    pdf = PDFReport()
    pdf.add_page()
    def clean_text_for_pdf(text):
        if not text: return ""
        replacements = {'ı': 'i', 'İ': 'I', '\u0131': 'i', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C', 'â': 'a', 'î': 'i', 'û': 'u', '₺': 'TL', '“': '"', '”': '"', '’': "'", '‘': "'", '–': '-', '—': '-', '…': '...'}
        temp_text = text
        for tr, en in replacements.items(): temp_text = temp_text.replace(tr, en)
        return temp_text.encode('latin-1', 'replace').decode('latin-1')
    final_text = clean_text_for_pdf(text_content)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, final_text)
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, "Bu rapor piyasa analiz sistemi tarafindan otomatik olarak olusturulmustur.")
    return pdf.output(dest='S').encode('latin-1', 'ignore')


# --- HABER MOTORU ---
def get_market_sentiment():
    rss_url = "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr"
    try:
        feed = feedparser.parse(rss_url)
        headlines = [entry.title for entry in feed.entries[:10]]
        news_text = "\n".join([f"- {h}" for h in headlines])
        prompt = f"Aşağıdaki Türkiye haberlerini tara. Ekonomi/Piyasa etkisi var mı? Tek kelimeyle havayı tanımla (Nötr/Gergin/İyimser). Kritik 1 haberi yorumla:\n{news_text}"
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text, headlines
    except Exception as e:
        return f"Haberler alınamadı: {str(e)}", []


# --- GITHUB İŞLEMLERİ ---
def get_github_repo():
    try: return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
    except: return None

def github_json_oku(dosya_adi):
    repo = get_github_repo()
    if not repo: return {}
    try:
        c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        return json.loads(c.decoded_content.decode("utf-8"))
    except: return {}

def github_json_yaz(dosya_adi, data, mesaj="Update JSON"):
    repo = get_github_repo()
    if not repo: return False
    try:
        content = json.dumps(data, indent=4)
        try:
            c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
            repo.update_file(c.path, mesaj, content, c.sha, branch=st.secrets["github"]["branch"])
        except:
            repo.create_file(dosya_adi, mesaj, content, branch=st.secrets["github"]["branch"])
        return True
    except: return False

# --- HIZLANDIRILMIŞ (CACHED) VERİ OKUMA ---
@st.cache_data(ttl=60, show_spinner=False)
def github_excel_oku(dosya_adi, sayfa_adi=None):
    repo = get_github_repo()
    if not repo: return pd.DataFrame()
    try:
        c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        if sayfa_adi: df = pd.read_excel(BytesIO(c.decoded_content), sheet_name=sayfa_adi, dtype=str)
        else: df = pd.read_excel(BytesIO(c.decoded_content), dtype=str)
        return df
    except: return pd.DataFrame()

def github_excel_guncelle(df_yeni, dosya_adi):
    repo = get_github_repo()
    if not repo: return "Repo Yok"
    try:
        try:
            c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
            old = pd.read_excel(BytesIO(c.decoded_content), dtype=str)
            yeni_tarih = str(df_yeni['Tarih'].iloc[0])
            old = old[~((old['Tarih'].astype(str) == yeni_tarih) & (old['Kod'].isin(df_yeni['Kod'])))]
            final = pd.concat([old, df_yeni], ignore_index=True)
        except: c = None; final = df_yeni
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w: final.to_excel(w, index=False, sheet_name='Fiyat_Log')
        msg = f"Data Update"
        if c: repo.update_file(c.path, msg, out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else: repo.create_file(dosya_adi, msg, out.getvalue(), branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e: return str(e)


# --- RESMİ ENFLASYON & PROPHET ---
def get_official_inflation():
    api_key = st.secrets.get("evds", {}).get("api_key")
    if not api_key: return None, "API Key Yok"
    start_date = (datetime.now() - timedelta(days=365)).strftime("%d-%m-%Y")
    end_date = datetime.now().strftime("%d-%m-%Y")
    url = f"https://evds2.tcmb.gov.tr/service/evds/series=TP.FG.J0&startDate={start_date}&endDate={end_date}&type=json&key={api_key}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10, verify=False)
        if res.status_code == 200:
            data = res.json()
            if "items" in data:
                df = pd.DataFrame(data["items"])[['Tarih', 'TP_FG_J0']]
                df.columns = ['Tarih', 'Resmi_TUFE']
                df['Tarih'] = pd.to_datetime(df['Tarih'] + "-01", format="%Y-%m-%d")
                df['Resmi_TUFE'] = pd.to_numeric(df['Resmi_TUFE'], errors='coerce')
                return df, "OK"
        return None, "Hata"
    except Exception as e: return None, str(e)

@st.cache_data(ttl=3600, show_spinner=False)
def predict_inflation_prophet(df_trend):
    try:
        df_p = df_trend.rename(columns={'Tarih': 'ds', 'TÜFE': 'y'})
        m = Prophet(daily_seasonality=True, yearly_seasonality=False).fit(df_p)
        return m.predict(m.make_future_dataframe(periods=90))[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    except: return pd.DataFrame()


# --- SCRAPER (FİYAT ÇEKİCİ) ---
def temizle_fiyat(t):
    if not t: return None
    t = str(t).replace('TL', '').replace('₺', '').strip()
    t = t.replace('.', '').replace(',', '.') if ',' in t and '.' in t else t.replace(',', '.')
    try: return float(re.sub(r'[^\d.]', '', t))
    except: return None

def kod_standartlastir(k): return str(k).replace('.0', '').strip().zfill(7)

def fiyat_bul_siteye_gore(soup, url):
    fiyat = 0; kaynak = ""; domain = url.lower() if url else ""
    if "migros" in domain:
        for g in ["sm-list-page-item", ".similar-products", "div.badges-wrapper"]: 
            for x in soup.select(g): x.decompose()
        if el := soup.select_one(".name-price-wrapper .price.subtitle-1, .single-price-amount, #sale-price"):
             if val := temizle_fiyat(el.get_text()): return val, "Migros"
    elif "cimri" in domain:
         if els := soup.select("div.rTdMX, .offer-price"):
             vals = [v for v in [temizle_fiyat(e.get_text()) for e in els] if v and v > 0]
             if vals: fiyat = vals[0]; kaynak = "Cimri"
    if fiyat == 0:
        if m := re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', soup.get_text()[:5000]):
             if v := temizle_fiyat(m.group(1)): fiyat = v; kaynak = "Genel"
    return fiyat, kaynak

def html_isleyici(log_callback):
    repo = get_github_repo()
    if not repo: return "GitHub Hatası"
    log_callback("📂 Konfigürasyon okunuyor...")
    try:
        df_conf = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)
        df_conf.columns = df_conf.columns.str.strip()
        kod_col = next((c for c in df_conf.columns if c.lower() == 'kod'), None)
        url_col = next((c for c in df_conf.columns if c.lower() == 'url'), None)
        ad_col = next((c for c in df_conf.columns if 'ad' in c.lower()), 'Madde adı')
        if not kod_col or not url_col: return "Sütun eksik"
        
        df_conf['Kod'] = df_conf[kod_col].astype(str).apply(kod_standartlastir)
        url_map = {str(row[url_col]).strip(): row for _, row in df_conf.iterrows() if pd.notna(row[url_col])}
        veriler = []; islenen_kodlar = set()
        bugun = datetime.now().strftime("%Y-%m-%d"); simdi = datetime.now().strftime("%H:%M")
        
        if manuel_col := next((c for c in df_conf.columns if 'manuel' in c.lower()), None):
            for _, row in df_conf.iterrows():
                if pd.notna(row[manuel_col]) and str(row[manuel_col]).strip():
                    if (f := float(row[manuel_col])) > 0:
                        veriler.append({"Tarih": bugun, "Zaman": simdi, "Kod": row['Kod'], "Madde_Adi": row[ad_col], "Fiyat": f, "Kaynak": "Manuel", "URL": row[url_col]})
                        islenen_kodlar.add(row['Kod'])
        
        contents = repo.get_contents("", ref=st.secrets["github"]["branch"])
        for zip_file in [c for c in contents if c.name.endswith(".zip") and c.name.startswith("Bolum")]:
            log_callback(f"📂 {zip_file.name} taranıyor...")
            try:
                with zipfile.ZipFile(BytesIO(base64.b64decode(repo.get_git_blob(zip_file.sha).content))) as z:
                    for fn in z.namelist():
                        if not fn.endswith(('.html', '.htm')): continue
                        soup = BeautifulSoup(z.open(fn).read().decode("utf-8", "ignore"), 'html.parser')
                        if found_url := (soup.find("link", rel="canonical") or soup.find("meta", property="og:url")):
                            url_val = found_url.get("href") if found_url.name=="link" else found_url.get("content")
                            if url_val and str(url_val).strip() in url_map:
                                target = url_map[str(url_val).strip()]
                                if target['Kod'] in islenen_kodlar: continue
                                fiyat, kaynak = fiyat_bul_siteye_gore(soup, target[url_col])
                                if fiyat > 0:
                                    veriler.append({"Tarih": bugun, "Zaman": simdi, "Kod": target['Kod'], "Madde_Adi": target[ad_col], "Fiyat": fiyat, "Kaynak": kaynak, "URL": target[url_col]})
                                    islenen_kodlar.add(target['Kod'])
            except: pass
        return github_excel_guncelle(pd.DataFrame(veriler), FIYAT_DOSYASI) if veriler else "Veri yok"
    except Exception as e: return str(e)


# --- DASHBOARD MODU ---
def dashboard_modu():
    bugun = datetime.now().strftime("%Y-%m-%d")
    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    # --- SIDEBAR ---
    with st.sidebar:
        # 1. CANLI PİYASA KARTLARI (KART GÖRÜNÜMÜ)
        st.markdown(
            "<h3 style='color:#1e293b; font-size:14px; margin-bottom:10px; padding-left:5px;'>💎 CANLI PİYASA</h3>",
            unsafe_allow_html=True)
        
        tv_theme = "dark" # Tema sabitlendi
        
        symbols = [
            {"s": "FX:USDTRY", "d": "Dolar / TL"},
            {"s": "FX:EURTRY", "d": "Euro / TL"},
            {"s": "FX_IDC:XAUTRYG", "d": "Gram Altın"},
            {"s": "TVC:UKOIL", "d": "Brent Petrol"},
            {"s": "BINANCE:BTCUSDT", "d": "Bitcoin ($)"}
        ]
        
        widgets_html = ""
        for sym in symbols:
            widgets_html += f"""
            <div class="tradingview-widget-container" style="margin-bottom: 15px;">
              <div class="tradingview-widget-container__widget"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
              {{
              "symbol": "{sym['s']}",
              "width": "100%",
              "height": 120,
              "locale": "tr",
              "dateRange": "12M",
              "colorTheme": "{tv_theme}",
              "isTransparent": true,
              "autosize": true,
              "largeChartUrl": "",
              "chartOnly": false,
              "noTimeScale": true
              }}
              </script>
            </div>
            """
        
        total_height = len(symbols) * 135 
        components.html(f'<div style="display:flex; flex-direction:column; overflow:hidden;">{widgets_html}</div>', height=total_height)
        
        st.markdown("<div style='border-bottom:1px solid #e2e8f0; margin-bottom:20px;'></div>", unsafe_allow_html=True)

        # 2. YENİ AYARLAR KISMI (Buraya Eklendi)
        st.title("⚙️ Ayarlar")
        
        # Risk Hassasiyeti (Slider)
        risk_threshold = st.slider("⚠️ Risk Eşiği (%)", min_value=1, max_value=50, value=5, help="Bu oranın üzerindeki günlük/toplam artışlar kayan yazıda kırmızı görünür.")
        
        # Rapor Dili (Selectbox)
        report_tone = st.selectbox("📝 Rapor Dili", ["Yönetici Özeti (Resmi)", "Teknik Analiz (Detaylı)", "Yatırımcı Notu (Kısa)"])
        
        # Önbellek Temizleme (Button)
        st.markdown("---")
        if st.button("🧹 Önbelleği Temizle"):
            st.cache_data.clear()
            st.toast("Önbellek temizlendi!", icon="✨")
            time.sleep(1)
            st.rerun()

    # --- CSS: Global Styles ---
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Poppins:wght@400;600;800&family=JetBrains+Mono:wght@400&display=swap');
        .header-container { display: flex; justify-content: space-between; align-items: center; padding: 20px 30px; background: #1e2329; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); border-bottom: 4px solid #3b82f6; }
        .app-title { font-family: 'Poppins', sans-serif; font-size: 32px; font-weight: 800; letter-spacing: -1px; background: linear-gradient(90deg, #FAFAFA 0%, #3b82f6 50%, #FAFAFA 100%); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: shine 5s linear infinite; }
        @keyframes shine { to { background-position: 200% center; } }
        .update-btn-container button { background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important; color: white !important; font-weight: 700 !important; font-size: 16px !important; border-radius: 12px !important; height: 60px !important; border: none !important; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3); transition: all 0.3s ease !important; animation: pulse 2s infinite; }
        .update-btn-container button:hover { transform: scale(1.02); box-shadow: 0 10px 25px rgba(37, 99, 235, 0.5); animation: none; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(37, 99, 235, 0); } 100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); } }
        .ticker-wrap { width: 100%; overflow: hidden; background: linear-gradient(90deg, #0f172a, #1e293b); color: white; padding: 12px 0; margin-bottom: 25px; border-radius: 12px; }
        .ticker { display: inline-block; animation: ticker 45s linear infinite; white-space: nowrap; }
        .ticker-item { display: inline-block; padding: 0 2rem; font-weight: 500; font-size: 14px; font-family: 'JetBrains Mono', monospace; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .bot-bubble { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; border-radius: 0 8px 8px 8px; margin-top: 15px; color: #1e3a8a; font-size: 14px; line-height: 1.5; }
        .bot-log { background: #1e293b; color: #4ade80; font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 15px; border-radius: 12px; height: 180px; overflow-y: auto; }
        #live_clock_js { font-family: 'JetBrains Mono', monospace; color: #2563eb; }
        .metric-card { padding: 24px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.03); position: relative; overflow: hidden; transition: all 0.3s ease; }
        .metric-card:hover { transform: translateY(-5px); box-shadow: 0 20px 40px rgba(59, 130, 246, 0.15); border-color: #3b82f6; }
        .metric-card::before { content: ''; position: absolute; top: 0; left: 0; width: 6px; height: 100%; }
        .card-blue::before { background: #3b82f6; } .card-purple::before { background: #8b5cf6; } .card-emerald::before { background: #10b981; } .card-orange::before { background: #f59e0b; }
        .metric-label { color: #64748b; font-size: 13px; font-weight: 700; text-transform: uppercase; margin-bottom: 5px; }
        .metric-val { color: #FAFAFA; font-size: 36px; font-weight: 800; font-family: 'Poppins', sans-serif; letter-spacing: -1px; }
        .metric-val.long-text { font-size: 24px !important; line-height: 1.2; }
    </style>
    """, unsafe_allow_html=True)

    # --- HEADER & LIVE CLOCK ---
    tr_time_start = datetime.now() + timedelta(hours=3)
    header_html = f"""
    <div class="header-container">
        <div class="app-title">Enflasyon Monitörü</div>
        <div style="text-align:right;">
            <div style="color:#64748b; font-size:12px; font-weight:600; margin-bottom:4px;">İSTANBUL, TR</div>
            <div id="live_clock_js" style="color:#FAFAFA; font-size:16px; font-weight:800; font-family:'JetBrains Mono', monospace;">{tr_time_start.strftime('%d %B %Y, %H:%M:%S')}</div>
        </div>
    </div>
    <script>
    function startClock() {{
        var clockElement = document.getElementById('live_clock_js');
        function update() {{
            var now = new Date();
            var options = {{ timeZone: 'Europe/Istanbul', day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }};
            if (clockElement) {{ clockElement.innerHTML = now.toLocaleTimeString('tr-TR', options); }}
        }}
        setInterval(update, 1000); update(); 
    }}
    startClock();
    </script>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    if 'toast_shown' not in st.session_state:
        st.toast('Sistem Başarıyla Yüklendi! 🚀', icon='✅')
        st.session_state['toast_shown'] = True

    # --- SİSTEMİ GÜNCELLE BUTONU (HERKESE AÇIK) ---
    st.markdown('<div class="update-btn-container">', unsafe_allow_html=True)
    if st.button("🚀 SİSTEMİ GÜNCELLE VE ANALİZ ET", type="primary", use_container_width=True):
        with st.status("Veri Tabanı Güncelleniyor...", expanded=True) as status:
            st.write("📡 GitHub bağlantısı kuruluyor...")
            time.sleep(0.5)
            st.write("📦 ZIP dosyaları taranıyor...")
            log_ph = st.empty()
            log_msgs = []

            def logger(m):
                log_msgs.append(f"> {m}")
                log_ph.markdown(f'<div class="bot-log">{"<br>".join(log_msgs)}</div>', unsafe_allow_html=True)

            res = html_isleyici(logger)
            status.update(label="İşlem Tamamlandı!", state="complete", expanded=False)

        if "OK" in res:
            st.cache_data.clear()
            st.toast('Veritabanı Güncellendi!', icon='🎉')
            st.success("✅ Sistem Başarıyla Senkronize Edildi!")
            time.sleep(2)
            st.rerun()
        elif "Veri bulunamadı" in res:
            st.warning("⚠️ Yeni fiyat verisi bulunamadı. ZIP dosyalarını kontrol et.")
        else:
            st.error(res)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if not df_f.empty and not df_s.empty:
        try:
            df_s.columns = df_s.columns.str.strip()
            kod_col = next((c for c in df_s.columns if c.lower() == 'kod'), 'Kod')
            ad_col = next((c for c in df_s.columns if 'ad' in c.lower()), 'Madde adı')
            agirlik_col = next((c for c in df_s.columns if 'agirlik' in c.lower().replace('ğ', 'g').replace('ı', 'i')),
                               'Agirlik_2025')

            df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
            df_s['Kod'] = df_s[kod_col].astype(str).apply(kod_standartlastir)
            df_f['Tarih_DT'] = pd.to_datetime(df_f['Tarih'], errors='coerce')
            df_f = df_f.dropna(subset=['Tarih_DT']).sort_values('Tarih_DT')
            df_f['Tarih_Str'] = df_f['Tarih_DT'].dt.strftime('%Y-%m-%d')
            df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
            df_f = df_f[df_f['Fiyat'] > 0]

            pivot = df_f.pivot_table(index='Kod', columns='Tarih_Str', values='Fiyat', aggfunc='last').ffill(
                axis=1).bfill(axis=1).reset_index()

            if not pivot.empty:
                if 'Grup' not in df_s.columns:
                    grup_map = {"01": "Gıda", "02": "Alkol", "03": "Giyim", "04": "Konut", "05": "Ev", "06": "Sağlık",
                                "07": "Ulaşım", "08": "İletişim", "09": "Eğlence", "10": "Eğitim", "11": "Lokanta",
                                "12": "Çeşitli"}
                    df_s['Grup'] = df_s['Kod'].str[:2].map(grup_map).fillna("Diğer")
                df_analiz = pd.merge(df_s, pivot, on='Kod', how='left')
                if agirlik_col in df_analiz.columns:
                    df_analiz[agirlik_col] = pd.to_numeric(df_analiz[agirlik_col], errors='coerce').fillna(1)
                else:
                    df_analiz['Agirlik_2025'] = 1;
                    agirlik_col = 'Agirlik_2025'

                gunler = [c for c in pivot.columns if c != 'Kod']
                if len(gunler) < 1: st.warning("Yeterli tarih verisi yok."); return
                baz, son = gunler[0], gunler[-1]

                endeks_genel = (df_analiz.dropna(subset=[son, baz])[agirlik_col] * (
                        df_analiz[son] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[son, baz])[
                                   agirlik_col].sum() * 100
                enf_genel = (endeks_genel / 100 - 1) * 100
                df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
                top = df_analiz.sort_values('Fark', ascending=False).iloc[0]
                gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
                enf_gida = ((gida[son] / gida[baz] * gida[agirlik_col]).sum() / gida[
                    agirlik_col].sum() - 1) * 100 if not gida.empty else 0

                dt_son = datetime.strptime(son, '%Y-%m-%d')
                dt_baz = datetime.strptime(baz, '%Y-%m-%d')
                days_left = calendar.monthrange(dt_son.year, dt_son.month)[1] - dt_son.day
                month_end_forecast = enf_genel + ((enf_genel / max(dt_son.day, 1)) * days_left)
                gun_farki = (dt_son - dt_baz).days

                # --- KAYAN YAZI (TICKER) - RİSK EŞİĞİ ENTEGRE EDİLDİ ---
                if len(gunler) >= 2:
                    dunku_tarih = gunler[-2]
                    bugunku_tarih = gunler[-1]
                    df_analiz['Gunluk_Degisim'] = (df_analiz[bugunku_tarih] / df_analiz[dunku_tarih]) - 1
                else:
                    df_analiz['Gunluk_Degisim'] = 0

                # Sadece Artanları Risk Eşiğine Göre Filtrele
                items = []
                for _, r in df_analiz.sort_values('Fark', ascending=False).iterrows():
                    # Fark %5 (veya seçilen değer) üzerindeyse göster
                    if r['Fark'] * 100 >= risk_threshold:
                         items.append(f"<span style='color:#f87171'>▲ {r[ad_col]} %{r['Fark'] * 100:.1f}</span>")

                if not items: items.append(f"Piyasada {risk_threshold}% üzerinde artış gösteren ürün yok.")

                st.markdown(
                    f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;&nbsp; • &nbsp;&nbsp; ".join(items)}</div></div></div>',
                    unsafe_allow_html=True)
                
                # --- KPI KARTLARI ---
                def kpi_card(title, val, sub, sub_color, color_class, is_long_text=False):
                    val_class = "metric-val long-text" if is_long_text else "metric-val"
                    st.markdown(f"""
                        <div class="metric-card {color_class}">
                            <div class="metric-label">{title}</div>
                            <div class="{val_class}">{val}</div>
                            <div class="metric-sub" style="color:{sub_color}">{sub}</div>
                        </div>
                    """, unsafe_allow_html=True)

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    kpi_card("Genel Enflasyon", f"%{enf_genel:.2f}", f"{gun_farki} Günlük Değişim", "#ef4444",
                             "card-blue")
                with c2:
                    kpi_card("Gıda Enflasyonu", f"%{enf_gida:.2f}", "Mutfak Sepeti", "#ef4444", "card-emerald")
                with c3:
                    kpi_card("Simülasyon Beklentisi", f"%{month_end_forecast:.2f}", f"🗓️ {days_left} gün kaldı", "#8b5cf6",
                             "card-purple")
                with c4:
                    # En yüksek riski her zaman göster
                    top_risk = df_analiz.sort_values('Fark', ascending=False).iloc[0]
                    kpi_card("En Yüksek Risk", f"{top_risk[ad_col][:15]}", f"%{top_risk['Fark'] * 100:.1f} Artış",
                             "#f59e0b",
                             "card-orange", is_long_text=True)
                st.markdown("<br>", unsafe_allow_html=True)

                # --- SEKMELER (DÜZENLENDİ: PİYASA VERİLERİ KALDIRILDI) ---
                t_analiz, t_istatistik, t_harita, t_liste, t_haber, t_rapor = st.tabs(
                    ["📊 ANALİZ", "📈 İSTATİSTİK", "🗺️ HARİTA", "📋 LİSTE", "📰 HABERLER", "📝 RAPOR"])

                with t_analiz:
                    st.markdown("### 📈 Enflasyon Analizi ve Gelecek Tahmini")

                    # --- SENİN VERİNİN HAZIRLANMASI ---
                    trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (
                            df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                                           agirlik_col].sum() * 100} for g in gunler]
                    df_trend = pd.DataFrame(trend_data)
                    df_trend['Tarih'] = pd.to_datetime(df_trend['Tarih'])

                    # --- RESMİ VERİ ÇEKME (SADECE KUTU İÇİN) ---
                    df_resmi, msg = get_official_inflation()

                    # Varsayılan Manuel Veri (B Planı)
                    resmi_aylik_enf = 2.24
                    resmi_tarih_str = "Kasım 2024"
                    kaynak_notu = "⚠️ TCMB API bağlantısı kurulamadı, son bilinen veri gösteriliyor."
                    api_basarili = False

                    # Eğer API'den veri geldiyse üzerine yaz
                    if df_resmi is not None and not df_resmi.empty and len(df_resmi) > 1:
                        try:
                            df_resmi = df_resmi.sort_values('Tarih')
                            son_veri = df_resmi.iloc[-1]
                            onceki_veri = df_resmi.iloc[-2]
                            resmi_aylik_enf = ((son_veri['Resmi_TUFE'] / onceki_veri['Resmi_TUFE']) - 1) * 100

                            aylar = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
                                     7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}
                            resmi_tarih_str = f"{aylar[son_veri['Tarih'].month]} {son_veri['Tarih'].year}"
                            kaynak_notu = "Veriler TCMB veri tabanından çekilmiştir."
                            api_basarili = True
                        except:
                            pass

                    # Kutu Rengi Ayarı
                    border_color = "#f59e0b" if api_basarili else "#94a3b8"
                    bg_color = "#fefff5" if api_basarili else "#f1f5f9"
                    text_color = "#d97706" if api_basarili else "#475569"

                    # --- BİLGİ KUTUSU ---
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; border: 1px solid {border_color}; padding: 15px; border-radius: 10px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <div style="color: {text_color}; font-weight: bold; font-size: 14px;">🏛️ RESMİ TÜİK VERİSİ ({resmi_tarih_str})</div>
                            <div style="color: {text_color}; opacity:0.8; font-size: 11px;">{kaynak_notu}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="color: {text_color}; font-size: 24px; font-weight: 800;">%{resmi_aylik_enf:.2f}</div>
                            <div style="color: {text_color}; font-size: 10px; font-weight: 600;">AYLIK DEĞİŞİM</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if not api_basarili:
                        st.caption(f"Teknik Detay: {msg}")

                    # --- GRAFİK (RESMİ VERİ ÇIKARILDI) ---
                    with st.spinner("Gelecek tahmini yapıyor..."):
                        df_forecast = predict_inflation_prophet(df_trend)

                    current_year = df_trend['Tarih'].dt.year.max()
                    start_date = df_trend['Tarih'].min()
                    end_date_fixed = f"{current_year}-12-31"

                    fig_main = go.Figure()

                    # 1. Senin Hesapladığın Enflasyon
                    fig_main.add_trace(go.Scatter(x=df_trend['Tarih'], y=df_trend['TÜFE'], mode='lines+markers',
                                                  name='Enflasyon Monitörü', line=dict(color='#2563eb', width=3)))

                    # 2. AI Tahmini (Prophet)
                    if not df_forecast.empty:
                        future_only = df_forecast[df_forecast['ds'] > df_trend['Tarih'].max()]
                        fig_main.add_trace(
                            go.Scatter(x=future_only['ds'], y=future_only['yhat'], mode='lines', name='AI Tahmini',
                                       line=dict(color='#f59e0b', dash='dot')))
                        fig_main.add_trace(go.Scatter(x=future_only['ds'].tolist() + future_only['ds'].tolist()[::-1],
                                                      y=future_only['yhat_upper'].tolist() + future_only[
                                                          'yhat_lower'].tolist()[
                                                          ::-1], fill='toself',
                                                      fillcolor='rgba(245, 158, 11, 0.2)',
                                                      line=dict(color='rgba(255,255,255,0)'), hoverinfo="skip",
                                                      showlegend=False))

                    fig_main.update_layout(
                        template=st.session_state.plotly_template,
                        title="Enflasyon: Geçmiş, Şimdi ve Gelecek",
                        title_font=dict(color='white', size=22),
                        legend=dict(orientation="h", y=1.1, font=dict(color="white")),
                        yaxis=dict(title="TÜFE Endeksi", range=[95, 110]),
                        xaxis=dict(range=[start_date, end_date_fixed]),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_main, use_container_width=True)

                with t_istatistik:
                    st.markdown("### 📊 İstatistiksel Risk ve Dağılım Analizi")
                    col_hist, col_vol = st.columns(2)

                    # 1. Histogram
                    df_analiz['Fark_Yuzde'] = df_analiz['Fark'] * 100
                    fig_hist = px.histogram(df_analiz, x="Fark_Yuzde", nbins=40, title="📊 Zam Dağılımı Frekansı",
                                            color_discrete_sequence=['#8b5cf6'])
                    fig_hist.update_layout(
                        template=st.session_state.plotly_template,
                        title_font=dict(color='white', size=22),
                        xaxis_title="Artış Oranı (%)",
                        yaxis_title="Ürün Adedi",
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    col_hist.plotly_chart(fig_hist, use_container_width=True)

                    # 2. Volatilite Analizi
                    try:
                        fiyat_sutunlari = [c for c in pivot.columns if c != 'Kod']
                        pivot['Std'] = pivot[fiyat_sutunlari].std(axis=1)
                        pivot['Mean'] = pivot[fiyat_sutunlari].mean(axis=1)
                        pivot['Volatilite'] = (pivot['Std'] / pivot['Mean']) * 100

                        df_vol = pd.merge(df_analiz, pivot[['Kod', 'Volatilite']], on='Kod', how='left')

                        fig_vol = px.scatter(df_vol, x="Fark_Yuzde", y="Volatilite", color="Grup",
                                             hover_data=[ad_col],
                                             title="⚡ Risk Analizi: Fiyat Hareketliliği vs Değişim",
                                             labels={"Fark_Yuzde": "Fiyat Değişimi (%)",
                                                     "Volatilite": "Hareketlilik Endeksi (Risk)"})

                        fig_vol.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
                        fig_vol.add_hline(y=df_vol['Volatilite'].mean(), line_dash="dash", line_color="red",
                                          annotation_text="Ortalama Risk")

                        fig_vol.update_layout(
                            template=st.session_state.plotly_template,
                            title_font=dict(color='white', size=22),
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            legend=dict(
                                font=dict(color='white')
                            )
                        )

                        col_vol.plotly_chart(fig_vol, use_container_width=True)
                        riskli_urunler = df_vol.sort_values("Volatilite", ascending=False).head(3)
                        st.info(f"⚠️ **En Dengesiz Fiyatlar:** " + ", ".join(
                            [f"{r[ad_col]} (Risk: {r['Volatilite']:.1f})" for _, r in riskli_urunler.iterrows()]))
                    except Exception as e:
                        col_vol.error(f"Volatilite hesaplanamadı: {e}")

                with t_harita:
                    fig_tree = px.treemap(df_analiz, path=[px.Constant("Piyasa"), 'Grup', ad_col], values=agirlik_col,
                                          color='Fark', color_continuous_scale='RdYlGn_r', title="🔥 Isı Haritası")

                    fig_tree.update_traces(marker=dict(line=dict(color='black', width=1)))

                    fig_tree.update_layout(
                        template=st.session_state.plotly_template,
                        title_font=dict(color='white', size=22),
                        margin=dict(t=40, l=0, r=0, b=0),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_tree, use_container_width=True)

                with t_liste:
                    st.data_editor(
                        df_analiz[['Grup', ad_col, 'Fark', baz, son]],
                        column_config={
                            "Fark": st.column_config.ProgressColumn("Değişim Oranı", format="%.2f", min_value=-0.5,
                                                                    max_value=0.5), ad_col: "Ürün Adı",
                            "Grup": "Kategori"},
                        hide_index=True, use_container_width=True
                    )
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer: df_analiz.to_excel(writer, index=False,
                                                                                                 sheet_name='Analiz')
                    st.download_button("📥 Excel Raporunu İndir", data=output.getvalue(),
                                       file_name=f"Enflasyon_Raporu_{son}.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                with t_haber:
                    st.markdown("### 🌍 Piyasa Gündemi")
                    if st.button("Haberleri Tara ve Analiz Et", key="btn_news"):
                        with st.spinner("İnternet taranıyor, yorumlanıyor..."):
                            analysis_text, headlines = get_market_sentiment()
                            c_news1, c_news2 = st.columns([2, 1])
                            with c_news1:
                                st.markdown("#### 🧠 Piyasa Yorumu")
                                st.success(analysis_text)
                            with c_news2:
                                st.markdown("#### 🗞️ Son Başlıklar")
                                for h in headlines:
                                    st.caption(f"• {h}")

                with t_rapor:
                    st.markdown("### 📝 Profesyonel Yönetici Raporu")
                    col_gen, col_download = st.columns(2)
                    if 'report_text' not in st.session_state: st.session_state['report_text'] = ""
                    with col_gen:
                        if st.button("✍️ Raporu Yazdır", type="primary"):
                            with st.spinner("Veriler derleniyor, rapor yazılıyor..."):
                                sepet_dagilimi = df_analiz.groupby('Grup')['Fark'].mean().sort_values(ascending=False)
                                kategori_metni = ""
                                for kat, oran in sepet_dagilimi.items(): durum = "YÜKSELİŞ" if oran > 0 else "DÜŞÜŞ"; kategori_metni += f"- {kat}: %{oran * 100:.2f} ({durum})\n"
                                report_summary = f"Tarih: {datetime.now().strftime('%d-%m-%Y')}\nGenel Enflasyon: %{enf_genel:.2f}\nGıda Enflasyonu: %{enf_gida:.2f}\nEn Çok Artan: {top[ad_col]} (%{top['Fark'] * 100:.2f})\nTahmin: %{month_end_forecast:.2f}"
                                
                                # RAPOR DİLİNİ PROMPT'A EKLE
                                prompt_report = f"Sen kıdemli bir analistsin. Şu verilere göre {report_tone.upper()} formatında bir rapor yaz:\nVERİLER:\n{report_summary}\nSEKTÖREL:\n{kategori_metni}\nŞABLON: 1.GİRİŞ 2.DETAYLAR 3.ÖNGÖRÜ. İmza: Enflasyon Monitörü Ekibi"
                                
                                model_rep = genai.GenerativeModel('gemini-2.5-flash')
                                st.session_state['report_text'] = model_rep.generate_content(prompt_report).text
                                st.success("Rapor oluşturuldu!")
                    if st.session_state['report_text']:
                        st.markdown("---");
                        st.markdown(st.session_state['report_text'])
                        pdf_bytes = create_pdf_report(st.session_state['report_text'])
                        with col_download: st.download_button(label="📥 PDF Olarak İndir", data=pdf_bytes,
                                                              file_name=f"Enflasyon_Raporu_{bugun}.pdf",
                                                              mime="application/pdf")


        except Exception as e:
            st.error(f"Kritik Hata: {e}")
    st.markdown(
        '<div style="text-align:center; color:#94a3b8; font-size:11px; margin-top:50px;">VALIDASYON MUDURLUGU © 2025</div>',
        unsafe_allow_html=True)


# --- 5. ANA GİRİŞ SİSTEMİ (SADELEŞTİRİLMİŞ) ---
def main():
    dashboard_modu()


if __name__ == "__main__":
    main()
