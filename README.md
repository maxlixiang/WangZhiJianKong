# YunyouJianKong V2

一个通过 Telegram 机器人发送提醒的网页库存监控程序。程序会定时访问配置好的商品页面，解析页面中的商品卡片，发现目标商品不再显示为“售罄”时，向指定 Telegram 用户发送补货通知。

## 功能

- 定时巡检网页库存状态
- 支持通过 Telegram 命令添加、查看、删除监控任务
- 支持手动触发一次巡检
- 发现补货后向白名单用户发送 Telegram 消息
- 消息中带有确认按钮，确认后本轮不再重复提醒
- 使用 JSON 文件保存监控任务和提醒状态

## 项目结构

```text
.
├── main.py              # 程序入口，注册 Telegram 命令和定时任务
├── monitor.py           # 网页请求、HTML 解析、库存判断、发送提醒
├── handlers.py          # Telegram 命令处理逻辑
├── config.py            # 环境变量和基础配置
├── utils.py             # JSON 读写、用户权限限制
├── tasks.json           # 监控任务列表
├── stock_state.json     # 商品提醒状态
├── Dockerfile           # Docker 构建文件
├── docker-compose.yml   # Docker Compose 配置
└── .env                 # Telegram Token 和用户白名单
```

## 环境要求

- Python 3.10+
- Telegram Bot Token
- 需要接收提醒的 Telegram 用户 ID

Python 依赖：

```bash
pip install httpx beautifulsoup4 "python-telegram-bot[job-queue]" python-dotenv
```

## 配置

在项目根目录创建 `.env` 文件：

```env
BOT_TOKEN=你的_Telegram_Bot_Token
ALLOWED_USERS=123456789,987654321
```

说明：

- `BOT_TOKEN`：从 Telegram 的 BotFather 获取。
- `ALLOWED_USERS`：允许使用机器人的 Telegram 用户 ID，多个用户用英文逗号分隔。

## 运行

直接运行：

```bash
python main.py
```

启动后，机器人会通过 polling 方式连接 Telegram，并每 30 分钟自动巡检一次。

巡检间隔在 `config.py` 中配置：

```python
CHECK_INTERVAL = 1800
```

单位是秒。

## Docker 运行

项目已经支持 Docker Compose 部署：

```bash
docker compose up -d --build
```

`docker-compose.yml` 会读取 `.env`，并挂载以下状态文件：

- `tasks.json`
- `stock_state.json`

这样容器重启后，监控任务和提醒状态仍会保留。

## Telegram 命令

### `/start`

启动提示。

### `/help`

查看命令菜单。

### `/add`

添加监控任务。

格式：

```text
/add 站点名称 | 商品页面链接 | 商品名1, 商品名2
```

示例：

```text
/add 东京 | https://yunyoo.cc/cart?fid=5&gid=21 | 日本东京 TCVM - Mini, 日本东京 TCVM - Basic
```

添加后会写入 `tasks.json`。

### `/list`

查看当前所有监控任务。

### `/del`

按序号删除监控任务。

格式：

```text
/del 0
```

序号来自 `/list` 输出。

### `/check`

立即手动巡检所有监控任务。

## 监控逻辑

程序会读取 `tasks.json` 中的任务，每个任务包含：

```json
{
    "site_name": "东京",
    "url": "https://example.com/cart",
    "targets": [
        "商品名 1",
        "商品名 2"
    ]
}
```

巡检时会：

1. 请求任务中的 `url`。
2. 使用 BeautifulSoup 解析 HTML。
3. 查找页面里的 `div.cartitem` 商品卡片。
4. 从 `div.card-body` 中读取商品名。
5. 如果商品名在 `targets` 中，则读取 `div.card-footer` 判断是否包含“售罄”。
6. 如果没有“售罄”，则认为商品可购买，并发送 Telegram 提醒。

提醒状态保存在 `stock_state.json`，用于避免已确认的商品重复提醒。

## 注意事项

- `tasks.json` 和 `stock_state.json` 目前在 `.gitignore` 中，适合存放本地运行状态；如果要部署到服务器，需要手动准备这两个文件。
- 监控逻辑依赖目标网页的 HTML 结构。如果网页结构变化，例如商品卡片不再使用 `div.cartitem`，需要同步修改 `monitor.py`。
- 机器人命令会被 `ALLOWED_USERS` 限制，未授权用户无法操作。
- `.env` 中包含敏感 Token，不要提交到公开仓库，也不会被打包进 Docker 镜像。

## 后续可改进

- 增加任务重复校验，避免重复添加同一个商品
- 增加异常通知，例如网页请求失败时发送提醒
- 增加日志文件，方便排查长期运行问题
- 支持更灵活的商品匹配方式，例如包含匹配或正则匹配
