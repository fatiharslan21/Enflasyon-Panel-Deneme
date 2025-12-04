import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime, timedelta
import time
import json
import hashlib
from github import Github
from io import BytesIO
import zipfile
import base64

# --- 1. AYARLAR ---
st.set_page_config(page_title="ENFLASYON MONITORU ENTERPRISE", page_icon="💎", layout="wide",
                   initial_sidebar_state="expanded")

# --- ADMIN AYARI (BURAYA KENDİ KULLANICI ADINI YAZ) ---
ADMIN_USER = "fatiharslan"  # Buraya üye olurken kullandığın kullanıcı adını yaz

# --- CSS (FORM VE YENİ STİLLER EKLENDİ) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400&display=swap');
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #1e293b; }
        [data-testid="stSidebar"], [data-testid="stToolbar"], footer {display: none !important;}

        /* HEADER */
        .header-container { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 20px; }
        .app-title { font-size: 32px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; }
        .live-indicator { display: flex; align-items: center; font-size: 13px; font-weight: 600; color: #15803d; background: #ffffff; padding: 6px 12px; border-radius: 20px; border: 1px solid #bbf7d0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .pulse { width: 8px; height: 8px; background-color: #22c55e; border-radius: 50%; margin-right: 8px; box-shadow: 0 0 0 rgba(34, 197, 94, 0.4); animation: pulse 2s infinite; }

        /* TICKER */
        .ticker-wrap { width: 100%; overflow: hidden; background: #ffffff; border-bottom: 2px solid #3b82f6; white-space: nowrap; padding: 12px 0; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        .ticker { display: inline-block; animation: ticker 60s linear infinite; }
        .ticker-item { display: inline-block; padding: 0 2rem; font-weight: 600; font-size: 14px; color: #334155; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* KARTLAR */
        .metric-card { background: #ffffff; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; transition: all 0.3s ease; }
        .metric-card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-color: #3b82f6; }
        .metric-label { font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; }
        .metric-value { font-size: 28px; font-weight: 800; color: #0f172a; margin: 8px 0; }
        .metric-delta { font-size: 13px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
        .delta-pos { background: #fee2e2; color: #ef4444; } .delta-neg { background: #dcfce7; color: #16a34a; } .delta-neu { background: #f1f5f9; color: #475569; }

        /* LOGIN KUTUSU */
        .login-container { max-width: 400px; margin: 80px auto; padding: 40px; background: white; border-radius: 20px; box-shadow: 0 20px 50px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }

        /* SIDEBAR USER LIST */
        .user-stat { padding: 8px 12px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
        .status-dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .dot-online { background-color: #22c55e; box-shadow: 0 0 5px #22c55e; }
        .dot-offline { background-color: #cbd5e1; }
        .admin-badge { background: #0f172a; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px; }

        /* ANALİZ KUTUSU */
        .analysis-box { background: #ffffff; border-left: 5px solid #2563eb; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); font-size: 15px; line-height: 1.6; color: #334155; margin-bottom: 20px; }
        .highlight { font-weight: 700; background: #eff6ff; color: #1e40af; padding: 0 4px; border-radius: 3px; }

        /* BUTONLAR */
        .action-container { margin-top: 40px; text-align: center; }
        .action-btn button { background: #0f172a !important; color: white !important; height: 60px; font-size: 18px !important; border-radius: 12px !important; width: 100%; border: none !important; transition: all 0.2s ease; }
        .action-btn button:hover { background: #334155 !important; transform: translateY(-2px); }
        .bot-log { background: #1e293b; color: #4ade80; font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 15px; border-radius: 8px; height: 150px; overflow-y: auto; text-align: left; margin-top: 20px; }

        .signature-footer { text-align: center; margin-top: 60px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 12px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
USERS_DOSYASI = "kullanicilar.json"
ACTIVITY_DOSYASI = "user_activity.json"  # KULLANICI AKTİVİTESİ İÇİN
SEPETLER_DOSYASI = "user_baskets.json"
SAYFA_ADI = "Madde_Sepeti"
HTML_KLASORU = "HTML_DOSYALARI"


def get_github_repo():
    try:
        return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
    except:
        return None


# --- AUTH, JSON & ACTIVITY FUNCTIONS ---
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


def update_user_status(username):
    """Kullanıcının son görülme zamanını günceller"""
    try:
        activity = github_json_oku(ACTIVITY_DOSYASI)
        activity[username] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Github'a her saniye yazmak yavaşlatır, sadece session'da tutuyoruz
        # Gerçek zamanlı olması için normalde DB lazım ama burada hile yapıyoruz:
        # Sadece Login/Logout ve önemli işlemlerde GitHub'a yazıyoruz.
        github_json_yaz(ACTIVITY_DOSYASI, activity, f"Activity: {username}")
    except:
        pass


def github_user_islem(action, username=None, password=None):
    users_db = github_json_oku(USERS_DOSYASI)

    if action == "login":
        if username in users_db and users_db[username] == hash_password(password):
            update_user_status(username)  # GİRİŞTE ONLİNE YAP
            return True, "Başarılı"
        return False, "Hatalı Kullanıcı Adı veya Şifre"

    elif action == "register":
        if username in users_db: return False, "Bu kullanıcı adı zaten alınmış."
        users_db[username] = hash_password(password)
        if github_json_yaz(USERS_DOSYASI, users_db, f"New User: {username}"):
            update_user_status(username)  # KAYITTA DA ONLİNE YAP
            return True, "Kayıt Başarılı"
        return False, "Kayıt hatası"


# --- EXCEL MOTORU ---
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
            c = None; final = df_yeni

        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            final.to_excel(w, index=False, sheet_name='Fiyat_Log')

        msg = f"Data Update: {len(df_yeni)} items"
        if c:
            repo.update_file(c.path, msg, out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, msg, out.getvalue(), branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e:
        return str(e)


# --- PARSER ---
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
    kaynak = ""
    domain = url.lower() if url else ""
    if "migros" in domain:
        try:
            s = soup.find('script', type='application/ld+json');
            d = json.loads(s.string)
            if isinstance(d, list): d = d[0]
            if "offers" in d and "price" in d["offers"]: fiyat = float(d["offers"]["price"]); kaynak = "Migros(JSON)"
        except:
            pass
        if fiyat == 0:
            selectors = [
                lambda s: s.find("span", class_="currency").parent if s.find("span", class_="currency") else None,
                lambda s: s.select_one("fe-product-price .amount"), lambda s: s.select_one(".product-price")]
            for get in selectors:
                if el := get(soup):
                    if v := temizle_fiyat(el.get_text()): fiyat = v; kaynak = "Migros(CSS)"; break
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
    else:
        try:
            s = soup.find('script', type='application/ld+json');
            d = json.loads(s.string)
            if isinstance(d, list): d = d[0]
            if "offers" in d: fiyat = float(d["offers"]["price"]); kaynak = "Genel(JSON)"
        except:
            pass
        if fiyat == 0:
            for sel in [".product-price", ".price", ".current-price", "span[itemprop='price']"]:
                if el := soup.select_one(sel):
                    if v := temizle_fiyat(el.get_text()): fiyat = v; kaynak = "Genel(CSS)"; break
    if fiyat == 0 and "cimri" not in domain:
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
        zip_files = [c for c in contents if c.name.endswith(".zip")]
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


# --- 4. DASHBOARD MODU ---
def dashboard_modu():
    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    # --- YAN MENÜ (KULLANICILAR & ADMIN) ---
    with st.sidebar:
        # Kullanıcı Bilgisi
        user = st.session_state['username']
        role_badge = '<span class="admin-badge">ADMIN</span>' if user == ADMIN_USER else ''
        st.markdown(f"### 👤 {user.upper()} {role_badge}", unsafe_allow_html=True)

        # Çıkış
        if st.button("Çıkış Yap", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

        st.divider()

        # Online Kullanıcılar
        st.markdown("### 🟢 Canlı Durum")
        users_db = github_json_oku(USERS_DOSYASI)
        activity_db = github_json_oku(ACTIVITY_DOSYASI)

        # Kendimizi güncelle
        # activity_db[user] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        online_count = 0
        for u in users_db.keys():
            last_seen_str = activity_db.get(u, "2000-01-01 00:00:00")
            try:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
            except:
                last_seen = datetime(2000, 1, 1)

            # 10 dakika içinde aktifse online say
            is_online = (datetime.now() - last_seen).total_seconds() < 600
            if is_online: online_count += 1

            # Sadece Admin veya Kendisi detayları görsün
            if user == ADMIN_USER or u == user:
                status_html = f"<span class='status-dot dot-online'></span>Online" if is_online else "<span class='status-dot dot-offline'></span>Offline"
                st.markdown(f"<div class='user-stat'><div>{u}</div><div>{status_html}</div></div>",
                            unsafe_allow_html=True)

        if user != ADMIN_USER:
            st.caption(f"Toplam {len(users_db)} üye, {online_count} online.")

    # HEADER
    st.markdown(
        f'<div class="header-container"><div class="app-title">Enflasyon Monitörü <span style="font-weight:300; color:#64748b;">Enterprise</span></div><div class="live-indicator"><div class="pulse"></div>{user.upper()}</div></div>',
        unsafe_allow_html=True)

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

                # Global Enflasyon
                endeks_genel = (df_analiz.dropna(subset=[son, baz])[agirlik_col] * (
                            df_analiz[son] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[son, baz])[
                                   agirlik_col].sum() * 100
                enf_genel = (endeks_genel / 100 - 1) * 100

                df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
                top = df_analiz.sort_values('Fark', ascending=False).iloc[0]
                gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
                enf_gida = ((gida[son] / gida[baz] * gida[agirlik_col]).sum() / gida[
                    agirlik_col].sum() - 1) * 100 if not gida.empty else 0

                # TICKER (GERİ GELDİ)
                items = []
                for _, r in df_analiz.sort_values('Fark', ascending=False).head(20).iterrows():
                    clr = "#dc2626" if r['Fark'] > 0 else "#16a34a"
                    items.append(f"<span style='color:{clr}'>{r[ad_col]} %{r['Fark'] * 100:.1f}</span>")
                st.markdown(
                    f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;•&nbsp; ".join(items)}</div></div></div>',
                    unsafe_allow_html=True)

                # UI METRİKLER
                c1, c2, c3, c4 = st.columns(4)

                def card(c, t, v, s, m="neu"):
                    c.markdown(
                        f'<div class="metric-card"><div class="metric-label">{t}</div><div class="metric-value">{v}</div><div class="metric-delta {"delta-pos" if m == "pos" else "delta-neg" if m == "neg" else "delta-neu"}">{s}</div></div>',
                        unsafe_allow_html=True)

                card(c1, "Genel Enflasyon", f"%{enf_genel:.2f}", "Kümülatif", "pos")
                card(c2, "Gıda Enflasyonu", f"%{enf_gida:.2f}", "Mutfak", "pos")
                card(c3, "En Yüksek Risk", f"{top[ad_col][:12]}..", f"%{top['Fark'] * 100:.1f} Artış", "pos")
                card(c4, "Veri Tarihi", str(son), f"{len(gunler)} Günlük", "neu")
                st.markdown("<br>", unsafe_allow_html=True)

                # ANALİZ METNİ
                grp_max = df_analiz.groupby('Grup')['Fark'].mean().idxmax();
                grp_val = df_analiz.groupby('Grup')['Fark'].mean().max() * 100
                st.markdown(
                    f'<div class="analysis-box"><div class="analysis-title">📊 Piyasa Analiz Raporu ({str(son)})</div><p>Piyasa genelinde <span class="highlight">%{enf_genel:.2f}</span> seviyesinde bir enflasyon gözlemleniyor. En yüksek fiyat baskısı ortalama <span class="trend-up">%{grp_val:.2f}</span> artışla <span class="highlight">{grp_max}</span> sektöründe yaşanıyor. Gıda ürünlerindeki <span class="trend-up">%{enf_gida:.2f}</span> artış, mutfak harcamalarını doğrudan etkiliyor.</p></div>',
                    unsafe_allow_html=True)

                # SEKMELER
                tabs = st.tabs(
                    ["📊 GENEL BAKIŞ", "🛒 KENDİ SEPETİM", "🗺️ SEKTÖREL", "🤖 ASİSTAN", "📉 FIRSATLAR", "🎲 SİMÜLASYON",
                     "📑 LİSTE"])

                with tabs[0]:  # GENEL
                    trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (
                                df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                                           agirlik_col].sum() * 100} for g in gunler]
                    fig_main = px.area(pd.DataFrame(trend_data), x='Tarih', y='TÜFE', title="📈 Enflasyon Trendi",
                                       color_discrete_sequence=['#2563eb'])
                    fig_main.update_layout(plot_bgcolor='white', margin=dict(t=40, b=0, l=0, r=0),
                                           yaxis=dict(showgrid=True, gridcolor='#f1f5f9'))
                    st.plotly_chart(fig_main, use_container_width=True)

                with tabs[1]:  # KİŞİSEL SEPET
                    st.markdown("### 🛒 Kişisel Enflasyonun")
                    baskets = github_json_oku(SEPETLER_DOSYASI)
                    user_codes = baskets.get(st.session_state['username'], [])
                    all_products = df_analiz[ad_col].unique()
                    default_names = df_analiz[df_analiz['Kod'].isin(user_codes)][ad_col].tolist()

                    with st.expander("Sepetini Düzenle", expanded=False):
                        with st.form("basket_form"):
                            selected_names = st.multiselect("Ürünleri Seç:", all_products, default=default_names)
                            if st.form_submit_button("Sepeti Kaydet"):
                                new_codes = df_analiz[df_analiz[ad_col].isin(selected_names)]['Kod'].tolist()
                                baskets[st.session_state['username']] = new_codes
                                github_json_yaz(SEPETLER_DOSYASI, baskets, "Basket Update")
                                st.success("Kaydedildi!")
                                time.sleep(1);
                                st.rerun()

                    if selected_names:
                        my_df = df_analiz[df_analiz[ad_col].isin(selected_names)]
                        if not my_df.empty:
                            my_enf = ((my_df[son] / my_df[baz] * my_df[agirlik_col]).sum() / my_df[
                                agirlik_col].sum() - 1) * 100
                            col_my, col_ch = st.columns([1, 2])
                            col_my.metric("SENİN ENFLASYONUN", f"%{my_enf:.2f}", f"Piyasa: %{enf_genel:.2f}",
                                          delta_color="inverse")
                            col_ch.plotly_chart(go.Figure(go.Bar(x=['Genel', 'Senin'], y=[enf_genel, my_enf],
                                                                 marker_color=['#94a3b8', '#3b82f6'])).update_layout(
                                height=250, margin=dict(t=0, b=0)), use_container_width=True)
                            st.dataframe(my_df[[ad_col, 'Fark', baz, son]], use_container_width=True)
                    else:
                        st.info("Sepetin boş.")

                with tabs[2]:  # SEKTÖREL & TREEMAP
                    c1, c2 = st.columns(2)
                    c1.plotly_chart(
                        px.treemap(df_analiz, path=[px.Constant("Piyasa"), 'Grup', ad_col], values=agirlik_col,
                                   color='Fark', color_continuous_scale='RdYlGn_r', title="Sıcaklık Haritası"),
                        use_container_width=True)
                    # Sektörel Pasta
                    sect_data = df_analiz.groupby('Grup')['Fark'].mean().reset_index()
                    c2.plotly_chart(
                        px.pie(sect_data, values='Fark', names='Grup', title="Sektörel Artış Dağılımı", hole=0.4),
                        use_container_width=True)

                with tabs[3]:  # ASİSTAN
                    with st.form("ask_form"):
                        q = st.text_input("Ürün Ara:", placeholder="Örn: Süt")
                        if st.form_submit_button("Analiz Et") and q:
                            res = df_analiz[df_analiz[ad_col].str.lower().str.contains(q.lower())]
                            if not res.empty:
                                t = res.iloc[0]
                                fark = t['Fark'] * 100
                                st.markdown(
                                    f'<div class="bot-bubble"><b>{t[ad_col]}</b><br>Değişim: <span style="color:{"#dc2626" if fark > 0 else "#16a34a"}">%{fark:.2f}</span><br>Fiyat: {t[baz]:.2f} ➜ {t[son]:.2f} TL</div>',
                                    unsafe_allow_html=True)
                            else:
                                st.warning("Bulunamadı")

                with tabs[4]:  # FIRSATLAR
                    low = df_analiz[df_analiz['Fark'] < 0].sort_values('Fark').head(10)
                    if not low.empty:
                        st.table(low[[ad_col, 'Grup', 'Fark']].assign(
                            Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
                    else:
                        st.info("Şu an indirimde ürün yok.")

                with tabs[5]:  # SİMÜLASYON
                    c = st.columns(4)
                    inps = {g: c[i % 4].number_input(f"{g} (%)", -50., 100., 0.) for i, g in
                            enumerate(sorted(df_analiz['Grup'].unique()))}
                    etki = sum(
                        [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v
                         for g, v in inps.items()])
                    st.success(f"Yeni Tahmin: %{(enf_genel + etki):.2f}")

                with tabs[6]:  # LİSTE
                    st.dataframe(df_analiz[['Grup', ad_col, 'Fark', baz, son]], use_container_width=True)

        except Exception as e:
            st.error(f"Hata: {e}")

    # ACTION BUTTON
    st.markdown('<div class="action-container"><div class="action-btn">', unsafe_allow_html=True)
    if st.button("VERİTABANINI GÜNCELLE (ZIP & MANUEL)", type="primary", use_container_width=True):
        log_ph = st.empty();
        log_msgs = []

        def logger(m):
            log_msgs.append(f"> {m}"); log_ph.markdown(f'<div class="bot-log">{"<br>".join(log_msgs)}</div>',
                                                       unsafe_allow_html=True)

        res = html_isleyici(logger)
        if "OK" in res:
            st.success("✅ Güncellendi!"); time.sleep(2); st.rerun()
        else:
            st.error(res)
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="signature-footer">Designed by Fatih Arslan © 2025</div>', unsafe_allow_html=True)


# --- 5. LOGIN ---
def main():
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        st.markdown("<h1 style='text-align: center; color: #0f172a; margin-top:50px;'>ENFLASYON MONİTÖRÜ PRO</h1>",
                    unsafe_allow_html=True)
        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["GİRİŞ YAP", "KAYIT OL"])
        with tab1:
            with st.form("login_form"):
                l_user = st.text_input("Kullanıcı Adı")
                l_pass = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap", use_container_width=True):
                    ok, msg = github_user_islem("login", l_user, l_pass)
                    if ok:
                        st.session_state['logged_in'] = True;
                        st.session_state['username'] = l_user
                        st.success("Giriş Başarılı!");
                        time.sleep(1);
                        st.rerun()
                    else:
                        st.error(msg)
        with tab2:
            with st.form("register_form"):
                r_user = st.text_input("Kullanıcı Adı Seçin")
                r_pass = st.text_input("Şifre Belirleyin", type="password")
                if st.form_submit_button("Kayıt Ol", use_container_width=True):
                    if r_user and r_pass:
                        ok, msg = github_user_islem("register", r_user, r_pass)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("Alanları doldurun.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        dashboard_modu()


if __name__ == "__main__":
    main()