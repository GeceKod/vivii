import requests
import json
from github import Github
import os

# GitHub ve VAVOO ayarları
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
JSON_FILE_PATH_TV = "vavoo_tv_channels.json"
JSON_FILE_PATH_MOVIES = "vavoo_movies.json"

# VAVOO.TO API ayarları
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

# Canlı TV kanallarını çekme
def fetch_tv_channels():
    try:
        response = requests.get(VAVOO_LIVE_URL, headers=VAVOO_HEADERS)
        print(f"Yanıt Durumu (LIVE_URL): {response.status_code}")
        print(f"Yanıt İçeriği (LIVE_URL): {response.text}")
        response.raise_for_status()
        data = response.json()
        channels = []
        for item in data:  # Doğrudan liste üzerinde iterasyon
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

# Film bilgilerini çekme (geçici olarak devre dışı)
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
    
    # movies = fetch_movies()  # Geçici olarak devre dışı
    # if movies:
    #     upload_to_github(movies, JSON_FILE_PATH_MOVIES)

if __name__ == "__main__":
    main()
