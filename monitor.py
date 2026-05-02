import logging

import httpx
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ALLOWED_USERS, STATE_FILE, TASKS_FILE
from utils import load_json, save_json, state_token

# 加载数据
monitor_tasks = load_json(TASKS_FILE, [])
stock_state = load_json(STATE_FILE, {})


async def check_all_sites(context):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    found_count, total_products = 0, 0
    has_changes = False

    for task in monitor_tasks:
        site, url, targets = task["site_name"], task["url"], task["targets"]
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.find_all("div", class_="cartitem")

            for item in items:
                body = item.find("div", class_="card-body")
                name_tag = body.find(True) if body else None
                if not name_tag:
                    continue

                product_name = name_tag.get_text(strip=True)
                if product_name not in targets:
                    continue

                total_products += 1
                state_id = f"{site} | {product_name}"
                footer = item.find("div", class_="card-footer")
                footer_text = footer.get_text(strip=True) if footer else ""
                is_available = "售罄" not in footer_text

                if is_available:
                    if not stock_state.get(state_id, {}).get("acknowledged", False):
                        stock_state[state_id] = {
                            "in_stock": True,
                            "acknowledged": False,
                        }
                        has_changes = True
                        found_count += 1
                        await send_stock_alert(context, site, product_name, url)
                elif stock_state.get(state_id, {}).get("acknowledged", False):
                    stock_state[state_id] = {
                        "in_stock": False,
                        "acknowledged": False,
                    }
                    has_changes = True
        except Exception as exc:
            logging.error("站点 %s 检查失败：%s", site, exc)

    if has_changes:
        save_json(STATE_FILE, stock_state)

    return found_count, total_products


async def send_stock_alert(context, site, name, url):
    state_id = f"{site} | {name}"
    keyboard = [
        [
            InlineKeyboardButton(
                "停止提醒",
                callback_data=f"ack|{state_token(state_id)}",
            )
        ]
    ]
    text = (
        f"*补货通知：{site}*\n\n"
        f"产品：`{name}`\n\n"
        f"[立即前往购买]({url})"
    )

    for uid in ALLOWED_USERS:
        await context.bot.send_message(
            chat_id=uid,
            text=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
