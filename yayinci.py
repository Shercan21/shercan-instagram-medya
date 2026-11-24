"""GitHub'daki yedek Instagram yayıncısı.

Bilgisayardaki atölye kapalıysa, plan.json'daki paylaşım saatinden 15 dakika sonra hâlâ gönderilmemiş
olanları Instagram'a paylaşır. Bilgisayar zamanında paylaştıysa durum.json'da "ok" yazar ve burada atlanır.
Instagram anahtarı deponun gizli ayarlarında (Settings → Secrets → Actions → IG_TOKEN) durur.
"""
import os, sys
from datetime import datetime, timedelta

import ig_ortak as o

YEDEK_GECIKME = timedelta(minutes=15)


def main():
    repo = os.environ['GITHUB_REPOSITORY']; dal = os.environ.get('GITHUB_REF_NAME') or 'main'
    gh_tok = os.environ['GITHUB_TOKEN']; ig_tok = os.environ.get('IG_TOKEN', '').strip()
    if not ig_tok:
        print('IG_TOKEN gizli ayarı yok; yedek yayıncı çalışmıyor.'); return 0
    plan, _ = o.gh_json_oku(repo, dal, gh_tok, 'plan.json', {})
    ig_id = (plan or {}).get('ig_id'); maddeler = (plan or {}).get('paylasimlar') or []
    if not ig_id or not maddeler:
        print('Plan boş (otomatik yayın kapalı ya da bekleyen yok).'); return 0
    durum, _ = o.gh_json_oku(repo, dal, gh_tok, 'durum.json', {})
    simdi = datetime.now(o.TR); hata = 0
    for p in sorted(maddeler, key=lambda x: x['zaman']):
        z = o.zaman_coz(p['zaman'])
        if simdi < z + YEDEK_GECIKME: continue          # önce bilgisayara fırsat ver
        if not o.ustlenilebilir(durum.get(p['anahtar'], {})): continue   # gitti, başkası gönderiyor ya da 3 kez denendi
        sonuc = o.yayinla(repo, dal, gh_tok, ig_id, ig_tok, p, 'github')
        print(p['anahtar'], '→', sonuc)
        if sonuc not in ('ok', 'atlandi', 'kacti'): hata += 1
    return 1 if hata else 0


if __name__ == '__main__':
    sys.exit(main())
