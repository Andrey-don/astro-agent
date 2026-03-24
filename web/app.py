import os
import sys
import time
import asyncio
import threading
import queue
import logging
from flask import Flask, render_template, request, Response, stream_with_context
from dotenv import load_dotenv
from bot import orchestrator
from bot.utils import wp_posts
from bot.utils.file_loader import mark_topic_used

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Очередь сообщений для SSE (Server-Sent Events)
message_queues: dict[str, queue.Queue] = {}
cancel_flags: dict[str, bool] = {}


def send_msg(session_id: str, text: str):
    if session_id in message_queues:
        message_queues[session_id].put(text)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/plan")
def plan():
    text = orchestrator.get_plan()
    return {"plan": text}


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    topic = data.get("topic", "").strip()
    article_type = data.get("article_type", "научпоп")
    session_id = data.get("session_id", "default")

    if not topic:
        return {"error": "Тема не указана"}, 400

    message_queues[session_id] = queue.Queue()
    cancel_flags[session_id] = False

    def run():
        try:
            send_msg(session_id, f"⏳ Пишу статью «{topic}»... (1-2 минуты)")
            result = orchestrator.generate_article(topic=topic, article_type=article_type)
            draft = wp_posts.create_draft(
                result["title"], result["article"],
                result.get("category_id"),
                result.get("tags", []),
                result.get("featured_image", ""),
                result.get("meta_description", ""),
                result.get("focus_keyword", ""),
                result.get("slug", ""),
            )
            if draft:
                wp_posts.publish_post(draft["id"])
                wp_url = os.getenv("WP_URL", "").rstrip("/")
                edit_link = f"{wp_url}/wp-admin/post.php?post={draft['id']}&action=edit"
                cat = result.get("category_name", "")
                send_msg(session_id, f"✅ Опубликовано: «{result['title']}»")
                send_msg(session_id, f"📁 {cat}" if cat else "")
                send_msg(session_id, f"🔗 {edit_link}")
            else:
                send_msg(session_id, "⚠️ Не удалось сохранить в WordPress")
        except Exception as e:
            logging.exception("Ошибка генерации")
            send_msg(session_id, f"❌ Ошибка: {e}")
        finally:
            send_msg(session_id, "__DONE__")

    threading.Thread(target=run, daemon=True).start()
    return {"status": "started"}


@app.route("/generate_week", methods=["POST"])
def generate_week():
    data = request.json
    start_date = data.get("start_date", "").strip()
    session_id = data.get("session_id", "default")

    if not start_date:
        return {"error": "Дата не указана"}, 400

    message_queues[session_id] = queue.Queue()
    cancel_flags[session_id] = False

    def run():
        try:
            schedule = orchestrator.get_schedule_topics(start_date=start_date, days=10)
            send_msg(session_id, f"📅 Генерирую 10 статей с {start_date}... (~30 мин)")
            for i, item in enumerate(schedule, 1):
                if cancel_flags.get(session_id):
                    send_msg(session_id, "⏹ Генерация остановлена.")
                    break
                topic = item["topic"]
                article_type = item["article_type"]
                pub_date = item["publish_date"]
                pub_day = pub_date[:10]

                send_msg(session_id, f"[{i}/{len(schedule)}] Пишу: «{topic}» ({pub_day})...")
                mark_topic_used(topic)
                try:
                    result = orchestrator.generate_article(topic=topic, article_type=article_type)
                except Exception as e:
                    logging.exception(f"Ошибка: {topic}")
                    send_msg(session_id, f"❌ Ошибка: {topic}\n{e}")
                    continue

                draft = wp_posts.create_draft(
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
                    send_msg(session_id, f"✅ {pub_day} — «{result['title']}»")
                    if cat:
                        send_msg(session_id, f"📁 {cat}")
                    send_msg(session_id, f"🔗 {edit_link}")
                else:
                    send_msg(session_id, f"⚠️ Не сохранилась: {topic}")
            else:
                send_msg(session_id, "🎉 10 дней готовы! Все статьи запланированы в WordPress.")
        except Exception as e:
            logging.exception("Ошибка планировщика")
            send_msg(session_id, f"❌ Критическая ошибка: {e}")
        finally:
            send_msg(session_id, "__DONE__")

    threading.Thread(target=run, daemon=True).start()
    return {"status": "started"}


@app.route("/stop", methods=["POST"])
def stop():
    data = request.json
    session_id = data.get("session_id", "default")
    cancel_flags[session_id] = True
    return {"status": "stopped"}


@app.route("/restart", methods=["POST"])
def restart():
    import subprocess
    def do_restart():
        time.sleep(1)
        subprocess.Popen([sys.executable, "-m", "web.app"])
        os._exit(0)
    threading.Thread(target=do_restart, daemon=True).start()
    return {"status": "restarting"}


@app.route("/stream/<session_id>")
def stream(session_id):
    def generate():
        message_queues[session_id] = message_queues.get(session_id, queue.Queue())
        while True:
            try:
                msg = message_queues[session_id].get(timeout=60)
                yield f"data: {msg}\n\n"
                if msg == "__DONE__":
                    break
            except queue.Empty:
                yield "data: __PING__\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)
