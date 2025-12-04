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
st.set_page_config(page_title="ENFLASYON MONITORU PRO", page_icon="💎", layout="wide", initial_sidebar_state="expanded")

# --- CSS (ULTRA PRO TASARIM) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400&display=swap');
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #1e293b; }

        /* HEADER */
        .header-container { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 30px; }
        .app-title { font-size: 32px; font-weight: 800; color: #0f172a; }
        .live-indicator { display: flex; align-items: center; font-size: 13px; font-weight: 600; color: #15803d; background: #ffffff; padding: 6px 12px; border-radius: 20px; border: 1px solid #bbf7d0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .pulse { width: 8px; height: 8px; background-color: #22c55e; border-radius: 50%; margin-right: 8px; box-shadow: 0 0 0 rgba(34, 197, 94, 0.4); animation: pulse 2s infinite; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); } 70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); } 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); } }

        /* KARTLAR */
        .metric-card { background: #ffffff; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; transition: all 0.3s ease; }
        .metric-card:hover { transform: translateY(-2px); border-color: #94a3b8; }
        .metric-label { font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; }
        .metric-value { font-size: 28px; font-weight: 800; color: #0f172a; margin: 8px 0; }
        .metric-delta { font-size: 13px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
        .delta-pos { background: #fee2e2; color: #ef4444; } .delta-neg { background: #dcfce7; color: #16a34a; } .delta-neu { background: #f1f5f9; color: #475569; }

        /* ANALİZ KUTUSU */
        .analysis-box { background: #ffffff; border-left: 6px solid #3b82f6; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); font-size: 16px; line-height: 1.7; color: #334155; }
        .analysis-title { font-size: 20px; font-weight: 800; color: #0f172a; margin-bottom: 15px; }
        .highlight { font-weight: 700; color: #1e293b; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }
        .trend-up { color: #dc2626; font-weight: 700; } .trend-down { color: #16a34a; font-weight: 700; }

        /* ASİSTAN & BUTONLAR */
        .bot-bubble { background: #f8fafc; border-left: 4px solid #3b82f6; padding: 20px; border-radius: 0 8px 8px 8px; margin-top: 20px; color: #334155; font-size: 15px; line-height: 1.6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .action-container { margin-top: 40px; text-align: center; }
        .action-btn button { background: #0f172a !important; color: white !important; height: 60px; font-size: 18px !important; font-weight: 600 !important; border-radius: 8px !important; width: 100%; border: none !important; transition: all 0.2s ease; }
        .action-btn button:hover { background: #334155 !important; transform: translateY(-1px); }
        .bot-log { background: #1e293b; color: #4ade80; font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 15px; border-radius: 8px; height: 200px; overflow-y: auto; text-align: left; margin-top: 20px; }

        /* USER SIDEBAR */
        .user-stat { padding: 10px; background: #f1f5f9; border-radius: 8px; margin-bottom: 10px; font-size: 14px; font-weight: 600; color: #334155; }
        .user-online { color: #16a34a; font-size: 12px; float: right; }

        .signature-footer { text-align: center; margin-top: 60px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 14px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
USERS_DOSYASI = "kullanicilar.json"
SEPETLER_DOSYASI = "user_baskets.json"  # YENİ: KİŞİSEL SEPETLER
SAYFA_ADI = "Madde_Sepeti"
HTML_KLASORU = "HTML_DOSYALARI"


def get_github_repo():
    try:
        return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
    except:
        return None


# --- AUTH & JSON FONKSIYONLARI ---
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
        return False, "Hatalı Giriş"

    elif action == "register":
        if username in users_db: return False, "Kullanıcı adı dolu"
        users_db[username] = hash_password(password)
        github_json_yaz(USERS_DOSYASI, users_db, f"New User: {username}")
        return True, "Kayıt Başarılı"


# --- EXCEL & GUNCELLEME MOTORU ---
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
        if fiyat == 0:  # Regex fallback
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

    # --- YENİ: KULLANICI ADMİN PANELİ (SIDEBAR) ---
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['username'].upper()}")
        if st.button("Çıkış Yap"):
            st.session_state['logged_in'] = False
            st.rerun()

        st.divider()
        st.markdown("### 👥 Kullanıcı İstatistikleri")
        users_db = github_json_oku(USERS_DOSYASI)
        st.metric("Toplam Üye", len(users_db))

        st.caption("Kayıtlı Kullanıcılar:")
        for user in users_db.keys():
            status = "🟢 Online" if user == st.session_state['username'] else "⚪ Offline"
            st.markdown(f"<div class='user-stat'>{user} <span class='user-online'>{status}</span></div>",
                        unsafe_allow_html=True)

    st.markdown(
        '<div class="header-container"><div class="app-title">Enflasyon Monitörü <span style="font-weight:300; color:#64748b;">Pro</span></div><div class="live-indicator"><div class="pulse"></div>SİSTEM AKTİF</div></div>',
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

                # UI METRİKLER
                st.markdown(
                    f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;•&nbsp; ".join([f"<span style=\'color:{'#dc2626' if r['Fark'] > 0 else '#16a34a'}\'>{r[ad_col]} %{r['Fark'] * 100:.1f}</span>" for _, r in df_analiz.sort_values("Fark", ascending=False).head(15).iterrows()])}</div></div></div>',
                    unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)

                def card(c, t, v, s, m="neu"):
                    c.markdown(
                        f'<div class="metric-card"><div class="metric-label">{t}</div><div class="metric-value">{v}</div><div class="metric-delta {"delta-pos" if m == "pos" else "delta-neg" if m == "neg" else "delta-neu"}">{s}</div></div>',
                        unsafe_allow_html=True)

                card(c1, "Genel Enflasyon", f"%{enf_genel:.2f}", "Piyasa Ortalaması", "pos")
                card(c2, "Gıda Enflasyonu", f"%{enf_gida:.2f}", "Mutfak", "pos")
                card(c3, "En Yüksek Risk", f"{top[ad_col][:12]}..", f"%{top['Fark'] * 100:.1f} Artış", "pos")
                card(c4, "Veri Tarihi", str(son), f"{len(gunler)} Günlük", "neu")
                st.markdown("<br>", unsafe_allow_html=True)

                grp_max = df_analiz.groupby('Grup')['Fark'].mean().idxmax();
                grp_val = df_analiz.groupby('Grup')['Fark'].mean().max() * 100
                st.markdown(
                    f'<div class="analysis-box"><div class="analysis-title">📊 Piyasa Raporu</div><p>Piyasa genelinde <span class="trend-up">YÜKSELİŞ</span> hakim. Enflasyon sepeti <span class="highlight">%{enf_genel:.2f}</span> artış gösterdi. En yüksek baskı <span class="trend-up">%{grp_val:.2f}</span> ile <span class="highlight">{grp_max}</span> grubundan geliyor.</p></div>',
                    unsafe_allow_html=True)

                # --- YENİ: KİŞİSEL SEPET SEKMESİ ---
                t1, t2, t3, t4, t5, t6 = st.tabs(
                    ["🛒 KENDİ SEPETİM", "🤖 ASİSTAN", "🫧 DAĞILIM", "🚀 ZİRVE", "📉 FIRSATLAR", "📑 LİSTE"])

                with t1:
                    st.markdown("### 🛒 Kişisel Enflasyon Hesaplayıcı")
                    st.caption(
                        "Burada kendi tükettiğiniz ürünleri seçerek, size özel enflasyon oranını görebilirsiniz.")

                    # Sepetleri Yükle
                    baskets = github_json_oku(SEPETLER_DOSYASI)
                    user_codes = baskets.get(st.session_state['username'], [])

                    # Seçim Kutusu
                    all_products = df_analiz[ad_col].unique()
                    # Kod'dan isme çevir
                    default_names = df_analiz[df_analiz['Kod'].isin(user_codes)][ad_col].tolist()

                    selected_names = st.multiselect("Sepetinizdeki Ürünler:", all_products, default=default_names)

                    # Kaydet Butonu
                    if st.button("Sepetimi Kaydet"):
                        new_codes = df_analiz[df_analiz[ad_col].isin(selected_names)]['Kod'].tolist()
                        baskets[st.session_state['username']] = new_codes
                        if github_json_yaz(SEPETLER_DOSYASI, baskets, "Basket Update"):
                            st.success("✅ Sepetiniz kaydedildi!")
                            time.sleep(1);
                            st.rerun()
                        else:
                            st.error("Kayıt hatası")

                    # Kişisel Enflasyon Hesabı
                    if selected_names:
                        my_df = df_analiz[df_analiz[ad_col].isin(selected_names)]
                        if not my_df.empty:
                            my_enf = ((my_df[son] / my_df[baz] * my_df[agirlik_col]).sum() / my_df[
                                agirlik_col].sum() - 1) * 100

                            col_my, col_chart = st.columns([1, 2])
                            with col_my:
                                st.metric("SANA ÖZEL ENFLASYON", f"%{my_enf:.2f}", f"Genel: %{enf_genel:.2f}")
                                if my_enf > enf_genel:
                                    st.warning("🚨 Senin enflasyonun piyasa ortalamasından yüksek!")
                                else:
                                    st.success("✅ Senin enflasyonun piyasadan daha düşük.")

                            with col_chart:
                                fig_comp = go.Figure()
                                fig_comp.add_trace(
                                    go.Bar(x=['Genel Enflasyon', 'Senin Enflasyonun'], y=[enf_genel, my_enf],
                                           marker_color=['#94a3b8', '#3b82f6']))
                                fig_comp.update_layout(title="Kişisel vs Genel Enflasyon", height=300)
                                st.plotly_chart(fig_comp, use_container_width=True)

                                st.dataframe(my_df[[ad_col, 'Fark', baz, son]], use_container_width=True)
                    else:
                        st.info("Henüz sepetine ürün eklemedin.")

                with t2:
                    st.markdown("##### 🤖 Asistan")
                    with st.container():
                        q = st.text_input("", placeholder="Ürün ara...", label_visibility="collapsed")
                    if q:
                        res = df_analiz[df_analiz[ad_col].str.lower().str.contains(q.lower())]
                        if not res.empty:
                            t = res.iloc[0] if len(res) == 1 else \
                            df_analiz[df_analiz[ad_col] == st.selectbox("Seç:", res[ad_col].unique())].iloc[0]
                            fark = t['Fark'] * 100
                            style = {"c": "#dc2626", "b": "#fef2f2", "i": "📈", "t": "ZAMLANDI"} if fark > 0 else {
                                "c": "#16a34a", "b": "#f0fdf4", "i": "🎉", "t": "İNDİRİMDE"} if fark < 0 else {
                                "c": "#475569", "b": "#f8fafc", "i": "➖", "t": "SABİT"}
                            st.markdown(
                                f'<div style="background:{style["b"]}; border-left:5px solid {style["c"]}; padding:20px; border-radius:8px; margin-top:20px;"><div style="color:{style["c"]}; font-weight:800; font-size:20px;">{style["i"]} {style["t"]} (%{fark:.2f})</div><b>{t[ad_col]}</b><br>Başlangıç: {t[baz]:.2f} TL ➜ Son: {t[son]:.2f} TL</div>',
                                unsafe_allow_html=True)
                        else:
                            st.warning("Bulunamadı")

                with t3:
                    st.plotly_chart(
                        px.treemap(df_analiz, path=[px.Constant("Piyasa"), 'Grup', ad_col], values=agirlik_col,
                                   color='Fark', color_continuous_scale='RdYlGn_r'), use_container_width=True)
                with t4:
                    st.table(df_analiz.sort_values('Fark', ascending=False).head(10)[[ad_col, 'Grup', 'Fark']].assign(
                        Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
                with t5:
                    low = df_analiz[df_analiz['Fark'] < 0].sort_values('Fark').head(10)
                    if not low.empty:
                        st.table(low[[ad_col, 'Grup', 'Fark']].assign(
                            Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
                    else:
                        st.info("İndirim yok.")
                with t6:
                    st.dataframe(df_analiz[['Grup', ad_col, 'Fark', baz, son]], use_container_width=True)

        except Exception as e:
            st.error(f"Hata: {e}")

    else:
        st.warning("Veri bekleniyor... Lütfen ZIP dosyalarınızı yükleyin ve butona basın.")

    st.markdown('<div class="action-container"><div class="action-btn">', unsafe_allow_html=True)
    if st.button("VERİTABANINI GÜNCELLE (ZIP & MANUEL)", type="primary", use_container_width=True):
        log_ph = st.empty();
        log_msgs = []

        def logger(m):
            log_msgs.append(f"> {m}");
            log_ph.markdown(f'<div class="bot-log">{"<br>".join(log_msgs)}</div>', unsafe_allow_html=True)

        res = html_isleyici(logger)
        if "OK" in res:
            st.success("✅ Güncellendi!"); time.sleep(2); st.rerun()
        else:
            st.error(res)
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="signature-footer">Designed by Fatih Arslan © 2025</div>', unsafe_allow_html=True)


# --- 5. ANA GİRİŞ KONTROLÜ ---
def main():
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        st.markdown("<h1 style='text-align: center; color: #0f172a; margin-top:50px;'>ENFLASYON MONİTÖRÜ PRO</h1>",
                    unsafe_allow_html=True)
        st.markdown(
            '<div class="login-container"><div class="login-header">Giriş Yap</div><div class="login-sub">Piyasa verilerine erişmek için giriş yapın.</div>',
            unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["GİRİŞ YAP", "KAYIT OL"])
        with tab1:
            l_user = st.text_input("Kullanıcı Adı", key="l_u")
            l_pass = st.text_input("Şifre", type="password", key="l_p")
            if st.button("Giriş Yap", use_container_width=True):
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
            r_user = st.text_input("Kullanıcı Adı Seçin", key="r_u")
            r_pass = st.text_input("Şifre Belirleyin", type="password", key="r_p")
            if st.button("Kayıt Ol", use_container_width=True):
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