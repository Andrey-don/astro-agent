import os
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

    # Сохраняем .html файл (для вставки в WordPress → вкладка Код)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_topic = topic[:40].replace(" ", "-").replace("/", "-")
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
        "file": filepath,
    }


def get_plan() -> str:
    return read_project_file("content-plan.md")
