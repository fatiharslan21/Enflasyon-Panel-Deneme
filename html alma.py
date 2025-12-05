import os
import time
import math
import random
from DrissionPage import ChromiumPage, ChromiumOptions

# --- AYARLAR ---
ana_klasor = "html_dosyalari"
BOLUM_SAYISI = 10

# --- AÇIK CHROME'A BAĞLANMA ---
co = ChromiumOptions()
co.set_address('127.0.0.1:9222')

try:
    # Tarayıcı nesnesi (Bu ana yönetici)
    browser = ChromiumPage(co)
    print("✅ Açık olan Chrome'a bağlandım!")
except Exception as e:
    print("❌ HATA: Chrome portu bulunamadı.")
    print("Lütfen önce siyah ekranı kapatıp 'chrome_ac.py' dosyasını yeniden çalıştırın.")
    exit()


def klasorleri_hazirla():
    if not os.path.exists(ana_klasor):
        os.makedirs(ana_klasor)
    for i in range(1, BOLUM_SAYISI + 1):
        yol = os.path.join(ana_klasor, f"Bolum_{i}")
        if not os.path.exists(yol):
            os.makedirs(yol)


def islem_yap():
    if not os.path.exists("urller.txt"):
        print("urller.txt yok!")
        return

    with open("urller.txt", "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    toplam_link = len(lines)
    bolum_limiti = math.ceil(toplam_link / BOLUM_SAYISI)

    print(f"Toplam {toplam_link} link var.")
    print(f"Sistem: YENİ SEKME TAKTİĞİ (Cloudflare'i Kandırma Modu)")
    print("-" * 50)

    klasorleri_hazirla()

    for index, line in enumerate(lines):
        parts = line.split()
        if len(parts) < 2: continue

        kod = parts[0]
        url = parts[-1]

        # Klasör Hesabı
        mevcut_bolum = (index // bolum_limiti) + 1
        if mevcut_bolum > BOLUM_SAYISI: mevcut_bolum = BOLUM_SAYISI
        hedef_klasor = os.path.join(ana_klasor, f"Bolum_{mevcut_bolum}")
        klasor_adi = f"Bölüm {mevcut_bolum}"

        cimri_modu = "cimri" in url

        try:
            if cimri_modu:
                print(f"[{index + 1}/{toplam_link}] [{klasor_adi}] 🛡️ [CİMRİ] {kod}")
            else:
                print(f"[{index + 1}/{toplam_link}] [{klasor_adi}] 🚀 [HIZLI] {kod}")

            # --- KRİTİK DEĞİŞİKLİK: YENİ SEKME AÇ ---
            # Mevcut sayfayı değiştirmek yerine yeni sekme açıyoruz.
            # Bu, Cloudflare'in "Navigasyon geçmişi" takibini bozar.
            tab = browser.new_tab(url)

            page_loaded = False

            # --- SENARYO 1: CİMRİ ---
            if cimri_modu:
                start_wait = time.time()
                timeout = 40

                while time.time() - start_wait < timeout:
                    # Cloudflare varsa
                    if "Just a moment" in tab.title or "Cloudflare" in tab.title:
                        print(f"\r      ⚠️ Cloudflare ekranı! (Otomatik geçmezse elle tıklayın)", end="")
                        time.sleep(1)
                        continue

                    # Fiyat kutusu geldi mi?
                    if tab.ele(".rTdMX") or tab.ele(".offer-price") or tab.ele(".fe-product-price"):
                        print("\n      ✅ Fiyat bulundu.")
                        page_loaded = True
                        break

                    # HTML dolu mu?
                    if len(tab.html) > 20000 and "Just a moment" not in tab.title:
                        print("\n      ✅ Sayfa yüklendi.")
                        page_loaded = True
                        break
                    time.sleep(1)

                if page_loaded:
                    # Cimri'de insan gibi biraz rastgele bekle
                    tab.scroll.to_bottom()
                    time.sleep(random.uniform(1.5, 2.5))

                    # --- SENARYO 2: HIZLI MOD ---
            else:
                tab.scroll.to_bottom()
                time.sleep(1)
                page_loaded = True

            # --- KAYDET ---
            if page_loaded:
                save_path = os.path.join(hedef_klasor, f"{kod}.html")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(tab.html)
                print(f"      💾 KAYDEDİLDİ")
            else:
                if cimri_modu:
                    save_path = os.path.join(hedef_klasor, f"{kod}.html")
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(tab.html)
                    print(f"      ⚠️ Zaman aşımı (Mevcut hali alındı)")
                else:
                    print(f"      ❌ HATA: Yüklenemedi")

            # --- İŞ BİTİNCE SEKMEYİ KAPAT (RAM TEMİZLİĞİ) ---
            tab.close()

        except Exception as e:
            print(f"      ❌ HATA: {e}")
            # Hata durumunda da sekmeyi kapatmaya çalış
            try:
                tab.close()
            except:
                pass

    print("\n🏁 İşlem tamamlandı.")


if __name__ == "__main__":
    islem_yap()