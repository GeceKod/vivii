import requests
import json
from github import Github
import hashlib
import time

# GitHub ayarları
GITHUB_TOKEN = "your_github_personal_access_token"  # GitHub Personal Access Token
REPO_NAME = "your_username/your_repository"  # Örnek: "kullanici_adiniz/depo_adiniz"
JSON_FILE_PATH_TV = "vavoo_tv_channels.json"
JSON_FILE_PATH_MOVIES = "vavoo_movies.json"

# VAVOO.TO API ayarları
VAVOO_CATALOG_URL = "https://vavoo.to/mediahubmx-catalog.json"
VAVOO_RESOLVE_URL = "https://vavoo.to/mediahubmx-resolve.json"
VAVOO_LIVE_URL = "https://www2.vavoo.to/live2/index?output=json"
VAVOO_MOVIE_URL = "https://vavoo.to/ccapi/"
TMDB_API_KEY = "your_tmdb_api_key"  # TMDB API anahtarı (opsiyonel)

# VAVOO.TO için gerekli başlıklar
VAVOO_HEADERS = {
    "user-agent": "okhttp/4.11.0",
    "accept": "application/json",
    "content-type": "application/json; charset=utf-8",
    "accept-encoding": "gzip",
}

# VAVOO.TO için auth signature oluşturma (basit bir örnek)
def get_auth_signature():
    # Gerçek uygulamada RSA-SHA256 ile doğrulama gerekir, burada basit bir örnek
    timestamp = str(int(time.time()))
    data = f"some_data{timestamp}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()

# Canlı TV kanallarını çekme
def fetch_tv_channels():
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
        response.raise_for_status()
        data = response.json()
        
        # Kanal listesini düzenle
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
        print(f"Hata (TV Kanalları): {e}")
        return []

# Film bilgilerini çekme
def fetch_movies():
    try:
        response = requests.get(VAVOO_MOVIE_URL, headers=VAVOO_HEADERS)
        response.raise_for_status()
        data = response.json()
        
        # Film listesini düzenle
        movies = []
        for item in data.get("items", []):
            movie = {
                "title": item.get("title", ""),
                "id": item.get("id", ""),
                "year": item.get("year", ""),
                "poster": item.get("poster", "")
            }
            # TMDB ile meta veri çekme (opsiyonel)
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
            # Dosya varsa güncelle
            repo.update_file(
                path=file_path,
                message=f"Update {file_path}",
                content=json_data,
                sha=contents.sha,
                branch="main"
            )
        else:
            # Dosya yoksa oluştur
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
    # TV kanallarını çek ve JSON olarak kaydet
    tv_channels = fetch_tv_channels()
    if tv_channels:
        upload_to_github(tv_channels, JSON_FILE_PATH_TV)
    
    # Filmleri çek ve JSON olarak kaydet
    movies = fetch_movies()
    if movies:
        upload_to_github(movies, JSON_FILE_PATH_MOVIES)

if __name__ == "__main__":
    main()
