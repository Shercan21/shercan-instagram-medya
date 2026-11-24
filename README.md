# shercan-instagram-medya

SHERCAN Hoca · Kimya Koçum Instagram paylaşımlarının görselleri ve yayın planı.

- `m/` — paylaşılacak görsel ve videolar (Instagram herkese açık adresten alır).
- `plan.json` — atölyenin yazdığı paylaşım planı (saat, açıklama, medya adresleri).
- `durum.json` — hangi paylaşımın gittiği (bilgisayar ya da GitHub).
- `yayinci.py` + `.github/workflows/yayin.yml` — bilgisayar kapalıyken saatinden 15 dakika sonra paylaşan yedek yayıncı.
  Instagram anahtarı **Settings → Secrets and variables → Actions → `IG_TOKEN`** gizli ayarında durur.
