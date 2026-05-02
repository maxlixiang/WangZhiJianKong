import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
# 将字符串 ID 列表转换为整数列表。
ALLOWED_USERS = [int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x]

CHECK_INTERVAL = 1800  # 30 分钟
STATE_FILE = "stock_state.json"
TASKS_FILE = "tasks.json"
