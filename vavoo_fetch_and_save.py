import requests
import json
import os
import time

# VAVOO ayarları
JSON_FILE_PATH_TV = "vavoo_tv_channels.json"
VAVOO_LIVE_URL = "https://www2.vavoo.to/live2/index?output=json"

# VAVOO.TO için gerekli başlıklar
VAVOO_HEADERS = {
    "user-agent": "VAVOO/2.6",
    "accept": "application/json",
    "content-type": "application/json; charset=utf-8",
    "accept-encoding": "gzip",
}

# mediahubmx-resolve.json için başlıklar
RESOLVE_HEADERS = {
    "user-agent": "MediaHubMX/2",
    "accept": "application/json",
    "content-type": "application/json; charset=utf-8",
    "content-length": "115",
    "accept-encoding": "gzip",
}

# Dinamik mediahubmx-signature oluşturma
def getAuthSignature():
    try:
        _headers = {
            "user-agent": "okhttp/4.11.0",
            "accept": "application/json",
            "content-type": "application/json; charset=utf-8",
            "content-length": "1106",
            "accept-encoding": "gzip"
        }
        _data = {
            "token": "tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g",
            "reason": "app-blur",
            "locale": "de",
            "theme": "dark",
            "metadata": {
                "device": {"type": "Handset", "brand": "google", "model": "Nexus", "name": "21081111RG", "uniqueId": "d10e5d99ab665233"},
                "os": {"name": "android", "version": "7.1.2", "abis": ["arm64-v8a", "armeabi-v7a", "armeabi"], "host": "android"},
                "app": {"platform": "android", "version": "3.1.20", "buildId": "289515000", "engine": "hbc85", "signatures": ["6e8a975e3cbf07d5de823a760d4c2547f86c1403105020adee5de67ac510999e"], "installer": "app.revanced.manager.flutter"},
                "version": {"package": "tv.vavoo.app", "binary": "3.1.20", "js": "3.1.20"}
            },
            "appFocusTime": 0,
            "playerActive": False,
            "playDuration": 0,
            "devMode": False,
            "hasAddon": True,
            "castConnected": False,
            "package": "tv.vavoo.app",
            "version": "3.1.20",
            "process": "app",
            "firstAppStart": 1743962904623,
            "lastAppStart": 1743962904623,
            "ipLocation": "",
            "adblockEnabled": True,
            "proxy": {"supported": ["ss", "openvpn"], "engine": "ss", "ssVersion": 1, "enabled": True, "autoServer": True, "id": "pl-waw"},
            "iap": {"supported": False}
        }
        response = requests.post('https://www.vavoo.tv/api/app/ping', json=_data, headers=_headers, verify=False)
        response.raise_for_status()
        signature = response.json().get("addonSig", "")
        print(f"Auth Signature Response (app/ping): {response.text}")
        if signature:
            return signature
        # Alternatif endpoint: /api/box/ping2
        print("app/ping başarısız, box/ping2 deneniyor...")
        vec = {
            "vec": "9frjpxPjxSNilxJPCJ0XGYs6scej3dW/h/VWlnKUiLSG8IP7mfyDU7NirOlld+VtCKGj03XjetfliDMhIev7wcARo+YTU8KPFuVQP9E2DVXzY2BFo1NhE6qEmPfNDnm74eyl/7iFJ0EETm6XbYyz8IKBkAqPN/Spp3PZ2ulKg3QBSDxcVN4R5zRn7OsgLJ2CNTuWkd/h451lDCp+TtTuvnAEhcQckdsydFhTZCK5IiWrrTIC/d4qDXEd+GtOP4hPdoIuCaNzYfX3lLCwFENC6RZoTBYLrcKVVgbqyQZ7DnLqfLqvf3z0FVUWx9H21liGFpByzdnoxyFkue3NzrFtkRL37xkx9ITucepSYKzUVEfyBh+/3mtzKY26VIRkJFkpf8KVcCRNrTRQn47Wuq4gC7sSwT7eHCAydKSACcUMMdpPSvbvfOmIqeBNA83osX8FPFYUMZsjvYNEE3arbFiGsQlggBKgg1V3oN+5ni3Vjc5InHg/xv476LHDFnNdAJx448ph3DoAiJjr2g4ZTNynfSxdzA68qSuJY8UjyzgDjG0RIMv2h7DlQNjkAXv4k1BrPpfOiOqH67yIarNmkPIwrIV+W9TTV/yRyE1LEgOr4DK8uW2AUtHOPA2gn6P5sgFyi68w55MZBPepddfYTQ+E1N6R/hWnMYPt/i0xSUeMPekX47iucfpFBEv9Uh9zdGiEB+0P3LVMP+q+pbBU4o1NkKyY1V8wH1Wilr0a+q87kEnQ1LWYMMBhaP9yFseGSbYwdeLsX9uR1uPaN+u4woO2g8sw9Y5ze5XMgOVpFCZaut02I5k0U4WPyN5adQjG8sAzxsI3KsV04DEVymj224iqg2Lzz53Xz9yEy+7/85ILQpJ6llCyqpHLFyHq/kJxYPhDUF755WaHJEaFRPxUqbparNX+mCE9Xzy7Q/KTgAPiRS41FHXXv+7XSPp4cy9jli0BVnYf13Xsp28OGs/D8Nl3NgEn3/eUcMN80JRdsOrV62fnBVMBNf36+LbISdvsFAFr0xyuPGmlIETcFyxJkrGZnhHAxwzsvZ+Uwf8lffBfZFPRrNv+tgeeLpatVcHLHZGeTgWWml6tIHwWUqv2TVJeMkAEL5PPS4Gtbscau5HM+FEjtGS+KClfX1CNKvgYJl7mLDEf5ZYQv5kHaoQ6RcPaR6vUNn02zpq5/X3EPIgUKF0r/0ctmoT84B2J1BKfCbctdFY9br7JSJ6DvUxyde68jB+Il6qNcQwTFj4cNErk4x719Y42NoAnnQYC2/qfL/gAhJl8TKMvBt3Bno+va8ve8E0z8yEuMLUqe8OXLce6nCa+L5LYK1aBdb60BYbMeWk1qmG6Nk9OnYLhzDyrd9iHDd7X95OM6X5wiMVZRn5ebw4askTTc50xmrg4eic2U1w1JpSEjdH/u/hXrWKSMWAxaj34uQnMuWxPZEXoVxzGyuUbroXRfkhzpqmqqqOcypjsWPdq5BOUGL/Riwjm6yMI0x9kbO8+VoQ6RYfjAbxNriZ1cQ+AW1fqEgnRWXmjt4Z1M0ygUBi8w71bDML1YG6UHeC2cJ2CCCxSrfycKQhpSdI1QIuwd2eyIpd4LgwrMiY3xNWreAF+qobNxvE7ypKTISNrz0iYIhU0aKNlcGwYd0FXIRfKVBzSBe4MRK2pGLDNO6ytoHxvJweZ8h1XG8RWc4aB5gTnB7Tjiqym4b64lRdj1DPHJnzD4aqRixpXhzYzWVDN2kONCR5i2quYbnVFN4sSfLiKeOwKX4JdmzpYixNZXjLkG14seS6KR0Wl8Itp5IMIWFpnNokjRH76RYRZAcx0jP0V5/GfNNTi5QsEU98en0SiXHQGXnROiHpRUDXTl8FmJORjwXc0AjrEMuQ2FDJDmAIlKUSLhjbIiKw3iaqp5TVyXuz0ZMYBhnqhcwqULqtFSuIKpaW8FgF8QJfP2frADf4kKZG1bQ99MrRrb2A="
        }
        response = requests.post('https://www.vavoo.tv/api/box/ping2', data=vec, verify=False)
        response.raise_for_status()
        signature = response.json()['response'].get('signed', "")
        print(f"Auth Signature Response (box/ping2): {response.text}")
        return signature
    except Exception as e:
        print(f"Error getting auth signature: {e}")
        return "tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g"

# .ts URL'sini .m3u8 formatına çevirme veya .ts ile devam etme
def resolve_to_m3u8(url):
    try:
        RESOLVE_HEADERS["mediahubmx-signature"] = getAuthSignature()
        _data = {
            "language": "de",
            "region": "AT",
            "url": url,
            "clientVersion": "3.0.2"
        }
        print(f"Resolving URL {url} with headers: {RESOLVE_HEADERS}")
        response = requests.post("https://vavoo.to/mediahubmx-resolve.json", json=_data, headers=RESOLVE_HEADERS, verify=False)
        response.raise_for_status()
        resolved_url = response.json()[0]["url"]
        print(f"Resolved URL: {resolved_url}")
        return resolved_url
    except Exception as e:
        print(f"Error resolving URL {url}: {e}")
        # Yedek olarak .ts URL'sine vavoo_auth ekle
        auth_token = getAuthSignature()[:32]
        ts_url = f"{url.replace('vavoo-iptv', 'live2')[0:-12]}.ts?n=1&b=5&vavoo_auth={auth_token}"
        print(f"Falling back to .ts URL: {ts_url}")
        return ts_url

# Canlı TV kanallarını çekme
def fetch_tv_channels():
    try:
        response = requests.get(VAVOO_LIVE_URL, headers=VAVOO_HEADERS)
        print(f"Yanıt Durumu (LIVE_URL): {response.status_code}")
        print(f"Yanıt İçeriği (LIVE_URL): {response.text[:1000]}")
        response.raise_for_status()
        data = response.json()
        channels = []
        for item in data:
            original_url = item.get("url", "")
            # .ts URL'sini .m3u8'e çevir veya .ts ile devam et
            resolved_url = resolve_to_m3u8(original_url) if "vavoo" in original_url else original_url
            channel = {
                "name": item.get("name", ""),
                "url": resolved_url,
                "group": item.get("group", ""),
                "logo": item.get("logo", "")
            }
            channels.append(channel)
        return channels
    except Exception as e:
        print(f"Hata (TV Kanalları - LIVE_URL): {e}")
        return []

# JSON dosyasını yerel olarak kaydetme
def save_to_file(data, file_path):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"{file_path} yerel olarak kaydedildi.")
    except Exception as e:
        print(f"Hata (Dosya Kaydetme): {e}")

# Ana fonksiyon
def main():
    tv_channels = fetch_tv_channels()
    if tv_channels:
        save_to_file(tv_channels, JSON_FILE_PATH_TV)

if __name__ == "__main__":
    main()
