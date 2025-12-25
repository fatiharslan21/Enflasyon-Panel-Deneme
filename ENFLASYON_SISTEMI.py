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
import os
import urllib.request

# --- 1. AYARLAR VE TEMA YÖNETİMİ ---
st.set_page_config(
    page_title="Enflasyon Monitörü",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

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
        .stApp {{ background-color: {colors['bg']}; color: {colors['text']}; }}
        section[data-testid="stSidebar"] {{ background-color: {colors['sidebar']}; border-right: 1px solid {colors['border_color']}; }}
        h1, h2, h3, h4, h5, h6, p, li, label, .stMarkdown, .stRadio label {{ color: {colors['text']} !important; }}
        .stTextInput input, .stNumberInput input {{
            background-color: {colors['input_bg']} !important;
            color: {colors['text']} !important;
            border: 1px solid {colors['input_border']} !important;
        }}
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
            background-color: {colors['card_bg']} !important;
            border: 1px solid {colors['border_color']} !important;
        }}
        div.stButton > button, div.stFormSubmitButton > button, [data-testid="stDownloadButton"] button {{
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 2px solid #FFFFFF !important;
            border-radius: 8px !important;
            font-weight: bold !important;
        }}
        div.stButton > button:hover, [data-testid="stDownloadButton"] button:hover {{
            background-color: #E0E0E0 !important;
            border-color: #E0E0E0 !important;
            color: #000000 !important;
        }}
        div.stButton > button *, [data-testid="stDownloadButton"] button * {{
            color: #000000 !important;
        }}
        .metric-card {{ background: {colors['card_bg']} !important; border: 1px solid {colors['border_color']} !important; }}
        .metric-val {{ color: {colors['text']} !important; }}
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


# --- 3. GELİŞMİŞ PDF MOTORU (VAKIFBANK TEMASI & SANDVİÇ MODELİ) ---
class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.font_family = 'Arial'
        self.tr_active = False
        
        # VAKIFBANK & KURUMSAL RENKLER
        self.c_sari = (253, 185, 19)   # Vakıf Sarısı
        self.c_lacivert = (0, 40, 85)  # Kurumsal Lacivert
        self.c_koyu = (30, 30, 30)     # Antrasit
        self.c_gri = (100, 100, 100)   # Gri
        
        # Font Yükleme
        self.font_path = 'Roboto-Regular.ttf'
        self.font_bold_path = 'Roboto-Bold.ttf'
        if self._try_download_font():
            try:
                self.add_font('Roboto', '', self.font_path, uni=True)
                self.add_font('Roboto', 'B', self.font_bold_path, uni=True)
                self.font_family = 'Roboto'
                self.tr_active = True
            except: pass

    def _try_download_font(self):
        if os.path.exists(self.font_path) and os.path.exists(self.font_bold_path): return True
        try:
            import requests
            url_base = "https://github.com/google/fonts/raw/main/apache/roboto/"
            r1 = requests.get(url_base + "Roboto-Regular.ttf", timeout=5); 
            with open(self.font_path, 'wb') as f: f.write(r1.content)
            r2 = requests.get(url_base + "Roboto-Bold.ttf", timeout=5); 
            with open(self.font_bold_path, 'wb') as f: f.write(r2.content)
            return True
        except: return False

    def fix_text(self, text):
        if text is None: return ""
        text = str(text)
        if self.tr_active: return text
        tr_map = {'Ğ': 'G', 'ğ': 'g', 'Ş': 'S', 'ş': 's', 'İ': 'I', 'ı': 'i', 'Ö': 'O', 'ö': 'o', 'Ü': 'U', 'ü': 'u', 'Ç': 'C', 'ç': 'c'}
        for k, v in tr_map.items(): text = text.replace(k, v)
        return text.encode('latin-1', 'replace').decode('latin-1')

    def header(self):
        if self.page_no() > 1:
            self.set_font(self.font_family, 'B', 10)
            self.set_text_color(*self.c_koyu)
            self.cell(0, 10, self.fix_text("ENFLASYON MONİTÖRÜ"), 0, 0, 'L')
            self.set_font(self.font_family, '', 8)
            self.set_text_color(*self.c_gri)
            tarih = datetime.now().strftime("%d.%m.%Y")
            self.cell(0, 10, self.fix_text(f'Rapor Tarihi: {tarih}'), 0, 1, 'R')
            self.set_draw_color(*self.c_sari)
            self.set_line_width(0.8)
            self.line(10, 20, 200, 20)
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family, '', 8)
        self.set_text_color(*self.c_gri)
        self.cell(0, 10, self.fix_text(f'Sayfa {self.page_no()}'), 0, 0, 'C')

    def chapter_title(self, label):
        self.ln(5)
        self.set_font(self.font_family, 'B', 14)
        self.set_text_color(*self.c_koyu)
        self.cell(0, 10, self.fix_text(str(label)), 0, 1, 'L')
        self.set_draw_color(*self.c_sari)
        self.set_line_width(1.5)
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.ln(5)

    def create_kpi_summary(self, enf_genel, enf_gida, en_yuksek_urun):
        self.ln(5)
        self.set_font(self.font_family, 'B', 10)
        
        # 3 Kutu Yan Yana
        w = 60
        h = 25
        margin = 5
        
        # 1. Kutu: Genel Enflasyon (SARI)
        x = self.get_x()
        y = self.get_y()
        self.set_fill_color(*self.c_sari)
        self.rect(x, y, w, h, 'F')
        self.set_xy(x, y+5)
        self.set_text_color(*self.c_lacivert)
        self.cell(w, 5, self.fix_text("GENEL ENFLASYON"), 0, 2, 'C')
        self.set_font(self.font_family, 'B', 16)
        self.cell(w, 10, self.fix_text(f"%{enf_genel:.2f}"), 0, 0, 'C')
        
        # 2. Kutu: Gıda (LACİVERT)
        self.set_xy(x + w + margin, y)
        self.set_fill_color(*self.c_lacivert)
        self.rect(x + w + margin, y, w, h, 'F')
        self.set_xy(x + w + margin, y+5)
        self.set_text_color(255, 255, 255) # Beyaz yazı
        self.set_font(self.font_family, 'B', 10)
        self.cell(w, 5, self.fix_text("GIDA ENFLASYONU"), 0, 2, 'C')
        self.set_font(self.font_family, 'B', 16)
        self.cell(w, 10, self.fix_text(f"%{enf_gida:.2f}"), 0, 0, 'C')

        # 3. Kutu: En Çok Artan (GRİ)
        self.set_xy(x + (w + margin)*2, y)
        self.set_fill_color(240, 240, 240)
        self.rect(x + (w + margin)*2, y, w, h, 'F')
        self.set_xy(x + (w + margin)*2, y+5)
        self.set_text_color(*self.c_koyu)
        self.set_font(self.font_family, 'B', 10)
        self.cell(w, 5, self.fix_text("EN YÜKSEK ARTIŞ"), 0, 2, 'C')
        self.set_font(self.font_family, 'B', 11)
        self.cell(w, 10, self.fix_text(str(en_yuksek_urun)[:15]), 0, 0, 'C') # İlk 15 harf
        
        self.ln(20) # Aşağı geç

    def write_markdown(self, text):
        if not text: return
        self.set_text_color(50, 50, 50)
        self.set_font(self.font_family, '', 11)
        lines = str(text).split('\n')
        for line in lines:
            line = self.fix_text(line)
            if any(x in line for x in ["Saygilarimizla", "[Basekonomist", "[Kurum", "Unvani]", "Basekonomist Ofisi"]): continue
            if not line.strip(): self.ln(5); continue
            parts = line.split('**')
            for i, part in enumerate(parts):
                if i % 2 == 1: self.set_font(self.font_family, 'B', 11)
                else: self.set_font(self.font_family, '', 11)
                self.write(6, part)
            self.ln(6)

    def create_cover(self, date_str, rate_val):
        self.add_page()
        self.set_fill_color(*self.c_sari)
        self.rect(0, 0, 210, 297, 'F')
        self.set_fill_color(255, 255, 255)
        self.rect(20, 40, 170, 200, 'F')
        self.set_y(60)
        self.set_font(self.font_family, 'B', 28)
        self.set_text_color(*self.c_koyu)
        self.cell(0, 15, self.fix_text("PİYASA & ENFLASYON"), 0, 1, 'C')
        self.cell(0, 15, self.fix_text("STRATEJİ RAPORU"), 0, 1, 'C')
        self.ln(25)
        self.set_font(self.font_family, 'B', 70)
        self.set_text_color(*self.c_koyu)
        self.cell(0, 30, self.fix_text(f"%{rate_val}"), 0, 1, 'C')
        self.set_font(self.font_family, 'B', 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 15, self.fix_text("AYLIK ENFLASYON GÖSTERGESİ"), 0, 1, 'C')
        self.ln(30)
        self.set_font(self.font_family, '', 12)
        self.set_text_color(*self.c_koyu)
        aciklama = f"Bu rapor, {date_str} dönemi için yapay zeka destekli piyasa analiz sistemi tarafından oluşturulmuştur."
        self.set_x(40)
        self.multi_cell(130, 6, self.fix_text(aciklama), 0, 'C')

    def add_plot_image(self, plot_bytes, title="Grafik"):
        if plot_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                tmpfile.write(plot_bytes); path = tmpfile.name
            
            self.ln(5)
            self.set_font(self.font_family, 'B', 11)
            self.set_text_color(*self.c_lacivert)
            self.cell(0, 8, self.fix_text(f"» {title}"), 0, 1, 'L')
            
            if self.get_y() > 200: self.add_page()
            
            try: self.image(path, x=10, w=190)
            except: pass
            
            self.ln(5)
            try: os.unlink(path)
            except: pass

    def create_table(self, df):
        self.set_font(self.font_family, 'B', 9)
        self.set_fill_color(*self.c_sari)
        self.set_text_color(*self.c_koyu)
        cols = df.columns
        w = 190 / len(cols) if len(cols) > 0 else 190
        for col in cols: self.cell(w, 9, self.fix_text(str(col)), 1, 0, 'C', True)
        self.ln()
        self.set_font(self.font_family, '', 8)
        self.set_text_color(0, 0, 0)
        for i, row in df.iterrows():
            if i % 2 == 0: self.set_fill_color(248, 248, 248)
            else: self.set_fill_color(255, 255, 255)
            for col in cols:
                val = row[col]
                txt = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
                self.cell(w, 8, self.fix_text(txt), 1, 0, 'C', True)
            self.ln()

def create_pdf_report_advanced(text_content, df_table, figures, manset_oran, metrics_dict, date_str_ignored):
    pdf = PDFReport()
    
    # Tarih Hesapla
    aylar = {1:"Ocak", 2:"Şubat", 3:"Mart", 4:"Nisan", 5:"Mayıs", 6:"Haziran", 
             7:"Temmuz", 8:"Ağustos", 9:"Eylül", 10:"Ekim", 11:"Kasım", 12:"Aralık"}
    simdi = datetime.now()
    tr_tarih = f"{aylar[simdi.month]} {simdi.year}"
    
    # Kapak
    pdf.create_cover(tr_tarih, f"{manset_oran:.2f}")
    
    # --- SAYFA 2: ANALİZ VE GRAFİKLER ---
    pdf.add_page()
    pdf.chapter_title("YÖNETİCİ ÖZETİ VE PİYASA ANALİZİ")
    
    # 1. KPI KARTLARI (EN TEPEYE)
    if metrics_dict:
        pdf.create_kpi_summary(
            metrics_dict.get('genel', 0), 
            metrics_dict.get('gida', 0), 
            metrics_dict.get('top_urun', 'Yok')
        )
    
    # 2. TREND GRAFİĞİ (METİNDEN HEMEN ÖNCE)
    if figures:
        keys = list(figures.keys())
        if len(keys) > 0:
            trend_title = keys[0]
            trend_fig = figures[trend_title]
            try:
                img = trend_fig.to_image(format="png", width=1600, height=700, scale=2)
                pdf.add_plot_image(img, title=trend_title)
            except: pass

    # 3. YÖNETİCİ ÖZETİ (METİN)
    pdf.ln(5)
    pdf.write_markdown(text_content)
    
    # 4. DAĞILIM GRAFİĞİ (METİNDEN HEMEN SONRA)
    if figures and len(keys) > 1:
        hist_title = keys[1]
        hist_fig = figures[hist_title]
        try:
            pdf.ln(5)
            img = hist_fig.to_image(format="png", width=1600, height=800, scale=2)
            pdf.add_plot_image(img, title=hist_title)
        except: pass

    # 5. İMZA
    pdf.ln(10)
    pdf.set_y(pdf.get_y() + 10)
    pdf.set_font(pdf.font_family, 'B', 12)
    pdf.set_text_color(*pdf.c_koyu)
    pdf.cell(0, 6, pdf.fix_text("Saygilarimizla,"), 0, 1, 'R')
    pdf.cell(0, 6, pdf.fix_text("VALIDASYON MUDURLUGU"), 0, 1, 'R')

    # 6. TABLO (YENİ SAYFAYA)
    if not df_table.empty:
        pdf.add_page()
        pdf.chapter_title("DETAYLI FİYAT LİSTESİ")
        cols = [c for c in df_table.columns if 'Kod' not in c and 'URL' not in c]
        pdf.create_table(df_table[cols].head(35))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.close()
        with open(tmp.name, "rb") as f: pdf_bytes = f.read()
        try: os.unlink(tmp.name)
        except: pass
            
    return pdf_bytes

# --- 4. GITHUB İŞLEMLERİ ---
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


# --- 5. RESMİ ENFLASYON & PROPHET ---
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


# --- 6. SCRAPER ---
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


# --- 7. DASHBOARD MODU ---
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

                # --- GRAFİK STİL FONKSİYONU ---
                def style_chart(fig, is_pdf=False):
                    if is_pdf:
                        # PDF İÇİN: BEYAZ TEMA (Dergi Gibi)
                        fig.update_layout(
                            template="plotly_white", 
                            font=dict(family="Arial", size=14, color="black"),
                            plot_bgcolor="white",
                            paper_bgcolor="white",
                            title_font=dict(size=20, color="#002855", family="Arial Black"), 
                            margin=dict(l=50, r=50, t=80, b=50)
                        )
                    else:
                        # EKRAN İÇİN: DARK TEMA
                        fig.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            title_font=dict(color="white"),
                            margin=dict(l=20, r=20, t=50, b=20)
                        )
                    return fig

                # 1. VERİLERİ HAZIRLA
                trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[agirlik_col].sum() * 100} for g in gunler]
                df_trend = pd.DataFrame(trend_data); df_trend['Tarih'] = pd.to_datetime(df_trend['Tarih'])

                # 2. GRAFİKLERİ GLOBAL OLARAK OLUŞTUR (Hata vermemesi için tablardan önce)
                
                # --- TREND GRAFİĞİ ---
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=df_trend['Tarih'], y=df_trend['TÜFE'], 
                    mode='lines+markers', name='Enflasyon', 
                    line=dict(color='#FDB913', width=4), # Vakıf Sarısı
                    marker=dict(size=8, line=dict(width=2, color='white'))
                ))
                # İSTEĞİN ÜZERİNE Y EKSENİ SABİTLENDİ: [95, 105]
                fig_trend.update_layout(
                    title="Enflasyon Trendi",
                    yaxis=dict(range=[95, 105]) 
                )
                
                # --- HİSTOGRAM ---
                df_analiz['Fark_Yuzde'] = df_analiz['Fark'] * 100
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(
                    x=df_analiz['Fark_Yuzde'], nbinsx=30, 
                    marker_color='#3b82f6', opacity=0.8
                ))
                fig_hist.update_layout(title="Fiyat Değişim Dağılımı", xaxis_title="Değişim (%)")

                # 3. TABLARI OLUŞTUR VE YERLEŞTİR
                t_analiz, t_istatistik, t_harita, t_liste, t_haber, t_rapor = st.tabs(["📊 ANALİZ", "📈 İSTATİSTİK", "🗺️ HARİTA", "📋 LİSTE", "📰 HABERLER", "📝 RAPOR"])
                
                with t_analiz: 
                    # Ekrana basarken is_pdf=False diyoruz
                    st.plotly_chart(style_chart(go.Figure(fig_trend), is_pdf=False), use_container_width=True)
                
                with t_istatistik:
                    st.plotly_chart(style_chart(go.Figure(fig_hist), is_pdf=False), use_container_width=True)
                    try:
                        cols_p = [c for c in pivot.columns if c != 'Kod']
                        pivot['Std'] = pivot[cols_p].std(axis=1)
                        pivot['Mean'] = pivot[cols_p].mean(axis=1)
                        pivot['Volatilite'] = (pivot['Std'] / pivot['Mean']) * 100
                        df_vol = pd.merge(df_analiz, pivot[['Kod', 'Volatilite']], on='Kod', how='left')
                        fig_vol = px.scatter(df_vol, x="Fark_Yuzde", y="Volatilite", color="Grup", size="Agirlik_2025", hover_data=[ad_col], title="Risk Haritası (Volatilite vs Zam)")
                        fig_vol.update_layout(showlegend=False)
                        st.plotly_chart(style_chart(fig_vol, is_pdf=False), use_container_width=True)
                    except: pass
                
                with t_harita:
                    fig_tree = px.treemap(df_analiz, path=[px.Constant("Sepet"), 'Grup', ad_col], values=agirlik_col, color='Fark', color_continuous_scale='RdYlGn_r', title="Enflasyon Isı Haritası")
                    fig_tree.update_traces(marker=dict(line=dict(color='black', width=1)))
                    st.plotly_chart(style_chart(fig_tree, is_pdf=False), use_container_width=True)

                with t_liste:
                     st.data_editor(df_analiz[['Grup', ad_col, 'Fark', baz, son]], column_config={"Fark": st.column_config.ProgressColumn("Değişim Oranı", format="%.2f", min_value=-0.5, max_value=0.5), ad_col: "Ürün Adı", "Grup": "Kategori"}, hide_index=True, use_container_width=True)
                     output = BytesIO()
                     with pd.ExcelWriter(output, engine='openpyxl') as writer: df_analiz.to_excel(writer, index=False, sheet_name='Analiz')
                     st.download_button("📥 Excel Raporunu İndir", data=output.getvalue(), file_name=f"Enflasyon_Raporu_{son}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                with t_haber:
                     st.markdown("### 🌍 Ekonomi Gündemi")
                     if st.button("Haberleri Tara ve Analiz Et", key="btn_news"):
                         with st.spinner("Piyasa verileri taranıyor..."):
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
                    if st.button("🚀 PROFESYONEL RAPORU OLUŞTUR", type="primary"):
                        with st.spinner("Veriler işleniyor, grafikler çiziliyor ve rapor diziliyor..."):
                            
                            # A. METNİ HAZIRLA
                            prompt = f"Tarih: {son}. Genel Enflasyon: %{enf_genel:.2f}. Gıda: %{enf_gida:.2f}. Piyasa özeti yaz."
                            try:
                                model = genai.GenerativeModel('gemini-2.5-flash')
                                rap_text = model.generate_content(prompt).text
                            except: rap_text = "AI Bağlantı Hatası."

                            # B. GRAFİKLERİ PDF FORMATINA ÇEVİR (Dergi Modu)
                            # Trend Grafiğini Kopyala ve Beyazlat
                            # is_pdf=True ile Vakıf Laciverti/Sarısı ve Beyaz Zemin uygulanacak
                            fig_print_trend = go.Figure(fig_trend)
                            style_chart(fig_print_trend, is_pdf=True)
                            fig_print_trend.update_traces(line=dict(color='#002855')) # Çizgiyi Lacivert yap

                            # Histogramı Kopyala ve Beyazlat
                            fig_print_hist = go.Figure(fig_hist)
                            style_chart(fig_print_hist, is_pdf=True)
                            fig_print_hist.update_traces(marker_color='#FDB913') # Çubukları Sarı yap

                            figs = {"Enflasyon Seyri (Trend)": fig_print_trend, "Fiyat Hareketliliği (Dağılım)": fig_print_hist}
                            
                            # C. KPI VERİLERİ (Kutucuklar için)
                            en_cok_artan = df_analiz.sort_values('Fark', ascending=False).iloc[0][ad_col]
                            metrics = {'genel': enf_genel, 'gida': enf_gida, 'top_urun': en_cok_artan}

                            # D. PDF OLUŞTUR
                            pdf_data = create_pdf_report_advanced(
                                text_content=rap_text,
                                df_table=df_analiz.sort_values('Fark', ascending=False).head(20),
                                figures=figs,
                                manset_oran=enf_genel,
                                metrics_dict=metrics, 
                                date_str_ignored="-"
                            )
                            
                            st.download_button("📥 PDF Raporunu İndir", data=pdf_data, file_name=f"Strateji_Raporu_{son}.pdf", mime="application/pdf")
                            st.success("Rapor başarıyla oluşturuldu!")

        except Exception as e:
            st.error(f"Kritik Hata: {e}")
    st.markdown('<div style="text-align:center; color:#94a3b8; font-size:11px; margin-top:50px;">VALIDASYON MUDURLUGU © 2025</div>', unsafe_allow_html=True)

# --- 5. ANA GİRİŞ SİSTEMİ ---
def main():
    dashboard_modu()

if __name__ == "__main__":
    main()
