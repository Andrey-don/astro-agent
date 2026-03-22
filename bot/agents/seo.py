from bot.utils.openrouter import call_agent

MODEL = "anthropic/claude-haiku-4-5"
TEMPERATURE = 0.2

SYSTEM_PROMPT = """Ты — SEO-специалист для контентного сайта об астрономии.

Анализируешь статью и выдаёшь:
1. **SEO-заголовок** (Title) — до 60 символов, с ключевым словом
2. **Meta Description** — 150-160 символов, привлекательный
3. **Ключевые слова** — 5-7 слов/фраз из текста
4. **Slug** (URL) — латиницей, через дефис, без стоп-слов
5. **Замечания** — что исправить для лучшего SEO

Формат ответа строго по пунктам."""


def run(article: str) -> str:
    context = f"""
СТАТЬЯ:
{article[:3000]}

Выдай SEO-данные для публикации в WordPress.
"""
    return call_agent(SYSTEM_PROMPT, context, MODEL, TEMPERATURE)
