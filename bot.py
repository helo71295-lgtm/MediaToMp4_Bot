import os
import logging
import ffmpeg
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Fetch bot token from environment variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcoming message when /start command is issued."""
    await update.message.reply_text(
        "👋 Welcome! Send or forward any video or document file, "
        "and I will convert it to **MP4** for you."
    )


async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download video/document, convert to MP4 using FFmpeg, and send back."""
    message = update.message
    file_obj = None

    # Determine whether user sent a Video or Document
    if message.video:
        file_obj = message.video
    elif message.document:
        file_obj = message.document
    else:
        await message.reply_text("Please send a valid video file.")
        return

    status_msg = await message.reply_text("📥 Downloading file...")

    input_path = f"input_{file_obj.file_unique_id}"
    output_path = f"converted_{file_obj.file_unique_id}.mp4"

    try:
        # Download file from Telegram
        tg_file = await context.bot.get_file(file_obj.file_id)
        await tg_file.download_to_drive(input_path)

        await status_msg.edit_text("⚙️ Converting video to MP4...")

        # Convert video to MP4 using FFmpeg (H.264 video codec + AAC audio codec)
        (
            ffmpeg.input(input_path)
            .output(
                output_path,
                vcodec="libx264",
                acodec="aac",
                preset="fast",
                movflags="faststart",
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        await status_msg.edit_text("📤 Uploading converted MP4...")

        # Send back converted file
        with open(output_path, "rb") as converted_file:
            await message.reply_video(
                video=converted_file,
                caption="✅ Here is your converted MP4 video!",
            )

        await status_msg.delete()

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg Error: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
        await status_msg.edit_text("❌ Failed to convert video. Please check the file format.")
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await status_msg.edit_text("❌ An unexpected error occurred.")
    finally:
        # Clean up local temporary files
        for path in (input_path, output_path):
            if os.path.exists(path):
                os.remove(path)


def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, process_video))

    logger.info("Bot started and listening...")
    app.run_polling()


if __name__ == "__main__":
    main()