import subprocess
import os
import time

# Chrome'un bilgisayardaki olası yolları
olasi_yollar = [
    r"\\Cb0146018\c$\Program Files\Google\Chrome\Application\chrome.exe"
]

chrome_exe = None
for yol in olasi_yollar:
    if os.path.exists(yol):
        chrome_exe = yol
        break

if not chrome_exe:
    print("Chrome.exe bulunamadı! Yolu kontrol edin.")
    exit()

# Bot profilini şu anki klasöre kuralım (İzin hatası almamak için)
profil_klasoru = os.path.join(os.getcwd(), "Ozel_Chrome_Profili")
if not os.path.exists(profil_klasoru):
    os.makedirs(profil_klasoru)

print("🚀 Chrome Özel Modda Açılıyor...")
print("Lütfen açılan pencereyi KAPATMAYIN.")

# Komutu çalıştır (CMD kullanmadan direkt process olarak)
komut = [
    chrome_exe,
    "--remote-debugging-port=9222",
    f"--user-data-dir={profil_klasoru}"
]

try:
    subprocess.Popen(komut)
    print("✅ Başarılı! Chrome açıldı.")
    print("Şimdi diğer 'tarama kodunu' çalıştırabilirsin.")
except Exception as e:
    print(f"Hata: {e}")

# Kodu bitir ama pencere açık kalsın
time.sleep(2)