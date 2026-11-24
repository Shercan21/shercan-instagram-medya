"""Instagram yayını için ortak parçalar.

Hem bilgisayardaki atölye (insta_yayin.py) hem de GitHub'daki yedek yayıncı (yayinci.py) bunu kullanır.
Yalnız Python standart kütüphanesi.

Ortak durum dosyası: medya deposundaki durum.json. Bir paylaşımı göndermeden önce
"gonderiliyor" diye işaretlenir; GitHub bu dosyayı sürüm (sha) kontrolüyle yazdığı için
bilgisayar ile GitHub aynı anda aynı paylaşımı üstlenemez → iki kez paylaşılmaz.
"""
import base64, json, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

GRAPH = 'https://graph.facebook.com/v21.0'
TR = timezone(timedelta(hours=3))
GEC_KALMA_SINIRI = timedelta(hours=6)    # bundan eski paylaşım kendiliğinden gönderilmez
GONDERILIYOR_ZAMAN_ASIMI = 1800          # sn; yarıda kalan "gönderiliyor" işareti bu kadar sonra düşer
MAKS_DENEME = 3


def hata_metni(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            j = json.loads(e.read().decode('utf-8'))
            er = j.get('error') if isinstance(j.get('error'), dict) else j
            return str(er.get('error_user_msg') or er.get('message') or j)[:400]
        except Exception:
            return f'HTTP {e.code}'
    return str(e)[:400]


def istek(method, url, headers=None, data=None, timeout=60):
    body = None; h = {'User-Agent': 'KimyaKocum-Atolye', **(headers or {})}
    if data is not None:
        if h.get('Content-Type') == 'application/json': body = json.dumps(data).encode('utf-8')
        else:
            body = urllib.parse.urlencode(data).encode('utf-8'); h.setdefault('Content-Type', 'application/x-www-form-urlencoded')
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8') or '{}')


# ---------------- GitHub içerik API'si ----------------
def gh(method, yol, token, data=None):
    return istek(method, 'https://api.github.com' + yol, {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'}, data)


def gh_json_oku(repo, dal, token, yol, varsayilan):
    try:
        j = gh('GET', f'/repos/{repo}/contents/{yol}?ref={dal}', token)
        return json.loads(base64.b64decode(j['content']).decode('utf-8')), j['sha']
    except urllib.error.HTTPError as e:
        if e.code == 404: return varsayilan, None
        raise


def gh_dosya_yaz(repo, dal, token, yol, icerik_bytes, sha=None, mesaj=None):
    veri = {'message': mesaj or ('güncelle: ' + yol), 'content': base64.b64encode(icerik_bytes).decode('ascii'), 'branch': dal}
    if sha: veri['sha'] = sha
    return gh('PUT', f'/repos/{repo}/contents/{yol}', token, veri)['content']['sha']


def gh_json_yaz(repo, dal, token, yol, veri, sha=None, mesaj=None):
    return gh_dosya_yaz(repo, dal, token, yol, json.dumps(veri, ensure_ascii=False, indent=1).encode('utf-8'), sha, mesaj)


def durum_guncelle(repo, dal, token, anahtar, kosul, alan, kim):
    """durum.json'da tek kaydı sürüm kontrolüyle günceller. kosul(eski)->bool False dönerse yazmaz.
    Başka biri araya girdiyse (409/422) dosyayı yeniden okuyup tekrar dener. Yazdıysa True."""
    for _ in range(6):
        d, sha = gh_json_oku(repo, dal, token, 'durum.json', {})
        eski = d.get(anahtar, {})
        if not kosul(eski): return False
        yeni = alan(eski) if callable(alan) else alan
        d[anahtar] = {**eski, **yeni, 'kim': kim, 'guncel': int(time.time())}
        try:
            gh_json_yaz(repo, dal, token, 'durum.json', d, sha, f'durum: {anahtar} {yeni.get("durum", "")}'); return True
        except urllib.error.HTTPError as e:
            if e.code not in (409, 422): raise
            time.sleep(2)
    raise RuntimeError('Durum dosyası yazılamadı (çakışma).')


def ustlenilebilir(eski, simdi=None):
    simdi = simdi or time.time()
    if eski.get('durum') in ('ok', 'kacti'): return False
    if eski.get('durum') == 'gonderiliyor' and simdi - eski.get('guncel', 0) < GONDERILIYOR_ZAMAN_ASIMI: return False
    if eski.get('deneme', 0) >= MAKS_DENEME: return False
    return True


# ---------------- Instagram (Birleşik giriş, graph.facebook.com) ----------------
def ig(method, yol, token, data=None):
    try:
        return istek(method, f'{GRAPH}/{yol}', {'Authorization': 'Bearer ' + token}, data, timeout=120)
    except urllib.error.HTTPError as e:
        raise RuntimeError('Instagram: ' + hata_metni(e))


def _bekle(cid, token, sure=600):
    bas = time.time()
    while time.time() - bas < sure:
        j = ig('GET', f'{cid}?fields=status_code,status', token)
        s = j.get('status_code')
        if s == 'FINISHED': return
        if s in ('ERROR', 'EXPIRED'): raise RuntimeError('Instagram medyayı işleyemedi: ' + str(j.get('status') or s))
        time.sleep(5)
    raise RuntimeError('Instagram medyayı zamanında işlemedi.')


def _konteyner(ig_id, token, url, **ek):
    alan = {'video_url': url} if url.lower().endswith('.mp4') else {'image_url': url}
    if url.lower().endswith('.mp4') and 'media_type' not in ek: alan['media_type'] = 'VIDEO'
    return ig('POST', f'{ig_id}/media', token, {**alan, **ek})['id']


def paylas_url(ig_id, token, tur, urller, aciklama=''):
    """Herkese açık adreslerdeki medyayı Instagram'a paylaşır; yayınlanan medya kimliğini döndürür."""
    if tur == 'carousel':
        cocuk = []
        for u in urller[:10]:
            c = _konteyner(ig_id, token, u, is_carousel_item='true')
            if u.lower().endswith('.mp4'): _bekle(c, token)
            cocuk.append(c)
        cid = ig('POST', f'{ig_id}/media', token, {'media_type': 'CAROUSEL', 'children': ','.join(cocuk), 'caption': aciklama})['id']
    elif tur == 'image':
        cid = _konteyner(ig_id, token, urller[0], caption=aciklama)
    elif tur == 'story':
        cid = _konteyner(ig_id, token, urller[0], media_type='STORIES')
    elif tur == 'reels':
        ek = {'media_type': 'REELS', 'caption': aciklama, 'share_to_feed': 'true'}
        if len(urller) > 1: ek['cover_url'] = urller[1]
        cid = _konteyner(ig_id, token, urller[0], **ek)
    else:
        raise RuntimeError('Bilinmeyen paylaşım türü: ' + str(tur))
    _bekle(cid, token)
    return ig('POST', f'{ig_id}/media_publish', token, {'creation_id': cid})['id']


def zaman_coz(s):
    """'2026-11-24T20:30:00+03:00' ya da '2026-11-24T20:30' (İstanbul saati) → aware datetime."""
    s = str(s)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        d = datetime.strptime(s[:16], '%Y-%m-%dT%H:%M')
    return d if d.tzinfo else d.replace(tzinfo=TR)


def yayinla(repo, dal, gh_token, ig_id, ig_token, p, kim, zorla=False):
    """Plan maddesini üstlenir, paylaşır ve sonucu durum.json'a yazar. Sonuç: 'ok' | 'atlandi' | 'kacti' | hata metni."""
    an = p['anahtar']; z = zaman_coz(p['zaman']); simdi = datetime.now(TR)
    if not zorla and simdi - z > GEC_KALMA_SINIRI:
        durum_guncelle(repo, dal, gh_token, an, lambda e: e.get('durum') not in ('ok', 'kacti'),
                       {'durum': 'kacti', 'mesaj': 'Saati 6 saatten fazla geçti; “Şimdi yayınla” ile gönderilebilir.'}, kim)
        return 'kacti'
    kosul = (lambda e: e.get('durum') != 'ok' and not (e.get('durum') == 'gonderiliyor' and time.time() - e.get('guncel', 0) < GONDERILIYOR_ZAMAN_ASIMI)) if zorla else ustlenilebilir
    if not durum_guncelle(repo, dal, gh_token, an, kosul, {'durum': 'gonderiliyor'}, kim):
        return 'atlandi'
    try:
        mid = paylas_url(ig_id, ig_token, p['tur'], p['urller'], p.get('aciklama') or '')
    except Exception as e:
        msg = str(e)[:400]
        durum_guncelle(repo, dal, gh_token, an, lambda e: True, lambda e: {'durum': 'hata', 'mesaj': msg, 'deneme': int(e.get('deneme', 0)) + 1}, kim)
        return msg
    durum_guncelle(repo, dal, gh_token, an, lambda e: True, {'durum': 'ok', 'medya': mid, 'mesaj': ''}, kim)
    return 'ok'
