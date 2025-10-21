import requests, urllib, os, re, threading
from urllib.parse import urlsplit
from config.settings import VERIFY_YN, BASE_DIR, CERT_DIR
from config.constants import DEFAULT_HEADERS
from network_utils import _SESSION

def safe_filepart(s: str) -> str:
    # 파일명 안전화(한글은 그대로 두고, 위험 문자만 제거)
    return re.sub(r'[\\/:*?"<>|]+', "_", s or "").strip()

def guess_ext_from_headers(url: str, resp: requests.Response) -> str:
    ct = (resp.headers.get("content-type") or "").lower()
    if "image/jpeg" in ct or "image/jpg" in ct: return ".jpg"
    if "image/png" in ct: return ".png"
    if "image/webp" in ct: return ".webp"
    # URL 확장자 힌트
    path_ext = os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower()
    if path_ext in (".jpg",".jpeg",".png",".webp"): return path_ext
    return ".jpg"  # 기본

def download_image_to(dest_path: str, url: str, host: str, referer: str | None = None) -> str | None:
    """이미지 URL을 dest_path로 저장. 실제 저장된 경로 반환(None=실패)"""
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        hd = dict(DEFAULT_HEADERS)
        if referer:
            hd["Referer"] = referer
            hd["Accept"] = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"

        r = _SESSION.get(url, timeout=20, verify=VERIFY_YN,
                        headers=hd, stream=True, allow_redirects=True)
        if r.status_code != 200:
            return None

        # 확장자 결정
        def _guess_ext(url_, resp):
            ct = (resp.headers.get("content-type") or "").lower()
            if "jpeg" in ct: return ".jpg"
            if "png" in ct:  return ".png"
            if "webp" in ct: return ".webp"
            ext = os.path.splitext(urlsplit(url_).path)[1].lower()
            if ext in (".jpg",".jpeg",".png",".webp"): return ext
            return ".jpg"

        ext = _guess_ext(url, r)
        if not dest_path.lower().endswith(ext):
            dest_path = os.path.splitext(dest_path)[0] + ext

        # 기존 파일 있으면 스킵(최신 덮어쓰려면 이 블록 제거)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 512:
            return dest_path

        # 임시 파일은 스레드/프로세스 고유명으로
        tmp = f"{dest_path}.part.{os.getpid()}.{threading.get_ident()}"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(64*1024):
                if chunk:
                    f.write(chunk)
        os.replace(tmp, dest_path)
        return dest_path
    except Exception as e:
        # 디버깅 도움
        print(f"[warn] save failed: {type(e).__name__}: {e}")
        return None
    
def save_certificate_to_disk(host: str, usedata: str, bib: str, ensured_image_url: str, referer: str | None) -> str | None:
    event_dir = os.path.join(CERT_DIR, safe_filepart(usedata or "unknown"))
    filename  = safe_filepart(f"{usedata}-{bib}")  # 0패딩 유지
    dest      = os.path.join(event_dir, filename + ".jpg")
    return download_image_to(dest, ensured_image_url, host, referer)

def to_web_static_url(local_path: str | None) -> str | None:
    """윈도 경로(C:\\...)나 절대 경로를 /static/... 웹 경로로 바꿔준다."""
    if not local_path:
        return None
    p = str(local_path).replace("\\", "/")
    # 경로 안에 /static/가 포함돼 있으면 그 뒤를 그대로 씀
    idx = p.lower().rfind("/static/")
    if idx != -1:
        return p[idx:]  # '/static/...' 형태

    # 프로젝트 static 디렉토리 하위에 있으면 그 상대경로로 변환
    static_root = os.path.join(BASE_DIR, "static").replace("\\", "/")
    if p.startswith(static_root):
        rel = p[len(static_root):]
        if not rel.startswith("/"):
            rel = "/" + rel
        return "/static" + rel

    # 못 찾겠으면 None
    return None
