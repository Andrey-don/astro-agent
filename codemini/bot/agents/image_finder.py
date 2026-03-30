import json
import logging
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from bot.utils.openrouter import call_agent
from codemini.bot.utils.wp_media import upload_image_from_url

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

MODEL = "anthropic/claude-haiku-4-5"
TEMPERATURE = 0.2

EXTRACT_PROMPT = """Ты помогаешь подобрать иллюстрации для статьи об онлайн-школах программирования для детей.

Прочитай статью и определи 2-3 места, где уместно вставить изображение.
Для каждого места укажи:
- search_query: поисковый запрос на английском для Unsplash (2-4 слова, например: "child coding computer", "kids programming class", "boy learning scratch")
- after_heading: точный текст H2-заголовка БЕЗ ## и пробелов по краям, после которого вставить изображение

Верни строго JSON-массив без пояснений и markdown-обёртки:
[
  {"search_query": "child coding laptop", "after_heading": "Почему Scratch подходит детям 7 лет"},
  ...
]"""


def search_unsplash_image(query: str) -> dict | None:
    access_key = os.getenv("UNSPLASH_ACCESS_KEY", "")
    if not access_key:
        return None
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 3, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        photo = results[0]
        url = photo["urls"]["regular"]
        title = photo.get("alt_description") or photo.get("description") or query
        return {"url": url, "title": title.capitalize() if title else query}
    except Exception as e:
        logging.warning(f"codemini image_finder: Unsplash error for '{query}': {e}")
        return None


def insert_image_after_heading(article: str, heading: str, url: str, title: str) -> str:
    heading_md = f"## {heading}"
    if heading_md not in article:
        return article
    image_md = f"\n![{title}]({url})\n"
    return article.replace(heading_md + "\n", heading_md + image_md, 1)


def run(article: str) -> tuple[str, int | None]:
    raw = call_agent(EXTRACT_PROMPT, f"СТАТЬЯ:\n{article}", MODEL, TEMPERATURE)

    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        positions = json.loads(cleaned)
    except Exception as e:
        logging.warning(f"codemini image_finder: не удалось разобрать JSON: {e}")
        return article, None

    result = article
    first_media_id = None
    for pos in positions:
        query = pos.get("search_query", "").strip()
        heading = pos.get("after_heading", "").strip()
        if not query or not heading:
            continue

        image = search_unsplash_image(query)
        if not image:
            image = search_unsplash_image("kids programming education")

        if image:
            wp_url, media_id = upload_image_from_url(image["url"], image["title"])
            if first_media_id is None and media_id:
                first_media_id = media_id
            final_url = wp_url if wp_url else image["url"]
            result = insert_image_after_heading(result, heading, final_url, image["title"])
            logging.info(f"codemini image_finder: вставлено '{image['title']}' после '{heading}'")
        else:
            logging.warning(f"codemini image_finder: не найдено изображение для '{query}'")

    return result, first_media_id
