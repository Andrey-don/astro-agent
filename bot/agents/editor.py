from bot.utils.openrouter import call_agent
from bot.utils.file_loader import read_project_file

MODEL = "anthropic/claude-sonnet-4-6"
TEMPERATURE = 0.4

SYSTEM_PROMPT = """Ты — редактор сайта об астрономии и космосе.

Получаешь черновик статьи и улучшаешь его:
- Убираешь воду и повторы
- Режешь длинные предложения
- Проверяешь: цепляет ли первый абзац
- Проверяешь: понятны ли объяснения для неспециалиста
- Проверяешь SEO: есть ли H1, есть ли H2-подзаголовки
- Не меняешь факты и структуру — только улучшаешь форму

Верни только отредактированный текст, без комментариев."""


def run(draft: str) -> str:
    context = f"""
ЧЕРНОВИК СТАТЬИ:
{draft}

Отредактируй. Верни только готовый текст.
"""
    return call_agent(SYSTEM_PROMPT, context, MODEL, TEMPERATURE)
