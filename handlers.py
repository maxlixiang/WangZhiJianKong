from telegram import Update
from telegram.ext import ContextTypes
from config import TASKS_FILE, STATE_FILE
from utils import restricted, save_json
from monitor import monitor_tasks, stock_state, check_all_sites

@restricted
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_text = update.message.text.split('/add ')[1]
        parts = [p.strip() for p in raw_text.split('|')]
        site_name, url, targets_raw = parts[0], parts[1], parts[2]
        targets = [t.strip() for t in targets_raw.split(',')]
        
        monitor_tasks.append({"site_name": site_name, "url": url, "targets": targets})
        save_json(TASKS_FILE, monitor_tasks)
        await update.message.reply_text(f"✅ 已添加任务：{site_name}")
    except:
        await update.message.reply_text("❌ 格式：`/add 名字 | 链接 | 产品1, 产品2`", parse_mode='Markdown')

@restricted
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitor_tasks: 
        return await update.message.reply_text("空空如也。")
    res = "📋 **当前监控列表：**\n\n"
    for i, t in enumerate(monitor_tasks):
        res += f"{i}. **{t['site_name']}**\n🔗 [点击查看]({t['url']})\n📦 `{', '.join(t['targets'])}`\n\n"
    await update.message.reply_text(res, parse_mode='Markdown', disable_web_page_preview=True)

@restricted
async def del_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0])
        removed = monitor_tasks.pop(idx)
        save_json(TASKS_FILE, monitor_tasks)
        await update.message.reply_text(f"🗑 已删除：{removed['site_name']}")
    except:
        await update.message.reply_text("❌ 用法：`/del 序号`", parse_mode='Markdown')

@restricted
async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 正在巡检所有网页...")
    found, total = await check_all_sites(context)
    msg = f"✅ 发现 {found} 个补货！" if found > 0 else "📭 目前全部【售罄】。"
    await update.message.reply_text(f"巡检完毕。共检查 {total} 个产品，{msg}")

@restricted
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = ("🤖 **监控机器人手册**\n\n"
                 "• `/add` - 添加监控\n"
                 "• `/list` - 查看任务\n"
                 "• `/del` - 删除任务\n"
                 "• `/check` - 手动巡检\n"
                 "• `/help` - 召唤菜单")
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ack|"):
        sid_prefix = query.data.split("|")[1]
        for key in list(stock_state.keys()):
            if key.startswith(sid_prefix):
                stock_state[key]["acknowledged"] = True
        save_json(STATE_FILE, stock_state)
        await query.edit_message_text(text="👌 已确认补货，此轮将停止提醒。")