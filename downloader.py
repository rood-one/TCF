import os
import time
import requests
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def _safe_filename_from_url(url: str) -> str:
    name = url.split("/")[-1].split("?")[0] or "downloaded"
    return name[:120]  # قص الاسم ليكون آمنًا


def download_file(url: str, dest_path: Path, max_retries: int = 5, retry_delay: int = 10):
    """
    تنزيل مع دعم الاستئناف (Range) وإعادة المحاولة.
    يعيد: (ok: bool, final_path: Path, error: str|None)
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    filename = _safe_filename_from_url(url)
    final_path = dest_path.with_name(filename)

    downloaded = final_path.stat().st_size if final_path.exists() else 0

    for attempt in range(max_retries):
        try:
            headers = {
                "User-Agent": USER_AGENT,
                "Range": f"bytes={downloaded}-" if downloaded else None
            }
            # إزالة المفاتيح None حتى لا تُرسل
            headers = {k: v for k, v in headers.items() if v is not None}

            with requests.get(url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()
                mode = "ab" if downloaded else "wb"
                with open(final_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):  # 256KB
                        if chunk:
                            f.write(chunk)
            return True, final_path, None
        except Exception as e:
            if attempt == max_retries - 1:
                return False, final_path, str(e)
            time.sleep(retry_delay)