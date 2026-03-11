Bu klasordeki CSV dosyalari ulke/source-group bazli manuel duzeltme icindir.

Kullanim:

1. `python .\vavoo_categorizer.py` calistirin.
2. Bu klasorde olusan `Turkey.csv`, `Germany.csv`, `Arabia.csv` gibi dosyalari acin.
3. Sadece `override_*` kolonlarini doldurun.
4. Scripti tekrar calistirin.

Temel kolonlar:

- `override_category`: Kanali elle kategoriye zorlar.
- `override_country_code`: ISO ulke kodu. Ornek: `TR`, `DE`, `JO`.
- `override_logo_url`: Kanal logosu URL'si.
- `override_tvg_id`: IPTV-Org kanal id'si. Logo otomatik bulunabiliyorsa buradan cekilir.
- `override_matched_name`: Gorunen eslesen kanal adi.
- `override_matched_country`: Eslesen kanal ulke kodu.
- `override_website`: Kanal sitesi.
- `notes`: Serbest not.

Not:

- `suggested_*` kolonlari sadece oneridir; script bunlari override olarak kullanmaz.
- Dosyalar her calistirmada guncellenir ama mevcut `override_*` ve `notes` alanlari korunur.
