"""Display-only NASA Gateway enrichment. Never mutates frozen model inputs."""
import html
import re
import time
from functools import lru_cache
import httpx

ID = re.compile(r'^([A-Z0-9]{1,20})-([A-Z0-9]{1,10})-(\d{1,12})$')

def parse_focal_length(page):
    # Match the value cell in the same table row as the Focal Length heading.
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', page, re.I | re.S):
        text = html.unescape(re.sub(r'<[^>]+>', ' ', row))
        match = re.search(r'Focal\s+Length\s*:?\s*(\d+(?:\.\d+)?)\s*mm\b', text, re.I)
        if match and 0 < float(match[1]) < 10000:
            return float(match[1])
    return None

@lru_cache(maxsize=4096)
def fetch_metadata(photo_id, cache_period):
    parts = ID.fullmatch(photo_id)
    if not parts: return {}
    mission, roll, frame = parts.groups()
    url = f'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}'
    try:
        response = httpx.get(url, timeout=8, follow_redirects=False)
        response.raise_for_status()
        focal = parse_focal_length(response.text)
    except (httpx.HTTPError, ValueError):
        return {}
    return {} if focal is None else {'focal_length': focal, 'focal_length_source': 'NASA Gateway photo page', 'focal_length_source_url': url}

def nasa_metadata(photo_id):
    return fetch_metadata(photo_id, int(time.time() // 3600))
