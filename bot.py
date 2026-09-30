import os
import logging
import ffmpeg
from telegram import Update, BotCommand
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


async def post_init(application: Application) -> None:
    """Set bot commands menu and remove active webhooks automatically on startup."""
    commands = [
        BotCommand("start", "Start the video converter bot"),
        BotCommand("help", "Get instructions and supported formats"),
        BotCommand("settings", "View video encoding settings"),
    ]
    await application.bot.set_my_commands(commands)
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot commands set and webhook cleared successfully.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcoming message when /start command is issued."""
    await update.message.reply_text(
        "👋 Welcome! Send or forward any video or document file, "
        "and I will convert it to **MP4** for you.\n\n"
        "Use /help to see full instructions."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help instructions when /help command is issued."""
    await update.message.reply_text(
        "📖 **How to Use:**\n"
        "1. Send or forward any video file or document.\n"
        "2. The bot will automatically convert it to MP4 format.\n\n"
        "🎥 **Supported Formats:** MKV, AVI, MOV, WEBM, FLV, WMV, etc.\n"
        "⚠️ **Limit:** Files up to 50 MB (Telegram Bot API limit)."
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send video settings details."""
    await update.message.reply_text(
        "⚙️ **Encoding Settings:**\n"
        "• Video Codec: H.264 (libx264)\n"
        "• Audio Codec: AAC\n"
        "• Format: MP4\n"
        "• Preset: Fast"
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

    # Check file size limit (50 MB limit)
    if file_obj.file_size and file_obj.file_size > 50 * 1024 * 1024:
        await message.reply_text("❌ File too large! Telegram allows bot downloads up to 50 MB.")
        return

    status_msg = await message.reply_text("📥 Downloading file...")

    input_path = f"input_{file_obj.file_unique_id}"
    output_path = f"converted_{file_obj.file_unique_id}.mp4"

    try:
        # Download file from Telegram
        tg_file = await context.bot.get_file(file_obj.file_id)
        await tg_file.download_to_drive(input_path)

        await status_msg.edit_text("⚙️ Converting video to MP4...")

        # Convert video to MP4 using FFmpeg
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

    # Build application and register post_init setup
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, process_video))

    logger.info("Video to MP4 Converter Bot is active and running...")
    app.run_polling()


if __name__ == "__main__":
    main()
