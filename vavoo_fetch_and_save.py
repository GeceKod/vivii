import requests
import json
import os

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

# Canlı TV kanallarını çekme
def fetch_tv_channels():
    try:
        response = requests.get(VAVOO_LIVE_URL, headers=VAVOO_HEADERS)
        print(f"Yanıt Durumu (LIVE_URL): {response.status_code}")
        print(f"Yanıt İçeriği (LIVE_URL): {response.text[:1000]}")  # İlk 1000 karakter
        response.raise_for_status()
        data = response.json()
        channels = []
        for item in data:
            channel = {
                "name": item.get("name", ""),
                "url": item.get("url", ""),
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
