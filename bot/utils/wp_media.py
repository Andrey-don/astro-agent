import os
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")


def upload_image_from_url(image_url: str, title: str = "") -> str | None:
    """
    Скачивает изображение по URL и загружает в медиатеку WordPress.
    Возвращает постоянный URL из WordPress или None при ошибке.
    """
    if not WP_URL or not WP_USERNAME or not WP_APP_PASSWORD:
        logging.warning("wp_media: WordPress credentials не заданы в .env")
        return None

    # Скачиваем изображение с источника
    try:
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
        image_data = resp.content
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    except Exception as e:
        logging.warning(f"wp_media: не удалось скачать изображение {image_url}: {e}")
        return None

    # Определяем расширение файла
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
    ext = ext_map.get(content_type, "jpg")
    safe_title = title[:50].replace(" ", "-").replace("/", "-") if title else "nasa-image"
    filename = f"{safe_title}.{ext}"

    # Загружаем в WordPress через REST API
    try:
        response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media",
            auth=(WP_USERNAME, WP_APP_PASSWORD),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type,
            },
            data=image_data,
            timeout=30,
        )
        response.raise_for_status()
        wp_url = response.json().get("source_url")
        logging.info(f"wp_media: загружено в медиатеку → {wp_url}")
        return wp_url
    except Exception as e:
        logging.warning(f"wp_media: ошибка загрузки в WordPress: {e}")
        return None
