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


def get_or_create_tag(name: str) -> int | None:
    """Ищет тег по имени, создаёт если нет. Возвращает ID."""
    if not WP_URL:
        return None
    try:
        resp = requests.get(
            f"{WP_URL}/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 5},
            auth=_auth(), timeout=10,
        )
        resp.raise_for_status()
        for tag in resp.json():
            if tag["name"].lower() == name.lower():
                return tag["id"]
        # Не нашли — создаём
        resp = requests.post(
            f"{WP_URL}/wp-json/wp/v2/tags",
            auth=_auth(), json={"name": name}, timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        logging.warning(f"wp_posts: ошибка с тегом '{name}': {e}")
        return None


def get_media_id_by_url(image_url: str) -> int | None:
    """Ищет ID медиафайла в WordPress по URL изображения."""
    if not WP_URL or not image_url:
        return None
    # Берём имя файла из URL для поиска
    filename = image_url.rstrip("/").split("/")[-1].rsplit(".", 1)[0]
    try:
        resp = requests.get(
            f"{WP_URL}/wp-json/wp/v2/media",
            params={"search": filename, "per_page": 5},
            auth=_auth(), timeout=10,
        )
        resp.raise_for_status()
        for item in resp.json():
            if item.get("source_url") == image_url:
                return item["id"]
    except Exception as e:
        logging.warning(f"wp_posts: не удалось найти медиафайл по URL: {e}")
    return None


def update_media_meta(media_id: int, alt_text: str = "", description: str = "") -> bool:
    """Обновляет alt text и описание медиафайла в WordPress."""
    if not WP_URL or not media_id:
        return False
    payload = {}
    if alt_text:
        payload["alt_text"] = alt_text
    if description:
        payload["description"] = {"raw": description}
    if not payload:
        return False
    try:
        resp = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media/{media_id}",
            auth=_auth(),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        logging.info(f"wp_posts: обновлено мета медиафайла {media_id} (alt: {alt_text[:30]})")
        return True
    except Exception as e:
        logging.warning(f"wp_posts: не удалось обновить мета медиафайла {media_id}: {e}")
        return False


def _update_body_images_alt(html: str, exclude_url: str = "") -> None:
    """Обновляет alt text для изображений из тела статьи в медиатеке WordPress."""
    if not WP_URL:
        return
    import re
    for tag in re.findall(r"<img[^>]+>", html, re.IGNORECASE):
        src_m = re.search(r'src=["\']([^"\']+)["\']', tag)
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', tag)
        if not src_m:
            continue
        src = src_m.group(1)
        alt = alt_m.group(1).strip() if alt_m else ""
        if src == exclude_url or not alt or WP_URL not in src:
            continue
        media_id = get_media_id_by_url(src)
        if media_id:
            update_media_meta(media_id, alt_text=alt, description=alt)


def create_draft(
    title: str,
    html_content: str,
    category_id: int | None = None,
    tag_names: list[str] | None = None,
    featured_image_url: str = "",
    meta_description: str = "",
    focus_keyword: str = "",
    slug: str = "",
) -> dict | None:
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
    if slug:
        payload["slug"] = slug
    if category_id:
        payload["categories"] = [category_id]

    # Yoast SEO поля
    yoast_meta = {}
    if meta_description:
        yoast_meta["_yoast_wpseo_metadesc"] = meta_description
    if focus_keyword:
        yoast_meta["_yoast_wpseo_focuskw"] = focus_keyword
    if title:
        yoast_meta["_yoast_wpseo_title"] = title
    if yoast_meta:
        payload["meta"] = yoast_meta

    # Создаём/находим теги и добавляем их ID
    if tag_names:
        tag_ids = [tid for name in tag_names if (tid := get_or_create_tag(name))]
        if tag_ids:
            payload["tags"] = tag_ids

    # Изображение записи — ищем ID по URL и обновляем alt text
    if featured_image_url:
        media_id = get_media_id_by_url(featured_image_url)
        if media_id:
            payload["featured_media"] = media_id
            update_media_meta(media_id, alt_text=title, description=meta_description)
            logging.info(f"wp_posts: изображение записи → ID {media_id}")

    # Обновляем alt text для изображений в теле статьи
    _update_body_images_alt(html_content, exclude_url=featured_image_url)

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
