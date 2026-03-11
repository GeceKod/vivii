GitHub uzerinden 6 saatte bir otomatik playlist ve EPG guncellemesi icin:

1. Bu projeyi GitHub'a push et.
2. GitHub repo ayarlarinda `Settings > Pages` bolumune gir.
3. `Source` olarak `GitHub Actions` sec.
4. `Actions` sekmesinden `Publish Playlists` workflow'unu bir kez elle calistir.

Workflow ne yapar:

- `vavoo_categorizer.py` ile playlist, logo, kategori ve manuel override ciktilarini uretir.
- Resmi `iptv-org/epg` reposunu klonlar.
- Ulke bazli `output/epg/channels/*.xml` dosyalarindan gercek XMLTV dosyalari uretir.
- GitHub Pages'e su yollarla yayinlar:
  - `/playlists/*.m3u8`
  - `/epg/*.xml`
  - `/reports/*`

Yayinlanan ornek URL'ler:

- `https://KULLANICI.github.io/REPO/playlists/vavoo_Germany.m3u8`
- `https://KULLANICI.github.io/REPO/epg/Germany.xml`

Eger repo adi `kullanici.github.io` ise `REPO` parcasi olmaz.

Otomatik guncelleme:

- Workflow her 6 saatte bir calisir.
- Ayrica istersen `Actions > Publish Playlists > Run workflow` ile elle de tetikleyebilirsin.

Onemli not:

- GitHub, uzun sure hareketsiz kalan repolarda schedule workflow'larini devre disi birakabilir.
- Bu durumda Actions ekranindan workflow'u yeniden acman veya manuel bir run tetiklemen gerekir.
