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

# --- 1. AYARLAR ---
st.set_page_config(
    page_title="ENFLASYON MONİTÖRÜ PRO",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ADMIN AYARI ---
ADMIN_USER = "fatih"

# --- 2. GITHUB & VERİ MOTORU ---
EXCEL_DOSYASI = "TUFE_Konfigurasyon.xlsx"
FIYAT_DOSYASI = "Fiyat_Veritabani.xlsx"
USERS_DOSYASI = "kullanicilar.json"
ACTIVITY_DOSYASI = "user_activity.json"
SEPETLER_DOSYASI = "user_baskets.json"
PREFERENCES_DOSYASI = "user_preferences.json"
SAYFA_ADI = "Madde_Sepeti"


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


def update_user_status(username):
    try:
        activity = github_json_oku(ACTIVITY_DOSYASI)
        activity[username] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        github_json_yaz(ACTIVITY_DOSYASI, activity, f"Activity: {username}")
    except:
        pass


def get_user_preferences(username):
    prefs = github_json_oku(PREFERENCES_DOSYASI)
    return prefs.get(username, {"theme": "light", "language": "tr", "notifications": True})


def save_user_preferences(username, prefs):
    all_prefs = github_json_oku(PREFERENCES_DOSYASI)
    all_prefs[username] = prefs
    github_json_yaz(PREFERENCES_DOSYASI, all_prefs, f"Prefs: {username}")


# --- MAİL GÖNDERME ---
def send_reset_email(to_email, username):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]

        app_url = "https://enflasyon-gida.streamlit.app/"
        reset_link = f"{app_url}?reset_user={username}"

        subject = "🔐 Şifre Sıfırlama - Enflasyon Monitörü"
        body = f"""
        Merhaba {username},

        Şifreni sıfırlamak için aşağıdaki bağlantıya tıkla:
        {reset_link}

        Sevgiler,
        Enflasyon Monitörü Ekibi
        """

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


# --- KULLANICI İŞLEMLERİ ---
def github_user_islem(action, username=None, password=None, email=None):
    users_db = github_json_oku(USERS_DOSYASI)

    if action == "login":
        if username in users_db:
            stored_data = users_db[username]
            stored_pass = stored_data if isinstance(stored_data, str) else stored_data.get("password")
            if stored_pass == hash_password(password):
                return True, "Başarılı"
        return False, "Hatalı Kullanıcı Adı veya Şifre"

    elif action == "register":
        if username in users_db: return False, "Kullanıcı adı alınmış."
        users_db[username] = {
            "password": hash_password(password),
            "email": email,
            "created_at": datetime.now().strftime("%Y-%m-%d")
        }
        github_json_yaz(USERS_DOSYASI, users_db, f"New User: {username}")
        return True, "Kayıt Başarılı"

    elif action == "forgot_password":
        found_user = None
        for u, data in users_db.items():
            if isinstance(data, dict) and data.get("email") == email:
                found_user = u
                break
        if found_user:
            return send_reset_email(email, found_user)
        return False, "Kayıtlı e-posta bulunamadı."

    elif action == "update_password":
        if username in users_db:
            user_data = users_db[username]
            if isinstance(user_data, str): user_data = {"email": "", "created_at": ""}
            user_data["password"] = hash_password(password)
            users_db[username] = user_data
            if github_json_yaz(USERS_DOSYASI, users_db, f"Password Reset: {username}"):
                return True, "Şifreniz başarıyla güncellendi! Giriş yapabilirsiniz."
        return False, "Kullanıcı bulunamadı."

    return False, "Hata"


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
            c = None
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


# --- BOT PARSERS ---
def temizle_fiyat(t):
    if not t: return None
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
        garbage_selectors = [
            "sm-list-page-item",
            ".horizontal-list-page-items-container",
            "app-product-carousel",
            ".similar-products",
            "div.badges-wrapper"
        ]
        for selector in garbage_selectors:
            for garbage in soup.select(selector):
                garbage.decompose()

        main_wrapper = soup.select_one(".name-price-wrapper")

        if main_wrapper:
            normal_div = main_wrapper.select_one(".price.subtitle-1")
            if normal_div:
                if val := temizle_fiyat(normal_div.get_text()):
                    return val, "Migros(Ana-Normal-Div)"

            normal_span = main_wrapper.select_one(".single-price-amount")
            if normal_span:
                if val := temizle_fiyat(normal_span.get_text()):
                    return val, "Migros(Ana-Normal-Span)"

            sale_el = main_wrapper.select_one("#sale-price, .sale-price")
            if sale_el:
                if val := temizle_fiyat(sale_el.get_text()):
                    return val, "Migros(Ana-İndirim)"

        if fiyat == 0:
            el = soup.select_one("fe-product-price .subtitle-1, .single-price-amount")
            if el:
                if val := temizle_fiyat(el.get_text()):
                    fiyat = val
                    kaynak = "Migros(Genel-Normal)"

            if fiyat == 0:
                el = soup.select_one("#sale-price")
                if el:
                    if val := temizle_fiyat(el.get_text()):
                        fiyat = val
                        kaynak = "Migros(Genel-İndirim)"

    elif "cimri" in domain:
        for sel in ["div.rTdMX", ".offer-price", "div.sS0lR", ".min-price-val"]:
            if els := soup.select(sel):
                vals = [v for v in [temizle_fiyat(e.get_text()) for e in els] if v and v > 0]
                if vals:
                    if len(vals) > 4: vals.sort(); vals = vals[1:-1]
                    fiyat = sum(vals) / len(vals)
                    kaynak = f"Cimri({len(vals)})"
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
                            veriler.append({"Tarih": bugun, "Zaman": simdi, "Kod": row['Kod'], "Madde_Adi": row[ad_col],
                                            "Fiyat": fiyat_man, "Kaynak": "Manuel", "URL": row[url_col]})
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


# ===================================================================
# 🤖 CLAUDE AI CHATBOT - AKILLI ASİSTAN
# ===================================================================
async def call_claude_api(messages, system_prompt=""):
    """Claude AI ile konuşma"""
    try:
        response = await fetch("https://api.anthropic.com/v1/messages", {
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "system": system_prompt,
                "messages": messages
            })
        })
        data = await response.json()
        return data.content[0].text if data.content else "Üzgünüm, cevap alamadım."
    except Exception as e:
        return f"API Hatası: {str(e)}"


def ai_chatbot_interface(df_analiz, ad_col, baz, son):
    """Gelişmiş AI Chatbot UI"""
    st.markdown("""
    <style>
    .chat-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 30px;
        box-shadow: 0 20px 60px rgba(102, 126, 234, 0.3);
        margin-bottom: 20px;
    }
    .chat-title {
        color: white;
        font-size: 28px;
        font-weight: 800;
        text-align: center;
        margin-bottom: 20px;
        text-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    .chat-message {
        background: white;
        border-radius: 15px;
        padding: 15px 20px;
        margin: 10px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        animation: fadeIn 0.5s ease-in;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .user-msg { 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 20%;
    }
    .ai-msg {
        background: white;
        margin-right: 20%;
        border-left: 4px solid #667eea;
    }
    .chat-input-container {
        background: white;
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .quick-btn {
        background: rgba(255,255,255,0.2);
        color: white;
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 20px;
        padding: 8px 16px;
        margin: 5px;
        cursor: pointer;
        transition: all 0.3s;
        display: inline-block;
        font-size: 13px;
    }
    .quick-btn:hover {
        background: rgba(255,255,255,0.3);
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    st.markdown('<div class="chat-title">🤖 AI Alışveriş Asistanı</div>', unsafe_allow_html=True)

    # Chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # Quick action buttons
    st.markdown("**💡 Hızlı Sorular:**", unsafe_allow_html=True)
    quick_questions = [
        "Bu hafta en çok ne zamlandı?",
        "100 TL'ye ne alabilirim?",
        "Sepetim için önerilerin neler?",
        "Hangi markette alışveriş yapmalıyım?",
        "Gelecek ay fiyatlar ne olacak?"
    ]

    cols = st.columns(3)
    for i, q in enumerate(quick_questions):
        if cols[i % 3].button(q, key=f"quick_{i}", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": q})
            # AI yanıtı (şimdilik mock, gerçek API için açıklamayı aşağıda yapacağım)
            ai_response = generate_smart_response(q, df_analiz, ad_col, baz, son)
            st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
            st.rerun()

    # Chat messages
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history[-6:]:  # Son 6 mesaj
            css_class = "user-msg" if msg["role"] == "user" else "ai-msg"
            icon = "👤" if msg["role"] == "user" else "🤖"
            st.markdown(f'<div class="chat-message {css_class}">{icon} {msg["content"]}</div>',
                        unsafe_allow_html=True)

    # Input
    st.markdown('<div class="chat-input-container">', unsafe_allow_html=True)
    user_input = st.text_input("Bir soru sor...", key="chat_input", placeholder="Örn: Peynir fiyatları nasıl?")

    col1, col2 = st.columns([4, 1])
    if col1.button("📤 Gönder", use_container_width=True) and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        ai_response = generate_smart_response(user_input, df_analiz, ad_col, baz, son)
        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
        st.rerun()

    if col2.button("🗑️ Temizle"):
        st.session_state.chat_history = []
        st.rerun()

    st.markdown('</div></div>', unsafe_allow_html=True)


def generate_smart_response(question, df_analiz, ad_col, baz, son):
    """Akıllı yanıt üretici (Claude API olmadan da çalışır)"""
    q_lower = question.lower()

    # En çok zamlanlar
    if "zam" in q_lower or "artan" in q_lower or "yükselen" in q_lower:
        top5 = df_analiz.nlargest(5, 'Fark')
        response = "📈 **Bu Hafta En Çok Zamlanlar:**\n\n"
        for i, row in top5.iterrows():
            response += f"• **{row[ad_col]}**: %{row['Fark'] * 100:.1f} artış ({row[baz]:.2f} TL → {row[son]:.2f} TL)\n"
        response += "\n💡 Öneri: Bu ürünleri alışverişini ertele veya alternatif markalar dene."
        return response

    # Bütçe planı
    elif "tl" in q_lower and any(c.isdigit() for c in q_lower):
        budget = float(''.join(filter(str.isdigit, q_lower)))
        affordable = df_analiz[df_analiz[son].astype(float) < budget / 5].sample(min(5, len(df_analiz)))
        response = f"🛒 **{budget:.0f} TL Bütçeli Alışveriş Listesi:**\n\n"
        total = 0
        for i, row in affordable.iterrows():
            price = float(row[son])
            response += f"• {row[ad_col]}: {price:.2f} TL\n"
            total += price
        response += f"\n**Toplam: {total:.2f} TL** (Kalan: {budget - total:.2f} TL)"
        return response

    # Sepet analizi
    elif "sepet" in q_lower:
        baskets = github_json_oku(SEPETLER_DOSYASI)
        user_codes = baskets.get(st.session_state.get('username', 'guest'), [])
        if user_codes:
            my_df = df_analiz[df_analiz['Kod'].isin(user_codes)]
            avg_change = my_df['Fark'].mean() * 100
            response = f"🛒 **Sepet Analizi:**\n\n"
            response += f"• Ortalama değişim: %{avg_change:.2f}\n"
            response += f"• En riskli ürün: {my_df.nlargest(1, 'Fark').iloc[0][ad_col]}\n"
            response += f"• En stabil ürün: {my_df.nsmallest(1, 'Fark').iloc[0][ad_col]}\n\n"
            response += "💡 Öneri: Riskli ürünleri başka marketten almayı dene."
            return response
        else:
            return "Henüz bir sepet oluşturmamışsın. 🛒 Sepet sekmesinden ürün ekleyebilirsin!"

    # Market önerisi
    elif "market" in q_lower or "nerede" in q_lower:
        return "🏪 **Market Önerileri:**\n\n• **Migros**: Geniş ürün yelpazesi, sık kampanyalar\n• **A101**: Ekonomik seçenekler\n• **Şok**: Temel gıda ürünlerinde uygun\n• **CarrefourSA**: Kalite-fiyat dengesi\n\n💡 Öneri: Hafta sonu broşürlerini takip et, dijital kuponları kullan."

    # Tahmin
    elif "gelecek" in q_lower or "olacak" in q_lower or "tahmin" in q_lower:
        avg_change = df_analiz['Fark'].mean() * 100
        return f"🔮 **Fiyat Tahmini:**\n\nMevcut trend: %{avg_change:.2f}\n\nEğer bu tempo devam ederse:\n• 1 ay sonra: %{avg_change * 1.2:.2f} ek artış bekleniyor\n• 3 ay sonra: %{avg_change * 2.5:.2f} kümülatif etki\n\n⚠️ Not: Bu bir istatistiksel tahmindir, kesin sonuç değildir."

    # Genel ürün sorgusu
    else:
        search_term = q_lower.replace("fiyat", "").replace("ne kadar", "").replace("?", "").strip()
        result = df_analiz[df_analiz[ad_col].str.lower().str.contains(search_term)]
        if not result.empty:
            item = result.iloc[0]
            change = item['Fark'] * 100
            emoji = "📈" if change > 0 else "📉"
            return f"{emoji} **{item[ad_col]}**\n\n• Eski fiyat: {item[baz]:.2f} TL\n• Yeni fiyat: {item[son]:.2f} TL\n• Değişim: %{change:.2f}\n• Kategori: {item['Grup']}\n\n{'⚠️ Dikkat! Bu üründe ciddi zam var.' if change > 20 else '✅ Fiyat makul seviyede.'}"
        return "🤔 Sorunuzu anlayamadım. Daha spesifik sorabilir misiniz? Örn: 'Süt fiyatları nasıl?'"


# ===================================================================
# 4. DASHBOARD MODU - PREMIUM UI/UX
# ===================================================================
def dashboard_modu():
    # Theme seçimi
    prefs = get_user_preferences(st.session_state['username'])
    theme = prefs.get('theme', 'light')

    df_f = github_excel_oku(FIYAT_DOSYASI)
    df_s = github_excel_oku(EXCEL_DOSYASI, SAYFA_ADI)

    # --- SIDEBAR ---
    with st.sidebar:
        user_upper = st.session_state['username'].upper()
        role_title = "SYSTEM ADMIN" if st.session_state['username'] == ADMIN_USER else "VERİ ANALİSTİ"

        # Animated profile card
        st.markdown(f"""
            <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        border-radius:20px; padding:20px; text-align:center; 
                        margin-bottom:20px; box-shadow:0 10px 30px rgba(102,126,234,0.3);
                        animation: pulse 3s infinite;">
                <div style="font-size:48px; margin-bottom:10px;">👤</div>
                <div style="font-family:'Poppins'; font-weight:800; font-size:20px; color:white;">{user_upper}</div>
                <div style="font-size:11px; text-transform:uppercase; color:rgba(255,255,255,0.8); 
                           margin-top:5px; letter-spacing:2px;">{role_title}</div>
            </div>
        """, unsafe_allow_html=True)

        # Theme switcher
        st.markdown("### 🎨 Tema Seçimi")
        new_theme = st.radio("", ["🌞 Light Mode", "🌙 Dark Mode"],
                             index=0 if theme == "light" else 1,
                             label_visibility="collapsed")
        if new_theme.startswith("🌙") and theme == "light":
            prefs['theme'] = "dark"
            save_user_preferences(st.session_state['username'], prefs)
            st.rerun()
        elif new_theme.startswith("🌞") and theme == "dark":
            prefs['theme'] = "light"
            save_user_preferences(st.session_state['username'], prefs)
            st.rerun()

        st.divider()
        st.markdown("<h3 style='font-size:16px;'>🟢 Çevrimiçi Ekip</h3>", unsafe_allow_html=True)

        users_db = github_json_oku(USERS_DOSYASI)
        activity_db = github_json_oku(ACTIVITY_DOSYASI)
        update_user_status(st.session_state['username'])

        online_count = 0
        user_list = []
        for u in users_db.keys():
            last_seen_str = activity_db.get(u, "2000-01-01 00:00:00")
            try:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
            except:
                last_seen = datetime(2000, 1, 1)
            is_online = (datetime.now() - last_seen).total_seconds() < 300
            user_list.append({"name": u, "online": is_online})
            if is_online: online_count += 1

        sorted_users = sorted(user_list, key=lambda x: (not x['online'], x['name'] != ADMIN_USER, x['name']))

        for u in sorted_users:
            role_icon = "🛡️" if u['name'] == ADMIN_USER else ""
            status_color = '#22c55e' if u['online'] else '#cbd5e1'
            st.markdown(f"""
                <div style="background:white; border:1px solid #e2e8f0; padding:12px; 
                           margin-bottom:8px; border-radius:12px; display:flex; 
                           justify-content:space-between; align-items:center;
                           transition: all 0.3s; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <span style="display:flex; align-items:center; color:#0f172a; 
                                font-size:14px; font-weight:600;">
                        <span style="height:10px; width:10px; border-radius:50%; 
                                    display:inline-block; margin-right:10px; 
                                    background-color:{status_color}; 
                                    box-shadow:0 0 8px {status_color};
                                    animation: {'pulse 2s infinite' if u['online'] else 'none'};"></span>
                        {u['name']} {role_icon}
                    </span>
                </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Notifications toggle
        notif_enabled = prefs.get('notifications', True)
        new_notif = st.toggle("🔔 Bildirimler", value=notif_enabled)
        if new_notif != notif_enabled:
            prefs['notifications'] = new_notif
            save_user_preferences(st.session_state['username'], prefs)
            st.toast("✅ Bildirim tercihleri güncellendi!")

        st.divider()
        if st.button("🚪 Güvenli Çıkış", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- CSS: DYNAMIC THEME SYSTEM ---
    if theme == "dark":
        bg_color = "#0f172a"
        card_bg = "#1e293b"
        text_color = "#f8fafc"
        border_color = "#334155"
        gradient = "linear-gradient(135deg, #1e293b 0%, #334155 100%)"
    else:
        bg_color = "#f8fafc"
        card_bg = "white"
        text_color = "#0f172a"
        border_color = "#e2e8f0"
        gradient = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Poppins:wght@400;600;800&family=JetBrains+Mono:wght@400&display=swap');

        .stApp {{ 
            background-color: {bg_color}; 
            font-family: 'Inter', sans-serif; 
            color: {text_color};
            transition: all 0.3s ease;
        }}

        section[data-testid="stSidebar"] {{ 
            background-color: {card_bg}; 
            border-right: 1px solid {border_color}; 
        }}

        .header-container {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 25px 35px; 
            background: {gradient}; 
            border-radius: 20px; 
            margin-bottom: 25px; 
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3); 
            position: relative;
            overflow: hidden;
        }}

        .header-container::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: rotate 20s linear infinite;
        }}

        @keyframes rotate {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}

        .app-title {{ 
            font-family: 'Poppins', sans-serif; 
            font-size: 36px; 
            font-weight: 800; 
            letter-spacing: -1px; 
            color: white;
            text-shadow: 0 4px 20px rgba(0,0,0,0.3);
            position: relative;
            z-index: 1;
        }}

        .metric-card {{ 
            background: {card_bg}; 
            padding: 28px; 
            border-radius: 24px; 
            box-shadow: 0 15px 35px rgba(0,0,0,0.08); 
            border: 1px solid {border_color}; 
            position: relative; 
            overflow: hidden; 
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }}

        .metric-card:hover {{ 
            transform: translateY(-8px) scale(1.02); 
            box-shadow: 0 25px 50px rgba(102, 126, 234, 0.25); 
        }}

        .metric-card::before {{ 
            content: ''; 
            position: absolute; 
            top: 0; 
            left: 0; 
            width: 6px; 
            height: 100%; 
        }}

        .card-blue::before {{ background: linear-gradient(180deg, #3b82f6, #2563eb); }}
        .card-purple::before {{ background: linear-gradient(180deg, #8b5cf6, #7c3aed); }}
        .card-emerald::before {{ background: linear-gradient(180deg, #10b981, #059669); }}
        .card-orange::before {{ background: linear-gradient(180deg, #f59e0b, #d97706); }}

        .metric-label {{ 
            color: #64748b; 
            font-size: 13px; 
            font-weight: 700; 
            text-transform: uppercase; 
            margin-bottom: 8px;
            letter-spacing: 1px;
        }}

        .metric-val {{ 
            color: {text_color}; 
            font-size: 40px; 
            font-weight: 800; 
            font-family: 'Poppins', sans-serif; 
            letter-spacing: -2px;
            line-height: 1;
        }}

        .metric-val.long-text {{ 
            font-size: 26px !important; 
            line-height: 1.3; 
        }}

        .update-btn-container button {{ 
            background: {gradient} !important; 
            color: white !important; 
            font-weight: 800 !important; 
            font-size: 18px !important; 
            border-radius: 16px !important; 
            height: 70px !important; 
            border: none !important; 
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4); 
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            position: relative;
            overflow: hidden;
        }}

        .update-btn-container button::before {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255,255,255,0.2);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }}

        .update-btn-container button:hover::before {{
            width: 300px;
            height: 300px;
        }}

        .update-btn-container button:hover {{ 
            transform: translateY(-3px) scale(1.02); 
            box-shadow: 0 20px 40px rgba(102, 126, 234, 0.6);
        }}

        .ticker-wrap {{ 
            width: 100%; 
            overflow: hidden; 
            background: {gradient}; 
            color: white; 
            padding: 15px 0; 
            margin-bottom: 30px; 
            border-radius: 16px;
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
        }}

        .ticker {{ 
            display: inline-block; 
            animation: ticker 50s linear infinite; 
            white-space: nowrap; 
        }}

        .ticker-item {{ 
            display: inline-block; 
            padding: 0 2.5rem; 
            font-weight: 600; 
            font-size: 15px; 
            font-family: 'JetBrains Mono', monospace; 
        }}

        @keyframes ticker {{ 
            0% {{ transform: translateX(100%); }} 
            100% {{ transform: translateX(-100%); }} 
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        #live_clock_js {{ 
            font-family: 'JetBrains Mono', monospace; 
            color: white; 
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
            position: relative;
            z-index: 1;
        }}

        /* Tab customization */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
            background-color: {card_bg};
            padding: 10px;
            border-radius: 15px;
        }}

        .stTabs [data-baseweb="tab"] {{
            background-color: transparent;
            border-radius: 10px;
            padding: 12px 24px;
            font-weight: 600;
            transition: all 0.3s;
        }}

        .stTabs [data-baseweb="tab"]:hover {{
            background-color: rgba(102, 126, 234, 0.1);
        }}

        .stTabs [aria-selected="true"] {{
            background: {gradient} !important;
            color: white !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    # --- HEADER & LIVE CLOCK ---
    tr_time_start = datetime.now() + timedelta(hours=3)
    header_html = f"""
    <div class="header-container">
        <div class="app-title">✨ Enflasyon Monitörü PRO</div>
        <div style="text-align:right; position:relative; z-index:1;">
            <div style="color:rgba(255,255,255,0.9); font-size:13px; font-weight:700; 
                       margin-bottom:5px; letter-spacing:1px;">İSTANBUL, TÜRKİYE</div>
            <div id="live_clock_js" style="font-size:18px; font-weight:800;">
                {tr_time_start.strftime('%d %B %Y, %H:%M:%S')}
            </div>
        </div>
    </div>
    <script>
    function startClock() {{
        var clockElement = document.getElementById('live_clock_js');
        function update() {{
            var now = new Date();
            var options = {{ timeZone: 'Europe/Istanbul', day: 'numeric', month: 'long', 
                           year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }};
            if (clockElement) {{ 
                clockElement.innerHTML = now.toLocaleTimeString('tr-TR', options); 
            }}
        }}
        setInterval(update, 1000); 
        update(); 
    }}
    startClock();
    </script>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # --- TOAST MESSAGE ---
    if 'toast_shown' not in st.session_state:
        st.toast('🚀 Sistem Aktif! Premium özelliklere hoş geldin.', icon='✨')
        st.session_state['toast_shown'] = True

    # --- UPDATE BUTTON ---
    st.markdown('<div class="update-btn-container">', unsafe_allow_html=True)
    if st.button("🚀 SİSTEMİ GÜNCELLE VE ANALİZ ET", type="primary", use_container_width=True):
        with st.status("🔄 Veri Tabanı Güncelleniyor...", expanded=True) as status:
            st.write("📡 GitHub bağlantısı kuruluyor...")
            time.sleep(0.5)
            st.write("📦 ZIP dosyaları taranıyor...")
            log_ph = st.empty()
            log_msgs = []

            def logger(m):
                log_msgs.append(f"> {m}")
                log_ph.markdown(
                    f'<div style="background:#1e293b; color:#4ade80; font-family:monospace; font-size:12px; padding:15px; border-radius:12px; height:180px; overflow-y:auto;">{"<br>".join(log_msgs)}</div>',
                    unsafe_allow_html=True)

            res = html_isleyici(logger)
            status.update(label="✅ İşlem Tamamlandı!", state="complete", expanded=False)

        if "OK" in res:
            st.toast('🎉 Veritabanı Güncellendi!', icon='✅')
            st.success("✅ Sistem Başarıyla Senkronize Edildi!")
            time.sleep(2)
            st.rerun()
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
                    df_analiz['Agirlik_2025'] = 1
                    agirlik_col = 'Agirlik_2025'

                gunler = [c for c in pivot.columns if c != 'Kod']
                if len(gunler) < 1:
                    st.warning("Yeterli tarih verisi yok.")
                    return
                baz, son = gunler[0], gunler[-1]

                # Hesaplamalar
                endeks_genel = (df_analiz.dropna(subset=[son, baz])[agirlik_col] * (
                            df_analiz[son] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[son, baz])[
                                   agirlik_col].sum() * 100
                enf_genel = (endeks_genel / 100 - 1) * 100
                df_analiz['Fark'] = (df_analiz[son] / df_analiz[baz]) - 1
                top = df_analiz.sort_values('Fark', ascending=False).iloc[0]
                gida = df_analiz[df_analiz['Kod'].str.startswith("01")].copy()
                enf_gida = ((gida[son] / gida[baz] * gida[agirlik_col]).sum() / gida[
                    agirlik_col].sum() - 1) * 100 if not gida.empty else 0

                # GELECEK TAHMİNİ
                dt_son = datetime.strptime(son, '%Y-%m-%d')
                dt_baz = datetime.strptime(baz, '%Y-%m-%d')
                days_in_month = calendar.monthrange(dt_son.year, dt_son.month)[1]
                days_passed = dt_son.day
                days_left = days_in_month - days_passed
                daily_rate = enf_genel / max(days_passed, 1)
                month_end_forecast = enf_genel + (daily_rate * days_left)
                gun_farki = (dt_son - dt_baz).days

                # --- TICKER ---
                inc = df_analiz.sort_values('Fark', ascending=False).head(5)
                dec = df_analiz.sort_values('Fark', ascending=True).head(5)
                items = []
                for _, r in inc.iterrows():
                    items.append(f"<span style='color:#f87171'>▲ {r[ad_col]} %{r['Fark'] * 100:.1f}</span>")
                for _, r in dec.iterrows():
                    items.append(f"<span style='color:#4ade80'>▼ {r[ad_col]} %{r['Fark'] * 100:.1f}</span>")
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
                            <div style="color:{sub_color}; font-size:13px; margin-top:8px; font-weight:600;">
                                {sub}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    kpi_card("Genel Enflasyon", f"%{enf_genel:.2f}", f"📊 {gun_farki} Günlük Değişim", "#ef4444",
                             "card-blue")
                with c2:
                    kpi_card("Gıda Enflasyonu", f"%{enf_gida:.2f}", "🍽️ Mutfak Sepeti", "#ef4444", "card-emerald")
                with c3:
                    kpi_card("Ay Sonu Tahmini", f"%{month_end_forecast:.2f}", f"🗓️ {days_left} gün kaldı", "#8b5cf6",
                             "card-purple")
                with c4:
                    kpi_card("En Yüksek Risk", f"{top[ad_col][:15]}", f"⚠️ %{top['Fark'] * 100:.1f} Artış", "#f59e0b",
                             "card-orange", is_long_text=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # --- SEKMELER ---
                t1, t2, t3, t4, t5, t6, t7 = st.tabs(
                    ["📊 ANALİZ", "🤖 AI ASİSTAN", "📈 İSTATİSTİK", "🛒 SEPET", "🗺️ HARİTA", "📉 FIRSATLAR", "📋 LİSTE"]
                )

                with t1:
                    # Trend grafiği
                    trend_data = [{"Tarih": g, "TÜFE": (df_analiz.dropna(subset=[g, baz])[agirlik_col] * (
                                df_analiz[g] / df_analiz[baz])).sum() / df_analiz.dropna(subset=[g, baz])[
                                                           agirlik_col].sum() * 100} for g in gunler]
                    df_trend = pd.DataFrame(trend_data)

                    fig_main = px.area(df_trend, x='Tarih', y='TÜFE', title="📈 Enflasyon Momentum Analizi")
                    fig_main.update_traces(line_color='#667eea', fillcolor="rgba(102, 126, 234, 0.3)",
                                           line_shape='spline', line_width=3)
                    fig_main.update_layout(template="plotly_white", height=500, hovermode="x unified",
                                           yaxis=dict(range=[95, 105]), plot_bgcolor='rgba(0,0,0,0)',
                                           paper_bgcolor='rgba(0,0,0,0)', font=dict(family="Inter", size=12))
                    st.plotly_chart(fig_main, use_container_width=True)

                with t2:
                    # AI CHATBOT INTERFACE
                    ai_chatbot_interface(df_analiz, ad_col, baz, son)

                with t3:
                    col_hist, col_box = st.columns(2)
                    df_analiz['Fark_Yuzde'] = df_analiz['Fark'] * 100
                    fig_hist = px.histogram(df_analiz, x="Fark_Yuzde", nbins=40, title="📊 Zam Dağılımı Frekansı",
                                            color_discrete_sequence=['#8b5cf6'])
                    fig_hist.update_layout(template="plotly_white", xaxis_title="Artış Oranı (%)",
                                           yaxis_title="Ürün Adedi", plot_bgcolor='rgba(0,0,0,0)',
                                           paper_bgcolor='rgba(0,0,0,0)')
                    col_hist.plotly_chart(fig_hist, use_container_width=True)

                    fig_box = px.box(df_analiz, x="Grup", y="Fark_Yuzde", title="📦 Kategori Bazlı Fiyat Dağılımı",
                                            color="Grup")
                    fig_box.update_layout(template="plotly_white",
                                          xaxis_title="Kategori",
                                          yaxis_title="Değişim (%)",
                                          plot_bgcolor='rgba(0,0,0,0)',
                                          paper_bgcolor='rgba(0,0,0,0)',
                                          showlegend=False)
                    col_box.plotly_chart(fig_box, use_container_width=True)

                with t4:
                    # 🛒 AKILLI SEPET YÖNETİMİ
                    st.markdown("### 🛒 Kişisel Alışveriş Sepetim")

                    # Kullanıcı sepetini çek
                    baskets = github_json_oku(SEPETLER_DOSYASI)
                    user = st.session_state['username']
                    if user not in baskets: baskets[user] = []

                    c_add, c_view = st.columns([1, 2])

                    with c_add:
                        st.markdown("##### ➕ Ürün Ekle")
                        secilen_urun = st.selectbox("Ürün Seçiniz:", df_analiz[ad_col].unique())
                        if st.button("Sepete Ekle"):
                            kod = df_analiz[df_analiz[ad_col] == secilen_urun]['Kod'].iloc[0]
                            if kod not in baskets[user]:
                                baskets[user].append(kod)
                                github_json_yaz(SEPETLER_DOSYASI, baskets, f"Sepet Update: {user}")
                                st.success(f"{secilen_urun} eklendi!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning("Bu ürün zaten sepetinizde.")

                    with c_view:
                        if baskets[user]:
                            sepet_df = df_analiz[df_analiz['Kod'].isin(baskets[user])].copy()
                            if not sepet_df.empty:
                                total_baz = sepet_df[baz].sum()
                                total_son = sepet_df[son].sum()
                                sepet_enf = ((total_son / total_baz) - 1) * 100

                                st.info(f"💰 **Sepet Toplamı:** {total_son:.2f} TL (Geçen Ay: {total_baz:.2f} TL)")
                                st.metric("Sepet Enflasyonu", f"%{sepet_enf:.2f}", f"{total_son - total_baz:.2f} TL Artış", delta_color="inverse")

                                st.dataframe(sepet_df[[ad_col, baz, son, 'Fark_Yuzde']], hide_index=True, use_container_width=True)

                                if st.button("🗑️ Sepeti Temizle"):
                                    baskets[user] = []
                                    github_json_yaz(SEPETLER_DOSYASI, baskets, f"Clear Basket: {user}")
                                    st.rerun()
                        else:
                            st.info("Sepetiniz henüz boş. Soldan ürün ekleyebilirsiniz.")

                with t5:
                    # 🗺️ ENFLASYON ISI HARİTASI (TREEMAP)
                    st.markdown("### 🗺️ Harcama Grupları Isı Haritası")
                    st.markdown("Kutucuk büyüklüğü harcama ağırlığını, renkler ise fiyat artış oranını gösterir.")

                    fig_tree = px.treemap(df_analiz,
                                          path=[px.Constant("TÜM ÜRÜNLER"), 'Grup', ad_col],
                                          values=agirlik_col,
                                          color='Fark_Yuzde',
                                          color_continuous_scale='RdYlGn_r',
                                          color_continuous_midpoint=0,
                                          hover_data={ad_col: True, 'Fark_Yuzde': ':.2f', son: ':.2f'})

                    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=600)
                    st.plotly_chart(fig_tree, use_container_width=True)

                with t6:
                    # 📉 FIRSATLAR VE UCUZLAYANLAR
                    st.markdown("### 📉 İndirime Giren Ürünler (Fırsatlar)")
                    indirimler = df_analiz[df_analiz['Fark'] < 0].sort_values('Fark')

                    if not indirimler.empty:
                        for _, row in indirimler.iterrows():
                            with st.container():
                                st.markdown(f"""
                                <div style="background:white; padding:15px; border-radius:10px; border-left: 5px solid #22c55e; margin-bottom:10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                                    <div style="display:flex; justify-content:space-between; align-items:center;">
                                        <div>
                                            <div style="font-weight:bold; font-size:16px;">{row[ad_col]}</div>
                                            <div style="font-size:12px; color:#64748b;">{row['Grup']}</div>
                                        </div>
                                        <div style="text-align:right;">
                                            <div style="font-weight:bold; color:#22c55e; font-size:18px;">%{row['Fark_Yuzde']:.1f} ▼</div>
                                            <div style="font-size:12px;"><strike>{row[baz]:.2f} TL</strike> ➝ <b>{row[son]:.2f} TL</b></div>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("Şu an sistemde fiyatı düşen bir ürün bulunamadı.")

                with t7:
                    # 📋 DETAYLI LİSTE
                    st.markdown("### 📋 Detaylı Veri Seti")

                    search = st.text_input("🔍 Listede Ara:", placeholder="Ürün adı yazın...")
                    if search:
                        mask = df_analiz[ad_col].str.lower().str.contains(search.lower())
                        display_df = df_analiz[mask]
                    else:
                        display_df = df_analiz

                    st.dataframe(
                        display_df[[ad_col, 'Grup', baz, son, 'Fark_Yuzde']],
                        column_config={
                            "Fark_Yuzde": st.column_config.NumberColumn("Değişim %", format="%.2f %%"),
                            baz: st.column_config.NumberColumn(f"Fiyat ({baz})", format="%.2f TL"),
                            son: st.column_config.NumberColumn(f"Fiyat ({son})", format="%.2f TL"),
                        },
                        use_container_width=True,
                        height=500
                    )

                    # Excel İndir
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_analiz.to_excel(writer, sheet_name='Analiz', index=False)

                    st.download_button(
                        label="📥 Excel Olarak İndir",
                        data=output.getvalue(),
                        file_name=f"Enflasyon_Analiz_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.ms-excel"
                    )

        except Exception as e:
            st.error(f"Bir hata oluştu: {str(e)}")
            st.code(str(e))
    else:
        st.info("Veri tabanı hazırlanıyor, lütfen bekleyiniz veya 'Sistemi Güncelle' butonuna basınız.")

# ===================================================================
# 5. GİRİŞ EKRANI (LOGIN PAGE)
# ===================================================================
def login_page():
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 40px;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stApp {
            background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
            background-size: 400% 400%;
            animation: gradient 15s ease infinite;
        }
        @keyframes gradient {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<h1 style='text-align: center; color: white; text-shadow: 0 2px 10px rgba(0,0,0,0.2);'>💎 Enflasyon Monitörü</h1>", unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Giriş Yap", "Kayıt Ol"])

        with tab_login:
            with st.form("login_form"):
                kadi = st.text_input("Kullanıcı Adı")
                sifre = st.text_input("Şifre", type="password")
                submit = st.form_submit_button("Giriş Yap", use_container_width=True)

                if submit:
                    if not kadi or not sifre:
                        st.warning("Lütfen tüm alanları doldurun.")
                    else:
                        success, msg = github_user_islem("login", username=kadi, password=sifre)
                        if success:
                            st.session_state['logged_in'] = True
                            st.session_state['username'] = kadi
                            st.success("Giriş başarılı!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)

            # Şifremi Unuttum Modalı
            if st.button("Şifremi Unuttum?", type="tertiary"):
                st.session_state['show_forgot'] = True

            if st.session_state.get('show_forgot', False):
                email_input = st.text_input("E-posta adresinizi girin:")
                if st.button("Sıfırlama Bağlantısı Gönder"):
                    if email_input:
                        suc, m = github_user_islem("forgot_password", email=email_input)
                        if suc: st.success(m)
                        else: st.error(m)
                    else:
                        st.warning("E-posta giriniz.")

        with tab_register:
            with st.form("register_form"):
                new_user = st.text_input("Kullanıcı Adı Seçin")
                new_email = st.text_input("E-posta Adresi")
                new_pass = st.text_input("Şifre Belirleyin", type="password")
                reg_submit = st.form_submit_button("Kayıt Ol", use_container_width=True)

                if reg_submit:
                    if new_user and new_pass and new_email:
                        success, msg = github_user_islem("register", username=new_user, password=new_pass, email=new_email)
                        if success:
                            st.success("Kayıt başarılı! Şimdi giriş yapabilirsiniz.")
                        else:
                            st.error(msg)
                    else:
                        st.warning("Eksik bilgi girdiniz.")

# ===================================================================
# 6. ANA UYGULAMA AKIŞI
# ===================================================================
if __name__ == "__main__":
    # Session state tanımları
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    # URL Parametresi ile Şifre Sıfırlama Kontrolü
    params = st.query_params
    if "reset_user" in params:
        user_reset = params["reset_user"]
        st.info(f"🔓 {user_reset} için şifre sıfırlama ekranı.")
        new_p = st.text_input("Yeni Şifreniz", type="password")
        if st.button("Şifreyi Güncelle"):
            s, m = github_user_islem("update_password", username=user_reset, password=new_p)
            if s:
                st.success(m)
                st.query_params.clear()
                time.sleep(2)
                st.rerun()
            else:
                st.error(m)

    # Ana ekran yönlendirmesi
    elif st.session_state["logged_in"]:
        dashboard_modu()
    else:
        login_page()