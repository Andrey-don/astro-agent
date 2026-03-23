import os
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")


def _auth():
    return (WP_USERNAME, WP_APP_PASSWORD)


def get_categories() -> list[dict]:
    """Возвращает список категорий WordPress: [{id, name}, ...]"""
    if not WP_URL:
        return []
    try:
        resp = requests.get(
            f"{WP_URL}/wp-json/wp/v2/categories",
            params={"per_page": 100, "hide_empty": False},
            auth=_auth(),
            timeout=10,
        )
        resp.raise_for_status()
        return [{"id": c["id"], "name": c["name"]} for c in resp.json()]
    except Exception as e:
        logging.warning(f"wp_posts: не удалось получить категории: {e}")
        return []


def create_category(name: str) -> int | None:
    """Создаёт новую категорию и возвращает её ID."""
    if not WP_URL:
        return None
    try:
        resp = requests.post(
            f"{WP_URL}/wp-json/wp/v2/categories",
            auth=_auth(),
            json={"name": name},
            timeout=10,
        )
        resp.raise_for_status()
        cat_id = resp.json().get("id")
        logging.info(f"wp_posts: создана категория '{name}' → ID {cat_id}")
        return cat_id
    except Exception as e:
        logging.warning(f"wp_posts: не удалось создать категорию '{name}': {e}")
        return None


def create_draft(title: str, html_content: str, category_id: int | None = None) -> dict | None:
    """
    Создаёт черновик записи в WordPress.
    Возвращает {id, link} или None при ошибке.
    """
    if not WP_URL:
        return None
    payload = {
        "title": title,
        "content": html_content,
        "status": "draft",
    }
    if category_id:
        payload["categories"] = [category_id]
    try:
        resp = requests.post(
            f"{WP_URL}/wp-json/wp/v2/posts",
            auth=_auth(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        result = {"id": data["id"], "link": data.get("link", "")}
        logging.info(f"wp_posts: черновик создан → ID {result['id']}, {result['link']}")
        return result
    except Exception as e:
        logging.warning(f"wp_posts: не удалось создать черновик: {e}")
        return None
