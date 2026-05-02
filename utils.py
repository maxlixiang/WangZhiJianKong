import json
import os
from hashlib import sha1

from config import ALLOWED_USERS


def load_json(file_path, default_value):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_value


def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def state_token(state_id):
    return sha1(state_id.encode("utf-8")).hexdigest()[:16]


def restricted(func):
    """权限控制装饰器。"""

    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            print(f"未授权的访问尝试：{user_id}")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped
