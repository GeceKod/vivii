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
        response = requests.post('https://www.vavoo.tv/api/app/ping', json=_data, headers=_headers)
        response.raise_for_status()
        return response.json().get("addonSig", "")
    except Exception as e:
        print(f"Error getting auth signature: {e}")
        return "tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g"

# .ts URL'sini .m3u8 formatına çevirme veya .ts ile devam etme
def resolve_to_m3u8(url):
    try:
        RESOLVE_HEADERS["mediahubmx-signature"] = getAuthSignature()
        _data = {"language": "de", "region": "AT", "url": url, "clientVersion": "3.0.2"}
        response = requests.post("https://vavoo.to/mediahubmx-resolve.json", json=_data, headers=RESOLVE_HEADERS)
        response.raise_for_status()
        resolved_url = response.json()[0]["url"]
        print(f"Resolved URL: {resolved_url}")
        return resolved_url
    except Exception as e:
        print(f"Error resolving URL {url}: {e}")
        # Yedek olarak .ts URL'sine vavoo_auth ekle
        auth_token = getAuthSignature()[:32]  # Örnek token, gerçek token için başka bir yöntem gerekebilir
        return f"{url}?n=1&b=5&vavoo_auth={auth_token}"

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
