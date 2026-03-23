from bot.utils.openrouter import call_agent
from bot.utils.file_loader import read_project_file

MODEL = "anthropic/claude-haiku-4-5"
TEMPERATURE = 0.2

SYSTEM_PROMPT = """Ты — SEO-специалист для контентного сайта об астрономии astro-obzor.ru.

Анализируешь статью и выдаёшь строго по пунктам:

1. **Заголовок** — финальный H1 для публикации (до 60 символов, с ключевым словом)
2. **Рубрика** — выбери одну из списка существующих рубрик сайта. Если ни одна не подходит — предложи новую
3. **Подрубрика** — уточняющая категория внутри рубрики (1-3 слова, можно новую)
4. **Метки** — 5-8 тегов через запятую (конкретные термины из статьи, для навигации по сайту)
5. **Изображение записи** — URL первого изображения из статьи (строка вида https://...), которое станет главным фото поста. Если изображений нет — напиши «нет»
6. **Meta Description** — 150-160 символов, привлекательный
7. **Ключевые слова** — 5-7 слов/фраз из текста
8. **Slug** (URL) — латиницей, через дефис, без стоп-слов
9. **Замечания** — что исправить для лучшего SEO"""


def run(article: str, categories: list[str] | None = None) -> str:
    brief = read_project_file("brief.md")
    if categories:
        cat_list = "\n".join(f"- {c}" for c in categories)
        categories_block = f"РУБРИКИ В WORDPRESS (выбери строго одну из этого списка, скопируй название ТОЧНО как написано):\n{cat_list}"
    else:
        categories_block = f"РУБРИКИ САЙТА (из brief):\n{brief}"
    context = f"""
СТАТЬЯ:
{article}

{categories_block}

Выдай SEO-данные и выбери рубрику для публикации в WordPress.
"""
    return call_agent(SYSTEM_PROMPT, context, MODEL, TEMPERATURE)
