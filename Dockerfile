# 使用轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装必要的依赖
RUN pip install --no-cache-dir \
    httpx \
    beautifulsoup4 \
    "python-telegram-bot[job-queue]" \
    python-dotenv

# 复制脚本和配置文件
COPY jiankong_bot.py .
COPY .env .

# 启动程序
CMD ["python", "jiankong_bot.py"]