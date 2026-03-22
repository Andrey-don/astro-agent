import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_project_file(filename: str) -> str:
    path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_article(filename: str, content: str) -> str:
    articles_path = os.path.join(PROJECT_ROOT, "articles")
    os.makedirs(articles_path, exist_ok=True)
    filepath = os.path.join(articles_path, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath
