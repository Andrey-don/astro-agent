import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters,
)
from telegram.request import HTTPXRequest
from bot import orchestrator
from bot.utils import wp_posts
from bot.utils.file_loader import mark_topic_used

load_dotenv()
logging.basicConfig(level=logging.INFO)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✍️ Написать статью", "📋 План на неделю"],
        ["📰 Новостная", "🔭 Научпоп", "🌐 Смешанная"],
        ["📅 Запланировать неделю", "⏹ Стоп"],
        ["🔄 Рестарт"],
    ],
    resize_keyboard=True,
)

BUTTON_TEXTS = {"✍️ Написать статью", "📋 План на неделю", "📰 Новостная", "🔭 Научпоп", "🌐 Смешанная", "📅 Запланировать неделю", "⏹ Стоп", "🔄 Рестарт"}
WEEK_STATES = {"waiting_week_date"}

# user_state[chat_id] = {"state": "waiting_topic", "article_type": "..."}
user_state: dict = {}
# cancel_flags[chat_id] = True означает что надо остановить генерацию
cancel_flags: dict = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я пишу статьи для astro-obzor.ru.\n\n"
        "Выбери действие или напиши тему:",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id
    state_data = user_state.get(chat_id, {})

    # Ожидание даты для планировщика недели
    if state_data.get("state") == "waiting_week_date" and text not in BUTTON_TEXTS:
        user_state.pop(chat_id)
        await update.message.reply_text(f"Генерирую 7 статей с {text}... ⏳ (~20 мин)")
        await _generate_week(update, start_date=text)
        return

    # Ожидание темы — но если пользователь нажал кнопку, сбрасываем и обрабатываем кнопку
    if state_data.get("state") == "waiting_topic" and text not in BUTTON_TEXTS:
        article_type = state_data["article_type"]
        user_state.pop(chat_id)
        await update.message.reply_text(f"Пишу статью «{text}»... Подожди 1-2 минуты. ⏳")
        try:
            result = await asyncio.to_thread(
                orchestrator.generate_article, topic=text, article_type=article_type
            )
        except Exception as e:
            logging.exception("Ошибка генерации статьи")
            await update.message.reply_text(f"❌ Ошибка при генерации: {e}")
            return

        # Сохраняем и публикуем в WordPress
        await _save_draft(update, result)
        return

    # Если была ожидающая тема, но пользователь нажал кнопку — сбрасываем состояние
    if state_data and text in BUTTON_TEXTS:
        user_state.pop(chat_id)

    if text == "✍️ Написать статью":
        user_state[chat_id] = {"state": "waiting_topic", "article_type": "научпоп"}
        await update.message.reply_text("Напиши тему статьи:")

    elif text == "📰 Новостная":
        user_state[chat_id] = {"state": "waiting_topic", "article_type": "новостная"}
        await update.message.reply_text("Напиши тему новостной статьи:")

    elif text == "🔭 Научпоп":
        user_state[chat_id] = {"state": "waiting_topic", "article_type": "научпоп"}
        await update.message.reply_text("Напиши тему для научпопа:")

    elif text == "🌐 Смешанная":
        user_state[chat_id] = {"state": "waiting_topic", "article_type": "смешанная"}
        await update.message.reply_text("Напиши тему:")

    elif text == "📋 План на неделю":
        plan = orchestrator.get_plan()
        await update.message.reply_text(f"📋 Контент-план:\n\n{plan[:4000]}")

    elif text == "📅 Запланировать неделю":
        user_state[chat_id] = {"state": "waiting_week_date"}
        await update.message.reply_text("С какой даты? (например: 25.03)")

    elif text == "⏹ Стоп":
        cancel_flags[chat_id] = True
        await update.message.reply_text("⏹ Останавливаю после текущей статьи...", reply_markup=MAIN_KEYBOARD)

    elif text == "🔄 Рестарт":
        await update.message.reply_text("🔄 Перезапускаю бота...")
        import subprocess, sys, os
        # Сохраняем chat_id чтобы новый процесс отправил подтверждение
        with open(".restart_chat_id", "w") as f:
            f.write(str(chat_id))
        subprocess.Popen([sys.executable, "-m", "bot.main"])
        os._exit(0)


async def _save_draft(update: Update, result: dict):
    """Сохраняет черновик в WordPress с заголовком, метками и изображением."""
    draft = await asyncio.to_thread(
        wp_posts.create_draft,
        result["title"],
        result["article"],
        result.get("category_id"),
        result.get("tags", []),
        result.get("featured_image", ""),
        result.get("meta_description", ""),
        result.get("focus_keyword", ""),
        result.get("slug", ""),
    )
    if draft:
        wp_url = os.getenv("WP_URL", "").rstrip("/")
        edit_link = f"{wp_url}/wp-admin/post.php?post={draft['id']}&action=edit"
        category_name = result.get("category_name", "")
        cat_line = f"📁 Рубрика: {category_name}\n" if category_name else ""
        # Публикуем сразу
        published = await asyncio.to_thread(wp_posts.publish_post, draft["id"])
        status = "🟢 Опубликовано!" if published else "📝 Черновик (не удалось опубликовать)"
        await update.message.reply_text(
            f"{status}\n"
            f"{cat_line}"
            f"🔗 {edit_link}",
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text("⚠️ Не удалось сохранить черновик в WordPress.")



async def _generate_week(update, start_date: str = ""):
    """Генерирует 7 статей с указанной даты с отложенной публикацией."""
    chat_id = update.message.chat_id
    cancel_flags[chat_id] = False
    schedule = orchestrator.get_schedule_topics(start_date=start_date, days=7)

    for i, item in enumerate(schedule, 1):
        if cancel_flags.get(chat_id):
            await update.message.reply_text("⏹ Генерация остановлена.", reply_markup=MAIN_KEYBOARD)
            return
        topic = item["topic"]
        article_type = item["article_type"]
        pub_date = item["publish_date"]
        pub_day = pub_date[:10]

        await update.message.reply_text(f"[{i}/{len(schedule)}] Пишу: «{topic}» ({pub_day})...")
        # Помечаем тему как использованную ДО генерации — чтобы не повторялась при перезапуске
        await asyncio.to_thread(mark_topic_used, topic)
        try:
            result = await asyncio.to_thread(
                orchestrator.generate_article, topic=topic, article_type=article_type
            )
        except Exception as e:
            logging.exception(f"Ошибка генерации '{topic}'")
            await update.message.reply_text(f"❌ Ошибка: {topic}\n{e}")
            continue

        draft = await asyncio.to_thread(
            wp_posts.create_draft,
            result["title"], result["article"],
            result.get("category_id"),
            result.get("tags", []),
            result.get("featured_image", ""),
            result.get("meta_description", ""),
            result.get("focus_keyword", ""),
            result.get("slug", ""),
            pub_date,
        )
        if draft:
            wp_url = os.getenv("WP_URL", "").rstrip("/")
            edit_link = f"{wp_url}/wp-admin/post.php?post={draft['id']}&action=edit"
            cat = result.get("category_name", "")
            await update.message.reply_text(
                f"✅ {pub_day} — «{result['title']}»\n"
                f"{'📁 ' + cat + chr(10) if cat else ''}"
                f"🔗 {edit_link}"
            )
        else:
            await update.message.reply_text(f"⚠️ Не сохранилась: {topic}")

    await update.message.reply_text(
        "🎉 Неделя готова! Все статьи запланированы в WordPress.",
        reply_markup=MAIN_KEYBOARD,
    )


async def on_startup(app):
    """Отправляет сообщение об успешном рестарте если был запрос."""
    if os.path.exists(".restart_chat_id"):
        with open(".restart_chat_id") as f:
            chat_id = f.read().strip()
        os.remove(".restart_chat_id")
        try:
            await app.bot.send_message(chat_id=int(chat_id), text="✅ Бот перезапущен успешно!", reply_markup=MAIN_KEYBOARD)
        except Exception:
            pass


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=60,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=30,
    )
    app = Application.builder().token(token).request(request).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Астро-агент запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()
