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

# --- 1. AYARLAR VE TEMA YÖNETİMİ ---
st.set_page_config(
    page_title="Enflasyon Monitörü",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# --- Session State ile Tema Hafızası ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'  # Varsayılan açılış modu

# --- SIDEBAR AYARLARI ---
with st.sidebar:
    st.title("Ayarlar")
    # Toggle değeri session_state'den gelir
    is_dark = st.toggle("🌙 Karanlık Mod", value=(st.session_state.theme == 'dark'))

    # Eğer kullanıcı butona basarsa state güncellenir ve sayfa yenilenir
    if is_dark and st.session_state.theme == 'light':
        st.session_state.theme = 'dark'
        st.rerun()
    elif not is_dark and st.session_state.theme == 'dark':
        st.session_state.theme = 'light'
        st.rerun()


# --- CSS MOTORU ---
def apply_theme():
    # --- TEMA RENK AYARLARI (Sadece Arka Plan ve Menüler İçin) ---
    if st.session_state.theme == 'dark':
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
    else:
        colors = {
            "bg": "#FFFFFF",
            "sidebar": "#F0F2F6",
            "text": "#31333F",
            "input_bg": "#FFFFFF",
            "input_border": "#D1D5DB",
            "card_bg": "#FFFFFF",
            "border_color": "#e2e8f0"
        }
        st.session_state.plotly_template = "plotly_white"

    # --- CSS MOTORU ---
    final_css = f"""
    <style>
        /* GİZLEMELER */
        header[data-testid="stHeader"] {{ display: none !important; }}
        [data-testid="stDecoration"] {{ display: none !important; }}
        [data-testid="collapsedControl"] {{ display: none !important; }}
        .block-container {{ padding-top: 1rem !important; }}
        footer {{ visibility: hidden; }}
        .stDeployButton {{ display: none; }}

        /* GENEL SAYFA YAPISI */
        .stApp {{ background-color: {colors['bg']}; color: {colors['text']}; }}
        section[data-testid="stSidebar"] {{ background-color: {colors['sidebar']}; border-right: 1px solid {colors['border_color']}; }}
        h1, h2, h3, h4, h5, h6, p, li, label, .stMarkdown, .stRadio label {{ color: {colors['text']} !important; }}

        /* INPUT VE SELECTBOX */
        .stTextInput input, .stNumberInput input {{
            background-color: {colors['input_bg']} !important;
            color: {colors['text']} !important;
            border: 1px solid {colors['input_border']} !important;
        }}

        /* DROPDOWN VE TOAST */
        div[data-baseweb="popover"], div[data-baseweb="toast"] {{ background-color: #FFFFFF !important; border: 1px solid #ccc !important; }}
        div[data-baseweb="popover"] li, div[data-baseweb="toast"] div {{ color: #000000 !important; }}

        /* TABLOLAR */
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
            background-color: {colors['card_bg']} !important;
            border: 1px solid {colors['border_color']} !important;
        }}
        [data-testid="stDataFrame"] td, [data-testid="stDataEditor"] td {{ color: {colors['text']} !important; }}
        [data-testid="stDataFrame"] th, [data-testid="stDataEditor"] th {{
            color: {colors['text']} !important;
            background-color: {colors['sidebar']} !important;
        }}

        /* BUTONLAR */
        div.stButton > button, 
        div.stFormSubmitButton > button,
        [data-testid="stDownloadButton"] button {{
            background-color: #ffffff !important;   
            color: #000000 !important;              
            border: 2px solid #000000 !important;   
            border-radius: 8px !important;
            font-weight: bold !important;
        }}
        div.stButton > button p,
        div.stFormSubmitButton > button p,
        [data-testid="stDownloadButton"] button * {{
            color: #000000 !important;
        }}
        div.stButton > button:hover,
        div.stFormSubmitButton > button:hover,
        [data-testid="stDownloadButton"] button:hover {{
            background-color: #f0f0f0 !important;
            border-color: #000000 !important;
            color: #000000 !important;
        }}
        div.stButton > button[kind="primary"] {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 2px solid #000000 !important;
        }}

        /* METRİKLER */
        .metric-card {{ background: {colors['card_bg']} !important; border: 1px solid {colors['border_color']} !important; }}
        .metric-val, div[data-testid="stMetricValue"] {{ color: {colors['text']} !important; }}

    </style>
    """
    st.markdown(final_css, unsafe_allow_html=True)


# Temayı Uygula
apply_theme()

if "gemini" in st.secrets:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])


# --- KUR ÇEKME FONKSİYONU ---
@st.cache_data(ttl=1800)
def get_exchange_rates():
    rates = {"USD": 0.0, "EUR": 0.0, "GA": 0.0}
    try:
        url_tcmb = "https://www.tcmb.gov.tr/kurlar/today.xml"
        res = requests.get(url_tcmb, timeout=5)
        soup = BeautifulSoup(res.content, 'xml')
        rates["USD"] = float(soup.find(attrs={"CurrencyCode": "USD"}).BanknoteSelling.text)
        rates["EUR"] = float(soup.find(attrs={"CurrencyCode": "EUR"}).BanknoteSelling.text)
    except:
        pass

    try:
        url_gold = "https://bigpara.hurriyet.com.tr/altin/gram-altin-fiyati/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        res_gold = requests.get(url_gold, headers=headers, timeout=5)
        soup_gold = BeautifulSoup(res_gold.content, 'html.parser')
        fiyat_text = soup_gold.select_one("span.value").text
        temiz_fiyat = fiyat_text.replace(".", "").replace(",", ".").strip()
        rates["GA"] = float(temiz_fiyat)
    except Exception as e:
        if rates["USD"] > 0:
            rates["GA"] = (2700 * rates["USD"]) / 31.10
    return rates


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
        replacements = {
            'ı': 'i', 'İ': 'I', '\u0131': 'i',
            'ğ': 'g', 'Ğ': 'G',
            'ü': 'u', 'Ü': 'U',
            'ş': 's', 'Ş': 'S',
            'ö': 'o', 'Ö': 'O',
            'ç': 'c', 'Ç': 'C',
            'â': 'a', 'î': 'i', 'û': 'u',
            '₺': 'TL', '“': '"', '”': '"', '’': "'", '‘': "'", '–': '-', '—': '-', '…': '...'
        }
        temp_text = text
        for tr, en in replacements.items():
            temp_text = temp_text.replace(tr, en)
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

        prompt = f"""
        Aşağıdaki Türkiye gündemindeki son dakika haber başlıklarını bir Piyasa Stratejisti gibi tara.
        HABERLER:
        {news_text}
        GÖREVİN:
        1. Bu genel gündem maddeleri arasında ekonomiyi, gıda fiyatlarını veya piyasa riskini etkileyebilecek bir olay var mı?
        2. Yoksa genel gündem siyaset/magazin ağırlıklı mı?
        3. "Piyasa Havası"nı tek kelimeyle tanımla (Örn: Nötr, Gergin, İyimser, Belirsiz).
        4. En kritik 1 haberi (varsa ekonomiyle ilgili) seç ve yorumla.
        Çıktıyı kısa, net ve madde madde ver.
        """
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text, headlines
    except Exception as e:
        return f"Haberler alınamadı: {str(e)}", []


# --- GITHUB İŞLEMLERİ ---
def get_github_repo():
    try:
        return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
    except:
        return None


def github_json_oku(dosya_adi):
    repo = get_github_repo()
    if not repo: return {}
    try:
        c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        return json.loads(c.decoded_content.decode("utf-8"))
    except:
        return {}


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
    except:
        return False


# --- HIZLANDIRILMIŞ (CACHED) VERİ OKUMA ---
@st.cache_data(ttl=60, show_spinner=False)
def github_excel_oku(dosya_adi, sayfa_adi=None):
    repo = get_github_repo()
    if not repo: return pd.DataFrame()
    try:
        c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        if sayfa_adi:
            df = pd.read_excel(BytesIO(c.decoded_content), sheet_name=sayfa_adi, dtype=str)
        else:
            df = pd.read_excel(BytesIO(c.decoded_content), dtype=str)
        return df
    except:
        return pd.DataFrame()


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
        except:
            c = None;
            final = df_yeni
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            final.to_excel(w, index=False, sheet_name='Fiyat_Log')
        msg = f"Data Update"
        if c:
            repo.update_file(c.path, msg, out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, msg, out.getvalue(), branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e:
        return str(e)


# --- RESMİ ENFLASYON & PROPHET (CACHED) ---
def get_official_inflation():
    api_key = st.secrets.get("evds", {}).get("api_key")
    if not api_key: return None, "API Key Yok"
    start_date = (datetime.now() - timedelta(days=365)).strftime("%d-%m-%Y")
    end_date = datetime.now().strftime("%d-%m-%Y")
    url = f"https://evds2.tcmb.gov.tr/service/evds/series=TP.FG.J0&startDate={start_date}&endDate={end_date}&type=json&key={api_key}"
    try:
        res = requests.get(url)
        data = res.json()
        if "items" in data:
            df_evds = pd.DataFrame(data["items"])
            df_evds = df_evds[['Tarih', 'TP_FG_J0']]
            df_evds.columns = ['Tarih', 'Resmi_TUFE']
            df_evds['Tarih'] = pd.to_datetime(df_evds['Tarih'] + "-01", format="%Y-%m-%d")
            df_evds['Resmi_TUFE'] = pd.to_numeric(df_evds['Resmi_TUFE'], errors='coerce')
            return df_evds, "OK"
        return None, "Veri Yapısı Hatası"
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=3600, show_spinner=False)
def predict_inflation_prophet(df_trend):
    try:
        df_p = df_trend.rename(columns={'Tarih': 'ds', 'TÜFE': 'y'})
        m = Prophet(daily_seasonality=True, yearly_seasonality=False)
        m.fit(df_p)
        future = m.make_future_dataframe(periods=90)
        forecast = m.predict(future)
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    except Exception as e:
        st.error(f"Prophet Hatası: {str(e)}")
        return pd.DataFrame()


# --- SCRAPER (FİYAT ÇEKİCİ) ---
def temizle_fiyat(t):
    if not t: return None
    t = str(t).replace('TL', '').replace('₺', '').strip()
    t = t.replace('.', '').replace(',', '.') if ',' in t and '.' in t else t.replace(',', '.')
    try:
        return float(re.sub(r'[^\d.]', '', t))
    except:
        return None


def kod_standartlastir(k): return str(k).replace('.0', '').strip().zfill(7)


def fiyat_bul_siteye_gore(soup, url):
    fiyat = 0;
    kaynak = "";
    domain = url.lower() if url else ""
    if "migros" in domain:
        garbage = ["sm-list-page-item", ".horizontal-list-page-items-container", "app-product-carousel",
                   ".similar-products", "div.badges-wrapper"]
        for g in garbage:
            for x in soup.select(g): x.decompose()
        main_wrapper = soup.select_one(".name-price-wrapper")
        if main_wrapper:
            for sel, k in [(".price.subtitle-1", "Migros(N)"), (".single-price-amount", "Migros(S)"),
                           ("#sale-price, .sale-price", "Migros(I)")]:
                if el := main_wrapper.select_one(sel):
                    if val := temizle_fiyat(el.get_text()): return val, k
        if fiyat == 0:
            if el := soup.select_one("fe-product-price .subtitle-1, .single-price-amount"):
                if val := temizle_fiyat(el.get_text()): fiyat = val; kaynak = "Migros(G)"
            if fiyat == 0:
                if el := soup.select_one("#sale-price"):
                    if val := temizle_fiyat(el.get_text()): fiyat = val; kaynak = "Migros(GI)"
    elif "cimri" in domain:
        for sel in ["div.rTdMX", ".offer-price", "div.sS0lR", ".min-price-val"]:
            if els := soup.select(sel):
                vals = [v for v in [temizle_fiyat(e.get_text()) for e in els] if v and v > 0]
                if vals:
                    if len(vals) > 4: vals.sort(); vals = vals[1:-1]
                    fiyat = sum(vals) / len(vals);
                    kaynak = f"Cimri({len(vals)})";
                    break
        if fiyat == 0:
            if m := re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', soup.get_text()[:10000]):
                ff = sorted([temizle_fiyat(x) for x in m if temizle_fiyat(x)])
                if ff: fiyat = sum(ff[:max(1, len(ff) // 2)]) / max(1, len(ff) // 2); kaynak = "Cimri(Reg)"
    if fiyat == 0 and "migros" not in domain:
        for sel in [".product-price", ".price", ".current-price", "span[itemprop='price']"]:
            if el := soup.select_one(sel):
                if v := temizle_fiyat(el.get_text()): fiyat = v; kaynak = "Genel(CSS)"; break
    if fiyat == 0 and "migros" not in domain and "cimri" not in domain:
        if m := re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', soup.get_text()[:5000]):
            if v := temizle_fiyat(m.group(1)): fiyat = v; kaynak = "Regex"
    return fiyat, kaynak


def html_isleyici(log_callback):
    repo = get_github_repo()
    if not repo: return "GitHub Bağlantı Hatası"
    log_callback("📂 Konfigürasyon okunuyor...")
    try:
        df_conf = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)
        df_conf.columns = df_conf.columns.str.strip()
        kod_col = next((c for c in df_conf.columns if c.lower() == 'kod'), None)
        url_col = next((c for c in df_conf.columns if c.lower() == 'url'), None)
        ad_col = next((c for c in df_conf.columns if 'ad' in c.lower()), 'Madde adı')
        if not kod_col or not url_col: return "Hata: Excel sütunları eksik."
        df_conf['Kod'] = df_conf[kod_col].astype(str).apply(kod_standartlastir)
        url_map = {str(row[url_col]).strip(): row for _, row in df_conf.iterrows() if pd.notna(row[url_col])}
        veriler = [];
        islenen_kodlar = set()
        bugun = datetime.now().strftime("%Y-%m-%d");
        simdi = datetime.now().strftime("%H:%M")

        log_callback("✍️ Manuel fiyatlar kontrol ediliyor...")
        manuel_col = next((c for c in df_conf.columns if 'manuel' in c.lower()), None)
        ms = 0
        if manuel_col:
            for _, row in df_conf.iterrows():
                if pd.notna(row[manuel_col]) and str(row[manuel_col]).strip() != "":
                    try:
                        fiyat_man = float(row[manuel_col])
                        if fiyat_man > 0:
                            veriler.append({"Tarih": bugun, "Zaman": simdi, "Kod": row['Kod'], "Madde_Adi": row[ad_col],
                                            "Fiyat": fiyat_man, "Kaynak": "Manuel", "URL": row[url_col]})
                            islenen_kodlar.add(row['Kod']);
                            ms += 1
                    except:
                        pass
        if ms > 0: log_callback(f"✅ {ms} manuel fiyat alındı.")

        log_callback("📦 ZIP dosyaları taranıyor...")
        contents = repo.get_contents("", ref=st.secrets["github"]["branch"])
        zip_files = [c for c in contents if c.name.endswith(".zip") and c.name.startswith("Bolum")]
        hs = 0
        for zip_file in zip_files:
            log_callback(f"📂 Arşiv okunuyor: {zip_file.name}")
            try:
                blob = repo.get_git_blob(zip_file.sha)
                zip_data = base64.b64decode(blob.content)
                with zipfile.ZipFile(BytesIO(zip_data)) as z:
                    for file_name in z.namelist():
                        if not file_name.endswith(('.html', '.htm')): continue
                        with z.open(file_name) as f:
                            raw = f.read().decode("utf-8", errors="ignore")
                            soup = BeautifulSoup(raw, 'html.parser')
                            found_url = None
                            if c := soup.find("link", rel="canonical"): found_url = c.get("href")
                            if not found_url and (m := soup.find("meta", property="og:url")): found_url = m.get(
                                "content")
                            if found_url and str(found_url).strip() in url_map:
                                target = url_map[str(found_url).strip()]
                                if target['Kod'] in islenen_kodlar: continue
                                fiyat, kaynak = fiyat_bul_siteye_gore(soup, target[url_col])
                                if fiyat > 0:
                                    veriler.append({"Tarih": bugun, "Zaman": simdi, "Kod": target['Kod'],
                                                    "Madde_Adi": target[ad_col], "Fiyat": fiyat, "Kaynak": kaynak,
                                                    "URL": target[url_col]})
                                    islenen_kodlar.add(target['Kod']);
                                    hs += 1
            except Exception as e:
                log_callback(f"⚠️ Hata ({zip_file.name}): {str(e)}")

        if veriler:
            log_callback(f"💾 {len(veriler)} veri kaydediliyor...")
            return github_excel_guncelle(pd.DataFrame(veriler), FIYAT_DOSYASI)
        else:
            return "Veri bulunamadı."
    except Exception as e:
        return f"Hata: {str(e)}"


# --- DASHBOARD MODU ---
def dashboard_modu():
    bugun = datetime.now().strftime("%Y-%m-%d")
    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    # --- SIDEBAR ---
    with st.sidebar:
        # 1. PİYASA GÖSTERGELERİ
        try:
            rates = get_exchange_rates()
            st.markdown(
                "<h3 style='color:#1e293b; font-size:14px; margin-bottom:10px; padding-left:5px;'>💱 PİYASA GÖSTERGELERİ</h3>",
                unsafe_allow_html=True)

            st.markdown(f"""
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-bottom:8px;">
                    <div style="background:white; border:1px solid #cbd5e1; border-radius:8px; padding:10px; text-align:center;">
                        <div style="font-size:10px; color:#64748b; font-weight:700;">USD/TRY</div>
                        <div style="font-size:15px; color:#0f172a; font-weight:800;">{rates['USD']:.2f} ₺</div>
                    </div>
                    <div style="background:white; border:1px solid #cbd5e1; border-radius:8px; padding:10px; text-align:center;">
                        <div style="font-size:10px; color:#64748b; font-weight:700;">EUR/TRY</div>
                        <div style="font-size:15px; color:#0f172a; font-weight:800;">{rates['EUR']:.2f} ₺</div>
                    </div>
                </div>
                <div style="background:white; border:1px solid #cbd5e1; border-radius:8px; padding:10px; text-align:center;">
                    <div style="font-size:10px; color:#64748b; font-weight:700;">GRAM ALTIN </div>
                    <div style="font-size:15px; color:#f59e0b; font-weight:800;">{rates['GA']:.2f} ₺</div>
                </div>
                <div style="text-align:right; font-size:9px; color:#94a3b8; margin-top:5px; margin-bottom:20px;">Veriler: TCMB</div>
                <div style="border-bottom:1px solid #e2e8f0; margin-bottom:20px;"></div>
                """, unsafe_allow_html=True)
        except:
            pass

    # --- CSS: Global Styles ---
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Poppins:wght@400;600;800&family=JetBrains+Mono:wght@400&display=swap');
        .header-container { display: flex; justify-content: space-between; align-items: center; padding: 20px 30px; background: white; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); border-bottom: 4px solid #3b82f6; }
        .app-title { font-family: 'Poppins', sans-serif; font-size: 32px; font-weight: 800; letter-spacing: -1px; background: linear-gradient(90deg, #0f172a 0%, #3b82f6 50%, #0f172a 100%); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: shine 5s linear infinite; }
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

        /* Metric Card Styles */
        .metric-card { padding: 24px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.03); position: relative; overflow: hidden; transition: all 0.3s ease; }
        .metric-card:hover { transform: translateY(-5px); box-shadow: 0 20px 40px rgba(59, 130, 246, 0.15); border-color: #3b82f6; }
        .metric-card::before { content: ''; position: absolute; top: 0; left: 0; width: 6px; height: 100%; }
        .card-blue::before { background: #3b82f6; } .card-purple::before { background: #8b5cf6; } .card-emerald::before { background: #10b981; } .card-orange::before { background: #f59e0b; }
        .metric-label { color: #64748b; font-size: 13px; font-weight: 700; text-transform: uppercase; margin-bottom: 5px; }
        .metric-val { color: #1e293b; font-size: 36px; font-weight: 800; font-family: 'Poppins', sans-serif; letter-spacing: -1px; }
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
            <div id="live_clock_js" style="color:#0f172a; font-size:16px; font-weight:800; font-family:'JetBrains Mono', monospace;">{tr_time_start.strftime('%d %B %Y, %H:%M:%S')}</div>
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

                # --- KAYAN YAZI (TICKER) ---
                if len(gunler) >= 2:
                    dunku_tarih = gunler[-2]
                    bugunku_tarih = gunler[-1]
                    df_analiz['Gunluk_Degisim'] = (df_analiz[bugunku_tarih] / df_analiz[dunku_tarih]) - 1
                else:
                    df_analiz['Gunluk_Degisim'] = 0

                inc = df_analiz.sort_values('Gunluk_Degisim', ascending=False).head(5)
                dec = df_analiz.sort_values('Gunluk_Degisim', ascending=True).head(5)

                if not inc.empty:
                    daily_risk_row = inc.iloc[0]
                    daily_risk_name = daily_risk_row[ad_col]
                    daily_risk_rate = daily_risk_row['Gunluk_Degisim']
                else:
                    daily_risk_name = "-"
                    daily_risk_rate = 0

                items = []
                for _, r in inc.iterrows():
                    if r['Gunluk_Degisim'] > 0:
                        items.append(
                            f"<span style='color:#f87171'>▲ {r[ad_col]} %{r['Gunluk_Degisim'] * 100:.1f}</span>")
                for _, r in dec.iterrows():
                    if r['Gunluk_Degisim'] < 0:
                        items.append(
                            f"<span style='color:#4ade80'>▼ {r[ad_col]} %{r['Gunluk_Degisim'] * 100:.1f}</span>")

                if not items: items.append("Piyasada son 24 saatte önemli bir fiyat değişimi olmadı.")

                st.markdown(
                    f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;&nbsp; • &nbsp;&nbsp; ".join(items)}</div></div></div>',
                    unsafe_allow_html=True)

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
                    kpi_card("Ay Sonu Beklentisi", f"%{month_end_forecast:.2f}", f"🗓️ {days_left} gün kaldı", "#8b5cf6",
                             "card-purple")
                with c4:
                    kpi_card("En Yüksek Risk (24s)", f"{daily_risk_name[:15]}", f"%{daily_risk_rate * 100:.1f} Artış",
                             "#f59e0b",
                             "card-orange", is_long_text=True)
                st.markdown("<br>", unsafe_allow_html=True)

                # --- SEKMELER (Sepet ve Alarm Kaldırıldı) ---
                t_analiz, t_istatistik, t_harita, t_firsat, t_liste, t_haber, t_rapor = st.tabs(
                    ["📊 ANALİZ", "📈 İSTATİSTİK", "🗺️ HARİTA", "📉 PİYASA VERİLERİ", "📋 LİSTE", "📰 HABERLER",
                     "📝 RAPOR"])

                with t_analiz:
                    st.markdown("### 📈 Enflasyon Momentum Analizi ve Gelecek Tahmini")
                    trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (
                            df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                                           agirlik_col].sum() * 100} for g in gunler]
                    df_trend = pd.DataFrame(trend_data)
                    df_trend['Tarih'] = pd.to_datetime(df_trend['Tarih'])
                    df_resmi, msg = get_official_inflation()

                    with st.spinner("Gelecek tahmini yapıyor..."):
                        df_forecast = predict_inflation_prophet(df_trend)

                    current_year = df_trend['Tarih'].dt.year.max()
                    start_date = df_trend['Tarih'].min()
                    end_date_fixed = f"{current_year}-12-31"

                    fig_main = go.Figure()
                    fig_main.add_trace(go.Scatter(x=df_trend['Tarih'], y=df_trend['TÜFE'], mode='lines+markers',
                                                  name='Enflasyon Monitörü', line=dict(color='#2563eb', width=3)))
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
                    if df_resmi is not None and not df_resmi.empty:
                        fig_main.add_trace(
                            go.Scatter(x=df_resmi['Tarih'], y=df_resmi['Resmi_TUFE'], mode='lines+markers',
                                       name='Resmi TÜİK', line=dict(color='#ef4444', width=2),
                                       marker=dict(symbol='square')))

                    fig_main.update_layout(
                        template=st.session_state.plotly_template,
                        title="Enflasyon: Geçmiş, Şimdi ve Gelecek",
                        title_font=dict(color='white', size=22),
                        legend=dict(orientation="h", y=1.1, font=dict(color="white")),
                        yaxis=dict(title="TÜFE Endeksi", range=[95, 105]),
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

                with t_firsat:
                    st.markdown("### 🛍️ Piyasadaki Benzer Ürünler")
                    st.info("Piyasadaki Benzer ürün fiyatlarını anlık tarar.")
                    product_list = sorted(df_analiz[ad_col].unique())
                    selected_product = st.selectbox("Hangi ürünü tarayalım?", product_list)
                    if st.button(f"Piyasa Fiyatlarını Çek", type="primary"):
                        try:
                            my_record = df_analiz[df_analiz[ad_col] == selected_product].iloc[0]
                            my_price = my_record[son]
                        except:
                            my_price = 0
                        st.metric("Senin Fiyatın", f"{my_price:.2f} TL")
                        results_data = []
                        target_url = f"https://www.google.com/search?q={selected_product}&tbm=shop&hl=tr&gl=TR"
                        with st.spinner("Google Taranıyor..."):
                            try:
                                chrome_options = Options()
                                chrome_options.add_argument("--headless")
                                chrome_options.add_argument("--no-sandbox")
                                chrome_options.add_argument("--disable-dev-shm-usage")
                                chrome_options.add_argument("--disable-gpu")
                                chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                                chrome_options.add_experimental_option('useAutomationExtension', False)
                                chrome_options.add_argument(
                                    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

                                chrome_path = shutil.which("chromium") or shutil.which(
                                    "chromium-browser") or shutil.which("google-chrome")
                                if chrome_path: chrome_options.binary_location = chrome_path

                                driver_path = shutil.which("chromedriver") or shutil.which(
                                    "chromium-driver") or "/usr/bin/chromedriver"
                                if not driver_path:
                                    st.error("⚠️ Sürücü bulunamadı. packages.txt dosyasını kontrol et.")
                                else:
                                    service = Service(executable_path=driver_path)
                                    driver = webdriver.Chrome(service=service, options=chrome_options)
                                    driver.get(target_url)
                                    try:
                                        wait = WebDriverWait(driver, 5)
                                        consent_buttons = driver.find_elements(By.XPATH,
                                                                               "//button[contains(., 'Kabul') or contains(., 'Accept') or contains(., 'Agree')]")
                                        if consent_buttons: consent_buttons[0].click(); time.sleep(2)
                                    except:
                                        pass
                                    time.sleep(3)
                                    page_source = driver.page_source
                                    driver.quit()
                                    soup = BeautifulSoup(page_source, "html.parser")

                                    cards = soup.find_all(attrs={"aria-label": re.compile(r"Şu Anki Fiyat:")})
                                    if not cards: price_elements = soup.find_all(string=re.compile(r"(₺|TL)\s*\d+"))

                                    for card in cards:
                                        raw_text = card['aria-label']
                                        raw_text = raw_text.replace(u'\xa0', ' ').strip()
                                        price_pattern = r"(?:₺\s?)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})(?:\s?TL)?"
                                        matches = list(re.finditer(price_pattern, raw_text))

                                        if matches:
                                            best_match = matches[0]
                                            p_price_str = best_match.group(1)
                                            try:
                                                clean_price = float(p_price_str.replace('.', '').replace(',', '.'))
                                            except:
                                                clean_price = 0
                                            if clean_price < 5 and len(matches) > 1:
                                                best_match = matches[1]
                                                p_price_str = best_match.group(1)
                                                try:
                                                    clean_price = float(p_price_str.replace('.', '').replace(',', '.'))
                                                except:
                                                    pass
                                            start, end = best_match.span()
                                            p_name = raw_text[:start].strip().rstrip('.').rstrip(':').replace(
                                                "Şu Anki Fiyat", "").strip()
                                            p_vendor_raw = raw_text[end:].strip()
                                            p_vendor = re.sub(r'^(TL|₺|\.|,)\s*', '', p_vendor_raw)
                                            p_vendor = p_vendor.replace("ve daha fazlası", "").replace(
                                                "ve diğer satıcılar", "").strip()
                                            if len(p_vendor) > 30: p_vendor = p_vendor.split('.')[0]
                                            if not p_name or len(p_name) < 2: continue
                                            if not p_vendor or len(p_vendor) < 2: continue
                                            if p_name.replace('.', '').replace(',', '').isdigit(): continue

                                            results_data.append({
                                                "Ürün": p_name,
                                                "Fiyat_Etiketi": p_price_str + " TL",
                                                "Fiyat_Sayi": clean_price,
                                                "Satıcı": p_vendor
                                            })

                                    if results_data:
                                        df_res = pd.DataFrame(results_data).sort_values("Fiyat_Sayi")
                                        for _, row in df_res.iterrows():
                                            is_cheaper = row['Fiyat_Sayi'] < my_price and row['Fiyat_Sayi'] > 0
                                            card_bg = "#ecfdf5" if is_cheaper else "#ffffff"
                                            border_col = "#10b981" if is_cheaper else "#e2e8f0"
                                            st.markdown(f"""
                                            <div style="background:{card_bg}; border:1px solid {border_col}; padding:15px; border-radius:10px; margin-bottom:10px;">
                                                <div style="font-weight:bold; color:#1e293b;">{row['Ürün']}</div>
                                                <div style="display:flex; justify-content:space-between; margin-top:5px;">
                                                    <div style="color:#64748b;">🏪 {row['Satıcı']}</div>
                                                    <div style="font-weight:800; color:#0f172a;">{row['Fiyat_Etiketi']}</div>
                                                </div>
                                            </div>""", unsafe_allow_html=True)
                                    else:
                                        st.warning("Veri okunamadı.")
                            except Exception as e:
                                st.error(f"Sistem Hatası: {e}")

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
                                prompt_report = f"Sen kıdemli bir analistsin. Şu verilere göre PROFESYONEL bir rapor yaz:\nVERİLER:\n{report_summary}\nSEKTÖREL:\n{kategori_metni}\nŞABLON: 1.GİRİŞ 2.DETAYLAR 3.ÖNGÖRÜ. İmza: Enflasyon Monitörü Ekibi"
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
        '<div style="text-align:center; color:#94a3b8; font-size:11px; margin-top:50px;">DESIGNED BY FATIH ARSLAN © 2025</div>',
        unsafe_allow_html=True)


# --- 5. ANA GİRİŞ SİSTEMİ (SADELEŞTİRİLMİŞ) ---
def main():
    dashboard_modu()


if __name__ == "__main__":
    main()