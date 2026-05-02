import logging

import httpx
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ALLOWED_USERS, STATE_FILE, TASKS_FILE
from utils import load_json, save_json, state_token

# 加载数据
monitor_tasks = load_json(TASKS_FILE, [])
stock_state = load_json(STATE_FILE, {})


def make_state_id(site, product_name):
    return f"{site} | {product_name}"


def get_monitored_products():
    products = []
    for task in monitor_tasks:
        for product_name in task["targets"]:
            products.append(
                {
                    "site": task["site_name"],
                    "url": task["url"],
                    "name": product_name,
                    "state_id": make_state_id(task["site_name"], product_name),
                }
            )
    return products


async def check_all_sites(context, send_alerts=True):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    summary = {
        "total": 0,
        "available": 0,
        "alerted": 0,
        "errors": [],
        "statuses": [],
    }
    has_changes = False

    for task in monitor_tasks:
        site, url, targets = task["site_name"], task["url"], task["targets"]
        seen_targets = set()

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

                seen_targets.add(product_name)
                summary["total"] += 1

                state_id = make_state_id(site, product_name)
                footer = item.find("div", class_="card-footer")
                footer_text = footer.get_text(strip=True) if footer else ""
                is_available = "售罄" not in footer_text
                acknowledged = stock_state.get(state_id, {}).get("acknowledged", False)

                if is_available:
                    summary["available"] += 1
                    new_state = {"in_stock": True, "acknowledged": acknowledged}
                    if stock_state.get(state_id) != new_state:
                        stock_state[state_id] = new_state
                        has_changes = True

                    if send_alerts and not acknowledged:
                        stock_state[state_id]["acknowledged"] = False
                        has_changes = True
                        summary["alerted"] += 1
                        await send_stock_alert(context, site, product_name, url)
                else:
                    new_state = {"in_stock": False, "acknowledged": False}
                    if stock_state.get(state_id) != new_state:
                        stock_state[state_id] = new_state
                        has_changes = True

                summary["statuses"].append(
                    {
                        "site": site,
                        "name": product_name,
                        "url": url,
                        "in_stock": is_available,
                        "acknowledged": stock_state[state_id]["acknowledged"],
                    }
                )

            for product_name in targets:
                if product_name in seen_targets:
                    continue

                state_id = make_state_id(site, product_name)
                summary["statuses"].append(
                    {
                        "site": site,
                        "name": product_name,
                        "url": url,
                        "in_stock": None,
                        "acknowledged": stock_state.get(state_id, {}).get(
                            "acknowledged",
                            False,
                        ),
                    }
                )
        except Exception as exc:
            logging.error("站点 %s 检查失败：%s", site, exc)
            summary["errors"].append(f"{site}: {exc}")

    if has_changes:
        save_json(STATE_FILE, stock_state)

    return summary


def reset_acknowledged():
    changed = 0
    for state in stock_state.values():
        if state.get("acknowledged", False):
            state["acknowledged"] = False
            changed += 1

    if changed:
        save_json(STATE_FILE, stock_state)

    return changed


async def send_stock_alert(context, site, name, url):
    state_id = make_state_id(site, name)
    keyboard = [
        [
            InlineKeyboardButton(
                "停止提醒",
                callback_data=f"ack|{state_token(state_id)}",
            )
        ]
    ]
    text = f"补货通知：{site}\n\n产品：{name}\n\n立即前往购买：{url}"

    for uid in ALLOWED_USERS:
        await context.bot.send_message(
            chat_id=uid,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
