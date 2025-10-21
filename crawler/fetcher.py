import urllib, time, re

from bs4 import BeautifulSoup
from config.settings import VERIFY_YN
from utils.network_utils import add_cache_buster, _SESSION, normalize_url
from crawler.worker import get_mr_worker

_CACHE = {}
_CACHE_TTL = 30

def fetch(url: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    url2 = add_cache_buster(url)
    verify = VERIFY_YN       
    # if host in INSECURE_HOSTS:
    #     verify = False
     # 1) myresult는 브라우저 렌더로 먼저 시도
    if any(h in host for h in ["myresult.co.kr", "spct.co.kr"]):
        html = get_mr_worker().fetch(url2, timeout=10)
        if html:                  # 성공적으로 HTML/JSON:: 받은 경우
            return html
        print("[warn] myresult fast fetch failed: worker empty")

    # 2) 그 외(또는 실패 시) 기존 요청 (너가 지금 verify=False 전역이면 유지)
    r = _SESSION.get(url2, timeout=10, verify=verify)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text

def fetch_cached(url: str) -> str:
    """캐싱이 적용된 fetch"""
    now = time.time()
    if url in _CACHE:
        data, ts = _CACHE[url]
        if now - ts < _CACHE_TTL:
            return data
    
    html = fetch(url)
    _CACHE[url] = (html, now)
    return html

def fetch_html_follow_js_redirect(url: str, timeout: int = 15) -> BeautifulSoup:
    resp = _SESSION.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # 1) <script> location.href="..."; 형태 감지
    m = re.search(r'location\.href\s*=\s*"([^"]+)"', html, re.I)
    if m:
        target = normalize_url(m.group(1))
        resp.url = normalize_url(resp.url)
        # 절대 URL로 보정
        target_abs = urllib.parse.urljoin(resp.url, target)
        # referer 유지
        _SESSION.headers["Referer"] = resp.url
        resp2 = _SESSION.get(target_abs, timeout=timeout, allow_redirects=True)
        resp2.raise_for_status()
        return BeautifulSoup(resp2.text, "html.parser")

    # 2) <meta http-equiv="refresh" content="0; url=..."> 대비
    meta = soup.select_one('meta[http-equiv="refresh" i]')
    if meta and meta.get("content"):
        m2 = re.search(r'url\s*=\s*([^;]+)', meta["content"], re.I)
        if m2:
            target = normalize_url(m2.group(1).strip(' "\''))
            resp.url = normalize_url(resp.url)
            target_abs = urllib.parse.urljoin(resp.url, target)
            _SESSION.headers["Referer"] = resp.url
            resp2 = _SESSION.get(target_abs, timeout=timeout, allow_redirects=True)
            resp2.raise_for_status()
            return BeautifulSoup(resp2.text, "html.parser")

    return soup
