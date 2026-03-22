from bot.utils.openrouter import call_agent
from bot.utils.file_loader import read_project_file

MODEL = "anthropic/claude-sonnet-4-6"
TEMPERATURE = 0.8

SYSTEM_PROMPT = """Ты — автор статей для сайта об астрономии и космосе astro-obzor.ru.

Пишешь для русскоязычных любителей космоса — интересно, доступно, без занудства.

Жёсткие правила:
- Начинай с цепляющего факта или вопроса — не с определения
- Объясняй через сравнения и масштаб (миллионы км → понятные единицы)
- Короткие абзацы — максимум 3-4 предложения
- Научные термины объясняй сразу в тексте
- Заканчивай интригой или сильным выводом
- SEO: ключевое слово в H1, естественно в тексте

Структура: H1 → лид → H2-блоки → вывод"""


def run(topic: str, article_type: str, research: str) -> str:
    tone = read_project_file("tone-of-voice.md")
    context = f"""
ТИП СТАТЬИ: {article_type}
ТЕМА: {topic}

ГОЛОС И СТИЛЬ:
{tone}

МАТЕРИАЛ ОТ РЕСЁРЧЕРА:
{research}

Напиши полную статью с заголовками H1 и H2. Используй markdown-разметку.
"""
    return call_agent(SYSTEM_PROMPT, context, MODEL, TEMPERATURE)
