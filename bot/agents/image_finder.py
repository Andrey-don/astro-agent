import json
import logging
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from bot.utils.openrouter import call_agent
from bot.utils.wp_media import upload_image_from_url

load_dotenv(Path(__file__).parent.parent.parent / ".env")

MODEL = "anthropic/claude-haiku-4-5"
TEMPERATURE = 0.2

EXTRACT_PROMPT = """Ты помогаешь подобрать иллюстрации для статьи об астрономии.

Прочитай статью и определи 2-3 места, где уместно вставить изображение.
Для каждого места укажи:
- search_query: поисковый запрос на английском для NASA Image Library (2-4 слова)
- after_heading: точный текст H2-заголовка БЕЗ ## и пробелов по краям, после которого вставить изображение

Верни строго JSON-массив без пояснений и markdown-обёртки:
[
  {"search_query": "black hole event horizon", "after_heading": "Что такое чёрная дыра"},
  ...
]"""


def search_nasa_image(query: str) -> dict | None:
    """Ищет изображение в NASA Image Library. Возвращает {url, title} или None."""
    try:
        resp = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image"},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("collection", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        title = item.get("data", [{}])[0].get("title", query)
        links = item.get("links", [])
        url = links[0].get("href") if links else None
        if not url:
            return None
        return {"url": url, "title": title}
    except Exception as e:
        logging.warning(f"NASA API error for query '{query}': {e}")
        return None


def search_unsplash_image(query: str) -> dict | None:
    """Ищет изображение на Unsplash. Возвращает {url, title} или None."""
    access_key = os.getenv("UNSPLASH_ACCESS_KEY", "")
    if not access_key or access_key == "your_unsplash_access_key_here":
        return None
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
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
        return {"url": url, "title": title.capitalize()}
    except Exception as e:
        logging.warning(f"Unsplash API error for query '{query}': {e}")
        return None


def insert_image_after_heading(article: str, heading: str, url: str, title: str) -> str:
    """Вставляет изображение после H2-заголовка в тексте."""
    heading_md = f"## {heading}"
    if heading_md not in article:
        return article
    image_md = f"\n![{title}]({url})\n"
    return article.replace(heading_md + "\n", heading_md + image_md, 1)


def run(article: str) -> str:
    # Шаг 1: LLM определяет места для изображений
    raw = call_agent(EXTRACT_PROMPT, f"СТАТЬЯ:\n{article}", MODEL, TEMPERATURE)

    try:
        # Чистим возможные markdown-блоки ```json ... ```
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        positions = json.loads(cleaned)
    except Exception as e:
        logging.warning(f"image_finder: не удалось разобрать JSON от LLM: {e}\nОтвет: {raw}")
        return article

    # Шаг 2: ищем изображения в NASA API и вставляем в текст
    result = article
    for pos in positions:
        query = pos.get("search_query", "").strip()
        heading = pos.get("after_heading", "").strip()
        if not query or not heading:
            continue
        # Сначала ищем в NASA, если не нашли — в Unsplash
        image = search_nasa_image(query)
        if not image:
            logging.info(f"image_finder: NASA не нашёл '{query}', пробуем Unsplash...")
            image = search_unsplash_image(query)

        if image:
            # Загружаем в медиатеку WordPress, получаем постоянный URL
            wp_url = upload_image_from_url(image["url"], image["title"])
            final_url = wp_url if wp_url else image["url"]
            result = insert_image_after_heading(result, heading, final_url, image["title"])
            logging.info(f"image_finder: вставлено '{image['title']}' после '{heading}' → {final_url}")
        else:
            logging.warning(f"image_finder: не найдено изображение для '{query}' ни в NASA, ни в Unsplash")

    return result
