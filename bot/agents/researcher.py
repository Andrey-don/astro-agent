from bot.utils.openrouter import call_agent
from bot.utils.file_loader import read_project_file

MODEL = "anthropic/claude-sonnet-4-6"
TEMPERATURE = 0.4

SYSTEM_PROMPT = """Ты — ресёрчер для сайта об астрономии и космосе.

По заданной теме собираешь:
- Ключевые факты и цифры
- Интересные детали и малоизвестные подробности
- Контекст: история открытия, текущее состояние исследований
- Сравнения и аналогии для объяснения масштаба
- Источники: NASA, ESA, научные журналы

Аудитория — любители космоса без профильного образования.
Пиши только то, что реально поможет написать интересную статью."""


def run(topic: str) -> str:
    brief = read_project_file("brief.md")
    context = f"""
ТЕМА: {topic}

САЙТ И АУДИТОРИЯ:
{brief}

Собери материал для статьи: факты, цифры, интересные детали, контекст.
"""
    return call_agent(SYSTEM_PROMPT, context, MODEL, TEMPERATURE)
