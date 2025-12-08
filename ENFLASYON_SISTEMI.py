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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- GEMINI AYARI ---
if "gemini" in st.secrets:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])

# --- 1. AYARLAR ---
st.set_page_config(
    page_title="ENFLASYON MONİTÖRÜ",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ADMIN AYARI ---
# Buraya yetkili olmasını istediğiniz kullanıcı adlarını yazın
ADMIN_USERS = ["fatih", "ahmet", "mehmet"]

# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
USERS_DOSYASI = "kullanicilar.json"
ACTIVITY_DOSYASI = "user_activity.json"
SEPETLER_DOSYASI = "user_baskets.json"
SAYFA_ADI = "Madde_Sepeti"


# --- PDF RAPOR MOTORU ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'ENFLASYON DURUM RAPORU', 0, 1, 'C')
        self.set_y(10)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(220, 50, 50)
        self.cell(0, 10, 'GIZLI / CONFIDENTIAL - YONETIM KURULU OZEL', 0, 1, 'R')
        self.set_text_color(0, 0, 0)
        self.ln(5)
        self.line(10, 25, 200, 25)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Enflasyon Monitoru AI - Sayfa {self.page_no()}', 0, 0, 'C')


def create_pdf_report(text_content, filename="Rapor.pdf"):
    pdf = PDFReport()
    pdf.add_page()
    tr_map = {'ğ': 'g', 'Ğ': 'G', 'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O',
              'ç': 'c', 'Ç': 'C', '₺': 'TL', 'â': 'a', 'î': 'i'}
    clean_text = text_content
    for k, v in tr_map.items():
        clean_text = clean_text.replace(k, v)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, clean_text)
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5,
                   "Bu rapor yapay zeka destekli piyasa analiz sistemi tarafindan otomatik olarak olusturulmustur.")
    return pdf.output(dest='S').encode('latin-1')


# --- HABER MOTORU ---
def get_market_sentiment():
    rss_url = "https://news.google.com/rss/search?q=ekonomi+gıda+zam+türkiye&hl=tr&gl=TR&ceid=TR:tr"
    try:
        feed = feedparser.parse(rss_url)
        headlines = [entry.title for entry in feed.entries[:8]]
        news_text = "\n".join([f"- {h}" for h in headlines])
        prompt = f"""
        Aşağıdaki son dakika ekonomi haber başlıklarını bir Piyasa Analisti gibi yorumla.
        HABERLER: {news_text}
        GÖREVİN:
        1. Bu haberler gıda fiyatlarını veya genel enflasyonu nasıl etkiler? (Olumlu/Olumsuz)
        2. "Piyasa Havası"nı tek kelimeyle tanımla (Örn: Gergin, Bekleyişte, Riskli, İyimser).
        3. En kritik 1 haberi seç ve nedenini kısaca açıkla.
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


def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()


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
@st.cache_data(ttl=600, show_spinner=False)
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


# --- YARDIMCI FONKSİYONLAR ---
def update_user_status(username):
    try:
        activity = github_json_oku(ACTIVITY_DOSYASI)
        activity[username] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        github_json_yaz(ACTIVITY_DOSYASI, activity, f"Activity: {username}")
    except:
        pass


def send_reset_email(to_email, username):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        app_url = "https://enflasyon-gida.streamlit.app/"
        reset_link = f"{app_url}?reset_user={username}"
        subject = "🔐 Şifre Sıfırlama - Enflasyon Monitörü"
        body = f"Merhaba {username},\n\nŞifreni sıfırlamak için:\n{reset_link}\n\nSevgiler."
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        return True, "Sıfırlama bağlantısı gönderildi."
    except Exception as e:
        return False, f"Mail Hatası: {str(e)}"


def github_user_islem(action, username=None, password=None, email=None):
    users_db = github_json_oku(USERS_DOSYASI)
    if action == "login":
        if username in users_db:
            stored_data = users_db[username]
            stored_pass = stored_data if isinstance(stored_data, str) else stored_data.get("password")
            if stored_pass == hash_password(password): return True, "Başarılı"
        return False, "Hatalı Kullanıcı Adı veya Şifre"
    elif action == "register":
        if username in users_db: return False, "Kullanıcı adı alınmış."
        users_db[username] = {"password": hash_password(password), "email": email,
                              "created_at": datetime.now().strftime("%Y-%m-%d")}
        github_json_yaz(USERS_DOSYASI, users_db, f"New User: {username}")
        return True, "Kayıt Başarılı"
    elif action == "forgot_password":
        found_user = None
        for u, data in users_db.items():
            if isinstance(data, dict) and data.get("email") == email: found_user = u; break
        if found_user: return send_reset_email(email, found_user)
        return False, "Kayıtlı e-posta bulunamadı."
    elif action == "update_password":
        if username in users_db:
            user_data = users_db[username]
            if isinstance(user_data, str): user_data = {"email": "", "created_at": ""}
            user_data["password"] = hash_password(password)
            users_db[username] = user_data
            if github_json_yaz(USERS_DOSYASI, users_db,
                               f"Password Reset: {username}"): return True, "Şifreniz güncellendi."
        return False, "Kullanıcı bulunamadı."
    return False, "Hata"


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
        user_upper = st.session_state['username'].upper()

        # --- YENİ EKLENEN KISIM ---
        is_admin = st.session_state['username'] in ADMIN_USERS
        role_title = "SYSTEM ADMIN" if is_admin else "VERİ ANALİSTİ"
        # ---------------------------

        st.markdown(f"""
            <div style="background:white; border:1px solid #e2e8f0; border-radius:12px; padding:15px; text-align:center; margin-bottom:20px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:32px; margin-bottom:5px;">👤</div>
                <div style="font-family:'Poppins'; font-weight:700; font-size:18px; color:#1e293b;">{user_upper}</div>
                <div style="font-size:11px; text-transform:uppercase; color:#64748b; margin-top:4px;">{role_title}</div>
            </div>
        """, unsafe_allow_html=True)

        if is_admin:
            st.markdown("<h3 style='color:#1e293b; font-size:16px;'>⚙️ Kontrol Paneli</h3>", unsafe_allow_html=True)
            st.divider()

            # Çevrimiçi ekip herkes görsün mü yoksa sadece admin mi?
            # Eğer sadece admin görsün isterseniz bu bloğu da if is_admin içine alın.
        st.markdown("<h3 style='color:#1e293b; font-size:16px;'>🟢 Çevrimiçi Ekip</h3>", unsafe_allow_html=True)

        users_db = github_json_oku(USERS_DOSYASI)
        activity_db = github_json_oku(ACTIVITY_DOSYASI)
        update_user_status(st.session_state['username'])

        user_list = []
        for u in users_db.keys():
            last_seen_str = activity_db.get(u, "2000-01-01 00:00:00")
            try:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
            except:
                last_seen = datetime(2000, 1, 1)
            is_online = (datetime.now() - last_seen).total_seconds() < 300
            user_list.append({"name": u, "online": is_online})

        for u in sorted(user_list, key=lambda x: (not x['online'], x['name'] != ADMIN_USER, x['name'])):
            role_icon = "🛡️" if u['name'] in ADMIN_USERS else ""
            st.markdown(f"""
                <div style="background:white; border:1px solid #e2e8f0; padding:10px; margin-bottom:6px; border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
                    <span style="display:flex; align-items:center; color:#0f172a; font-size:13px; font-weight:600;">
                        <span style="height:8px; width:8px; border-radius:50%; display:inline-block; margin-right:10px; background-color:{'#22c55e' if u['online'] else '#cbd5e1'}; box-shadow:{'0 0 4px #22c55e' if u['online'] else 'none'};"></span>
                        {u['name']} {role_icon}
                    </span>
                </div>
            """, unsafe_allow_html=True)
        st.divider()
        if st.button("Güvenli Çıkış", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- CSS: LIGHT MODE GLOBAL ---
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Poppins:wght@400;600;800&family=JetBrains+Mono:wght@400&display=swap');
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #0f172a; }
        section[data-testid="stSidebar"] { background-color: #f1f5f9; border-right: 1px solid #e2e8f0; }
        section[data-testid="stSidebar"] h1, h2, h3, .stMarkdown { color: #1e293b !important; }
        .header-container { display: flex; justify-content: space-between; align-items: center; padding: 20px 30px; background: white; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); border-bottom: 4px solid #3b82f6; }
        .app-title { font-family: 'Poppins', sans-serif; font-size: 32px; font-weight: 800; letter-spacing: -1px; background: linear-gradient(90deg, #0f172a 0%, #3b82f6 50%, #0f172a 100%); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: shine 5s linear infinite; }
        @keyframes shine { to { background-position: 200% center; } }
        .metric-card { background: white; padding: 24px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.03); border: 1px solid #e2e8f0; position: relative; overflow: hidden; transition: all 0.3s ease; }
        .metric-card:hover { transform: translateY(-5px); box-shadow: 0 20px 40px rgba(59, 130, 246, 0.15); border-color: #3b82f6; }
        .metric-card::before { content: ''; position: absolute; top: 0; left: 0; width: 6px; height: 100%; }
        .card-blue::before { background: #3b82f6; } .card-purple::before { background: #8b5cf6; } .card-emerald::before { background: #10b981; } .card-orange::before { background: #f59e0b; }
        .metric-label { color: #64748b; font-size: 13px; font-weight: 700; text-transform: uppercase; margin-bottom: 5px; }
        .metric-val { color: #1e293b; font-size: 36px; font-weight: 800; font-family: 'Poppins', sans-serif; letter-spacing: -1px; }
        .metric-val.long-text { font-size: 24px !important; line-height: 1.2; }
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

    if is_admin:
        st.markdown('<div class="update-btn-container">', unsafe_allow_html=True)
        if st.button("🚀 SİSTEMİ GÜNCELLE VE ANALİZ ET", type="primary", use_container_width=True):
            with st.status("Veri Tabanı Güncelleniyor...", expanded=True) as status:
                st.write("📡 GitHub bağlantısı kuruluyor...")
                time.sleep(0.5)
                st.write("📦 ZIP dosyaları taranıyor...")
                log_ph = st.empty();
                log_msgs = []

                def logger(m):
                    log_msgs.append(f"> {m}");
                    log_ph.markdown(f'<div class="bot-log">{"<br>".join(log_msgs)}</div>', unsafe_allow_html=True)

                res = html_isleyici(logger)
                status.update(label="İşlem Tamamlandı!", state="complete", expanded=False)
            if "OK" in res:
                st.toast('Veritabanı Güncellendi!', icon='🎉')
                st.success("✅ Sistem Başarıyla Senkronize Edildi!");
                time.sleep(2);
                st.rerun()
            else:
                st.error(res)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    else:
        # Admin değilse sadece boşluk bırak veya bilgilendirme mesajı yaz
        st.info("👋 Hoşgeldiniz. Veriler otomatik olarak sunulmaktadır.")
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
                    df_analiz['Agirlik_2025'] = 1; agirlik_col = 'Agirlik_2025'

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

                inc = df_analiz.sort_values('Fark', ascending=False).head(5)
                dec = df_analiz.sort_values('Fark', ascending=True).head(5)
                items = [f"<span style='color:#f87171'>▲ {r[ad_col]} %{r['Fark'] * 100:.1f}</span>" for _, r in
                         inc.iterrows()] + [f"<span style='color:#4ade80'>▼ {r[ad_col]} %{r['Fark'] * 100:.1f}</span>"
                                            for _, r in dec.iterrows()]
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
                    kpi_card("En Yüksek Risk", f"{top[ad_col][:15]}", f"%{top['Fark'] * 100:.1f} Artış", "#f59e0b",
                             "card-orange", is_long_text=True)
                st.markdown("<br>", unsafe_allow_html=True)

                # --- SEKMELER (DÜZENLENDİ) ---
                t_analiz, t_istatistik, t_sepet, t_harita, t_firsat, t_liste, t_haber, t_rapor = st.tabs(
                    ["📊 ANALİZ", "📈 İSTATİSTİK", "🛒 SEPET", "🗺️ HARİTA", "📉 PİYASA VERİLERİ", "📋 LİSTE", "📰 HABERLER",
                     "📝 PRO RAPOR"])

                with t_analiz:
                    st.markdown("### 📈 Enflasyon Momentum Analizi ve Gelecek Tahmini")
                    trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (
                                df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                                           agirlik_col].sum() * 100} for g in gunler]
                    df_trend = pd.DataFrame(trend_data)
                    df_trend['Tarih'] = pd.to_datetime(df_trend['Tarih'])
                    df_resmi, msg = get_official_inflation()

                    with st.spinner("Yapay zeka gelecek tahmini yapıyor..."):
                        df_forecast = predict_inflation_prophet(df_trend)

                    start_date = df_trend['Tarih'].min()
                    end_date = df_forecast['ds'].max() if not df_forecast.empty else df_trend['Tarih'].max()

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

                    fig_main.update_layout(template="plotly_white", height=500, hovermode="x unified",
                                           title="Enflasyon: Geçmiş, Şimdi ve Gelecek",
                                           legend=dict(orientation="h", y=1.1), yaxis=dict(title="TÜFE Endeksi"),
                                           xaxis=dict(range=[start_date, end_date]), plot_bgcolor='rgba(0,0,0,0)',
                                           paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_main, use_container_width=True)

                with t_istatistik:
                    col_hist, col_box = st.columns(2)
                    df_analiz['Fark_Yuzde'] = df_analiz['Fark'] * 100
                    fig_hist = px.histogram(df_analiz, x="Fark_Yuzde", nbins=40, title="📊 Zam Dağılımı Frekansı",
                                            color_discrete_sequence=['#8b5cf6'])
                    fig_hist.update_layout(template="plotly_white", xaxis_title="Artış Oranı (%)",
                                           yaxis_title="Ürün Adedi", plot_bgcolor='rgba(0,0,0,0)',
                                           paper_bgcolor='rgba(0,0,0,0)')
                    col_hist.plotly_chart(fig_hist, use_container_width=True)
                    fig_box = px.box(df_analiz, x="Grup", y="Fark_Yuzde", title="📦 Sektörel Fiyat Dengesizliği",
                                     color="Grup")
                    fig_box.update_layout(template="plotly_white", xaxis_title="Sektör", showlegend=False,
                                          plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    col_box.plotly_chart(fig_box, use_container_width=True)

                with t_sepet:
                    st.info(
                        "💡 **Akıllı İpucu:** Kendi tüketim alışkanlıklarına göre ürünleri seçerek kişisel enflasyonunu hesapla.")
                    baskets = github_json_oku(SEPETLER_DOSYASI)
                    user_codes = baskets.get(st.session_state['username'], [])
                    all_products = df_analiz[ad_col].unique()
                    default_names = df_analiz[df_analiz['Kod'].isin(user_codes)][ad_col].tolist()
                    with st.expander("📝 Sepet İçeriğini Düzenle", expanded=False):
                        with st.form("basket_form"):
                            selected_names = st.multiselect("Takip Ettiğin Ürünler:", all_products,
                                                            default=default_names)
                            if st.form_submit_button("Sepeti Güncelle"):
                                new_codes = df_analiz[df_analiz[ad_col].isin(selected_names)]['Kod'].tolist()
                                baskets[st.session_state['username']] = new_codes
                                github_json_yaz(SEPETLER_DOSYASI, baskets, "Basket Update")
                                st.success("Sepet güncellendi!");
                                time.sleep(1);
                                st.rerun()
                    if selected_names:
                        my_df = df_analiz[df_analiz[ad_col].isin(selected_names)]
                        if not my_df.empty:
                            my_enf = ((my_df[son] / my_df[baz] * my_df[agirlik_col]).sum() / my_df[
                                agirlik_col].sum() - 1) * 100
                            c_my, c_ch = st.columns([1, 2])
                            c_my.metric("KİŞİSEL ENFLASYON", f"%{my_enf:.2f}", f"Genel: %{enf_genel:.2f}",
                                        delta_color="inverse")
                            fig_comp = go.Figure()
                            fig_comp.add_trace(go.Bar(y=['Genel', 'Senin'], x=[enf_genel, my_enf], orientation='h',
                                                      marker_color=['#cbd5e1', '#3b82f6'],
                                                      text=[f"%{enf_genel:.2f}", f"%{my_enf:.2f}"],
                                                      textposition='auto'))
                            fig_comp.update_layout(template="plotly_white", height=200, margin=dict(t=0, b=0, l=0, r=0),
                                                   xaxis=dict(showgrid=False), plot_bgcolor='rgba(0,0,0,0)',
                                                   paper_bgcolor='rgba(0,0,0,0)')
                            c_ch.plotly_chart(fig_comp, use_container_width=True)
                            st.dataframe(my_df[[ad_col, 'Fark', baz, son]], use_container_width=True)
                    else:
                        st.warning("Henüz bir sepet oluşturmadın.")

                with t_harita:
                    c1, c2 = st.columns([2, 1])
                    fig_tree = px.treemap(df_analiz, path=[px.Constant("Piyasa"), 'Grup', ad_col], values=agirlik_col,
                                          color='Fark', color_continuous_scale='RdYlGn_r', title="🔥 Isı Haritası")
                    fig_tree.update_layout(margin=dict(t=40, l=0, r=0, b=0))
                    c1.plotly_chart(fig_tree, use_container_width=True)
                    fig_sun = px.sunburst(df_analiz, path=['Grup', ad_col], values=agirlik_col,
                                          title="Sektörel Ağırlık")
                    fig_sun.update_layout(margin=dict(t=40, l=0, r=0, b=0))
                    c2.plotly_chart(fig_sun, use_container_width=True)

                with t_firsat:
                    st.markdown("### 🛍️ Piyasadaki Benzer Ürünler")
                    st.info("Piyasadaki Google fiyatlarını anlık tarar.")
                    product_list = sorted(df_analiz[ad_col].unique())
                    selected_product = st.selectbox("Hangi ürünü Google Shopping'te tarayalım?", product_list)
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

                                        # 1. Temizlik
                                        raw_text = raw_text.replace(u'\xa0', ' ').strip()

                                        # 2. Regex ile Fiyat Formatını Bul
                                        price_pattern = r"(?:₺\s?)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})(?:\s?TL)?"
                                        matches = list(re.finditer(price_pattern, raw_text))

                                        if matches:
                                            # En iyi fiyat eşleşmesini seç
                                            best_match = matches[0]
                                            p_price_str = best_match.group(1)

                                            try:
                                                clean_price = float(p_price_str.replace('.', '').replace(',', '.'))
                                            except:
                                                clean_price = 0

                                            # Hata Düzeltme: ₺1 gibi küçük sayıları ele
                                            if clean_price < 5 and len(matches) > 1:
                                                best_match = matches[1]
                                                p_price_str = best_match.group(1)
                                                try:
                                                    clean_price = float(p_price_str.replace('.', '').replace(',', '.'))
                                                except:
                                                    pass

                                            # 3. Metni Böl ve Temizle
                                            start, end = best_match.span()

                                            # İSİM ALANI
                                            p_name = raw_text[:start].strip().rstrip('.').rstrip(':').replace(
                                                "Şu Anki Fiyat", "").strip()

                                            # SATICI ALANI
                                            p_vendor_raw = raw_text[end:].strip()
                                            # "ve daha fazlası" gibi Google eklerini temizle
                                            p_vendor = re.sub(r'^(TL|₺|\.|,)\s*', '', p_vendor_raw)
                                            p_vendor = p_vendor.replace("ve daha fazlası", "").replace(
                                                "ve diğer satıcılar", "").strip()

                                            # Satıcı çok uzunsa (muhtemelen yorum metni karışmıştır) kısalt
                                            if len(p_vendor) > 30: p_vendor = p_vendor.split('.')[0]

                                            # --- 🛑 KATI FİLTRELEME (SORUNU ÇÖZEN KISIM) ---
                                            # 1. İsim boşsa EKLEME
                                            if not p_name or len(p_name) < 2: continue

                                            # 2. Satıcı boşsa EKLEME
                                            if not p_vendor or len(p_vendor) < 2: continue

                                            # 3. İsim sadece rakamlardan oluşuyorsa (Google hatası) EKLEME
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
                                        st.warning("Google Shopping'den veri okunamadı.")
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
                    st.markdown("### 🌍 Yapay Zeka Destekli Piyasa Gündemi")
                    if st.button("Haberleri Tara ve Analiz Et", key="btn_news"):
                        with st.spinner("İnternet taranıyor, Gemini yorumluyor..."):
                            analysis_text, headlines = get_market_sentiment()
                            c_news1, c_news2 = st.columns([2, 1])
                            with c_news1: st.markdown("#### 🧠 Gemini Piyasa Yorumu"); st.success(analysis_text)
                            with c_news2: st.markdown("#### 🗞️ Son Başlıklar"); [st.caption(f"• {h}") for h in
                                                                                 headlines]

                with t_rapor:
                    st.markdown("### 📝 Profesyonel Yönetici Raporu")
                    col_gen, col_download = st.columns(2)
                    if 'report_text' not in st.session_state: st.session_state['report_text'] = ""
                    with col_gen:
                        if st.button("✍️ Raporu Yazdır (AI)", type="primary"):
                            with st.spinner("Veriler derleniyor, rapor yazılıyor..."):
                                sepet_dagilimi = df_analiz.groupby('Grup')['Fark'].mean().sort_values(ascending=False)
                                kategori_metni = ""
                                for kat, oran in sepet_dagilimi.items(): durum = "YÜKSELİŞ" if oran > 0 else "DÜŞÜŞ"; kategori_metni += f"- {kat}: %{oran * 100:.2f} ({durum})\n"
                                report_summary = f"Tarih: {datetime.now().strftime('%d-%m-%Y')}\nGenel Enflasyon: %{enf_genel:.2f}\nGıda Enflasyonu: %{enf_gida:.2f}\nEn Çok Artan: {top[ad_col]} (%{top['Fark'] * 100:.2f})\nTahmin: %{month_end_forecast:.2f}"
                                prompt_report = f"Sen kıdemli bir analistsin. Şu verilere göre PROFESYONEL bir rapor yaz:\nVERİLER:\n{report_summary}\nSEKTÖREL:\n{kategori_metni}\nŞABLON: 1.GİRİŞ 2.DETAYLAR 3.ÖNGÖRÜ. İmza: Enflasyon Monitörü AI"
                                model_rep = genai.GenerativeModel('gemini-2.5-flash')
                                st.session_state['report_text'] = model_rep.generate_content(prompt_report).text
                                st.success("Rapor oluşturuldu!")
                    if st.session_state['report_text']:
                        st.markdown("---");
                        st.markdown(st.session_state['report_text'])
                        pdf_bytes = create_pdf_report(st.session_state['report_text'])
                        with col_download: st.download_button(label="📥 PDF Olarak İndir (Kurumsal)", data=pdf_bytes,
                                                              file_name=f"Enflasyon_Raporu_{bugun}.pdf",
                                                              mime="application/pdf")
        except Exception as e:
            st.error(f"Kritik Hata: {e}")
    st.markdown(
        '<div style="text-align:center; color:#94a3b8; font-size:11px; margin-top:50px;">DESIGNED BY FATIH ARSLAN © 2025</div>',
        unsafe_allow_html=True)


# --- 5. LOGIN ---
def main():
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    params = st.query_params
    if "reset_user" in params and not st.session_state['logged_in']:
        reset_user = params["reset_user"]
        st.markdown(
            """<style>.stApp { background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab); background-size: 400% 400%; animation: gradient 15s ease infinite; } @keyframes gradient { 0% {background-position: 0% 50%;} 50% {background-position: 100% 50%;} 100% {background-position: 0% 50%;} } [data-testid="stForm"] { background: rgba(255, 255, 255, 0.95); padding: 40px; border-radius: 20px; box-shadow: 0 20px 50px rgba(0,0,0,0.3); border: 1px solid rgba(255, 255, 255, 0.2); position: relative; z-index: 9999; } [data-testid="stForm"] input { background: #f8fafc !important; border: 1px solid #e2e8f0 !important; color: #1e293b !important; }</style>""",
            unsafe_allow_html=True)
        st.markdown(
            "<div style='text-align: center; margin-top:80px; margin-bottom:30px; position:relative; z-index:9999;'><h1 style='color:white; font-family:Poppins; font-size:36px; font-weight:800;'>ŞİFRE SIFIRLAMA</h1></div>",
            unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            with st.form("reset_form"):
                st.info(f"Kullanıcı: {reset_user}")
                new_p = st.text_input("Yeni Şifre", type="password")
                conf_p = st.text_input("Şifreyi Onayla", type="password")
                if st.form_submit_button("ŞİFREYİ GÜNCELLE", use_container_width=True):
                    if new_p and new_p == conf_p:
                        ok, msg = github_user_islem("update_password", username=reset_user, password=new_p)
                        if ok:
                            st.success(msg); time.sleep(2); st.query_params.clear(); st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Şifreler uyuşmuyor.")
        return

    if not st.session_state['logged_in']:
        st.markdown(
            """<style>.stApp { background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab); background-size: 400% 400%; animation: gradient 15s ease infinite; } @keyframes gradient { 0% {background-position: 0% 50%;} 50% {background-position: 100% 50%;} 100% {background-position: 0% 50%;} } [data-testid="stForm"] { background: rgba(255, 255, 255, 0.95); padding: 40px; border-radius: 20px; box-shadow: 0 20px 50px rgba(0,0,0,0.3); border: 1px solid rgba(255, 255, 255, 0.2); position: relative; z-index: 9999; } [data-testid="stForm"] input { background: #f8fafc !important; border: 1px solid #e2e8f0 !important; color: #1e293b !important; }</style>""",
            unsafe_allow_html=True)
        st.markdown(
            "<div style='text-align: center; margin-top:80px; margin-bottom:30px; position:relative; z-index:9999;'><h1 style='color:white; font-family:Poppins; font-size:48px; font-weight:800; text-shadow: 0 4px 20px rgba(0,0,0,0.3);'>ENFLASYON MONİTÖRÜ</h1></div>",
            unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            t_log, t_reg, t_forgot = st.tabs(["🔒 GİRİŞ YAP", "📝 KAYIT OL", "🔑 ŞİFREMİ UNUTTUM"])
            with t_log:
                with st.form("login_f"):
                    l_u = st.text_input("Kullanıcı Adı");
                    l_p = st.text_input("Şifre", type="password");
                    st.checkbox("Beni Hatırla")
                    if st.form_submit_button("SİSTEME GİRİŞ", use_container_width=True):
                        ok, msg = github_user_islem("login", l_u, l_p)
                        if ok:
                            st.session_state['logged_in'] = True; st.session_state['username'] = l_u; st.success(
                                "Giriş Başarılı!"); time.sleep(1); st.rerun()
                        else:
                            st.error(msg)
            with t_reg:
                with st.form("reg_f"):
                    r_u = st.text_input("Kullanıcı Adı Belirle");
                    r_e = st.text_input("E-Posta Adresi");
                    r_p = st.text_input("Şifre Belirle", type="password")
                    if st.form_submit_button("HESAP OLUŞTUR", use_container_width=True):
                        if r_u and r_p and r_e:
                            ok, msg = github_user_islem("register", r_u, r_p, r_e)
                            if ok:
                                st.success("Kayıt Başarılı! Otomatik giriş yapılıyor..."); st.session_state[
                                    'logged_in'] = True; st.session_state['username'] = r_u; time.sleep(2); st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("Tüm alanları doldurunuz.")
            with t_forgot:
                with st.form("forgot_f"):
                    f_email = st.text_input("Kayıtlı E-Posta Adresi")
                    if st.form_submit_button("ŞİFRE SIFIRLAMA LİNKİ GÖNDER", use_container_width=True):
                        if f_email:
                            ok, msg = github_user_islem("forgot_password", email=f_email)
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                        else:
                            st.warning("Lütfen e-posta adresinizi girin.")
    else:
        dashboard_modu()


if __name__ == "__main__":
    main()