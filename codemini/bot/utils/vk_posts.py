import logging
import requests


VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"


def post_to_vk(
    title: str,
    excerpt: str,
    url: str,
    tags: list[str],
    token: str,
    group_id: str,
) -> bool:
    """
    Публикует пост в группу ВКонтакте.
    group_id — числовой ID группы (без минуса, только цифры).
    """
    hashtags = " ".join(f"#{t.replace(' ', '_')}" for t in tags[:5]) if tags else ""
    text = f"{title}\n\n{excerpt}\n\n{url}"
    if hashtags:
        text += f"\n\n{hashtags}"

    try:
        resp = requests.post(
            f"{VK_API}/wall.post",
            params={
                "access_token": token,
                "v": VK_VERSION,
                "owner_id": f"-{group_id}",
                "from_group": 1,
                "message": text,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            logging.warning(f"codemini vk_posts: ошибка VK API — {data['error']}")
            return False
        post_id = data.get("response", {}).get("post_id")
        logging.info(f"codemini vk_posts: пост опубликован, ID={post_id}")
        return True
    except Exception as e:
        logging.warning(f"codemini vk_posts: исключение — {e}")
        return False
