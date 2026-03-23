import os
import re
import markdown as md_converter
from datetime import datetime
from bot.agents import researcher, writer, editor, seo, image_finder
from bot.utils.file_loader import read_project_file, save_article


def generate_article(topic: str, article_type: str = "научпоп") -> dict:
    """Полный цикл: Ресёрчер → Писатель → Редактор → SEO → Сохранение в файл"""

    print(f"[1/6] Ресёрчер собирает материал по теме: {topic}")
    research = researcher.run(topic)

    print(f"[2/6] Писатель пишет статью ({article_type})...")
    draft = writer.run(topic, article_type, research)

    print(f"[3/6] Редактор правит...")
    edited = editor.run(draft)

    print(f"[4/6] Редактор применяет SEO-замечания...")
    seo_draft = seo.run(edited)
    final = editor.run_seo_revision(edited, seo_draft)

    print(f"[5/6] Подбираем изображения из NASA...")
    final = image_finder.run(final)

    print(f"[6/6] SEO-анализ финальной статьи...")
    seo_data = seo.run(final)

    # Конвертируем Markdown → HTML для вставки в WordPress
    html_article = md_converter.markdown(final, extensions=["extra"])

    # Убираем featured image из тела статьи — оно уже будет как изображение записи
    featured_image_url = _parse_featured_image(seo_data)
    if featured_image_url:
        # Удаляем <img> с этим src (с любыми атрибутами вокруг)
        html_article = re.sub(
            r'<img[^>]*src=["\']' + re.escape(featured_image_url) + r'["\'][^>]*/?>',
            "",
            html_article,
        )
        # Убираем пустой <p></p> если он остался после удаления картинки
        html_article = re.sub(r"<p>\s*</p>", "", html_article)

    # Сохраняем .html файл (для вставки в WordPress → вкладка Код)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    # Убираем эмодзи и спецсимволы, оставляем буквы (включая кириллицу), цифры, пробелы, дефисы
    safe_topic = "".join(c for c in topic if c.isalnum() or c in " -_")
    safe_topic = safe_topic.strip().replace(" ", "-")[:40] or "article"
    filename = f"{timestamp}_{safe_topic}.html"

    date_str = datetime.now().strftime("%d.%m.%Y")
    full_content = f"""<!--
==============================================
  ПУБЛИКАЦИЯ В WORDPRESS
==============================================
  Тип статьи : {article_type}
  Дата       : {date_str}
----------------------------------------------
  SEO-ДАННЫЕ:
{seo_data}
==============================================
  КОД СТАТЬИ (вставить во вкладку "Код"):
==============================================
-->

{html_article}"""
    filepath = save_article(filename, full_content)
    print(f"Статья сохранена: {filepath}")

    return {
        "topic": topic,
        "type": article_type,
        "article": html_article,
        "seo": seo_data,
        "title": (_parse_title(seo_data) or topic).capitalize(),
        "tags": _parse_tags(seo_data),
        "featured_image": _parse_featured_image(seo_data),
        "file": filepath,
    }


def _parse_title(seo_data: str) -> str:
    """Извлекает SEO-заголовок из данных агента.
    Поддерживает формат '**Заголовок** — Текст' и '**Заголовок (H1)**\nТекст'.
    """
    match = re.search(r"\*{0,2}Заголовок[^\n*]*\*{0,2}[^\n]*\n?\s*([^\n#*]{10,})", seo_data)
    if not match:
        return ""
    title = match.group(1).strip()
    # Убираем возможный префикс "— " или "- "
    title = re.sub(r"^[—\-]\s*", "", title)
    return title


def _parse_tags(seo_data: str) -> list[str]:
    """Извлекает список меток из SEO-данных агента.
    Поддерживает формат '**Метки** — тег1, тег2' и '**Метки**\nтег1, тег2'.
    """
    # Ищем строку с "Метки" и берём всё после неё (на той же или следующей строке)
    match = re.search(r"\*{0,2}Метки\*{0,2}[^\n]*\n?\s*([^\n#*]+)", seo_data)
    if not match:
        return []
    raw = match.group(1).strip()
    # Убираем возможные маркеры "— " в начале
    raw = re.sub(r"^[—-]\s*", "", raw)
    return [t.strip() for t in raw.split(",") if t.strip()]


def _parse_featured_image(seo_data: str) -> str:
    """Извлекает URL изображения записи из SEO-данных агента.
    Поддерживает формат '**Изображение записи** — https://...' и многострочный.
    """
    match = re.search(r"\*{0,2}Изображение записи\*{0,2}[^\n]*\n?\s*(https?://\S+)", seo_data)
    return match.group(1).strip() if match else ""


def get_plan() -> str:
    return read_project_file("content-plan.md")
