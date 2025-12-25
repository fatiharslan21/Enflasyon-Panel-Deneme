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
import tempfile

# --- 1. AYARLAR VE TEMA YÖNETİMİ ---
st.set_page_config(
    page_title="Enflasyon Monitörü",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# --- CSS MOTORU (SADECE DARK MODE) ---
# --- CSS MOTORU (SADECE DARK MODE) ---
def apply_theme():
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
        @media (min-width: 768px) {{
            section[data-testid="stSidebar"] {{
                width: 400px !important;
                min-width: 400px !important;
                max-width: 400px !important;
                display: block !important;
            }}
            [data-testid="collapsedControl"] {{ display: none !important; }}
        }}

        @media (max-width: 768px) {{
            section[data-testid="stSidebar"] {{
                display: none !important;
                width: 0px !important;
            }}
            [data-testid="collapsedControl"] {{
                display: none !important;
            }}
            .block-container {{
                padding-top: 1rem !important;
                max-width: 100% !important;
            }}
        }}

        div[class*="viewerBadge"] {{ display: none !important; }}
        footer {{ visibility: hidden !important; display: none !important; height: 0px !important; }}
        #MainMenu {{ visibility: hidden !important; display: none !important; }}
        header {{ visibility: hidden !important; }}
        header[data-testid="stHeader"] {{ display: none !important; }}
        [data-testid="stDecoration"] {{ display: none !important; }}
        .stDeployButton {{ display: none !important; }}

        .stApp {{ background-color: {colors['bg']}; color: {colors['text']}; }}
        section[data-testid="stSidebar"] {{ background-color: {colors['sidebar']}; border-right: 1px solid {colors['border_color']}; }}
        
        h1, h2, h3, h4, h5, h6, p, li, label, .stMarkdown, .stRadio label {{ color: {colors['text']} !important; }}

        .stTextInput input, .stNumberInput input {{
            background-color: {colors['input_bg']} !important;
            color: {colors['text']} !important;
            border: 1px solid {colors['input_border']} !important;
        }}

        div[data-baseweb="popover"], div[data-baseweb="toast"] {{ background-color: #1A1C24 !important; border: 1px solid #414141 !important; }}
        div[data-baseweb="popover"] li, div[data-baseweb="toast"] div {{ color: #FAFAFA !important; }}

        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
            background-color: {colors['card_bg']} !important;
            border: 1px solid {colors['border_color']} !important;
        }}
        [data-testid="stDataFrame"] td, [data-testid="stDataEditor"] td {{ color: {colors['text']} !important; }}
        [data-testid="stDataFrame"] th, [data-testid="stDataEditor"] th {{
            color: {colors['text']} !important;
            background-color: {colors['sidebar']} !important;
        }}

        /* BUTON STİLLERİ (GÜNCELLENDİ) */
        div.stButton > button, 
        div.stFormSubmitButton > button,
        [data-testid="stDownloadButton"] button {{
            background-color: #FFFFFF !important;   /* Arka plan BEYAZ */
            color: #000000 !important;              /* Yazı SİYAH */
            border: 2px solid #FFFFFF !important;      
            border-radius: 8px !important;
            font-weight: bold !important;
        }}
        
        /* Buton Hover (Üzerine Gelince) */
        div.stButton > button:hover,
        div.stFormSubmitButton > button:hover,
        [data-testid="stDownloadButton"] button:hover {{
            background-color: #E0E0E0 !important;   /* Hafif gri */
            border-color: #E0E0E0 !important;
            color: #000000 !important;
        }}

        /* İÇERİKTEKİ YAZILARI ZORLA SİYAH YAP (SORUNUN ÇÖZÜMÜ) */
        div.stButton > button *, 
        div.stFormSubmitButton > button *,
        [data-testid="stDownloadButton"] button * {{
            color: #000000 !important;
        }}

        div.stButton > button[kind="primary"] {{
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #FFFFFF !important;
        }}

        .metric-card {{ background: {colors['card_bg']} !important; border: 1px solid {colors['border_color']} !important; }}
        .metric-val, div[data-testid="stMetricValue"] {{ color: {colors['text']} !important; }}
    </style>
    """
    st.markdown(final_css, unsafe_allow_html=True)


apply_theme()

if "gemini" in st.secrets:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])


# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"


# --- PDF RAPOR MOTORU (YENİLENMİŞ - TÜRKÇE VE GÖRSEL DESTEKLİ) ---
import os
import urllib.request

# --- PROFESYONEL PDF MOTORU (Türkçe Font & Markdown Destekli) ---
class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.primary_color = (44, 62, 80)    # Koyu Lacivert (Kurumsal)
        self.secondary_color = (231, 76, 60) # Vurgu Kırmızısı
        self.text_color = (50, 50, 50)       # Koyu Gri (Okunabilirlik için)
        
        # 1. Türkçe Destekli Fontu Otomatik İndir ve Yükle
        self.font_family = 'Roboto'
        self.download_and_register_font('Roboto-Regular.ttf', 'https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf')
        self.download_and_register_font('Roboto-Bold.ttf', 'https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf', style='B')
        
    def download_and_register_font(self, filename, url, style=''):
        if not os.path.exists(filename):
            try:
                urllib.request.urlretrieve(url, filename)
            except:
                pass # İndirme başarısızsa varsayılana döner
        
        try:
            self.add_font(self.font_family, style, filename, uni=True)
        except:
            # Font yüklenemezse Arial'a geri dön (Yedek plan)
            self.font_family = 'Arial'

    def header(self):
        if self.page_no() > 1:
            self.set_font(self.font_family, 'B', 10)
            self.set_text_color(*self.primary_color)
            self.cell(0, 10, "ENFLASYON MONITORU", 0, 0, 'L')
            
            self.set_font(self.font_family, '', 8)
            self.set_text_color(128, 128, 128)
            tarih_str = datetime.now().strftime("%d.%m.%Y")
            self.cell(0, 10, f'Rapor Tarihi: {tarih_str}', 0, 1, 'R')
            self.line(10, 20, 200, 20)
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family, '', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, label):
        self.ln(5)
        self.set_font(self.font_family, 'B', 14)
        self.set_text_color(*self.primary_color)
        self.cell(0, 10, str(label), 0, 1, 'L')
        self.ln(2)

    def write_markdown(self, text):
        """
        Metin içindeki **kalın** işaretlerini algılar ve stili değiştirir.
        Örnek: "Bu bir **önemli** kelimedir." -> PDF'te "önemli" kelimesi bold olur.
        """
        if not text: return
        
        self.set_text_color(*self.text_color)
        self.set_font(self.font_family, '', 11)
        
        # Satır satır işle
        lines = str(text).split('\n')
        for line in lines:
            if not line.strip():
                self.ln(5)
                continue
            
            # Markdown parçalarını (**) ayır
            parts = line.split('**')
            
            for i, part in enumerate(parts):
                if i % 2 == 1: 
                    # Çift indeksler (1, 3, 5...) ** işaretleri arasındadır -> KALIN YAZ
                    self.set_font(self.font_family, 'B', 11)
                    self.write(6, part)
                else:
                    # Tek indeksler normal yazıdır -> NORMAL YAZ
                    self.set_font(self.font_family, '', 11)
                    self.write(6, part)
            
            self.ln(6) # Satır sonu

    def create_cover(self, date_str, rate_val):
        self.add_page()
        # Arka Plan
        self.set_fill_color(*self.primary_color)
        self.rect(0, 0, 210, 80, 'F')
        
        self.set_y(25)
        self.set_font(self.font_family, 'B', 28)
        self.set_text_color(255, 255, 255)
        self.cell(0, 15, "PIYASA & ENFLASYON", 0, 1, 'C')
        self.cell(0, 15, "STRATEJI RAPORU", 0, 1, 'C')
        
        self.ln(40)
        
        # Ana Rakam (Kırmızı Vurgulu)
        self.set_font(self.font_family, 'B', 65)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 30, f"%{rate_val}", 0, 1, 'C')
        
        self.set_font(self.font_family, 'B', 14)
        self.set_text_color(80, 80, 80)
        self.cell(0, 10, "AYLIK ENFLASYON GÖSTERGESİ", 0, 1, 'C')
        
        self.ln(20)
        self.set_font(self.font_family, '', 12)
        aciklama = f"Bu rapor, {date_str} dönemi için yapay zeka destekli piyasa analiz sistemi tarafından oluşturulmuştur."
        self.multi_cell(0, 6, aciklama, 0, 'C')

    def add_plot_image(self, plot_bytes, title="Grafik"):
        if plot_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                tmpfile.write(plot_bytes)
                tmpfile_path = tmpfile.name
            
            self.ln(5)
            self.set_font(self.font_family, 'B', 11)
            self.set_text_color(*self.primary_color)
            self.cell(0, 8, title, 0, 1, 'L')
            
            try:
                # Resmi ortala
                x_pos = (210 - 180) / 2
                self.image(tmpfile_path, x=x_pos, w=180)
            except:
                pass
            self.ln(5)

    def create_table(self, df):
        self.set_font(self.font_family, 'B', 9)
        self.set_text_color(255, 255, 255)
        self.set_fill_color(*self.primary_color)
        
        cols = df.columns
        col_width = 190 / len(cols) if len(cols) > 0 else 190
        
        for col in cols:
            self.cell(col_width, 9, str(col), 1, 0, 'C', True)
        self.ln()
        
        self.set_font(self.font_family, '', 8)
        self.set_text_color(0, 0, 0)
        
        for i, row in df.iterrows():
            # Satır renklendirme (Zebra deseni)
            bg_color = 245 if i % 2 == 0 else 255
            self.set_fill_color(bg_color, bg_color, bg_color)
            
            for col in cols:
                val = row[col]
                val_str = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
                self.cell(col_width, 8, val_str, 1, 0, 'C', True)
            self.ln()

# --- GELİŞMİŞ PDF FONKSİYONU ---
def create_pdf_report_advanced(text_content, df_table, figures, manset_oran, date_str):
    pdf = PDFReport()
    
    # 1. KAPAK
    pdf.create_cover(date_str, f"{manset_oran:.2f}")
    
    # 2. METİN RAPORU (Markdown Destekli)
    pdf.add_page()
    pdf.chapter_title("YONETICI OZETI")
    pdf.write_markdown(text_content) # Artık chapter_body yerine bunu kullanıyoruz
    
    # 3. GRAFİKLER
    if figures:
        pdf.add_page()
        pdf.chapter_title("PIYASA GRAFIKLERI")
        for title, fig in figures.items():
            try:
                img_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
                pdf.add_plot_image(img_bytes, title=title)
            except: pass

    # 4. TABLO
    if not df_table.empty:
        pdf.add_page()
        pdf.chapter_title("DETAYLI FIYAT HAREKETLERI")
        cols_to_keep = [c for c in df_table.columns if 'Kod' not in c and 'URL' not in c]
        pdf.create_table(df_table[cols_to_keep].head(25))

    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- HABER MOTORU ---
def get_market_sentiment():
    rss_url = "https://news.google.com/rss/search?q=ekonomi+enflasyon+faiz+borsa+dolar&hl=tr&gl=TR&ceid=TR:tr"
    try:
        feed = feedparser.parse(rss_url)
        headlines = [entry.title for entry in feed.entries[:12]]
        news_text = "\n".join([f"- {h}" for h in headlines])

        prompt = f"""
        Aşağıdaki haber başlıkları Türkiye ekonomi gündemine aittir.
        Bir Kıdemli Piyasa Analisti olarak bu başlıkları süz ve yorumla.
        
        HABERLER:
        {news_text}
        
        GÖREVİN:
        1. Başlıklar arasından SADECE ekonomi, finans, kur ve enflasyon ile doğrudan ilgili olanları dikkate al.
        2. "Piyasa Havası"nı (Market Sentiment) tek kelimeyle tanımla (Örn: Risk İştahı Yüksek, Tedirgin, Bekle-Gör, Negatif).
        3. En kritik 3 ekonomik gelişmeyi maddeler halinde özetle.
        4. Bu haberlerin kısa vadeli enflasyon veya döviz kuru üzerindeki olası etkisini 1 cümle ile belirt.
        
        Çıktıyı profesyonel, kısa ve net ver. Magazin veya siyasi polemikleri yoksay.
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


# --- RESMİ ENFLASYON & PROPHET ---
def get_official_inflation():
    api_key = st.secrets.get("evds", {}).get("api_key")
    if not api_key: return None, "API Key Yok"

    start_date = (datetime.now() - timedelta(days=365)).strftime("%d-%m-%Y")
    end_date = datetime.now().strftime("%d-%m-%Y")
    url = f"https://evds2.tcmb.gov.tr/service/evds/series=TP.FG.J0&startDate={start_date}&endDate={end_date}&type=json"
    headers = {'User-Agent': 'Mozilla/5.0', 'key': api_key, 'Accept': 'application/json'}

    try:
        url_with_key = f"{url}&key={api_key}"
        res = requests.get(url_with_key, headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            data = res.json()
            if "items" in data:
                df_evds = pd.DataFrame(data["items"])
                df_evds = df_evds[['Tarih', 'TP_FG_J0']]
                df_evds.columns = ['Tarih', 'Resmi_TUFE']
                df_evds['Tarih'] = pd.to_datetime(df_evds['Tarih'] + "-01", format="%Y-%m-%d")
                df_evds['Resmi_TUFE'] = pd.to_numeric(df_evds['Resmi_TUFE'], errors='coerce')
                return df_evds, "OK"
            else:
                return None, "Boş Veri"
        else:
            return None, f"HTTP {res.status_code}"
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


# --- SCRAPER ---
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
    fiyat = 0; kaynak = ""; domain = url.lower() if url else ""
    if "migros" in domain:
        garbage = ["sm-list-page-item", ".horizontal-list-page-items-container", "app-product-carousel", ".similar-products", "div.badges-wrapper"]
        for g in garbage:
            for x in soup.select(g): x.decompose()
        main_wrapper = soup.select_one(".name-price-wrapper")
        if main_wrapper:
            for sel, k in [(".price.subtitle-1", "Migros(N)"), (".single-price-amount", "Migros(S)"), ("#sale-price, .sale-price", "Migros(I)")]:
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
                    fiyat = sum(vals) / len(vals); kaynak = f"Cimri({len(vals)})"; break
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
        veriler = []; islenen_kodlar = set()
        bugun = datetime.now().strftime("%Y-%m-%d"); simdi = datetime.now().strftime("%H:%M")

        log_callback("✍️ Manuel fiyatlar kontrol ediliyor...")
        manuel_col = next((c for c in df_conf.columns if 'manuel' in c.lower()), None)
        ms = 0
        if manuel_col:
            for _, row in df_conf.iterrows():
                if pd.notna(row[manuel_col]) and str(row[manuel_col]).strip() != "":
                    try:
                        fiyat_man = float(row[manuel_col])
                        if fiyat_man > 0:
                            veriler.append({"Tarih": bugun, "Zaman": simdi, "Kod": row['Kod'], "Madde_Adi": row[ad_col], "Fiyat": fiyat_man, "Kaynak": "Manuel", "URL": row[url_col]})
                            islenen_kodlar.add(row['Kod']); ms += 1
                    except: pass
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
                            if not found_url and (m := soup.find("meta", property="og:url")): found_url = m.get("content")
                            if found_url and str(found_url).strip() in url_map:
                                target = url_map[str(found_url).strip()]
                                if target['Kod'] in islenen_kodlar: continue
                                fiyat, kaynak = fiyat_bul_siteye_gore(soup, target[url_col])
                                if fiyat > 0:
                                    veriler.append({"Tarih": bugun, "Zaman": simdi, "Kod": target['Kod'], "Madde_Adi": target[ad_col], "Fiyat": fiyat, "Kaynak": kaynak, "URL": target[url_col]})
                                    islenen_kodlar.add(target['Kod']); hs += 1
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
    colors = {"bg": "#0E1117", "sidebar": "#262730", "text": "#FAFAFA", "input_bg": "#1A1C24", "input_border": "#4A4A4A", "card_bg": "#1A1C24", "border_color": "#414141"}

    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    # SIDEBAR
    with st.sidebar:
        st.title("💎 CANLI PİYASA")
        tv_theme = "dark"
        symbols = [{"s": "FX:USDTRY", "d": "Dolar / TL"}, {"s": "FX:EURTRY", "d": "Euro / TL"}, {"s": "FX_IDC:XAUTRYG", "d": "Gram Altın"}, {"s": "TVC:UKOIL", "d": "Brent Petrol"}, {"s": "BINANCE:BTCUSDT", "d": "Bitcoin ($)"}]
        widgets_html = ""
        for sym in symbols:
            widgets_html += f"""
            <div class="tradingview-widget-container" style="margin-bottom: 10px;">
              <div class="tradingview-widget-container__widget"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
              {{ "symbol": "{sym['s']}", "width": "100%", "height": 110, "locale": "tr", "dateRange": "12M", "colorTheme": "{tv_theme}", "isTransparent": true, "autosize": true, "largeChartUrl": "", "chartOnly": false, "noTimeScale": true }}
              </script>
            </div>
            """
        components.html(f'<div style="display:flex; flex-direction:column; overflow:hidden;">{widgets_html}</div>', height=len(symbols)*120)
        st.markdown("---")
        st.markdown("### 🇹🇷 BIST TÜM PİYASA")
        all_stocks_html = """
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-screener.js" async>
          { "width": "100%", "height": 600, "defaultColumn": "overview", "defaultScreen": "general", "market": "turkey", "showToolbar": false, "colorTheme": "dark", "locale": "tr", "isTransparent": true }
          </script>
        </div>
        """
        components.html(all_stocks_html, height=600)

    # CSS Header
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Poppins:wght@400;600;800&family=JetBrains+Mono:wght@400&display=swap');
        .header-container {{ display: flex; justify-content: space-between; align-items: center; padding: 20px 30px; background: #1A1C24; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); border-bottom: 4px solid #3b82f6; }}
        .app-title {{ font-family: 'Poppins', sans-serif; font-size: 32px; font-weight: 800; letter-spacing: -1px; background: linear-gradient(90deg, #FFFFFF 0%, #3b82f6 50%, #FFFFFF 100%); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: shine 5s linear infinite; }}
        @keyframes shine {{ to {{ background-position: 200% center; }} }}
        .update-btn-container button {{ background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important; color: white !important; font-weight: 700 !important; font-size: 16px !important; border-radius: 12px !important; height: 60px !important; border: none !important; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3); transition: all 0.3s ease !important; animation: pulse 2s infinite; }}
        .update-btn-container button:hover {{ transform: scale(1.02); box-shadow: 0 10px 25px rgba(37, 99, 235, 0.5); animation: none; }}
        @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7); }} 70% {{ box-shadow: 0 0 0 10px rgba(37, 99, 235, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }} }}
        .ticker-wrap {{ width: 100%; overflow: hidden; background: linear-gradient(90deg, #0f172a, #1e293b); color: white; padding: 12px 0; margin-bottom: 25px; border-radius: 12px; }}
        .ticker {{ display: inline-block; animation: ticker 45s linear infinite; white-space: nowrap; }}
        .ticker-item {{ display: inline-block; padding: 0 2rem; font-weight: 500; font-size: 14px; font-family: 'JetBrains Mono', monospace; }}
        @keyframes ticker {{ 0% {{ transform: translateX(100%); }} 100% {{ transform: translateX(-100%); }} }}
        .bot-bubble {{ background: #1A1C24; border-left: 4px solid #3b82f6; padding: 15px; border-radius: 0 8px 8px 8px; margin-top: 15px; color: #FAFAFA; font-size: 14px; line-height: 1.5; }}
        .bot-log {{ background: #1e293b; color: #4ade80; font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 15px; border-radius: 12px; height: 180px; overflow-y: auto; }}
        #live_clock_js {{ font-family: 'JetBrains Mono', monospace; color: #2563eb; }}
        .metric-card {{ padding: 24px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); position: relative; overflow: hidden; transition: all 0.3s ease; }}
        .metric-card:hover {{ transform: translateY(-5px); box-shadow: 0 20px 40px rgba(59, 130, 246, 0.15); border-color: #3b82f6; }}
        .metric-card::before {{ content: ''; position: absolute; top: 0; left: 0; width: 6px; height: 100%; }}
        .card-blue::before {{ background: #3b82f6; }} .card-purple::before {{ background: #8b5cf6; }} .card-emerald::before {{ background: #10b981; }} .card-orange::before {{ background: #f59e0b; }}
        .metric-label {{ color: #94a3b8; font-size: 13px; font-weight: 700; text-transform: uppercase; margin-bottom: 5px; }}
        .metric-val {{ color: #FAFAFA; font-size: 36px; font-weight: 800; font-family: 'Poppins', sans-serif; letter-spacing: -1px; }}
        .metric-val.long-text {{ font-size: 24px !important; line-height: 1.2; }}
    </style>
    """, unsafe_allow_html=True)

    tr_time_start = datetime.now() + timedelta(hours=3)
    header_html = f"""
    <div class="header-container">
        <div class="app-title">Enflasyon Monitörü</div>
        <div style="text-align:right;">
            <div style="color:#94a3b8; font-size:12px; font-weight:600; margin-bottom:4px;">İSTANBUL, TR</div>
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

    st.markdown('<div class="update-btn-container">', unsafe_allow_html=True)
    if st.button("🚀 SİSTEMİ GÜNCELLE VE ANALİZ ET", type="primary", use_container_width=True):
        with st.status("Veri Tabanı Güncelleniyor...", expanded=True) as status:
            st.write("📡 GitHub bağlantısı kuruluyor...")
            time.sleep(0.5)
            st.write("📦 ZIP dosyaları taranıyor...")
            log_ph = st.empty(); log_msgs = []
            def logger(m):
                log_msgs.append(f"> {m}")
                log_ph.markdown(f'<div class="bot-log">{"<br>".join(log_msgs)}</div>', unsafe_allow_html=True)
            res = html_isleyici(logger)
            status.update(label="İşlem Tamamlandı!", state="complete", expanded=False)
        if "OK" in res:
            st.cache_data.clear()
            st.toast('Veritabanı Güncellendi!', icon='🎉')
            st.success("✅ Sistem Başarıyla Senkronize Edildi!")
            time.sleep(2); st.rerun()
        elif "Veri bulunamadı" in res:
            st.warning("⚠️ Yeni fiyat verisi bulunamadı.")
        else:
            st.error(res)
    st.markdown('</div><br>', unsafe_allow_html=True)

    if not df_f.empty and not df_s.empty:
        try:
            df_s.columns = df_s.columns.str.strip()
            kod_col = next((c for c in df_s.columns if c.lower() == 'kod'), 'Kod')
            ad_col = next((c for c in df_s.columns if 'ad' in c.lower()), 'Madde adı')
            agirlik_col = next((c for c in df_s.columns if 'agirlik' in c.lower().replace('ğ', 'g').replace('ı', 'i')), 'Agirlik_2025')
            df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
            df_s['Kod'] = df_s[kod_col].astype(str).apply(kod_standartlastir)
            df_f['Tarih_DT'] = pd.to_datetime(df_f['Tarih'], errors='coerce')
            df_f = df_f.dropna(subset=['Tarih_DT']).sort_values('Tarih_DT')
            df_f['Tarih_Str'] = df_f['Tarih_DT'].dt.strftime('%Y-%m-%d')
            df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
            df_f = df_f[df_f['Fiyat'] > 0]
            pivot = df_f.pivot_table(index='Kod', columns='Tarih_Str', values='Fiyat', aggfunc='last').ffill(axis=1).bfill(axis=1).reset_index()

            if not pivot.empty:
                if 'Grup' not in df_s.columns:
                    grup_map = {"01": "Gıda", "02": "Alkol", "03": "Giyim", "04": "Konut", "05": "Ev", "06": "Sağlık", "07": "Ulaşım", "08": "İletişim", "09": "Eğlence", "10": "Eğitim", "11": "Lokanta", "12": "Çeşitli"}
                    df_s['Grup'] = df_s['Kod'].str[:2].map(grup_map).fillna("Diğer")
                df_analiz = pd.merge(df_s, pivot, on='Kod', how='left')
                if agirlik_col in df_analiz.columns:
                    df_analiz[agirlik_col] = pd.to_numeric(df_analiz[agirlik_col], errors='coerce').fillna(1)
                else:
                    df_analiz['Agirlik_2025'] = 1; agirlik_col = 'Agirlik_2025'
                
                gunler = [c for c in pivot.columns if c != 'Kod']
                if len(gunler) < 1: st.warning("Yeterli tarih verisi yok."); return
                baz, son = gunler[0], gunler[-1]
                
                endeks_genel = (df_analiz.dropna(subset=[son, baz])[agirlik_col] * (df_analiz[son] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[son, baz])[agirlik_col].sum() * 100
                enf_genel = (endeks_genel / 100 - 1) * 100
                df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
                top = df_analiz.sort_values('Fark', ascending=False).iloc[0]
                gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
                enf_gida = ((gida[son] / gida[baz] * gida[agirlik_col]).sum() / gida[agirlik_col].sum() - 1) * 100 if not gida.empty else 0
                
                dt_son = datetime.strptime(son, '%Y-%m-%d'); dt_baz = datetime.strptime(baz, '%Y-%m-%d')
                days_left = calendar.monthrange(dt_son.year, dt_son.month)[1] - dt_son.day
                month_end_forecast = enf_genel + ((enf_genel / max(dt_son.day, 1)) * days_left)
                gun_farki = (dt_son - dt_baz).days

                # Ticker
                if len(gunler) >= 2:
                    df_analiz['Gunluk_Degisim'] = (df_analiz[gunler[-1]] / df_analiz[gunler[-2]]) - 1
                else: df_analiz['Gunluk_Degisim'] = 0
                inc = df_analiz.sort_values('Gunluk_Degisim', ascending=False).head(5)
                dec = df_analiz.sort_values('Gunluk_Degisim', ascending=True).head(5)
                items = []
                for _, r in inc.iterrows():
                    if r['Gunluk_Degisim'] > 0: items.append(f"<span style='color:#f87171'>▲ {r[ad_col]} %{r['Gunluk_Degisim'] * 100:.1f}</span>")
                for _, r in dec.iterrows():
                    if r['Gunluk_Degisim'] < 0: items.append(f"<span style='color:#4ade80'>▼ {r[ad_col]} %{r['Gunluk_Degisim'] * 100:.1f}</span>")
                if not items: items.append("Piyasada son 24 saatte önemli bir fiyat değişimi olmadı.")
                st.markdown(f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;&nbsp; • &nbsp;&nbsp; ".join(items)}</div></div></div>', unsafe_allow_html=True)

                # KPI
                df_resmi, msg = get_official_inflation()
                resmi_aylik_enf = 0.0; resmi_tarih_str = "-"; resmi_alt_bilgi = "Veri Bekleniyor"
                if df_resmi is not None and not df_resmi.empty and len(df_resmi) > 1:
                    try:
                        df_resmi = df_resmi.sort_values('Tarih'); son_veri = df_resmi.iloc[-1]; onceki_veri = df_resmi.iloc[-2]
                        resmi_aylik_enf = ((son_veri['Resmi_TUFE'] / onceki_veri['Resmi_TUFE']) - 1) * 100
                        aylar = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}
                        resmi_tarih_str = f"{aylar[son_veri['Tarih'].month]} {son_veri['Tarih'].year}"
                        resmi_alt_bilgi = "TCMB/TÜİK Kaynaklı"
                    except: resmi_alt_bilgi = "Hesaplama Hatası"
                else: resmi_alt_bilgi = f"Bağlantı Sorunu: {msg}"

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
                with c1: kpi_card("Genel Enflasyon", f"%{enf_genel:.2f}", f"{gun_farki} Günlük Değişim", "#ef4444", "card-blue")
                with c2: kpi_card("Gıda Enflasyonu", f"%{enf_gida:.2f}", "Mutfak Sepeti", "#ef4444", "card-emerald")
                with c3: kpi_card("Simülasyon Beklentisi", f"%{month_end_forecast:.2f}", f"🗓️ {days_left} gün kaldı", "#8b5cf6", "card-purple")
                with c4: kpi_card("Resmi TÜİK Verisi", f"%{resmi_aylik_enf:.2f}", f"{resmi_tarih_str} Dönemi", "#f59e0b", "card-orange")
                st.markdown("<br>", unsafe_allow_html=True)

                t_analiz, t_istatistik, t_harita, t_liste, t_haber, t_rapor = st.tabs(["📊 ANALİZ", "📈 İSTATİSTİK", "🗺️ HARİTA", "📋 LİSTE", "📰 HABERLER", "📝 RAPOR"])

                # Veri Hazırlığı
                trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[agirlik_col].sum() * 100} for g in gunler]
                df_trend = pd.DataFrame(trend_data)
                df_trend['Tarih'] = pd.to_datetime(df_trend['Tarih'])
                
                with t_analiz:
                    st.markdown("### 📈 Enflasyon Analizi ve Gelecek Tahmini")
                    with st.spinner("Gelecek tahmini yapıyor..."):
                        df_forecast = predict_inflation_prophet(df_trend)
                    current_year = df_trend['Tarih'].dt.year.max(); start_date = df_trend['Tarih'].min(); end_date_fixed = f"{current_year}-12-31"
                    fig_main = go.Figure()
                    fig_main.add_trace(go.Scatter(x=df_trend['Tarih'], y=df_trend['TÜFE'], mode='lines+markers', name='Enflasyon Monitörü', line=dict(color='#2563eb', width=3)))
                    if not df_forecast.empty:
                        future_only = df_forecast[df_forecast['ds'] > df_trend['Tarih'].max()]
                        fig_main.add_trace(go.Scatter(x=future_only['ds'], y=future_only['yhat'], mode='lines', name='AI Tahmini', line=dict(color='#f59e0b', dash='dot')))
                        fig_main.add_trace(go.Scatter(x=future_only['ds'].tolist() + future_only['ds'].tolist()[::-1], y=future_only['yhat_upper'].tolist() + future_only['yhat_lower'].tolist()[::-1], fill='toself', fillcolor='rgba(245, 158, 11, 0.2)', line=dict(color='rgba(255,255,255,0)'), hoverinfo="skip", showlegend=False))
                    fig_main.update_layout(template=st.session_state.plotly_template, title="Enflasyon: Geçmiş, Şimdi ve Gelecek", title_font=dict(color='white', size=22), legend=dict(orientation="h", y=1.1, font=dict(color="white")), yaxis=dict(title="TÜFE Endeksi", range=[95, 110]), xaxis=dict(range=[start_date, end_date_fixed]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_main, use_container_width=True)

                with t_istatistik:
                    st.markdown("### 📊 İstatistiksel Risk ve Dağılım Analizi")
                    col_hist, col_vol = st.columns(2)
                    df_analiz['Fark_Yuzde'] = df_analiz['Fark'] * 100
                    fig_hist = px.histogram(df_analiz, x="Fark_Yuzde", nbins=40, title="📊 Zam Dağılımı Frekansı", color_discrete_sequence=['#8b5cf6'])
                    fig_hist.update_layout(template=st.session_state.plotly_template, title_font=dict(color='white', size=22), xaxis_title="Artış Oranı (%)", yaxis_title="Ürün Adedi", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    col_hist.plotly_chart(fig_hist, use_container_width=True)

                    try:
                        fiyat_sutunlari = [c for c in pivot.columns if c != 'Kod']
                        pivot['Std'] = pivot[fiyat_sutunlari].std(axis=1)
                        pivot['Mean'] = pivot[fiyat_sutunlari].mean(axis=1)
                        pivot['Volatilite'] = (pivot['Std'] / pivot['Mean']) * 100
                        df_vol = pd.merge(df_analiz, pivot[['Kod', 'Volatilite']], on='Kod', how='left')
                        fig_vol = px.scatter(df_vol, x="Fark_Yuzde", y="Volatilite", color="Grup", hover_data=[ad_col], title="⚡ Risk Analizi: Fiyat Hareketliliği vs Değişim", labels={"Fark_Yuzde": "Fiyat Değişimi (%)", "Volatilite": "Hareketlilik Endeksi (Risk)"})
                        fig_vol.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
                        fig_vol.add_hline(y=df_vol['Volatilite'].mean(), line_dash="dash", line_color="red", annotation_text="Ortalama Risk")
                        fig_vol.update_layout(template=st.session_state.plotly_template, title_font=dict(color='white', size=22), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', legend=dict(font=dict(color='white')))
                        col_vol.plotly_chart(fig_vol, use_container_width=True)
                        riskli_urunler = df_vol.sort_values("Volatilite", ascending=False).head(3)
                        st.info(f"⚠️ **En Dengesiz Fiyatlar:** " + ", ".join([f"{r[ad_col]} (Risk: {r['Volatilite']:.1f})" for _, r in riskli_urunler.iterrows()]))
                    except Exception as e: col_vol.error(f"Volatilite hesaplanamadı: {e}")

                with t_harita:
                    fig_tree = px.treemap(df_analiz, path=[px.Constant("Piyasa"), 'Grup', ad_col], values=agirlik_col, color='Fark', color_continuous_scale='RdYlGn_r', title="🔥 Isı Haritası")
                    fig_tree.update_traces(marker=dict(line=dict(color='black', width=1)))
                    fig_tree.update_layout(template=st.session_state.plotly_template, title_font=dict(color='white', size=22), margin=dict(t=40, l=0, r=0, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_tree, use_container_width=True)

                with t_liste:
                    st.data_editor(df_analiz[['Grup', ad_col, 'Fark', baz, son]], column_config={"Fark": st.column_config.ProgressColumn("Değişim Oranı", format="%.2f", min_value=-0.5, max_value=0.5), ad_col: "Ürün Adı", "Grup": "Kategori"}, hide_index=True, use_container_width=True)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer: df_analiz.to_excel(writer, index=False, sheet_name='Analiz')
                    st.download_button("📥 Excel Raporunu İndir", data=output.getvalue(), file_name=f"Enflasyon_Raporu_{son}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                with t_haber:
                    st.markdown("### 🌍 Ekonomi Gündemi")
                    if st.button("Haberleri Tara ve Analiz Et", key="btn_news"):
                        with st.spinner("Piyasa verileri taranıyor, yorumlanıyor..."):
                            analysis_text, headlines = get_market_sentiment()
                            c_news1, c_news2 = st.columns([2, 1])
                            with c_news1:
                                st.markdown("#### 🧠 Başekonomist Görüşü")
                                st.success(analysis_text)
                            with c_news2:
                                st.markdown("#### 🗞️ Son Başlıklar")
                                for h in headlines: st.caption(f"• {h}")

                with t_rapor:
                    st.markdown("### 📝 Stratejik Yönetim Raporu")
                    col_gen, col_download = st.columns(2)
                    
                    if 'report_text' not in st.session_state: 
                        st.session_state['report_text'] = ""
                    
                    with col_gen:
                        if st.button("✍️ Raporu Hazırla", type="primary"):
                            with st.spinner("Veriler analiz ediliyor..."):
                                sepet_dagilimi = df_analiz.groupby('Grup')['Fark'].mean().sort_values(ascending=False)
                                kategori_metni = ""
                                for kat, oran in sepet_dagilimi.items(): 
                                    durum = "YÜKSELİŞ" if oran > 0 else "DÜŞÜŞ"
                                    kategori_metni += f"- {kat}: %{oran * 100:.2f} ({durum})\n"
                                
                                report_summary = f"Tarih: {datetime.now().strftime('%d-%m-%Y')}\nGenel Enflasyon: %{enf_genel:.2f}\nGıda: %{enf_gida:.2f}"
                                
                                prompt_report = f"""
                                Bir Başekonomist olarak aşağıdaki verilerle profesyonel bir 'Piyasa Görünüm Raporu' yaz.
                                VERİLER: {report_summary}
                                DETAYLAR: {kategori_metni}
                                FORMAT: Giriş, Sektörel Analiz, Riskler ve Sonuç.
                                ÜSLUP: Resmi, finansal, tarafsız. Asla spesifik bir marka adı verme.
                                """
                                try:
                                    model_rep = genai.GenerativeModel('gemini-2.5-flash')
                                    st.session_state['report_text'] = model_rep.generate_content(prompt_report).text
                                    st.success("Analiz tamamlandı.")
                                except Exception as e:
                                    st.error("AI Bağlantı Hatası")
                                    st.session_state['report_text'] = "Veriler tabloda mevcuttur."

                    if st.session_state['report_text']:
                        st.markdown("---")
                        st.markdown(st.session_state['report_text'])
                        
                        with col_download:
                            st.write("🖨️ PDF Hazırlanıyor...")
                            try:
                                # Grafikleri Hazırla
                                figures_dict = {}
                                try:
                                    fig_pdf_trend = px.line(df_trend, x='Tarih', y='TÜFE', title='Trend Analizi')
                                    figures_dict["Trend"] = fig_pdf_trend
                                    fig_pdf_hist = px.histogram(df_analiz, x="Fark", nbins=20, title="Dagilim")
                                    figures_dict["Dagilim"] = fig_pdf_hist
                                except: pass

                                # PDF Oluştur
                                pdf_bytes = create_pdf_report_advanced(
                                    text_content=st.session_state['report_text'],
                                    df_table=df_analiz[['Grup', ad_col, 'Fark', son]].sort_values('Fark', ascending=False).head(20),
                                    figures=figures_dict,
                                    manset_oran=enf_genel,
                                    date_str=f"{datetime.now().strftime('%B %Y')}"
                                )
                                
                                # Dosya ismini de değiştirdim
                                st.download_button(
                                    label="📥 PDF Raporunu İndir", 
                                    data=pdf_bytes, 
                                    file_name=f"Enflasyon_Raporu_{bugun}.pdf", 
                                    mime="application/pdf"
                                )
                            except Exception as e:
                                st.error(f"Hata: {e}")

        except Exception as e:
            st.error(f"Kritik Hata: {e}")
    st.markdown('<div style="text-align:center; color:#94a3b8; font-size:11px; margin-top:50px;">VALIDASYON MUDURLUGU © 2025</div>', unsafe_allow_html=True)

# --- 5. ANA GİRİŞ SİSTEMİ ---
def main():
    dashboard_modu()

if __name__ == "__main__":
    main()





