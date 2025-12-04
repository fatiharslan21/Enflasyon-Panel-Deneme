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
from github import Github
from io import BytesIO

# --- 1. SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="ENFLASYON MONITORU PRO", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

# --- 🎨 ULTRA PREMIUM UI CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400&display=swap');
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #1e293b; }
        [data-testid="stSidebar"], [data-testid="stToolbar"], footer {display: none !important;}

        .header-container { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 30px; }
        .app-title { font-size: 32px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; }
        .live-indicator { display: flex; align-items: center; font-size: 13px; font-weight: 600; color: #15803d; background: #ffffff; padding: 6px 12px; border-radius: 20px; border: 1px solid #bbf7d0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .pulse { width: 8px; height: 8px; background-color: #22c55e; border-radius: 50%; margin-right: 8px; box-shadow: 0 0 0 rgba(34, 197, 94, 0.4); animation: pulse 2s infinite; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); } 70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); } 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); } }

        .metric-card { background: #ffffff; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; transition: all 0.3s ease; }
        .metric-card:hover { transform: translateY(-2px); border-color: #94a3b8; }
        .metric-label { font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; }
        .metric-value { font-size: 28px; font-weight: 800; color: #0f172a; margin: 8px 0; }
        .metric-delta { font-size: 13px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
        .delta-pos { background: #fee2e2; color: #ef4444; } .delta-neg { background: #dcfce7; color: #16a34a; } .delta-neu { background: #f1f5f9; color: #475569; }

        .ticker-wrap { width: 100%; overflow: hidden; background: #ffffff; border-bottom: 1px solid #cbd5e1; white-space: nowrap; padding: 10px 0; margin-bottom: 25px; }
        .ticker { display: inline-block; animation: ticker 50s linear infinite; }
        .ticker-item { display: inline-block; padding: 0 2rem; font-weight: 600; font-size: 14px; color: #475569; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .analysis-box { background: #ffffff; border-left: 6px solid #3b82f6; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); font-size: 16px; line-height: 1.7; color: #334155; }
        .analysis-title { font-size: 20px; font-weight: 800; color: #0f172a; margin-bottom: 15px; }
        .highlight { font-weight: 700; color: #1e293b; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }
        .trend-up { color: #dc2626; font-weight: 700; } .trend-down { color: #16a34a; font-weight: 700; }

        .action-container { margin-top: 40px; text-align: center; }
        .action-btn button { background: #0f172a !important; color: white !important; height: 60px; font-size: 18px !important; font-weight: 600 !important; border-radius: 8px !important; width: 100%; border: none !important; transition: all 0.2s ease; }
        .action-btn button:hover { background: #334155 !important; transform: translateY(-1px); }
        .bot-log { background: #1e293b; color: #4ade80; font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 15px; border-radius: 8px; height: 200px; overflow-y: auto; text-align: left; margin-top: 20px; }

        .bot-bubble { background: #f8fafc; border-left: 4px solid #3b82f6; padding: 20px; border-radius: 0 8px 8px 8px; margin-top: 20px; color: #334155; font-size: 15px; line-height: 1.6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .signature-footer { text-align: center; margin-top: 60px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 14px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
SAYFA_ADI = "Madde_Sepeti"
HTML_KLASORU = "HTML_DOSYALARI"


def get_github_repo():
    try:
        return Github(st.secrets["github"]["token"]).get_repo(st.secrets["github"]["repo_name"])
    except:
        return None


def github_excel_oku(dosya_adi, sayfa_adi=None):
    repo = get_github_repo()
    if not repo: return pd.DataFrame()
    try:
        c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
        return pd.read_excel(BytesIO(c.decoded_content), sheet_name=sayfa_adi,
                             dtype={'Kod': str}) if sayfa_adi else pd.read_excel(BytesIO(c.decoded_content))
    except:
        return pd.DataFrame()


# --- KRİTİK GÜNCELLEME: EKLEME (APPEND) MANTIĞI ---
def github_excel_guncelle(df_yeni, dosya_adi, log_cb=None):
    repo = get_github_repo()
    if not repo: return "Repo Yok"
    try:
        # 1. Mevcut Veritabanını İndir
        try:
            c = repo.get_contents(dosya_adi, ref=st.secrets["github"]["branch"])
            df_eski = pd.read_excel(BytesIO(c.decoded_content))

            # Formatlama (Çakışma olmaması için)
            df_eski['Tarih'] = pd.to_datetime(df_eski['Tarih']).dt.strftime('%Y-%m-%d')
            df_eski['Kod'] = df_eski['Kod'].astype(str)

            # 2. Bugüne ait verileri temizle (Yenilerini ekleyeceğiz, duplicate olmasın)
            yeni_tarih = df_yeni['Tarih'].iloc[0]
            if log_cb: log_cb(f"📅 Veritabanı Tarihi: {yeni_tarih} (Eski kayıtlar korunuyor...)")

            # Eski verilerden, bugüne ait olanları çıkar (sadece güncellenecek olanları)
            df_eski_filtered = df_eski[df_eski['Tarih'] != yeni_tarih]

            # 3. Eskiler + Yeniler (Append)
            df_final = pd.concat([df_eski_filtered, df_yeni], ignore_index=True)

        except Exception as e:
            # Dosya yoksa veya okunamadıysa sıfırdan oluştur
            df_final = df_yeni
            if log_cb: log_cb("⚠️ Mevcut veri bulunamadı, yeni dosya oluşturuluyor.")

        # 4. GitHub'a Geri Yükle
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            df_final.to_excel(w, index=False, sheet_name='Fiyat_Log')

        msg = f"Data Update: {len(df_yeni)} new items added on {datetime.now().strftime('%Y-%m-%d')}"

        if 'c' in locals():
            repo.update_file(c.path, msg, out.getvalue(), c.sha, branch=st.secrets["github"]["branch"])
        else:
            repo.create_file(dosya_adi, msg, out.getvalue(), branch=st.secrets["github"]["branch"])

        return "OK"
    except Exception as e:
        return str(e)


# --- 3. HTML & MANUEL PARSER ---
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

    # MİGROS
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
                lambda s: s.select_one("fe-product-price .amount"),
                lambda s: s.select_one(".product-price")
            ]
            for get in selectors:
                if el := get(soup):
                    if v := temizle_fiyat(el.get_text()): fiyat = v; kaynak = "Migros(CSS)"; break
    # CİMRİ
    elif "cimri" in domain:
        for sel in ["div.rTdMX", ".offer-price", "div.sS0lR"]:
            if els := soup.select(sel):
                vals = [v for v in [temizle_fiyat(e.get_text()) for e in els] if v and v > 0]
                if vals: fiyat = min(vals); kaynak = "Cimri(CSS)"; break
    # GENEL
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

    if fiyat == 0:  # REGEX
        if m := re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:TL|₺)', soup.get_text()[:5000]):
            if v := temizle_fiyat(m.group(1)): fiyat = v; kaynak = "Regex"

    return fiyat, kaynak


def html_isleyici(log_callback):
    repo = get_github_repo()
    if not repo: return "GitHub Bağlantı Hatası"
    log_callback("📂 Konfigürasyon okunuyor...")

    try:
        # 1. Konfigürasyonu Oku
        df_conf = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)
        df_conf['Kod'] = df_conf['Kod'].astype(str).apply(kod_standartlastir)
        url_map = {row['URL'].strip(): row for _, row in df_conf.iterrows() if pd.notna(row['URL'])}

        veriler = []
        islenen_kodlar = set()  # !!! ÖNCELİK TAKİP LİSTESİ !!!

        bugun = datetime.now().strftime("%Y-%m-%d")
        simdi = datetime.now().strftime("%H:%M")

        # --- A. ÖNCELİK: MANUEL FİYATLAR ---
        log_callback("✍️ Manuel fiyat girişleri taranıyor...")
        manuel_sayac = 0
        if 'Manuel_Fiyat' in df_conf.columns:
            for _, row in df_conf.iterrows():
                if pd.notna(row['Manuel_Fiyat']) and str(row['Manuel_Fiyat']).strip() != "":
                    try:
                        fiyat_man = float(row['Manuel_Fiyat'])
                        if fiyat_man > 0:
                            veriler.append({
                                "Tarih": bugun, "Zaman": simdi,
                                "Kod": row['Kod'], "Madde_Adi": row['Madde adı'],
                                "Fiyat": fiyat_man, "Kaynak": "Manuel Giriş", "URL": row['URL']
                            })
                            islenen_kodlar.add(row['Kod'])  # BU KODU KİLİTLE
                            manuel_sayac += 1
                    except:
                        pass

        if manuel_sayac > 0: log_callback(f"✅ {manuel_sayac} adet manuel fiyat eklendi (Öncelikli).")

        # --- B. İKİNCİ: HTML İŞLEME ---
        contents = repo.get_contents(HTML_KLASORU, ref=st.secrets["github"]["branch"])
        log_callback(f"📦 {len(contents)} HTML dosyası bulundu. İşleniyor...")

        html_sayac = 0
        for file_content in contents:
            if not file_content.name.endswith((".html", ".htm")): continue

            raw = file_content.decoded_content.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(raw, 'html.parser')

            found_url = None
            if c := soup.find("link", rel="canonical"): found_url = c.get("href")
            if not found_url and (m := soup.find("meta", property="og:url")): found_url = m.get("content")

            if found_url and found_url.strip() in url_map:
                target = url_map[found_url.strip()]

                # !!! ÖNCELİK KONTROLÜ: Eğer manuel girildiyse HTML'i atla !!!
                if target['Kod'] in islenen_kodlar:
                    continue

                fiyat, kaynak = fiyat_bul_siteye_gore(soup, target['URL'])

                if fiyat > 0:
                    veriler.append({
                        "Tarih": bugun, "Zaman": simdi,
                        "Kod": target['Kod'], "Madde_Adi": target['Madde adı'],
                        "Fiyat": fiyat, "Kaynak": kaynak, "URL": target['URL']
                    })
                    islenen_kodlar.add(target['Kod'])
                    html_sayac += 1

        if veriler:
            log_callback(f"💾 Toplam {len(veriler)} veri (Manuel: {manuel_sayac}, HTML: {html_sayac}) kaydediliyor...")
            return github_excel_guncelle(pd.DataFrame(veriler), FIYAT_DOSYASI, log_callback)
        else:
            return "Hiçbir veri bulunamadı."

    except Exception as e:
        return f"Hata: {str(e)}"


# --- 4. DASHBOARD MODU ---
def dashboard_modu():
    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    st.markdown(
        '<div class="header-container"><div class="app-title">Enflasyon Monitörü <span style="font-weight:300; color:#64748b;">Analist</span></div><div class="live-indicator"><div class="pulse"></div>SİSTEM AKTİF</div></div>',
        unsafe_allow_html=True)

    if not df_f.empty and not df_s.empty:
        df_f['Tarih'] = pd.to_datetime(df_f['Tarih']);
        df_f['Fiyat'] = pd.to_numeric(df_f['Fiyat'], errors='coerce')
        df_f['Tam_Zaman'] = pd.to_datetime(df_f['Tarih'].astype(str) + ' ' + df_f['Zaman'].astype(str),
                                           errors='coerce') if 'Zaman' in df_f.columns else df_f['Tarih']
        pivot = df_f.sort_values('Tam_Zaman').pivot_table(index='Kod', columns=df_f['Tarih'].dt.date, values='Fiyat',
                                                          aggfunc='last').ffill(axis=1).bfill(axis=1)

        if not pivot.empty:
            df_analiz = pd.merge(df_s, pivot, on='Kod', how='left').dropna(subset=['Agirlik_2025'])
            gunler = sorted(pivot.columns);
            baz, son = gunler[0], gunler[-1]
            trend = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])['Agirlik_2025'] * (
                        df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                              'Agirlik_2025'].sum() * 100} for g in gunler]
            df_trend = pd.DataFrame(trend)
            genel_enf = (df_trend['TÜFE'].iloc[-1] / 100 - 1) * 100
            df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
            top = df_analiz.sort_values('Fark', ascending=False).iloc[0]
            gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
            gida_enf = ((gida[son] / gida[baz] * gida['Agirlik_2025']).sum() / gida[
                'Agirlik_2025'].sum() - 1) * 100 if not gida.empty else 0

            # METRİKLER
            st.markdown(
                f'<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{" &nbsp;•&nbsp; ".join([f"<span style=\'color:{'#dc2626' if r['Fark'] > 0 else '#16a34a'}\'>{r['Madde adı']} %{r['Fark'] * 100:.1f}</span>" for _, r in df_analiz.sort_values("Fark", ascending=False).head(15).iterrows()])}</div></div></div>',
                unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)

            def card(c, t, v, s, m="neu"):
                c.markdown(
                    f'<div class="metric-card"><div class="metric-label">{t}</div><div class="metric-value">{v}</div><div class="metric-delta {"delta-pos" if m == "pos" else "delta-neg" if m == "neg" else "delta-neu"}">{s}</div></div>',
                    unsafe_allow_html=True)

            card(c1, "Genel Endeks", f"{df_trend['TÜFE'].iloc[-1]:.2f}", "Baz: 100", "neu")
            card(c2, "Genel Enflasyon", f"%{genel_enf:.2f}", "Kümülatif", "pos")
            card(c3, "Gıda Enflasyonu", f"%{gida_enf:.2f}", "Mutfak", "pos")
            card(c4, "En Yüksek Risk", f"{top['Madde adı'][:12]}..", f"%{top['Fark'] * 100:.1f} Artış", "pos")
            st.markdown("<br>", unsafe_allow_html=True)

            # ANALİZ
            grp_max = df_analiz.groupby('Grup')['Fark'].mean().idxmax();
            grp_val = df_analiz.groupby('Grup')['Fark'].mean().max() * 100
            st.markdown(
                f'<div class="analysis-box"><div class="analysis-title">📊 Piyasa Raporu</div><p>Piyasa genelinde <span class="trend-up">YÜKSELİŞ</span> hakim. Enflasyon sepeti <span class="highlight">%{genel_enf:.2f}</span> artış gösterdi. En yüksek baskı <span class="trend-up">%{grp_val:.2f}</span> ile <span class="highlight">{grp_max}</span> grubundan geliyor.</p></div>',
                unsafe_allow_html=True)

            c_txt, c_chart = st.columns([2, 3])
            with c_chart:
                fig = px.treemap(df_analiz, path=[px.Constant("Piyasa Geneli"), 'Grup', 'Madde adı'],
                                 values='Agirlik_2025', color='Fark', color_continuous_scale='RdYlGn_r',
                                 title="Enflasyon Sıcaklık Haritası")
                fig.update_layout(margin=dict(t=30, l=0, r=0, b=0), height=350);
                st.plotly_chart(fig, use_container_width=True)

            # TABS
            t1, t2, t3, t4, t5 = st.tabs(["🤖 ASİSTAN", "🫧 DAĞILIM", "🚀 ZİRVE", "📉 FIRSATLAR", "📑 LİSTE"])
            with t1:
                st.markdown("##### 🤖 Asistan")
                with st.container():
                    q = st.text_input("", placeholder="Ürün ara...", label_visibility="collapsed")
                if q:
                    res = df_analiz[df_analiz['Madde adı'].str.lower().str.contains(q.lower())]
                    if not res.empty:
                        if len(res) > 1:
                            st.info("Birden fazla sonuç:"); t = \
                            df_analiz[df_analiz['Madde adı'] == st.selectbox("Seç:", res['Madde adı'].unique())].iloc[0]
                        else:
                            t = res.iloc[0]
                        fark = t['Fark'] * 100
                        style = {"c": "#dc2626", "b": "#fef2f2", "i": "📈", "t": "ZAMLANDI"} if fark > 0 else {
                            "c": "#16a34a", "b": "#f0fdf4", "i": "🎉", "t": "İNDİRİMDE"} if fark < 0 else {
                            "c": "#475569", "b": "#f8fafc", "i": "➖", "t": "SABİT"}
                        st.markdown(
                            f'<div style="background:{style["b"]}; border-left:5px solid {style["c"]}; padding:20px; border-radius:8px; margin-top:20px;"><div style="color:{style["c"]}; font-weight:800; font-size:20px;">{style["i"]} {style["t"]} (%{fark:.2f})</div><b>{t["Madde adı"]}</b><br>Başlangıç: {t[baz]:.2f} TL ➜ Son: {t[son]:.2f} TL</div>',
                            unsafe_allow_html=True)
                    else:
                        st.warning("Bulunamadı")

            with t2:
                st.plotly_chart(px.scatter(df_analiz, x="Grup", y="Fark", size="Agirlik_2025", color="Fark",
                                           color_continuous_scale="RdYlGn_r", size_max=60), use_container_width=True)
            with t3:
                st.table(df_analiz.sort_values('Fark', ascending=False).head(10)[['Madde adı', 'Grup', 'Fark']].assign(
                    Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
            with t4:
                low = df_analiz[df_analiz['Fark'] < 0].sort_values('Fark').head(10)
                if not low.empty:
                    st.table(low[['Madde adı', 'Grup', 'Fark']].assign(
                        Fark=lambda x: x['Fark'].apply(lambda v: f"%{v * 100:.2f}")))
                else:
                    st.info("İndirim yok.")
            with t5:
                st.dataframe(df_analiz[['Grup', 'Madde adı', 'Fark', baz, son]], use_container_width=True)

    else:
        st.warning("Veri bekleniyor... Lütfen HTML klasörünü yükleyip butona basın.")

    # ACTION BUTTON
    st.markdown('<div class="action-container"><div class="action-btn">', unsafe_allow_html=True)
    if st.button("VERİTABANINI GÜNCELLE (HTML & MANUEL)", type="primary", use_container_width=True):
        log_ph = st.empty()
        log_msgs = []

        def logger(m):
            log_msgs.append(f"> {m}")
            log_ph.markdown(f'<div class="bot-log">{"<br>".join(log_msgs)}</div>', unsafe_allow_html=True)

        res = html_isleyici(logger)
        if "OK" in res:
            st.success("✅ Veritabanı Güncellendi!"); time.sleep(2); st.rerun()
        else:
            st.error(res)
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="signature-footer">Designed by Fatih Arslan © 2025</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    dashboard_modu()