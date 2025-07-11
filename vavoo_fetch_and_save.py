import requests
import json
from github import Github
import hashlib
import time
import os
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
import base64

# GitHub ve VAVOO ayarları
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
JSON_FILE_PATH_TV = "vavoo_tv_channels.json"
JSON_FILE_PATH_MOVIES = "vavoo_movies.json"

# VAVOO.TO API ayarları
VAVOO_CATALOG_URL = "https://vavoo.to/mediahubmx-catalog.json"
VAVOO_LIVE_URL = "https://www2.vavoo.to/live2/index?output=json"
VAVOO_MOVIE_URL = "https://vavoo.to/ccapi/"
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# VAVOO.TO için gerekli başlıklar
VAVOO_HEADERS = {
    "user-agent": "VAVOO/2.6",
    "accept": "application/json",
    "content-type": "application/json; charset=utf-8",
    "accept-encoding": "gzip",
}

# VAVOO.TO için auth signature oluşturma
def get_auth_signature():
    public_key = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDYQ/yPjdNq0WHTyvYSqGBspT/e
/dL9On1jW4TQ6cC1aXTtmGXwZvCRWAElFRItYps6Kh+oRzZmt2llfUhnYkC27Gzo
V4sDzsnE6juA8mtJIC2PO28wnHwQXKYjBl7l6u+6uGsFhlUu+hCT8uKPPZtq5n26
SFOGVgxIL5m9P1tZawIDAQAB
-----END PUBLIC KEY-----"""
    rsakey = RSA.importKey(public_key)
    signer = PKCS1_v1_5.new(rsakey)
    
    data = {
        "data": json.dumps({"timestamp": int(time.time())}),
        "signature": ""
    }
    digest = SHA256.new()
    digest.update(data["data"].encode("utf-8"))
    signature = signer.sign(digest)
    data["signature"] = base64.b64encode(signature).decode("utf-8")
    return base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")

# Canlı TV kanallarını çekme
def fetch_tv_channels():
    try:
        # Alternatif endpoint'i dene
        response = requests.get(VAVOO_LIVE_URL, headers=VAVOO_HEADERS)
        print(f"Yanıt Durumu (LIVE_URL): {response.status_code}")
        print(f"Yanıt İçeriği (LIVE_URL): {response.text}")
        response.raise_for_status()
        data = response.json()
        channels = []
        for item in data.get("channels", []):
            channel = {
                "name": item.get("name", ""),
                "url": item.get("url", ""),
                "group": item.get("group_title", ""),
                "logo": item.get("tvg_logo", "")
            }
            channels.append(channel)
        return channels
    except Exception as e:
        print(f"Hata (TV Kanalları - LIVE_URL): {e}")
        # İlk endpoint'i dene
        try:
            payload = {
                "language": "de",
                "region": "AT",
                "catalogId": "iptv",
                "id": "iptv",
                "adult": False,
                "search": "",
                "sort": "name",
                "filter": {},
                "cursor": "",
                "clientVersion": "3.0.2"
            }
            VAVOO_HEADERS["mediahubmx-signature"] = get_auth_signature()
            response = requests.post(VAVOO_CATALOG_URL, headers=VAVOO_HEADERS, json=payload)
            print(f"Yanıt Durumu (CATALOG_URL): {response.status_code}")
            print(f"Yanıt İçeriği (CATALOG_URL): {response.text}")
            response.raise_for_status()
            data = response.json()
            channels = []
            for item in data.get("items", []):
                channel = {
                    "name": item.get("name", ""),
                    "url": item.get("url", ""),
                    "group": item.get("group", ""),
                    "logo": item.get("logo", "")
                }
                channels.append(channel)
            return channels
        except Exception as e:
            print(f"Hata (TV Kanalları - CATALOG_URL): {e}")
            return []

# Film bilgilerini çekme
def fetch_movies():
    try:
        response = requests.get(VAVOO_MOVIE_URL, headers=VAVOO_HEADERS)
        print(f"Yanıt Durumu (MOVIE_URL): {response.status_code}")
        print(f"Yanıt İçeriği (MOVIE_URL): {response.text}")
        response.raise_for_status()
        data = response.json()
        
        movies = []
        for item in data.get("items", []):
            movie = {
                "title": item.get("title", ""),
                "id": item.get("id", ""),
                "year": item.get("year", ""),
                "poster": item.get("poster", "")
            }
            if TMDB_API_KEY:
                tmdb_data = fetch_tmdb_data(movie["title"])
                movie.update({
                    "plot": tmdb_data.get("overview", ""),
                    "genres": tmdb_data.get("genres", []),
                    "rating": tmdb_data.get("vote_average", 0)
                })
            movies.append(movie)
        return movies
    except Exception as e:
        print(f"Hata (Filmler): {e}")
        return []

# TMDB'den meta veri çekme
def fetch_tmdb_data(title):
    try:
        tmdb_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}"
        response = requests.get(tmdb_url)
        print(f"Yanıt Durumu (TMDB): {response.status_code}")
        print(f"Yanıt İçeriği (TMDB): {response.text}")
        response.raise_for_status()
        data = response.json()
        return data.get("results", [{}])[0]
    except Exception as e:
        print(f"Hata (TMDB): {e}")
        return {}

# GitHub'a JSON dosyasını yükleme
def upload_to_github(data, file_path):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(file_path, ref="main") if repo.get_contents(file_path, ref="main") else None
        json_data = json.dumps(data, indent=2, ensure_ascii=False)
        
        if contents:
            repo.update_file(
                path=file_path,
                message=f"Update {file_path}",
                content=json_data,
                sha=contents.sha,
                branch="main"
            )
        else:
            repo.create_file(
                path=file_path,
                message=f"Create {file_path}",
                content=json_data,
                branch="main"
            )
        print(f"{file_path} başarıyla GitHub'a yüklendi.")
    except Exception as e:
        print(f"Hata (GitHub): {e}")

# Ana fonksiyon
def main():
    tv_channels = fetch_tv_channels()
    if tv_channels:
        upload_to_github(tv_channels, JSON_FILE_PATH_TV)
    
    movies = fetch_movies()
    if movies:
        upload_to_github(movies, JSON_FILE_PATH_MOVIES)

if __name__ == "__main__":
    main()
