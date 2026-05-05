from telegram import Update
from telegram.ext import ContextTypes

from config import CHECK_INTERVAL, STATE_FILE, TASKS_FILE
from monitor import check_all_sites, monitor_tasks, reset_acknowledged, stock_state
from utils import restricted, save_json, state_token

MONITOR_JOB_NAME = "stock_monitor"


def schedule_monitor_job(job_queue):
    if job_queue.get_jobs_by_name(MONITOR_JOB_NAME):
        return False

    job_queue.run_repeating(
        check_all_sites,
        interval=CHECK_INTERVAL,
        first=1,
        name=MONITOR_JOB_NAME,
    )
    return True


def format_status_line(status):
    if status["in_stock"] is True:
        stock_text = "有货"
    elif status["in_stock"] is False:
        stock_text = "售罄"
    else:
        stock_text = "未在页面中找到"

    ack_text = "已停止提醒" if status["acknowledged"] else "提醒开启"
    return f"- {status['site']} / {status['name']}：{stock_text}，{ack_text}"


@restricted
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if schedule_monitor_job(context.job_queue):
        await update.message.reply_text("监控系统已启动。输入 /help 查看指令。")
    else:
        await update.message.reply_text("监控系统已经在运行中。输入 /help 查看指令。")


@restricted
async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name(MONITOR_JOB_NAME)
    if not jobs:
        await update.message.reply_text("当前没有正在运行的自动监控。")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("已停止自动监控。需要恢复时运行 /start。")


@restricted
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_text = update.message.text.split("/add ", 1)[1]
        parts = [p.strip() for p in raw_text.split("|")]
        if len(parts) != 3:
            raise ValueError("invalid add command format")

        site_name, url, targets_raw = parts
        targets = [t.strip() for t in targets_raw.split(",") if t.strip()]
        if not site_name or not url or not targets:
            raise ValueError("missing required task fields")

        monitor_tasks.append({"site_name": site_name, "url": url, "targets": targets})
        save_json(TASKS_FILE, monitor_tasks)
        await update.message.reply_text(f"已添加监控任务：{site_name}")
    except Exception:
        await update.message.reply_text(
            "格式错误：`/add 名字 | 链接 | 产品1, 产品2`",
            parse_mode="Markdown",
        )


@restricted
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitor_tasks:
        await update.message.reply_text("当前没有监控任务。")
        return

    res = "当前监控列表：\n\n"
    for i, task in enumerate(monitor_tasks):
        targets = ", ".join(task["targets"])
        res += (
            f"{i}. *{task['site_name']}*\n"
            f"[点击查看]({task['url']})\n"
            f"`{targets}`\n\n"
        )

    await update.message.reply_text(
        res,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


@restricted
async def del_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0])
        removed = monitor_tasks.pop(idx)
        save_json(TASKS_FILE, monitor_tasks)
        await update.message.reply_text(f"已删除：{removed['site_name']}")
    except Exception:
        await update.message.reply_text("用法：`/del 序号`", parse_mode="Markdown")


@restricted
async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("正在巡检所有网页...")
    summary = await check_all_sites(context, send_alerts=True)

    msg = (
        f"巡检完毕。共检查 {summary['total']} 个商品，"
        f"当前有货 {summary['available']} 个，"
        f"本次发送提醒 {summary['alerted']} 条。"
    )
    if summary["errors"]:
        msg += "\n\n检查失败：\n" + "\n".join(summary["errors"])

    await update.message.reply_text(msg)


@restricted
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("正在刷新库存状态...")
    summary = await check_all_sites(context, send_alerts=False)

    if not summary["statuses"]:
        await update.message.reply_text("暂时没有可显示的监控状态。")
        return

    lines = [format_status_line(status) for status in summary["statuses"]]
    msg = (
        f"当前监控状态：\n\n"
        + "\n".join(lines)
        + f"\n\n共检查 {summary['total']} 个商品，当前有货 {summary['available']} 个。"
    )
    if summary["errors"]:
        msg += "\n\n检查失败：\n" + "\n".join(summary["errors"])

    await update.message.reply_text(msg, disable_web_page_preview=True)


@restricted
async def restore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    changed = reset_acknowledged()
    await update.message.reply_text(
        f"已恢复提醒开关，共重置 {changed} 个已停止提醒的商品。现在可以运行 /check 重新巡检。"
    )


@restricted
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "*监控机器人手册*\n\n"
        "- `/add 名字 | 链接 | 产品1, 产品2` - 添加监控\n"
        "- `/list` - 查看任务\n"
        "- `/del 序号` - 删除任务\n"
        "- `/check` - 手动巡检，并对未停止提醒的有货商品发送提醒\n"
        "- `/status` - 刷新并查看所有监控商品的库存状态\n"
        "- `/restore` - 恢复所有已停止的提醒\n"
        "- `/stop` - 停止自动监控\n"
        "- `/help` - 查看菜单"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("ack|"):
        token = query.data.split("|", 1)[1]
        for key in list(stock_state.keys()):
            if state_token(key) == token:
                stock_state[key]["acknowledged"] = True

        save_json(STATE_FILE, stock_state)
        await query.edit_message_text(text="已停止提醒。该商品仍会在 /status 中显示真实库存。")
