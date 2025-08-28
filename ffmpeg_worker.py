import subprocess
from pathlib import Path
import zipfile
import mimetypes

def _run(cmd, timeout=3600):
    print("RUN:", " ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="ignore")[-800:])
    return p


def process_file(input_path: str, workdir: str) -> str:
    """
    - إن كان فيديو: حاول libx265 (CRF=28, preset=fast) ثم fallback إلى libx264 (CRF=23, preset=fast)
    - غير ذلك: ZIP للملف
    - يعيد مسار الناتج
    """
    inp = Path(input_path)
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)

    mime, _ = mimetypes.guess_type(str(inp))
    suffix = inp.suffix.lower()
    is_video = (mime and mime.startswith("video")) or suffix in {".mp4", ".mkv", ".mov", ".avi", ".webm"}

    if is_video:
        # نحافظ على الامتداد الأصلي إن أمكن
        out = work / (inp.stem + "_compressed" + (suffix if suffix else ".mp4"))
        # محاولة H.265 أولاً
        cmd265 = [
            "ffmpeg", "-y", "-i", str(inp),
            "-c:v", "libx265", "-crf", "28", "-preset", "fast",
            "-c:a", "aac", "-b:a", "96k",
            str(out)
        ]
        try:
            _run(cmd265, timeout=60*60)
            return str(out)
        except Exception as e:
            print("x265 failed -> fallback to x264:", e)
            cmd264 = [
                "ffmpeg", "-y", "-i", str(inp),
                "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                "-c:a", "aac", "-b:a", "96k",
                str(out)
            ]
            _run(cmd264, timeout=60*60)
            return str(out)
    else:
        out_zip = work / (inp.stem + ".zip")
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(inp, arcname=inp.name)
        return str(out_zip)