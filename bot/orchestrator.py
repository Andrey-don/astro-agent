import os
from datetime import datetime
from bot.agents import researcher, writer, editor, seo
from bot.utils.file_loader import read_project_file, save_article


def generate_article(topic: str, article_type: str = "научпоп") -> dict:
    """Полный цикл: Ресёрчер → Писатель → Редактор → SEO → Сохранение в файл"""

    print(f"[1/4] Ресёрчер собирает материал по теме: {topic}")
    research = researcher.run(topic)

    print(f"[2/4] Писатель пишет статью ({article_type})...")
    draft = writer.run(topic, article_type, research)

    print(f"[3/4] Редактор правит...")
    edited = editor.run(draft)

    print(f"[4/4] SEO-анализ...")
    seo_data = seo.run(edited)

    # Сохраняем в файл
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_topic = topic[:40].replace(" ", "-").replace("/", "-")
    filename = f"{timestamp}_{safe_topic}.md"

    full_content = f"""# {topic}

**Тип:** {article_type}
**Дата:** {datetime.now().strftime("%d.%m.%Y")}

---

{edited}

---

## SEO-данные для WordPress

{seo_data}
"""
    filepath = save_article(filename, full_content)
    print(f"Статья сохранена: {filepath}")

    return {
        "topic": topic,
        "type": article_type,
        "article": edited,
        "seo": seo_data,
        "file": filepath,
    }


def get_plan() -> str:
    return read_project_file("content-plan.md")
