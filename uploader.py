import os
import time
import base64
import logging
import requests
from pathlib import Path

logger = logging.getLogger("uploader")

PIXELDRAIN_UPLOAD_URL = "https://pixeldrain.com/api/file"


def upload_to_pixeldrain(file_path, filename=None):
    """رفع الملف إلى Pixeldrain بالطريقة الصحيحة (Basic auth: ":<API_KEY>")"""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"محاولة الرفع إلى Pixeldrain (المحاولة {attempt+1})")

            headers = {}
            api_key = os.getenv("PIXELDRAIN_API_KEY")
            if api_key:
                auth_str = f":{api_key}"
                b64_auth = base64.b64encode(auth_str.encode()).decode()
                headers["Authorization"] = f"Basic {b64_auth}"
                logger.info("تم إعداد مصادقة API")

            with open(p, "rb") as f:
                files = {"file": (filename or p.name, f)}
                response = requests.post(
                    PIXELDRAIN_UPLOAD_URL,
                    files=files,
                    headers=headers,
                    timeout=300
                )

            logger.info(f"حالة الاستجابة: {response.status_code}")
            response.raise_for_status()
            data = response.json()

            # شكل شائع: { success:true, id:"..." }
            if data.get("success", False):
                file_id = data.get("id")
                if file_id:
                    return f"https://pixeldrain.com/api/file/{file_id}"
                else:
                    raise Exception("فشل في الحصول على ID الملف من الاستجابة")
            else:
                err = data.get("value", "Unknown error")
                raise Exception(f"فشل الرفع: {err}")

        except Exception as e:
            logger.error(f"فشل الرفع إلى Pixeldrain: {e}")
            if attempt == max_retries - 1:
                return None
            time.sleep(10)