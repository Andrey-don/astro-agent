import os
import re
import markdown as md_converter
from datetime import datetime
from bot.agents import researcher, writer, editor, seo, image_finder, topic_generator
from bot.utils.file_loader import read_project_file, save_article, get_used_topics, mark_topic_used, append_topics_to_plan
from bot.utils import wp_posts


def generate_article(topic: str, article_type: str = "научпоп") -> dict:
    """Полный цикл: Ресёрчер → Писатель → Редактор → SEO → Сохранение в файл"""

    print(f"[1/6] Ресёрчер собирает материал по теме: {topic}")
    research = researcher.run(topic)

    print(f"[2/6] Писатель пишет статью ({article_type})...")
    draft = writer.run(topic, article_type, research)

    print(f"[3/6] Редактор правит...")
    edited = editor.run(draft)

    # Получаем список рубрик из WordPress один раз
    wp_categories = [c["name"] for c in wp_posts.get_categories() if c["name"] != "Без рубрики"]

    print(f"[4/6] Редактор применяет SEO-замечания...")
    seo_draft = seo.run(edited, wp_categories or None)
    final = editor.run_seo_revision(edited, seo_draft)

    print(f"[5/6] Подбираем изображения из NASA...")
    final = image_finder.run(final)

    print(f"[6/6] SEO-анализ финальной статьи...")
    seo_data = seo.run(final, wp_categories or None)

    # Конвертируем Markdown → HTML для вставки в WordPress
    html_article = md_converter.markdown(final, extensions=["extra"])

    # Убираем H1 из тела статьи — он уже передаётся как поле Title записи
    html_article = re.sub(r"<h1[^>]*>.*?</h1>", "", html_article, count=1, flags=re.IGNORECASE | re.DOTALL)
    html_article = re.sub(r"<p>\s*</p>", "", html_article)

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
    mark_topic_used(topic)
    print(f"Статья сохранена: {filepath}")

    # Определяем рубрику: парсим название из SEO, ищем в WordPress
    category_name = _parse_category(seo_data)
    category_id = _find_category_id(category_name) if category_name else None

    return {
        "topic": topic,
        "type": article_type,
        "article": html_article,
        "seo": seo_data,
        "title": (_parse_title(seo_data) or topic).capitalize(),
        "tags": _parse_tags(seo_data),
        "featured_image": featured_image_url,
        "meta_description": _parse_meta_description(seo_data),
        "focus_keyword": _parse_focus_keyword(seo_data),
        "slug": _parse_slug(seo_data),
        "category_id": category_id,
        "category_name": category_name,
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
    """Извлекает URL изображения записи из SEO-данных агента."""
    match = re.search(r"\*{0,2}Изображение записи\*{0,2}[^\n]*\n?\s*(https?://\S+)", seo_data)
    return match.group(1).strip() if match else ""


def _parse_meta_description(seo_data: str) -> str:
    """Извлекает meta description из SEO-данных агента."""
    match = re.search(r"\*{0,2}Meta Description\*{0,2}[^\n]*\n?\s*([^\n#*]{20,})", seo_data)
    if not match:
        return ""
    desc = match.group(1).strip()
    return re.sub(r"^[—\-]\s*", "", desc)


def _parse_focus_keyword(seo_data: str) -> str:
    """Извлекает фокусное слово из SEO-данных агента (одно слово)."""
    # Новый формат: отдельное поле "Фокусное слово"
    match = re.search(r"\*{0,2}Фокусное слово\*{0,2}[^\n]*\n?\s*([^\n#*]{2,30})", seo_data)
    if match:
        kw = match.group(1).strip()
        kw = re.sub(r"^[—\-]\s*", "", kw)
        # Берём только первое слово
        return kw.split()[0] if kw else ""
    # Фолбэк: первое слово из списка ключевых слов
    match = re.search(r"\*{0,2}Ключевые слова\*{0,2}[^\n]*\n\s*[-*]?\s*([^\n#*]{3,})", seo_data)
    if not match:
        return ""
    kw = match.group(1).strip()
    kw = re.sub(r"^[—\-]\s*", "", kw)
    return kw.split()[0] if kw else ""


def _parse_slug(seo_data: str) -> str:
    """Извлекает slug из SEO-данных агента."""
    match = re.search(r"\*{0,2}Slug[^\n*]*\*{0,2}[^\n]*\n?\s*[`\"]?([a-z0-9][a-z0-9\-]{3,})[`\"]?", seo_data)
    return match.group(1).strip() if match else ""


def _parse_category(seo_data: str) -> str:
    """Извлекает рубрику из SEO-данных агента."""
    match = re.search(r"\*{0,2}Рубрика\*{0,2}[^\n]*\n?\s*\*{0,2}([^\n#*\(]{3,})\*{0,2}", seo_data)
    if not match:
        return ""
    cat = match.group(1).strip()
    return re.sub(r"^[—\-]\s*", "", cat)


def _find_category_id(category_name: str) -> int | None:
    """Ищет ID рубрики по названию (нечёткое совпадение через difflib)."""
    from difflib import SequenceMatcher
    categories = wp_posts.get_categories()
    if not categories:
        return None
    name_lower = category_name.lower().strip()
    # Точное совпадение
    for cat in categories:
        if cat["name"].lower().strip() == name_lower:
            return cat["id"]
    # Fuzzy matching — берём рубрику с наибольшим сходством
    best_id, best_score = None, 0.0
    for cat in categories:
        cat_lower = cat["name"].lower().strip()
        score = SequenceMatcher(None, name_lower, cat_lower).ratio()
        if score > best_score:
            best_score, best_id = score, cat["id"]
    if best_score >= 0.6:
        logging.info(f"orchestrator: рубрика '{category_name}' → fuzzy match (score={best_score:.2f})")
        return best_id
    return None


def get_schedule_topics(start_date: str, days: int = 7) -> list[dict]:
    """
    Возвращает список тем начиная с start_date (формат "DD.MM" или "DD.MM.YYYY").
    Публикация каждый день в 10:00, без пропусков.
    Темы чередуются по разделам контент-плана.
    """
    from datetime import datetime, timedelta

    # Парсим дату старта
    for fmt in ("%d.%m.%Y", "%d.%m"):
        try:
            start = datetime.strptime(start_date.strip(), fmt)
            if fmt == "%d.%m":
                start = start.replace(year=datetime.now().year)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Не могу распознать дату: {start_date}. Напиши в формате ДД.ММ или ДД.ММ.ГГГГ")

    plan_text = read_project_file("content-plan.md")

    # Парсим темы по разделам
    sections = {}
    current_section = None
    for line in plan_text.splitlines():
        if line.startswith("### "):
            current_section = line[4:].strip()
            sections[current_section] = []
        elif current_section and re.match(r"^\d+\.\s+", line):
            topic = re.sub(r"^\d+\.\s+", "", line).strip()
            sections[current_section].append(topic)

    section_names = [s for s, topics in sections.items() if topics]
    used = get_used_topics()
    type_cycle = ["новостная", "научпоп", "смешанная", "научпоп", "новостная", "научпоп"]

    # Получаем заголовки уже существующих постов в WordPress
    from difflib import SequenceMatcher
    wp_titles = wp_posts.get_post_titles()

    _STOP_WORDS = {"и", "в", "на", "что", "как", "это", "она", "он", "а", "но", "то",
                   "из", "по", "за", "или", "же", "ни", "не", "от", "до", "при", "со",
                   "об", "для", "так", "уже", "ли", "бы", "со", "об", "его", "её", "их"}

    def _key_words(text: str) -> set:
        """Возвращает набор корней значимых слов (первые 5 символов, длина ≥ 4)."""
        words = re.sub(r"[^\w\s]", " ", text.lower()).split()
        return {w[:5] for w in words if len(w) >= 4 and w not in _STOP_WORDS}

    def _is_wp_duplicate(topic: str) -> bool:
        """Проверяет дубликат: по ключевым словам (2+ совпадений) ИЛИ по строке (≥0.55)."""
        t_lower = topic.lower()
        t_words = _key_words(topic)
        for title in wp_titles:
            # Проверка по ключевым словам
            if t_words and len(t_words & _key_words(title)) >= 2:
                return True
            # Проверка по строковому сходству
            if SequenceMatcher(None, t_lower, title).ratio() >= 0.55:
                return True
        return False

    # Фильтруем использованные темы и дубликаты из WordPress
    available = {s: [t for t in topics if t.lower() not in used and not _is_wp_duplicate(t)]
                 for s, topics in sections.items() if topics}

    # Если свободных тем меньше нужного — генерируем новые
    total_available = sum(len(v) for v in available.values())
    if total_available < days:
        print(f"[topic_generator] Осталось {total_available} тем, нужно {days}. Генерирую новые...")
        all_used = list(used) + [t for sec in sections.values() for t in sec]
        new_topics_raw = topic_generator.run(used_topics=all_used, count=14)
        new_topics = _parse_generated_topics(new_topics_raw)
        if new_topics:
            append_topics_to_plan(new_topics)
            # Добавляем в available
            for section, topic in new_topics:
                if topic.lower() not in used and not _is_wp_duplicate(topic):
                    available.setdefault(section, []).append(topic)
                    if section not in section_names:
                        section_names.append(section)

    schedule = []
    sec_idx = 0
    day_offset = 0
    while len(schedule) < days:
        section = section_names[sec_idx % len(section_names)]
        topics_left = available.get(section, [])
        if topics_left:
            topic = topics_left.pop(0)
            day = start.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
            schedule.append({
                "topic": topic,
                "article_type": type_cycle[day_offset % len(type_cycle)],
                "publish_date": day.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            day_offset += 1
        sec_idx += 1
        # Защита от бесконечного цикла если темы закончились
        if sec_idx > len(section_names) * 100:
            break

    return schedule


def _parse_generated_topics(raw: str) -> list[tuple[str, str]]:
    """Парсит ответ агента topic_generator в список (раздел, тема)."""
    result = []
    current_section = None
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("Раздел:"):
            current_section = line[7:].strip()
        elif line.startswith("Тема:") and current_section:
            topic = line[5:].strip()
            if topic:
                result.append((current_section, topic))
    return result


def get_plan() -> str:
    """Возвращает контент-план с отметками ✅/⬜ для каждой темы."""
    plan_text = read_project_file("content-plan.md")
    used = get_used_topics()
    wp_titles = wp_posts.get_post_titles()

    def _is_used(topic: str) -> bool:
        if topic.lower() in used:
            return True
        topic_words = set(re.sub(r"[^\w\s]", " ", topic.lower()).split())
        for title in wp_titles:
            title_words = set(re.sub(r"[^\w\s]", " ", title.lower()).split())
            if len(topic_words & title_words) >= 3:
                return True
        return False

    lines = []
    total = done = 0
    for line in plan_text.splitlines():
        if re.match(r"^\d+\.\s+", line):
            topic = re.sub(r"^\d+\.\s+", "", line).strip()
            total += 1
            if _is_used(topic):
                done += 1
                lines.append(f"✅ {line}")
            else:
                lines.append(f"⬜ {line}")
        else:
            lines.append(line)

    result = "\n".join(lines)
    if total > 0:
        result += f"\n\n📊 Написано: {done}/{total} тем ({total - done} осталось)"
    return result
