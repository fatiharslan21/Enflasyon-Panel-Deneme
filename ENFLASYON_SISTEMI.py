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
import hashlib
from github import Github
from io import BytesIO
import zipfile
import base64
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
import PIL.Image
import requests
from prophet import Prophet
import feedparser
from fpdf import FPDF
import shutil
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==============================================================================
# 1. AYARLAR VE TEMA YÖNETİMİ
# ==============================================================================
st.set_page_config(
    page_title="Enflasyon Monitörü",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# --- Session State Başlatma ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

# --- SIDEBAR ---
with st.sidebar:
    st.title("Ayarlar")
    is_dark = st.toggle("🌙 Karanlık Mod", value=(st.session_state.theme == 'dark'))

    # Tema Değişikliği Kontrolü
    if is_dark and st.session_state.theme == 'light':
        st.session_state.theme = 'dark'
        st.rerun()
    elif not is_dark and st.session_state.theme == 'dark':
        st.session_state.theme = 'light'
        st.rerun()


# --- CSS VE TEMA MOTORU ---
def apply_theme():
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

    final_css = f"""
    <style>
        /* GENEL TEMA */
        .stApp {{ background-color: {colors['bg']}; color: {colors['text']}; transition: none !important; }}
        section[data-testid="stSidebar"] {{ background-color: {colors['sidebar']}; border-right: 1px solid {colors['border_color']}; }}

        /* METİN RENKLERİ */
        h1, h2, h3, h4, h5, h6, p, li, label, .stMarkdown, .stRadio label {{ 
            color: {colors['text']} !important; 
        }}

        /* INPUT ALANLARI */
        .stTextInput input, .stNumberInput input {{ 
            background-color: {colors['input_bg']} !important; 
            color: {colors['text']} !important; 
            border: 1px solid {colors['input_border']} !important; 
        }}

        /* GİZLENECEK ÖĞELER */
        header[data-testid="stHeader"] {{ display: none !important; }}
        [data-testid="stDecoration"] {{ display: none !important; }}
        footer {{ visibility: hidden; }}
        .stDeployButton {{ display: none; }}
        .block-container {{ padding-top: 1rem !important; opacity: 1 !important; }}
        [data-testid="stStatusWidget"] {{ visibility: hidden !important; display: none !important; }}

        /* BUTONLAR (SİYAH ÇERÇEVE - BEYAZ ZEMİN) */
        div.stButton > button, div.stFormSubmitButton > button, [data-testid="stDownloadButton"] button {{
            background-color: #ffffff !important; 
            color: #000000 !important;
            border: 2px solid #000000 !important; 
            border-radius: 8px !important; 
            font-weight: bold !important;
        }}
        div.stButton > button p, div.stFormSubmitButton > button p, [data-testid="stDownloadButton"] button * {{ 
            color: #000000 !important; 
        }}
        div.stButton > button:hover, div.stFormSubmitButton > button:hover, [data-testid="stDownloadButton"] button:hover {{
            background-color: #f0f0f0 !important; 
            border-color: #000000 !important; 
            color: #000000 !important;
        }}
        div.stButton > button[kind="primary"] {{ 
            background-color: #ffffff !important; 
            color: #000000 !important; 
            border: 2px solid #000000 !important; 
        }}
        button:disabled {{ 
            opacity: 1 !important; 
            filter: none !important; 
            cursor: not-allowed !important; 
        }}

        /* METRİK KARTLARI */
        .metric-card {{ 
            background: {colors['card_bg']} !important; 
            border: 1px solid {colors['border_color']} !important; 
            padding: 24px; 
            border-radius: 20px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.03); 
            position: relative; 
            overflow: hidden; 
            transition: all 0.3s ease; 
        }}
        .metric-card:hover {{ 
            transform: translateY(-5px); 
            box-shadow: 0 20px 40px rgba(59, 130, 246, 0.15); 
            border-color: #3b82f6; 
        }}
        .metric-val {{ 
            color: {colors['text']} !important; 
            font-size: 36px; 
            font-weight: 800; 
            font-family: 'Poppins', sans-serif; 
        }}
        .metric-val.long-text {{ font-size: 24px !important; line-height: 1.2; }}
        .metric-label {{ color: #64748b; font-size: 13px; font-weight: 700; text-transform: uppercase; margin-bottom: 5px; }}

        /* Renkli Çizgiler */
        .metric-card::before {{ content: ''; position: absolute; top: 0; left: 0; width: 6px; height: 100%; }}
        .card-blue::before {{ background: #3b82f6; }} 
        .card-purple::before {{ background: #8b5cf6; }} 
        .card-emerald::before {{ background: #10b981; }} 
        .card-orange::before {{ background: #f59e0b; }}

        /* TICKER (KAYAN YAZI) */
        .ticker-wrap {{ 
            width: 100%; 
            overflow: hidden; 
            background: linear-gradient(90deg, #0f172a, #1e293b); 
            color: white; 
            padding: 12px 0; 
            margin-bottom: 25px; 
            border-radius: 12px; 
        }}
        .ticker {{ display: inline-block; animation: ticker 45s linear infinite; white-space: nowrap; }}
        .ticker-item {{ display: inline-block; padding: 0 2rem; font-weight: 500; font-size: 14px; font-family: 'JetBrains Mono', monospace; }}
        @keyframes ticker {{ 0% {{ transform: translateX(100%); }} 100% {{ transform: translateX(-100%); }} }}
    </style>
    """
    st.markdown(final_css, unsafe_allow_html=True)


apply_theme()

# --- SABİTLER ---
ADMIN_USERS = ["fatih", "ahmet", "mehmet"]
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
USERS_DOSYASI = "kullanicilar.json"
ACTIVITY_DOSYASI = "user_activity.json"
SEPETLER_DOSYASI = "user_baskets.json"
ALARMS_DOSYASI = "user_alarms.json"
SAYFA_ADI = "Madde_Sepeti"

if "gemini" in st.secrets:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])


# ==============================================================================
# 2. YARDIMCI VE VERİ FONKSİYONLARI
# ==============================================================================

@st.cache_data(ttl=1800)
def get_exchange_rates():
    rates = {"USD": 0.0, "EUR": 0.0, "GA": 0.0}
    try:
        res = requests.get("https://www.tcmb.gov.tr/kurlar/today.xml", timeout=5)
        soup = BeautifulSoup(res.content, 'xml')
        rates["USD"] = float(soup.find(attrs={"CurrencyCode": "USD"}).BanknoteSelling.text)
        rates["EUR"] = float(soup.find(attrs={"CurrencyCode": "EUR"}).BanknoteSelling.text)
    except:
        pass

    try:
        url_gold = "https://bigpara.hurriyet.com.tr/altin/gram-altin-fiyati/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res_gold = requests.get(url_gold, headers=headers, timeout=5)
        soup_gold = BeautifulSoup(res_gold.content, 'html.parser')
        fiyat_text = soup_gold.select_one("span.value").text
        temiz_fiyat = fiyat_text.replace(".", "").replace(",", ".").strip()
        rates["GA"] = float(temiz_fiyat)
    except:
        if rates["USD"] > 0:
            rates["GA"] = (2700 * rates["USD"]) / 31.10
    return rates


def get_github_repo():
    try:
        return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
    except:
        return None


def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()


def github_json_oku(dosya_adi):
    repo = get_github_repo()
    if not repo:
        return {}
    try:
        c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        return json.loads(c.decoded_content.decode("utf-8"))
    except:
        return {}


def github_json_yaz(dosya_adi, data, mesaj="Update JSON"):
    repo = get_github_repo()
    if not repo:
        return False
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
    if not repo:
        return pd.DataFrame()
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
    if not repo:
        return "Repo Yok"
    try:
        try:
            c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
            old = pd.read_excel(BytesIO(c.decoded_content), dtype=str)
            yeni_tarih = str(df_yeni['Tarih'].iloc[0])
            old = old[~((old['Tarih'].astype(str) == yeni_tarih) & (old['Kod'].isin(df_yeni['Kod'])))]
            final = pd.concat([old, df_yeni], ignore_index=True)
        except:
            final = df_yeni

        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            final.to_excel(w, index=False, sheet_name='Fiyat_Log')

        msg = "Data Update"
        if 'c' in locals() and c:
            repo.update_file(c.path, msg, out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, msg, out.getvalue(), branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e:
        return str(e)


# ==============================================================================
# 3. SCRAPER VE DATA ENGINE (EKSİKSİZ)
# ==============================================================================

def temizle_fiyat(t):
    if not t:
        return None
    t = str(t).replace('TL', '').replace('₺', '').strip()
    t = t.replace('.', '').replace(',', '.') if ',' in t and '.' in t else t.replace(',', '.')
    try:
        return float(re.sub(r'[^\d.]', '', t))
    except:
        return None


def kod_standartlastir(k):
    return str(k).replace('.0', '').strip().zfill(7)


def fiyat_bul_siteye_gore(soup, url):
    fiyat = 0
    kaynak = ""
    domain = url.lower() if url else ""

    if "migros" in domain:
        garbage = ["sm-list-page-item", ".horizontal-list-page-items-container", "app-product-carousel",
                   ".similar-products", "div.badges-wrapper"]
        for g in garbage:
            for x in soup.select(g):
                x.decompose()
        main_wrapper = soup.select_one(".name-price-wrapper")
        if main_wrapper:
            for sel, k in [(".price.subtitle-1", "Migros(N)"), (".single-price-amount", "Migros(S)"),
                           ("#sale-price, .sale-price", "Migros(I)")]:
                if el := main_wrapper.select_one(sel):
                    if val := temizle_fiyat(el.get_text()):
                        return val, k
        if fiyat == 0:
            if el := soup.select_one("fe-product-price .subtitle-1, .single-price-amount"):
                if val := temizle_fiyat(el.get_text()):
                    fiyat = val;
                    kaynak = "Migros(G)"
            if fiyat == 0:
                if el := soup.select_one("#sale-price"):
                    if val := temizle_fiyat(el.get_text()):
                        fiyat = val;
                        kaynak = "Migros(GI)"

    elif "cimri" in domain:
        for sel in ["div.rTdMX", ".offer-price", "div.sS0lR", ".min-price-val"]:
            if els := soup.select(sel):
                vals = [v for v in [temizle_fiyat(e.get_text()) for e in els] if v and v > 0]
                if vals:
                    if len(vals) > 4:
                        vals.sort();
                        vals = vals[1:-1]
                    fiyat = sum(vals) / len(vals)
                    kaynak = f"Cimri({len(vals)})"
                    break
        if fiyat == 0:
            if m := re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', soup.get_text()[:10000]):
                ff = sorted([temizle_fiyat(x) for x in m if temizle_fiyat(x)])
                if ff:
                    fiyat = sum(ff[:max(1, len(ff) // 2)]) / max(1, len(ff) // 2)
                    kaynak = "Cimri(Reg)"

    if fiyat == 0 and "migros" not in domain:
        for sel in [".product-price", ".price", ".current-price", "span[itemprop='price']"]:
            if el := soup.select_one(sel):
                if v := temizle_fiyat(el.get_text()):
                    fiyat = v;
                    kaynak = "Genel(CSS)";
                    break

    if fiyat == 0 and "migros" not in domain and "cimri" not in domain:
        if m := re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', soup.get_text()[:5000]):
            if v := temizle_fiyat(m.group(1)):
                fiyat = v;
                kaynak = "Regex"
    return fiyat, kaynak


def html_isleyici(log_callback):
    repo = get_github_repo()
    if not repo:
        return "GitHub Bağlantı Hatası"
    log_callback("📂 Konfigürasyon okunuyor...")
    try:
        df_conf = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)
        df_conf.columns = df_conf.columns.str.strip()
        kod_col = next((c for c in df_conf.columns if c.lower() == 'kod'), None)
        url_col = next((c for c in df_conf.columns if c.lower() == 'url'), None)
        ad_col = next((c for c in df_conf.columns if 'ad' in c.lower()), 'Madde adı')

        if not kod_col or not url_col:
            return "Hata: Excel sütunları eksik."

        df_conf['Kod'] = df_conf[kod_col].astype(str).apply(kod_standartlastir)
        url_map = {str(row[url_col]).strip(): row for _, row in df_conf.iterrows() if pd.notna(row[url_col])}
        veriler = []
        islenen_kodlar = set()
        bugun = datetime.now().strftime("%Y-%m-%d")
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
                            veriler.append({
                                "Tarih": bugun, "Zaman": simdi, "Kod": row['Kod'],
                                "Madde_Adi": row[ad_col], "Fiyat": fiyat_man,
                                "Kaynak": "Manuel", "URL": row[url_col]
                            })
                            islenen_kodlar.add(row['Kod'])
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
                            if c := soup.find("link", rel="canonical"):
                                found_url = c.get("href")
                            if not found_url and (m := soup.find("meta", property="og:url")):
                                found_url = m.get("content")

                            if found_url and str(found_url).strip() in url_map:
                                target = url_map[str(found_url).strip()]
                                if target['Kod'] in islenen_kodlar: continue
                                fiyat, kaynak = fiyat_bul_siteye_gore(soup, target[url_col])
                                if fiyat > 0:
                                    veriler.append({
                                        "Tarih": bugun, "Zaman": simdi, "Kod": target['Kod'],
                                        "Madde_Adi": target[ad_col], "Fiyat": fiyat,
                                        "Kaynak": kaynak, "URL": target[url_col]
                                    })
                                    islenen_kodlar.add(target['Kod'])
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


def check_alarms_and_notify(df_son_fiyatlar):
    alarms_db = github_json_oku("user_alarms.json")
    if not isinstance(alarms_db, list):
        return "0 adet"
    updated = False
    sent_count = 0

    for alarm in alarms_db:
        if alarm.get("durum") == "aktif":
            kod = alarm.get("kod")
            target = float(alarm.get("hedef_fiyat"))
            row = df_son_fiyatlar[df_son_fiyatlar['Kod'] == kod]
            if not row.empty:
                cols = [c for c in df_son_fiyatlar.columns if
                        c not in ['Kod', 'Ad', 'Grup', 'Madde_Adi', 'URL', 'Grup_Kodu', 'Agirlik_2025']]
                if cols:
                    current_price = float(row[cols[-1]].values[0])
                    if current_price > 0 and current_price <= target:
                        if send_notification_email(alarm["email"], alarm["urun_adi"], current_price, target):
                            alarm["durum"] = "tamamlandi"
                            updated = True
                            sent_count += 1

    if updated:
        github_json_yaz("user_alarms.json", alarms_db, "Alarm Sent")
    return f"{sent_count} adet alarm bildirimi gönderildi."


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


def get_official_inflation():
    api_key = st.secrets.get("evds", {}).get("api_key")
    if not api_key:
        return None, "API Key Yok"
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
        return m.predict(future)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    except Exception as e:
        st.error(f"Prophet Hatası: {str(e)}")
        return pd.DataFrame()


class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'ENFLASYON RAPORU', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')


def create_pdf_report(text):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    replacements = {'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S', 'ö': 'o', 'Ö': 'O',
                    'ç': 'c', 'Ç': 'C', '₺': 'TL'}
    for tr, en in replacements.items():
        text = text.replace(tr, en)
    pdf.multi_cell(0, 7, text.encode('latin-1', 'replace').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1', 'ignore')


# --- KULLANICI İŞLEMLERİ ---
def send_verification_email(to_email, code):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        msg = MIMEMultipart()
        msg['From'] = f"Enflasyon Monitörü <{sender_email}>"
        msg['To'] = to_email
        msg['Subject'] = "🔐 Doğrulama Kodun"
        msg.attach(MIMEText(f"Kodunuz: {code}", 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except:
        return False


def send_reset_email(to_email, username):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        reset_link = f"https://enflasyon-gida.streamlit.app/?reset_user={username}"
        msg = MIMEMultipart()
        msg['From'] = f"Sistem <{sender_email}>"
        msg['To'] = to_email
        msg['Subject'] = "Şifre Sıfırlama"
        msg.attach(MIMEText(f"Sıfırlama linki: {reset_link}", 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True, "Link gönderildi."
    except:
        return False, "Mail Hatası"


def send_notification_email(to_email, product_name, current_price, target_price):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = f"🔔 FİYAT DÜŞTÜ: {product_name}"
        msg.attach(MIMEText(f"{product_name} fiyatı {current_price} TL'ye düştü! Hedefin: {target_price} TL", 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except:
        return False


def github_user_islem(action, username=None, password=None, email=None):
    users_db = github_json_oku(USERS_DOSYASI)
    if action == "login":
        if username in users_db:
            if users_db[username].get("password") == hash_password(password):
                return True, "Giriş Başarılı"
        return False, "Hatalı Giriş"
    elif action == "register":
        if username in users_db:
            return False, "Kullanıcı Adı Dolu"
        users_db[username] = {"password": hash_password(password), "email": email, "created_at": str(datetime.now())}
        github_json_yaz(USERS_DOSYASI, users_db, "New User")
        return True, "Kayıt Başarılı"
    elif action == "forgot_password":
        for u, d in users_db.items():
            if d.get("email") == email:
                return send_reset_email(email, u)
        return False, "Email bulunamadı"
    elif action == "update_password":
        if username in users_db:
            users_db[username]["password"] = hash_password(password)
            github_json_yaz(USERS_DOSYASI, users_db, "Pass Reset")
            return True, "Güncellendi"
        return False, "Kullanıcı yok"
    return False, "Hata"


# ==============================================================================
# 4. FRAGMENTS (BAĞIMSIZ ÇALIŞAN PARÇACIKLAR - PERFORMANS İÇİN)
# ==============================================================================

@st.fragment
def render_analiz_tab(df_analiz, df_trend, df_resmi, baz, agirlik_col):
    st.markdown("### 📈 Enflasyon Momentum Analizi ve Gelecek Tahmini")
    with st.spinner("Gelecek tahmini yapıyor..."):
        df_forecast = predict_inflation_prophet(df_trend)

    start_date = df_trend['Tarih'].min()
    end_date_fixed = f"{df_trend['Tarih'].dt.year.max()}-12-31"

    fig_main = go.Figure()
    fig_main.add_trace(
        go.Scatter(x=df_trend['Tarih'], y=df_trend['TÜFE'], mode='lines+markers', name='Enflasyon Monitörü',
                   line=dict(color='#2563eb', width=3)))
    if not df_forecast.empty:
        future_only = df_forecast[df_forecast['ds'] > df_trend['Tarih'].max()]
        fig_main.add_trace(go.Scatter(x=future_only['ds'], y=future_only['yhat'], mode='lines', name='AI Tahmini',
                                      line=dict(color='#f59e0b', dash='dot')))
        fig_main.add_trace(go.Scatter(x=future_only['ds'].tolist() + future_only['ds'].tolist()[::-1],
                                      y=future_only['yhat_upper'].tolist() + future_only['yhat_lower'].tolist()[::-1],
                                      fill='toself', fillcolor='rgba(245, 158, 11, 0.2)',
                                      line=dict(color='rgba(0,0,0,0)'), showlegend=False))
    if df_resmi is not None and not df_resmi.empty:
        fig_main.add_trace(
            go.Scatter(x=df_resmi['Tarih'], y=df_resmi['Resmi_TUFE'], mode='lines+markers', name='Resmi TÜİK',
                       line=dict(color='#ef4444', width=2), marker=dict(symbol='square')))

    fig_main.update_layout(template=st.session_state.plotly_template, title="Enflasyon Trendi",
                           title_font=dict(color='white', size=22),
                           legend=dict(orientation="h", y=1.1, font=dict(color="white")), plot_bgcolor='rgba(0,0,0,0)',
                           paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_main, use_container_width=True)


@st.fragment
def render_istatistik_tab(df_analiz, pivot, ad_col):
    st.markdown("### 📊 İstatistiksel Risk ve Dağılım Analizi")
    c1, c2 = st.columns(2)
    df_analiz['Fark_Yuzde'] = df_analiz['Fark'] * 100
    fig_hist = px.histogram(df_analiz, x="Fark_Yuzde", nbins=40, title="📊 Zam Dağılımı",
                            color_discrete_sequence=['#8b5cf6'])
    fig_hist.update_layout(template=st.session_state.plotly_template, plot_bgcolor='rgba(0,0,0,0)',
                           paper_bgcolor='rgba(0,0,0,0)', title_font=dict(color='white'))
    c1.plotly_chart(fig_hist, use_container_width=True)

    try:
        cols = [c for c in pivot.columns if c not in ['Kod', 'Std', 'Mean', 'Volatilite']]
        pivot['Std'] = pivot[cols].std(axis=1)
        pivot['Mean'] = pivot[cols].mean(axis=1)
        pivot['Volatilite'] = (pivot['Std'] / pivot['Mean']) * 100
        df_vol = pd.merge(df_analiz, pivot[['Kod', 'Volatilite']], on='Kod', how='left')
        fig_vol = px.scatter(df_vol, x="Fark_Yuzde", y="Volatilite", color="Grup", hover_data=[ad_col],
                             title="⚡ Risk Analizi")
        fig_vol.update_layout(template=st.session_state.plotly_template, plot_bgcolor='rgba(0,0,0,0)',
                              paper_bgcolor='rgba(0,0,0,0)', legend=dict(font=dict(color='white')),
                              title_font=dict(color='white'))
        c2.plotly_chart(fig_vol, use_container_width=True)
    except:
        pass


@st.fragment
def render_sepet_tab(df_analiz, ad_col, baz, son, enf_genel, username):
    st.markdown("### 🛒 Kişisel Enflasyon Sepeti")
    baskets = github_json_oku(SEPETLER_DOSYASI)
    user_codes = baskets.get(username, [])
    all_products = df_analiz[ad_col].unique()
    default_names = df_analiz[df_analiz['Kod'].isin(user_codes)][ad_col].tolist()

    selected = st.multiselect("Takip Ettiğin Ürünler", all_products, default=default_names)

    if selected:
        my_df = df_analiz[df_analiz[ad_col].isin(selected)].copy()
        if 'Kullanici_Agirlik' not in st.session_state:
            st.session_state['Kullanici_Agirlik'] = {r['Kod']: 1.0 for _, r in my_df.iterrows()}
        my_df['Miktar'] = my_df['Kod'].map(st.session_state['Kullanici_Agirlik']).fillna(1.0)

        c1, c2 = st.columns([2, 1])
        with c1:
            edited = st.data_editor(my_df[[ad_col, 'Miktar', baz, son, 'Kod']], column_config={
                ad_col: "Ürün",
                "Miktar": st.column_config.NumberColumn("Adet/Kg", min_value=0.1, max_value=1000.0, step=0.5),
                baz: st.column_config.NumberColumn(f"Eski ({baz})", format="%.2f"),
                son: st.column_config.NumberColumn(f"Yeni ({son})", format="%.2f"), "Kod": None
            }, disabled=[ad_col, baz, son], use_container_width=True, key="sepet_edit")

        with c2:
            top_eski = (edited[baz] * edited['Miktar']).sum()
            top_yeni = (edited[son] * edited['Miktar']).sum()
            if top_eski > 0:
                kisisel = ((top_yeni / top_eski) - 1) * 100
                st.metric("Senin Enflasyonun", f"%{kisisel:.2f}", f"{top_yeni - top_eski:+.2f} TL Fark")
                st.divider()
                if kisisel > enf_genel:
                    st.error("Sepetin piyasadan daha çok pahalandı.")
                else:
                    st.success("Piyasa ortalamasından iyisin.")

        if st.button("💾 Sepeti Kaydet"):
            baskets[username] = edited['Kod'].tolist()
            if github_json_yaz(SEPETLER_DOSYASI, baskets, "Basket Upd"):
                st.toast("Kaydedildi!", icon='✅')
            else:
                st.error("Hata")


@st.fragment
def render_harita_tab(df_analiz, ad_col, agirlik_col):
    st.markdown("### 🗺️ Piyasa Isı Haritası")
    fig = px.treemap(df_analiz, path=[px.Constant("Piyasa"), 'Grup', ad_col], values=agirlik_col, color='Fark',
                     color_continuous_scale='RdYlGn_r')
    fig.update_layout(template=st.session_state.plotly_template, plot_bgcolor='rgba(0,0,0,0)',
                      paper_bgcolor='rgba(0,0,0,0)', title_font=dict(color='white'))
    st.plotly_chart(fig, use_container_width=True)


@st.fragment
def render_firsat_tab(df_analiz, ad_col, son):
    st.markdown("### 📉 Piyasa Verileri (Canlı)")
    product_list = sorted(df_analiz[ad_col].unique())
    sel = st.selectbox("Ürün Seç", product_list)
    if st.button("Fiyatları Getir (Selenium)", type="primary"):
        my_p = df_analiz[df_analiz[ad_col] == sel][son].values[0] if not df_analiz[
            df_analiz[ad_col] == sel].empty else 0
        st.metric("Senin Fiyatın", f"{my_p:.2f} TL")
        results_data = []
        target_url = f"https://www.google.com/search?q={sel}&tbm=shop&hl=tr&gl=TR"
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
                chrome_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which(
                    "google-chrome")
                if chrome_path:
                    chrome_options.binary_location = chrome_path
                driver_path = shutil.which("chromedriver") or shutil.which("chromium-driver") or "/usr/bin/chromedriver"
                if not driver_path:
                    st.error("⚠️ Sürücü bulunamadı.")
                else:
                    service = Service(executable_path=driver_path)
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    driver.get(target_url)
                    try:
                        wait = WebDriverWait(driver, 5)
                        consent_buttons = driver.find_elements(By.XPATH,
                                                               "//button[contains(., 'Kabul') or contains(., 'Accept')]")
                        if consent_buttons:
                            consent_buttons[0].click();
                            time.sleep(2)
                    except:
                        pass
                    time.sleep(3)
                    page_source = driver.page_source
                    driver.quit()
                    soup = BeautifulSoup(page_source, "html.parser")
                    cards = soup.find_all(attrs={"aria-label": re.compile(r"Şu Anki Fiyat:")})
                    for card in cards:
                        raw_text = card['aria-label'].replace(u'\xa0', ' ').strip()
                        price_pattern = r"(?:₺\s?)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})(?:\s?TL)?"
                        matches = list(re.finditer(price_pattern, raw_text))
                        if matches:
                            best_match = matches[0]
                            p_price_str = best_match.group(1)
                            try:
                                clean_price = float(p_price_str.replace('.', '').replace(',', '.'))
                            except:
                                clean_price = 0
                            start, end = best_match.span()
                            p_name = raw_text[:start].strip().rstrip('.').rstrip(':').replace("Şu Anki Fiyat",
                                                                                              "").strip()
                            p_vendor = re.sub(r'^(TL|₺|\.|,)\s*', '', raw_text[end:].strip()).replace("ve daha fazlası",
                                                                                                      "").strip()
                            if len(p_vendor) > 30:
                                p_vendor = p_vendor.split('.')[0]
                            if clean_price > 0:
                                results_data.append(
                                    {"Ürün": p_name, "Fiyat": f"{clean_price:.2f} TL", "Sayı": clean_price,
                                     "Satıcı": p_vendor})
                    if results_data:
                        df_res = pd.DataFrame(results_data).sort_values("Sayı")
                        for _, row in df_res.iterrows():
                            is_cheaper = row['Sayı'] < my_p and row['Sayı'] > 0
                            card_bg = "#ecfdf5" if is_cheaper else "#ffffff"
                            border_col = "#10b981" if is_cheaper else "#e2e8f0"
                            st.markdown(f"""
                            <div style="background:{card_bg}; border:1px solid {border_col}; padding:15px; border-radius:10px; margin-bottom:10px;">
                                <div style="font-weight:bold; color:#1e293b;">{row['Ürün']}</div>
                                <div style="display:flex; justify-content:space-between; margin-top:5px;">
                                    <div style="color:#64748b;">🏪 {row['Satıcı']}</div>
                                    <div style="font-weight:800; color:#0f172a;">{row['Fiyat']}</div>
                                </div>
                            </div>""", unsafe_allow_html=True)
                    else:
                        st.warning("Sonuç bulunamadı.")
            except Exception as e:
                st.error(f"Hata: {e}")


@st.fragment
def render_liste_tab(df_analiz, ad_col, baz, son):
    st.data_editor(df_analiz[['Grup', ad_col, 'Fark', baz, son]], column_config={
        "Fark": st.column_config.ProgressColumn("Değişim", format="%.2f", min_value=-0.5, max_value=0.5)
    }, hide_index=True, use_container_width=True)
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as w:
        df_analiz.to_excel(w, index=False)
    st.download_button("📥 İndir", out.getvalue(), "Rapor.xlsx")


@st.fragment
def render_haber_tab():
    st.markdown("### 📰 Haberler")
    if st.button("Haberleri Tara"):
        with st.spinner("Analiz ediliyor..."):
            txt, heads = get_market_sentiment()
            st.success(txt)
            for h in heads:
                st.caption(f"• {h}")


@st.fragment
def render_rapor_tab(df_analiz, enf_genel, top, ad_col, bugun):
    st.markdown("### 📝 Rapor Oluştur")
    if 'rep_txt' not in st.session_state:
        st.session_state.rep_txt = ""
    if st.button("Rapor Yazdır"):
        with st.spinner("Yazılıyor..."):
            summ = f"Enflasyon: %{enf_genel:.2f}, En Çok Artan: {top[ad_col]}"
            model = genai.GenerativeModel('gemini-2.5-flash')
            st.session_state.rep_txt = model.generate_content(f"Rapor yaz: {summ}").text

    if st.session_state.rep_txt:
        st.markdown(st.session_state.rep_txt)
        pdf = create_pdf_report(st.session_state.rep_txt)
        st.download_button("📥 PDF İndir", pdf, "Rapor.pdf")


@st.fragment
def render_alarm_tab(df_analiz, ad_col, son, username):
    st.markdown("### 🔔 Alarm Kur")
    alarms = github_json_oku(ALARMS_DOSYASI)
    if not isinstance(alarms, list):
        alarms = []

    sel = st.selectbox("Ürün", sorted(df_analiz[ad_col].unique()), key="al_prod")
    curr = df_analiz[df_analiz[ad_col] == sel][son].values[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Şu An", f"{curr:.2f} TL")
    tgt = c2.number_input("Hedef", value=float(curr) * 0.9)
    mail = c3.text_input("E-Posta")

    if st.button("Alarm Kur"):
        alarms.append({"user": username, "kod": df_analiz[df_analiz[ad_col] == sel]['Kod'].values[0], "hedef": tgt,
                       "durum": "aktif", "email": mail})
        github_json_yaz(ALARMS_DOSYASI, alarms)
        st.success("Kuruldu!")

    my_alarms = [a for a in alarms if a.get('user') == username]
    if my_alarms:
        st.dataframe(pd.DataFrame(my_alarms))
        if st.button("Temizle"):
            alarms = [a for a in alarms if a.get('user') != username]
            github_json_yaz(ALARMS_DOSYASI, alarms)
            st.rerun()


# ==============================================================================
# 5. DASHBOARD & MAIN
# ==============================================================================

def dashboard_modu():
    bugun = datetime.now().strftime("%Y-%m-%d")
    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    # --- Sidebar ---
    with st.sidebar:
        st.markdown(
            f"<div style='border:1px solid #444; padding:10px; border-radius:10px; text-align:center;'>👤 {st.session_state['username'].upper()}</div>",
            unsafe_allow_html=True)
        rates = get_exchange_rates()
        st.markdown(f"USD: {rates['USD']} | EUR: {rates['EUR']} | ALTIN: {rates['GA']:.0f}")
        if st.button("Çıkış"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- Header ---
    st.markdown(f"### 💎 Enflasyon Monitörü ({bugun})")

    # --- ADMIN UPDATE ---
    if st.session_state['username'] in ADMIN_USERS:
        if st.button("🚀 SİSTEMİ GÜNCELLE"):
            with st.status("Güncelleniyor..."):
                res = html_isleyici(lambda x: st.write(x))
                if "OK" in res:
                    st.cache_data.clear()
                    st.success("Tamam!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(res)

    if not df_f.empty and not df_s.empty:
        # --- VERİ HAZIRLIĞI ---
        df_s.columns = df_s.columns.str.strip()
        kod_col = next((c for c in df_s.columns if c.lower() == 'kod'), 'Kod')
        ad_col = next((c for c in df_s.columns if 'ad' in c.lower()), 'Madde adı')
        agirlik_col = next((c for c in df_s.columns if 'agirlik' in c.lower().replace('ğ', 'g')), 'Agirlik_2025')

        df_f['Kod'] = df_f['Kod'].astype(str).apply(kod_standartlastir)
        df_s['Kod'] = df_s[kod_col].astype(str).apply(kod_standartlastir)
        df_f['Tarih_DT'] = pd.to_datetime(df_f['Tarih'], errors='coerce')
        df_f = df_f.dropna(subset=['Tarih_DT']).sort_values('Tarih_DT')
        df_f['Tarih_Str'] = df_f['Tarih_DT'].dt.strftime('%Y-%m-%d')
        df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
        df_f = df_f[df_f['Fiyat'] > 0]

        pivot = df_f.pivot_table(index='Kod', columns='Tarih_Str', values='Fiyat', aggfunc='last').ffill(axis=1).bfill(
            axis=1).reset_index()

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
            baz, son = gunler[0], gunler[-1]

            # --- HESAPLAMALAR ---
            endeks_genel = (df_analiz.dropna(subset=[son, baz])[agirlik_col] * (
                        df_analiz[son] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[son, baz])[
                               agirlik_col].sum() * 100
            enf_genel = (endeks_genel / 100 - 1) * 100

            # --- 1. Kümülatif Fark (Isı Haritası için) ---
            df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1

            # --- 2. GÜNLÜK FARK (Ticker İçin) ---
            if len(gunler) >= 2:
                dunku = gunler[-2]
                df_analiz['Gunluk_Degisim'] = (df_analiz[son] / df_analiz[dunku]) - 1
            else:
                df_analiz['Gunluk_Degisim'] = 0

            # En Yüksek Risk (Günlük Değişime Göre)
            top = df_analiz.sort_values('Gunluk_Degisim', ascending=False).iloc[0]

            gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
            enf_gida = ((gida[son] / gida[baz] * gida[agirlik_col]).sum() / gida[
                agirlik_col].sum() - 1) * 100 if not gida.empty else 0

            # --- KPI & TICKER ---
            inc = df_analiz.sort_values('Gunluk_Degisim', ascending=False).head(5)
            dec = df_analiz.sort_values('Gunluk_Degisim', ascending=True).head(5)
            items = []
            for _, r in inc.iterrows():
                if r['Gunluk_Degisim'] > 0:
                    items.append(f"<span style='color:#f87171'>▲ {r[ad_col]} %{r['Gunluk_Degisim'] * 100:.1f}</span>")
            for _, r in dec.iterrows():
                if r['Gunluk_Degisim'] < 0:
                    items.append(f"<span style='color:#4ade80'>▼ {r[ad_col]} %{r['Gunluk_Degisim'] * 100:.1f}</span>")
            if not items:
                items.append("Son 24 saatte önemli değişim yok.")

            st.markdown(
                f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;&nbsp; • &nbsp;&nbsp; ".join(items)}</div></div></div>',
                unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Genel Enflasyon", f"%{enf_genel:.2f}")
            c2.metric("Gıda Enflasyonu", f"%{enf_gida:.2f}")
            c3.metric("Günün Zammı", f"{top[ad_col][:15]}", f"%{top['Gunluk_Degisim'] * 100:.1f}")
            c4.metric("Risk Durumu", "Yüksek" if enf_genel > 5 else "Stabil")

            # --- SEKMELER (FRAGMANLAR ÇAĞRILIYOR) ---
            tabs = st.tabs(
                ["📊 ANALİZ", "📈 İSTATİSTİK", "🛒 SEPET", "🗺️ HARİTA", "📉 PİYASA", "📋 LİSTE", "📰 HABER", "📝 RAPOR",
                 "🔔 ALARM"])

            # Trend Verisi Hazırla
            trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (
                        df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                                   agirlik_col].sum() * 100} for g in gunler]
            df_trend = pd.DataFrame(trend_data);
            df_trend['Tarih'] = pd.to_datetime(df_trend['Tarih'])
            df_resmi, _ = get_official_inflation()

            with tabs[0]:
                render_analiz_tab(df_analiz, df_trend, df_resmi, baz, agirlik_col)
            with tabs[1]:
                render_istatistik_tab(df_analiz, pivot, ad_col)
            with tabs[2]:
                render_sepet_tab(df_analiz, ad_col, baz, son, enf_genel, st.session_state['username'])
            with tabs[3]:
                render_harita_tab(df_analiz, ad_col, agirlik_col)
            with tabs[4]:
                render_firsat_tab(df_analiz, ad_col, son)
            with tabs[5]:
                render_liste_tab(df_analiz, ad_col, baz, son)
            with tabs[6]:
                render_haber_tab()
            with tabs[7]:
                render_rapor_tab(df_analiz, enf_genel, top, ad_col, bugun)
            with tabs[8]:
                render_alarm_tab(df_analiz, ad_col, son, st.session_state['username'])


def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    # URL Parametre Kontrolü
    params = st.query_params
    if "session_user" in params and not st.session_state['logged_in']:
        st.session_state['logged_in'] = True;
        st.session_state['username'] = params["session_user"];
        st.rerun()

    if "reset_user" in params and not st.session_state['logged_in']:
        reset_user = params["reset_user"]
        st.markdown("<h1 style='text-align:center;'>🔐 ŞİFRE SIFIRLAMA</h1>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            with st.form("reset_form"):
                st.info(f"Kullanıcı: {reset_user}")
                new_p = st.text_input("Yeni Şifre", type="password")
                conf_p = st.text_input("Şifreyi Onayla", type="password")
                if st.form_submit_button("GÜNCELLE"):
                    if new_p == conf_p:
                        ok, msg = github_user_islem("update_password", username=reset_user, password=new_p)
                        if ok:
                            st.success("Tamam!")
                            time.sleep(1)
                            st.query_params.clear()
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Şifreler uyuşmuyor.")
        return

    if not st.session_state['logged_in']:
        st.markdown("<h1 style='text-align:center;'>ENFLASYON MONİTÖRÜ</h1>", unsafe_allow_html=True)
        t_login, t_reg, t_forgot = st.tabs(["Giriş", "Kayıt", "Unuttum"])
        with t_login:
            with st.form("login"):
                u = st.text_input("Kullanıcı")
                p = st.text_input("Şifre", type="password")
                rem = st.checkbox("Beni Hatırla")
                if st.form_submit_button("Giriş"):
                    ok, msg = github_user_islem("login", u, p)
                    if ok:
                        st.session_state['logged_in'] = True;
                        st.session_state['username'] = u
                        if rem:
                            st.query_params["session_user"] = u
                        else:
                            st.query_params.clear()
                        st.rerun()
                    else:
                        st.error(msg)
        with t_reg:
            if 'reg_stage' not in st.session_state:
                st.session_state.reg_stage = 1
            if 'reg_temp' not in st.session_state:
                st.session_state.reg_temp = {}

            if st.session_state.reg_stage == 1:
                with st.form("reg1"):
                    u = st.text_input("Kullanıcı Adı")
                    e = st.text_input("Email")
                    p = st.text_input("Şifre", type="password")
                    if st.form_submit_button("Kod Gönder"):
                        code = str(random.randint(100000, 999999))
                        if send_verification_email(e, code):
                            st.session_state.reg_temp = {"u": u, "p": p, "e": e, "c": code}
                            st.session_state.reg_stage = 2;
                            st.rerun()
                        else:
                            st.error("Mail hatası")
            else:
                with st.form("reg2"):
                    st.info(f"{st.session_state.reg_temp.get('e')} adresine gelen kodu gir.")
                    code = st.text_input("Kod")
                    if st.form_submit_button("Onayla"):
                        if code == st.session_state.reg_temp['c']:
                            ok, msg = github_user_islem("register", st.session_state.reg_temp['u'],
                                                        st.session_state.reg_temp['p'], st.session_state.reg_temp['e'])
                            if ok:
                                st.success("Kaydedildi!")
                                st.session_state.reg_stage = 1
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("Hatalı Kod")
                if st.button("Geri"):
                    st.session_state.reg_stage = 1
                    st.rerun()

        with t_forgot:
            with st.form("forgot"):
                e = st.text_input("Email")
                if st.form_submit_button("Sıfırla"):
                    ok, msg = github_user_islem("forgot_password", email=e)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    else:
        dashboard_modu()


if __name__ == "__main__":
    main()