import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TOKEN, CHECK_INTERVAL
from monitor import check_all_sites
from handlers import add_task, list_tasks, del_task, check_cmd, help_cmd, button_callback

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start_cmd(update, context):
    await update.message.reply_text("🤖 监控系统已模块化启动。输入 /help 查看指令。")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # 注册定时巡检
    app.job_queue.run_repeating(check_all_sites, interval=CHECK_INTERVAL, first=1)
    
    # 注册指令
    app.add_handler(CommandHandler('start', start_cmd))
    app.add_handler(CommandHandler('add', add_task))
    app.add_handler(CommandHandler('list', list_tasks))
    app.add_handler(CommandHandler('del', del_task))
    app.add_handler(CommandHandler('check', check_cmd))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 模块化机器人正在运行...")
    app.run_polling()