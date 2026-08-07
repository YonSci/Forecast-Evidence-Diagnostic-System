from pathlib import Path
from html.parser import HTMLParser
import requests
from tqdm import tqdm


BASE_URL = "https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/2026050800"
OUT_DIR = Path("NMME_May2026/all_files")
OUT_DIR.mkdir(parents=True, exist_ok=True)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs = dict(attrs)
            href = attrs.get("href")
            if href:
                self.links.append(href)


def get_nc_files(base_url):
    response = requests.get(base_url, timeout=60)
    response.raise_for_status()

    parser = LinkParser()
    parser.feed(response.text)

    nc_files = [
        link for link in parser.links
        if link.endswith(".nc")
    ]

    return nc_files


def download_file(url, out_path):
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with open(out_path, "wb") as f, tqdm(
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=out_path.name,
    ) as progress:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                progress.update(len(chunk))


nc_files = get_nc_files(BASE_URL)

print(f"Found {len(nc_files)} NetCDF files.")

for fname in nc_files:
    url = f"{BASE_URL}/{fname}"
    out_path = OUT_DIR / fname

    if out_path.exists():
        print(f"Already exists, skipping: {out_path.name}")
        continue

    download_file(url, out_path)

print("All NetCDF files downloaded.")