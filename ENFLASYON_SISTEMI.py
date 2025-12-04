import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime
import time
import json
import hashlib
from github import Github
from io import BytesIO
import zipfile
import base64

# --- 1. AYARLAR ---
st.set_page_config(page_title="ENFLASYON MONITORU ", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")

# --- ADMIN AYARI ---
ADMIN_USER = "fatiharslan"

# --- CSS (ULTRA SHOW & ANİMASYONLAR) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Poppins:wght@400;600;800&display=swap');

        /* GENEL */
        .stApp { background-color: #f1f5f9; font-family: 'Inter', sans-serif; color: #0f172a; }
        [data-testid="stToolbar"], footer {display: none !important;}

        /* HEADER */
        .header-container { 
            display: flex; justify-content: space-between; align-items: center; 
            padding: 20px; background: white; border-radius: 16px; margin-bottom: 25px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;
        }
        .app-title { font-family: 'Poppins', sans-serif; font-size: 28px; font-weight: 800; background: -webkit-linear-gradient(#2563eb, #1e40af); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .user-badge { background: #eff6ff; color: #2563eb; padding: 5px 15px; border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #bfdbfe; }

        /* METRİK KARTLARI (HOVER EFEKTLİ) */
        .metric-card { 
            background: white; padding: 20px; border-radius: 16px; border: 1px solid #e2e8f0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.02); transition: all 0.3s ease;
        }
        .metric-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(37, 99, 235, 0.15); border-color: #3b82f6; }
        .metric-label { color: #64748b; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .metric-val { color: #0f172a; font-size: 32px; font-weight: 800; margin: 5px 0; font-family: 'Poppins', sans-serif; }
        .metric-sub { font-size: 13px; font-weight: 500; }
        .pos { color: #dc2626; background: #fef2f2; padding: 2px 8px; border-radius: 6px; }
        .neg { color: #16a34a; background: #f0fdf4; padding: 2px 8px; border-radius: 6px; }

        /* LOGIN EKRANI (SHOW ZAMANI) */
        .login-container {
            animation: slideIn 0.8s ease-out;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 50px; border-radius: 24px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
            border: 1px solid rgba(255,255,255,0.5);
            text-align: center; max-width: 500px; margin: 0 auto;
        }
        @keyframes slideIn { from { opacity: 0; transform: translateY(-50px); } to { opacity: 1; transform: translateY(0); } }

        /* SIDEBAR USER LIST */
        .sidebar-user { 
            display: flex; align-items: center; justify-content: space-between;
            padding: 10px; margin-bottom: 8px; background: white; border-radius: 8px; border: 1px solid #e2e8f0;
        }
        .sidebar-badge { background: #0f172a; color: white; font-size: 10px; padding: 2px 6px; border-radius: 4px; }

        /* ANALİZ KUTUSU */
        .analysis-box { background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border-left: 5px solid #2563eb; padding: 25px; border-radius: 12px; border: 1px solid #e2e8f0; font-size: 15px; line-height: 1.6; color: #334155; margin-bottom: 20px; }
        .highlight { font-weight: 700; background: #dbeafe; color: #1e40af; padding: 2px 6px; border-radius: 4px; }

        /* TICKER */
        .ticker-wrap { width: 100%; overflow: hidden; background: #0f172a; color: white; padding: 10px 0; margin-bottom: 20px; border-radius: 8px; }
        .ticker { display: inline-block; animation: ticker 60s linear infinite; }
        .ticker-item { display: inline-block; padding: 0 2rem; font-weight: 500; font-size: 13px; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        /* BUTONLAR */
        .action-btn button { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important; color: white !important; height: 60px; font-size: 18px !important; font-weight: 600 !important; border-radius: 12px !important; width: 100%; border: none !important; transition: all 0.3s ease; box-shadow: 0 10px 20px rgba(15, 23, 42, 0.2); }
        .action-btn button:hover { transform: translateY(-3px); box-shadow: 0 15px 30px rgba(15, 23, 42, 0.3); }

        .signature { text-align: center; color: #94a3b8; font-size: 12px; margin-top: 50px; border-top: 1px solid #e2e8f0; padding-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
USERS_DOSYASI = "kullanicilar.json"
SEPETLER_DOSYASI = "user_baskets.json"
SAYFA_ADI = "Madde_Sepeti"
HTML_KLASORU = "HTML_DOSYALARI"


def get_github_repo():
    try:
        return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
    except:
        return None


# --- AUTH & JSON ---
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


def github_user_islem(action, username=None, password=None):
    users_db = github_json_oku(USERS_DOSYASI)
    if action == "login":
        if username in users_db and users_db[username] == hash_password(password): return True, "Başarılı"
        return False, "Hatalı Kullanıcı Adı veya Şifre"
    elif action == "register":
        if username in users_db: return False, "Bu kullanıcı adı zaten alınmış."
        users_db[username] = hash_password(password)
        github_json_yaz(USERS_DOSYASI, users_db, f"New User: {username}")
        return True, "Kayıt Başarılı"
    return False, "Hata"


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

        msg = f"Data Update"
        if c:
            repo.update_file(c.path, msg, out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, msg, out.getvalue(), branch=st.secrets["github"]["branch"])
        return "OK"
    except Exception as e:
        return str(e)


# --- BOT PARSERS ---
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

        log_callback("✍️ Fiyatlar kontrol ediliyor...")
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
        if ms > 0: log_callback(f"✅ {ms} fiyat alındı.")

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

    # --- YAN MENÜ (SADE LİSTE) ---
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['username'].upper()}")

        st.divider()
        st.markdown("### 📋 Kayıtlı Üyeler")
        users_db = github_json_oku(USERS_DOSYASI)
        st.caption(f"Toplam: {len(users_db)} Üye")

        for u in users_db.keys():
            role = '<span class="admin-badge">ADMIN</span>' if u == ADMIN_USER else ''
            st.markdown(f"<div class='sidebar-user'>{u} {role}</div>", unsafe_allow_html=True)

        st.divider()
        if st.button("Çıkış Yap", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    st.markdown(
        f'<div class="header-container"><div class="app-title">Fintech Enflasyon <span style="font-weight:300; color:#64748b;">Pro</span></div><div class="live-indicator"><div class="pulse"></div>PANEL AKTİF</div></div>',
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

                # Enflasyon Hesapla
                endeks_genel = (df_analiz.dropna(subset=[son, baz])[agirlik_col] * (
                            df_analiz[son] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[son, baz])[
                                   agirlik_col].sum() * 100
                enf_genel = (endeks_genel / 100 - 1) * 100
                df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
                top = df_analiz.sort_values('Fark', ascending=False).iloc[0]
                gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
                enf_gida = ((gida[son] / gida[baz] * gida[agirlik_col]).sum() / gida[
                    agirlik_col].sum() - 1) * 100 if not gida.empty else 0

                # --- YENİ TICKER (5 ZAM - 5 İNDİRİM) ---
                top5_inc = df_analiz.sort_values('Fark', ascending=False).head(5)
                top5_dec = df_analiz.sort_values('Fark', ascending=True).head(5)
                items = []
                for _, r in top5_inc.iterrows(): items.append(f"🔺 {r[ad_col]} %{r['Fark'] * 100:.1f}")
                for _, r in top5_dec.iterrows(): items.append(f"🔻 {r[ad_col]} %{r['Fark'] * 100:.1f}")
                st.markdown(
                    f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;&nbsp;&nbsp;&nbsp; ".join(items)}</div></div></div>',
                    unsafe_allow_html=True)

                # UI METRİKLER
                c1, c2, c3, c4 = st.columns(4)

                def card(c, t, v, s, m="neu"):
                    c.markdown(
                        f'<div class="metric-card"><div class="metric-label">{t}</div><div class="metric-val">{v}</div><div class="metric-sub"><span class="{m}">{s}</span></div></div>',
                        unsafe_allow_html=True)

                card(c1, "Genel Enflasyon", f"%{enf_genel:.2f}", "Kümülatif Değişim", "pos")
                card(c2, "Gıda Enflasyonu", f"%{enf_gida:.2f}", "Mutfak Harcaması", "pos")
                card(c3, "En Yüksek Artış", f"%{top['Fark'] * 100:.1f}", f"{top[ad_col][:15]}", "pos")
                card(c4, "Veri Tarihi", str(son), f"{len(gunler)} Günlük Veri", "neu")
                st.markdown("<br>", unsafe_allow_html=True)

                # ANALİZ
                grp_max = df_analiz.groupby('Grup')['Fark'].mean().idxmax();
                grp_val = df_analiz.groupby('Grup')['Fark'].mean().max() * 100
                st.markdown(
                    f'<div class="analysis-box"><div class="analysis-title">📊 Detaylı Piyasa Analizi ({str(son)})</div><p>Piyasa genelinde <span class="highlight">%{enf_genel:.2f}</span> seviyesinde bir enflasyonist baskı gözlemleniyor. En yüksek fiyat artışı ortalama <span class="highlight">%{grp_val:.2f}</span> ile <b>{grp_max}</b> grubunda yaşanıyor. Gıda sepetindeki <span class="highlight">%{enf_gida:.2f}</span> artış, hane halkı bütçesini doğrudan etkileyen en önemli faktör olarak öne çıkıyor.</p></div>',
                    unsafe_allow_html=True)

                t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(
                    ["📊 GENEL BAKIŞ", "⚡ VOLATİLİTE", "🛒 SEPETİM", "🗺️ SEKTÖREL", "🤖 ASİSTAN", "📉 FIRSATLAR",
                     "🎲 SİMÜLASYON", "📑 LİSTE"])

                with t1:  # GENEL
                    trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (
                                df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                                           agirlik_col].sum() * 100} for g in gunler]
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        fig_main = px.area(pd.DataFrame(trend_data), x='Tarih', y='TÜFE',
                                           title="Enflasyon Trend Analizi", color_discrete_sequence=['#2563eb'])
                        fig_main.update_layout(plot_bgcolor='white', margin=dict(t=40, b=0, l=0, r=0),
                                               yaxis=dict(showgrid=True, gridcolor='#f1f5f9'))
                        st.plotly_chart(fig_main, use_container_width=True)
                    with col2:
                        fig_gauge = go.Figure(
                            go.Indicator(mode="gauge+number", value=enf_genel, title={'text': "Enflasyon Metre"},
                                         gauge={'axis': {'range': [None, 50]}, 'bar': {'color': "#2563eb"}}))
                        st.plotly_chart(fig_gauge, use_container_width=True)

                with t2:  # YENİ: VOLATİLİTE & DAĞILIM
                    c1, c2 = st.columns(2)
                    df_analiz['Volatilite'] = abs(df_analiz['Fark'])
                    top_vol = df_analiz.sort_values('Volatilite', ascending=False).head(10)
                    c1.plotly_chart(px.bar(top_vol, x='Fark', y=ad_col, orientation='h',
                                           title="Fiyatı En Çok Değişenler (Volatilite)", color='Fark',
                                           color_continuous_scale='RdBu_r'), use_container_width=True)
                    c2.plotly_chart(px.histogram(df_analiz, x='Fark', nbins=30, title="Zam Dağılımı Histogramı",
                                                 color_discrete_sequence=['#3b82f6']), use_container_width=True)

                with t3:  # KİŞİSEL SEPET
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
                                st.success("Kaydedildi!");
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

                with t4:  # SEKTÖREL
                    c1, c2 = st.columns(2)
                    c1.plotly_chart(
                        px.treemap(df_analiz, path=[px.Constant("Piyasa"), 'Grup', ad_col], values=agirlik_col,
                                   color='Fark', color_continuous_scale='RdYlGn_r', title="Sıcaklık Haritası"),
                        use_container_width=True)
                    sect_data = df_analiz.groupby('Grup')['Fark'].mean().reset_index()
                    c2.plotly_chart(
                        px.pie(sect_data, values='Fark', names='Grup', title="Sektörel Artış Dağılımı", hole=0.4),
                        use_container_width=True)

                with t5:  # ASİSTAN
                    st.markdown("##### 🤖 Asistan")
                    with st.form("ask_form"):
                        q = st.text_input("Ürün Ara:", placeholder="Örn: Süt")
                        submitted = st.form_submit_button("Analiz Et")
                    if submitted and q:
                        res = df_analiz[df_analiz[ad_col].str.lower().str.contains(q.lower())]
                        if not res.empty:
                            target = None
                            if len(res) > 1:
                                st.info("Birden fazla sonuç bulundu, lütfen seçim yapın:")
                                secilen = st.selectbox("Seçiniz:", res[ad_col].unique())
                                target = df_analiz[df_analiz[ad_col] == secilen].iloc[0]
                            else:
                                target = res.iloc[0]
                            if target is not None:
                                fark = target['Fark'] * 100
                                st.markdown(
                                    f'<div class="bot-bubble"><b>{target[ad_col]}</b><br>Değişim: <span style="color:{"#dc2626" if fark > 0 else "#16a34a"}">%{fark:.2f}</span><br>Fiyat: {target[baz]:.2f} ➜ {target[son]:.2f} TL</div>',
                                    unsafe_allow_html=True)
                        else:
                            st.warning("Bulunamadı")

                with t6:  # FIRSATLAR (İLK 10)
                    st.table(df_analiz.sort_values('Fark', ascending=True).head(10)[[ad_col, 'Grup', 'Fark']].assign(
                        Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))

                with t7:  # SİMÜLASYON
                    c = st.columns(4)
                    inps = {g: c[i % 4].number_input(f"{g} (%)", -50., 100., 0.) for i, g in
                            enumerate(sorted(df_analiz['Grup'].unique()))}
                    etki = sum(
                        [(df_analiz[df_analiz['Grup'] == g]['Agirlik_2025'].sum() / df_analiz['Agirlik_2025'].sum()) * v
                         for g, v in inps.items()])
                    st.success(f"Yeni Tahmin: %{(enf_genel + etki):.2f}")

                with t8:  # LİSTE & EXCEL
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer: df_analiz.to_excel(writer, index=False,
                                                                                                 sheet_name='Analiz')
                    st.download_button("📥 Excel Raporunu İndir", data=output.getvalue(),
                                       file_name=f"Enflasyon_Raporu_{son}.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       use_container_width=True)
                    st.dataframe(df_analiz[['Grup', ad_col, 'Fark', baz, son]], use_container_width=True)

        except Exception as e:
            st.error(f"Hata: {e}")

    st.markdown('<div class="action-container"><div class="action-btn">', unsafe_allow_html=True)
    if st.button("FİYATLARI GÜNCELLE ", type="primary", use_container_width=True):
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
    st.markdown('<div class="signature">Designed by Fatih Arslan © 2025</div>', unsafe_allow_html=True)


# --- 5. LOGIN ---
def main():
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        st.markdown(
            "<div style='text-align: center; padding-top: 50px;'><h1 style='color: #0f172a;'>FİNTECH ENFLASYON PRO</h1><p style='color: #64748b;'>Profesyonel Piyasa Analiz Terminali</p></div>",
            unsafe_allow_html=True)
        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["GİRİŞ YAP", "KAYIT OL"])
        with tab1:
            with st.form("login_f"):
                l_u = st.text_input("Kullanıcı Adı")
                l_p = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap", use_container_width=True):
                    ok, msg = github_user_islem("login", l_u, l_p)
                    if ok:
                        st.session_state['logged_in'] = True;
                        st.session_state['username'] = l_u
                        st.success("Giriş Başarılı!");
                        time.sleep(1);
                        st.rerun()
                    else:
                        st.error(msg)
        with tab2:
            with st.form("reg_f"):
                r_u = st.text_input("Kullanıcı Adı")
                r_p = st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt Ol", use_container_width=True):
                    if r_u and r_p:
                        ok, msg = github_user_islem("register", r_u, r_p)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("Doldurunuz.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        dashboard_modu()


if __name__ == "__main__":
    main()