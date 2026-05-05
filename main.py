import logging

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from config import TOKEN
from handlers import (
    add_task,
    button_callback,
    check_cmd,
    del_task,
    help_cmd,
    list_tasks,
    restore_cmd,
    schedule_monitor_job,
    start_cmd,
    status_cmd,
    stop_cmd,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # 注册定时巡检
    schedule_monitor_job(app.job_queue)

    # 注册命令
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("del", del_task))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("模块化机器人正在运行...")
    app.run_polling()
