import os
import asyncio
import logging
import shutil
from pathlib import Path
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType

from ffmpeg_worker import process_file
from uploader import upload_to_pixeldrain
from downloader import download_file
from app_server import run_flask
import threading

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

WORKDIR = Path("/tmp/bot_work")
WORKDIR.mkdir(parents=True, exist_ok=True)
MAX_TELEGRAM_FILESIZE = 50 * 1024 * 1024  # 50MB

# شغّل Flask في خيط منفصل (مطابق لطريقتك)
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()


@dp.message_handler(commands=["start", "help"])
async def cmd_start(message: types.Message):
    await message.reply(
        "أهلاً! أرسل:")
    await message.answer(
        "- ملفًا (Document/Video/Photo) أو رابط http/https.\n"
        "- يمكنك إعادة توجيه/اقتباس رسائل قناة إلى قناة يوجد فيها البوت.\n\n"
        "المعالجة: ZIP للملفات، H.265 ثم H.264 للفيديو.\n"
        "إن كان الناتج ≤ 50MB سأرسله مباشرة، وإلا سأرفعه إلى PixelDrain وأعيد لك الرابط."
    )


async def _download_tg_file(file_id: str, dest: Path):
    f = await bot.get_file(file_id)
    await bot.download_file(f.file_path, destination=dest)
    return dest


async def _handle_local_process_and_respond(message: types.Message, input_path: Path):
    try:
        work_sub = WORKDIR / f"{message.chat.id}_{message.message_id}"
        work_sub.mkdir(parents=True, exist_ok=True)
        # نسخ/نقل الإدخال إلى مجلد العمل
        local_input = work_sub / input_path.name
        if input_path != local_input:
            shutil.copy2(input_path, local_input)

        # معالجة
        loop = asyncio.get_event_loop()
        output_path_str = await loop.run_in_executor(None, process_file, str(local_input), str(work_sub))
        output_path = Path(output_path_str)

        size = output_path.stat().st_size
        if size <= MAX_TELEGRAM_FILESIZE:
            await message.reply("النتيجة ≤ 50MB — إرسال مباشر عبر تيليجرام…")
            with open(output_path, "rb") as f:
                await message.reply_document(f)
        else:
            await message.reply("الناتج > 50MB — جارٍ رفع الملف إلى PixelDrain …")
            url = await asyncio.get_event_loop().run_in_executor(None, upload_to_pixeldrain, str(output_path), output_path.name)
            if url:
                await message.reply(f"تم الرفع: {url}")
            else:
                await message.reply("فشل الرفع إلى PixelDrain.")
    finally:
        try:
            shutil.rmtree(work_sub, ignore_errors=True)
        except Exception:
            pass


# استقبال ملفات مباشرة في المحادثة الخاصة أو المجموعات أو القنوات
@dp.message_handler(content_types=[ContentType.DOCUMENT, ContentType.VIDEO, ContentType.PHOTO])
async def handle_incoming_media(message: types.Message):
    await message.reply("استلمت الملف — جاري التنزيل …")
    tmp_in = WORKDIR / f"tg_{message.chat.id}_{message.message_id}"
    tmp_in.parent.mkdir(parents=True, exist_ok=True)

    # document / video / photo
    if message.document:
        filename = message.document.file_name or "file"
        dest = tmp_in.with_name(filename)
        await _download_tg_file(message.document.file_id, dest)
    elif message.video:
        filename = message.video.file_name or "video.mp4"
        dest = tmp_in.with_name(filename)
        await _download_tg_file(message.video.file_id, dest)
    else:  # photo
        dest = tmp_in.with_suffix(".jpg")
        await _download_tg_file(message.photo[-1].file_id, dest)

    await message.reply("تم التنزيل — جاري المعالجة …")
    await _handle_local_process_and_respond(message, dest)


# استقبال روابط عامة http/https في الرسائل النصية
@dp.message_handler(regexp=r"^https?://")
async def handle_url(message: types.Message):
    url = message.text.strip()
    await message.reply("جاري تنزيل الرابط …")
    work_dir = WORKDIR / f"url_{message.chat.id}_{message.message_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    filename = None  # سيحاول الاستدلال من الرؤوس أو المسار
    dest = work_dir / "downloaded.bin"

    ok, final_path, err = download_file(url, dest)
    if not ok:
        await message.reply(f"فشل التنزيل: {err}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return

    await message.reply("تم التنزيل — جاري المعالجة …")
    await _handle_local_process_and_respond(message, final_path)


# استقبال منشورات القناة مباشرة (حين يكون البوت عضوًا)
@dp.channel_post_handler(content_types=[ContentType.DOCUMENT, ContentType.VIDEO, ContentType.PHOTO, ContentType.TEXT])
async def handle_channel_posts(message: types.Message):
    if message.content_type == ContentType.TEXT and message.text and message.text.startswith(("http://", "https://")):
        await handle_url(message)
    else:
        await handle_incoming_media(message)


if __name__ == "__main__":
    # تشغيل البوت بالـ polling

    executor.start_polling(dp, skip_updates=True)
