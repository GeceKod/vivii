import json
import os

# JSON ve M3U dosya yolları
JSON_FILE_PATH = "vavoo_tv_channels.json"
M3U_FILE_PATH = "vavoo.m3u"

def generate_m3u():
    try:
        # JSON dosyasını oku
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            channels = json.load(f)
        
        # M3U dosyasını oluştur
        m3u_content = ["#EXTM3U\n"]
        for channel in channels:
            name = channel.get("name", "")
            url = channel.get("url", "")
            group = channel.get("group", "Standart")
            logo = channel.get("logo", "")
            print(f"Adding channel: {name}, URL: {url}")
            # M3U satırı oluştur
            m3u_content.append(
                f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}\n{url}|User-Agent=VAVOO/2.6\n'
            )
        
        # M3U dosyasını kaydet
        with open(M3U_FILE_PATH, "w", encoding="utf-8") as f:
            f.writelines(m3u_content)
        print(f"{M3U_FILE_PATH} oluşturuldu.")
    except Exception as e:
        print(f"Hata (M3U Oluşturma): {e}")

if __name__ == "__main__":
    generate_m3u()
