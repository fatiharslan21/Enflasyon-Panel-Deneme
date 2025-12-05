import os
import shutil

# --- AYARLAR ---
kaynak_klasor = "HTML_DOSYALARI"  # HTML'lerin olduğu yer
hedef_klasor = "Ziplenmis_Dosyalar"  # Ziplerin konulacağı yer


def klasorleri_zip_yap():
    # 1. Kaynak klasör var mı kontrol et
    if not os.path.exists(kaynak_klasor):
        print(f"HATA: '{kaynak_klasor}' klasörü bulunamadı!")
        return

    # 2. Hedef klasörü oluştur (Yoksa)
    if not os.path.exists(hedef_klasor):
        os.makedirs(hedef_klasor)
        print(f"📁 '{hedef_klasor}' klasörü oluşturuldu.")

    # 3. Klasörleri listele ve ziple
    klasorler = [f for f in os.listdir(kaynak_klasor) if os.path.isdir(os.path.join(kaynak_klasor, f))]

    if not klasorler:
        print("Ziplenecek klasör bulunamadı.")
        return

    print(f"Toplam {len(klasorler)} klasör ziplenecek...")
    print("-" * 40)

    for klasor_adi in klasorler:
        # Ziplenecek klasörün tam yolu (Örn: html_dosyalari/Bolum_1)
        klasor_yolu = os.path.join(kaynak_klasor, klasor_adi)

        # Oluşacak zip dosyasının yolu ve adı (Örn: Ziplenmis_Dosyalar/Bolum_1)
        # Not: shutil.make_archive sonuna otomatik .zip ekler, biz sadece adı veriyoruz.
        zip_kayit_yolu = os.path.join(hedef_klasor, klasor_adi)

        print(f"📦 Zip yapılıyor: {klasor_adi}...", end="")

        try:
            shutil.make_archive(zip_kayit_yolu, 'zip', klasor_yolu)
            print(" ✅ TAMAMLANDI")
        except Exception as e:
            print(f" ❌ HATA: {e}")

    print("-" * 40)
    print(f"🎉 Tüm işlemler bitti! Dosyalar '{hedef_klasor}' içinde.")


if __name__ == "__main__":
    klasorleri_zip_yap()