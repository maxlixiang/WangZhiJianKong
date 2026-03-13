import httpx
import logging
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import TASKS_FILE, STATE_FILE, ALLOWED_USERS
from utils import load_json, save_json

# 加载数据
monitor_tasks = load_json(TASKS_FILE, [])
stock_state = load_json(STATE_FILE, {})

async def check_all_sites(context):
    global stock_state
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    found_count, total_products = 0, 0
    has_changes = False
    
    for task in monitor_tasks:
        site, url, targets = task["site_name"], task["url"], task["targets"]
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.find_all('div', class_='cartitem')
            
            for item in items:
                name_tag = item.find('div', class_='card-body').find(True)
                if not name_tag: continue
                p_name = name_tag.get_text(strip=True)
                
                if p_name in targets:
                    total_products += 1
                    state_id = f"{site} | {p_name}"
                    footer = item.find('div', class_='card-footer')
                    is_available = "售罄" not in (footer.get_text(strip=True) if footer else "")

                    if is_available:
                        if not stock_state.get(state_id, {}).get("acknowledged", False):
                            stock_state[state_id] = {"in_stock": True, "acknowledged": False}
                            has_changes = True
                            found_count += 1
                            await send_stock_alert(context, site, p_name, url)
                    else:
                        if stock_state.get(state_id, {}).get("acknowledged", False):
                            stock_state[state_id] = {"in_stock": False, "acknowledged": False}
                            has_changes = True
                            
        except Exception as e:
            logging.error(f"站点 {site} 检查失败: {e}")

    if has_changes:
        save_json(STATE_FILE, stock_state)
    return found_count, total_products

async def send_stock_alert(context, site, name, url):
    state_id = f"{site} | {name}"
    keyboard = [[InlineKeyboardButton("✅ 停止提醒", callback_data=f"ack|{state_id[:40]}")]]
    text = (f"🚨 **补货通知: {site}** 🚨\n\n"
            f"产品: `{name}`\n\n"
            f"🔗 [立即前往购买]({url})")
            
    for uid in ALLOWED_USERS:
        await context.bot.send_message(chat_id=uid, text=text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))