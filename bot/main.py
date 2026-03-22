import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters,
)
from bot import orchestrator

load_dotenv()
logging.basicConfig(level=logging.INFO)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✍️ Написать статью", "📋 План на неделю"],
        ["📰 Новостная", "🔭 Научпоп", "🌐 Смешанная"],
    ],
    resize_keyboard=True,
)

user_state: dict = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я пишу статьи для astro-obzor.ru.\n\n"
        "Выбери действие или напиши тему:",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    # Ожидание темы
    if chat_id in user_state:
        article_type = user_state.pop(chat_id)
        await update.message.reply_text(f"Пишу статью «{text}»... Подожди 1-2 минуты. ⏳")
        result = orchestrator.generate_article(topic=text, article_type=article_type)
        # Отправляем частями если длинная
        article_text = result["article"]
        if len(article_text) > 4000:
            await update.message.reply_text(article_text[:4000])
            await update.message.reply_text(article_text[4000:8000])
        else:
            await update.message.reply_text(article_text)
        await update.message.reply_text(f"📊 SEO:\n\n{result['seo']}")
        await update.message.reply_text(f"✅ Сохранено в файл:\n{result['file']}")
        return

    if text == "✍️ Написать статью":
        user_state[chat_id] = "научпоп"
        await update.message.reply_text("Напиши тему статьи:")

    elif text == "📰 Новостная":
        user_state[chat_id] = "новостная"
        await update.message.reply_text("Напиши тему новостной статьи:")

    elif text == "🔭 Научпоп":
        user_state[chat_id] = "научпоп"
        await update.message.reply_text("Напиши тему для научпопа:")

    elif text == "🌐 Смешанная":
        user_state[chat_id] = "смешанная"
        await update.message.reply_text("Напиши тему:")

    elif text == "📋 План на неделю":
        plan = orchestrator.get_plan()
        await update.message.reply_text(f"📋 Контент-план:\n\n{plan[:4000]}")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Астро-агент запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()
