import os
import logging
import httpx
import asyncio
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- 配置区 ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = [int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x]

CHECK_INTERVAL = 1800 
STATE_FILE = "stock_state.json"  
TASKS_FILE = "tasks.json"        

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 数据持久化逻辑 ---
def load_json(file_path, default_value):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return default_value

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 初始化数据
monitor_tasks = load_json(TASKS_FILE, [])
stock_state = load_json(STATE_FILE, {})

# --- 权限装饰器 ---
def restricted(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in ALLOWED_USERS: return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- 核心监控逻辑 ---
async def check_all_sites(context: ContextTypes.DEFAULT_TYPE):
    """巡检所有站点并返回统计结果 (发现数, 总产品数)"""
    global stock_state
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    found_count = 0
    total_products = 0
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
                    status_text = footer.get_text(strip=True) if footer else ""
                    is_available = "售罄" not in status_text

                    if is_available:
                        # 如果有货 且 未被确认 -> 发送/重复提醒
                        if not stock_state.get(state_id, {}).get("acknowledged", False):
                            stock_state[state_id] = {"in_stock": True, "acknowledged": False}
                            has_changes = True
                            found_count += 1
                            await send_stock_alert(context, site, p_name, status_text, url)
                    else:
                        # 如果售罄，重置确认为 False，为下次补货做准备
                        if stock_state.get(state_id, {}).get("acknowledged", False):
                            stock_state[state_id] = {"in_stock": False, "acknowledged": False}
                            has_changes = True
                            
        except Exception as e:
            logging.error(f"站点 {site} 检查失败: {e}")

    if has_changes: 
        save_json(STATE_FILE, stock_state)
    
    return found_count, total_products

async def send_stock_alert(context: ContextTypes.DEFAULT_TYPE, site, name, status, url):
    state_id = f"{site} | {name}"
    # 限制 callback_data 长度防止溢出
    keyboard = [[InlineKeyboardButton("✅ 停止提醒", callback_data=f"ack|{state_id[:40]}")]]
    
    text = (f"🚨 **补货通知: {site}** 🚨\n\n"
            f"产品: `{name}`\n"
            f"状态: {status}\n\n"
            f"🔗 [立即前往购买]({url})")
            
    for uid in ALLOWED_USERS:
        await context.bot.send_message(
            chat_id=uid, 
            text=text, 
            parse_mode='Markdown', 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- 指令处理 ---
@restricted
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用法: /add 站点名 | URL | 产品1, 产品2"""
    try:
        raw_text = update.message.text.split('/add ')[1]
        parts = [p.strip() for p in raw_text.split('|')]
        site_name, url, targets_raw = parts[0], parts[1], parts[2]
        targets = [t.strip() for t in targets_raw.split(',')]
        
        monitor_tasks.append({"site_name": site_name, "url": url, "targets": targets})
        save_json(TASKS_FILE, monitor_tasks)
        await update.message.reply_text(f"✅ 已添加监控任务：{site_name}\n产品列表：{', '.join(targets)}")
    except:
        await update.message.reply_text("❌ 格式错误！请使用：\n`/add 名字 | 链接 | 产品1, 产品2`")

@restricted
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前所有监控任务及其详细信息"""
    if not monitor_tasks: 
        return await update.message.reply_text("空空如也，快用 `/add` 添加任务吧。", parse_mode='Markdown')
    
    res = "📋 **当前监控列表：**\n\n"
    for i, t in enumerate(monitor_tasks):
        # 将产品列表转换为逗号分隔的字符串
        targets_str = ", ".join(t['targets'])
        
        # 拼接任务详情：序号. 站点名、链接、监控产品
        res += (
            f"{i}. **{t['site_name']}**\n"
            f"🔗 链接: [点击查看]({t['url']})\n"
            f"📦 产品: `{targets_str}`\n\n"
        )
    
    # 使用 disable_web_page_preview 防止生成大量的网页预览卡片
    await update.message.reply_text(res, parse_mode='Markdown', disable_web_page_preview=True)

@restricted
async def del_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0])
        removed = monitor_tasks.pop(idx)
        save_json(TASKS_FILE, monitor_tasks)
        await update.message.reply_text(f"🗑 已删除任务：{removed['site_name']}")
    except:
        await update.message.reply_text("❌ 请输入正确的序号，例如：`/del 0`")

@restricted
async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """手动巡检并反馈统计结果"""
    await update.message.reply_text("🔎 正在巡检所有网页，请稍候...")
    found, total = await check_all_sites(context)
    if found > 0:
        await update.message.reply_text(f"✅ 巡检完毕！共检查 {total} 个产品，发现 {found} 个补货！已发送通知。")
    else:
        await update.message.reply_text(f"📭 巡检完毕。共检查 {total} 个产品，目前全部【售罄】。")


@restricted
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示帮助信息"""
    help_text = (
        "🤖 **监控机器人使用手册**\n\n"
        "🟢 **基础指令**\n"
        "• `/start` - 查看机器人运行状态\n"
        "• `/help` - 召唤本帮助菜单\n\n"
        "🔍 **监控管理**\n"
        "• `/add 站点名 | 链接 | 产品1, 产品2` \n"
        "  _例子：/add 东京 | http://... | Mini, Pro_\n"
        "• `/list` - 查看当前所有监控任务及其 ID\n"
        "• `/del ID` - 根据 ID 删除任务（ID 从 /list 获取）\n\n"
        "🚀 **手动操作**\n"
        "• `/check` - 立即巡检所有网页库存\n\n"
        "💡 **提示**：\n"
        "1. 只有检测到补货且您**未点击确认**时，机器人才会每小时提醒。\n"
        "2. 点击补货通知下的按钮可停止该产品此轮的轰炸。"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

            
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ack|"):
        sid_prefix = query.data.split("|")[1]
        # 匹配对应状态
        for key in list(stock_state.keys()):
            if key.startswith(sid_prefix):
                stock_state[key]["acknowledged"] = True
        save_json(STATE_FILE, stock_state)
        await query.edit_message_text(text=f"👌 已确认补货信息。该产品此轮补货将停止提醒。")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # 定时巡检
    app.job_queue.run_repeating(check_all_sites, interval=CHECK_INTERVAL, first=1)
    
    # 指令注册
    app.add_handler(CommandHandler('start', lambda u, c: u.message.reply_text("🤖 监控系统运行中...")))
    app.add_handler(CommandHandler('add', add_task))
    app.add_handler(CommandHandler('list', list_tasks))
    app.add_handler(CommandHandler('del', del_task))
    app.add_handler(CommandHandler('check', check_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler('help', help_cmd))
    
    print("🤖 动态监控系统已启动...")
    app.run_polling()