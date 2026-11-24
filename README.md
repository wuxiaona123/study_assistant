# 学习助手 · 运行说明

本文档面向第一次接触本项目的人。按本文从零操作，可以把前端和后端完整跑起来。

---

## 0. 这是什么

一个基于大模型课程资料的学习助手，共 5 个页面：学习（聊资料）、资料库（上传管理）、测评（AI 出题阅卷）、进度（掌握度统计）、报告（AI 写周报）。

技术栈：

| 层 | 技术 |
|---|---|
| 前端 | 纯 HTML / CSS / JavaScript，无构建步骤 |
| 后端 | Python + Flask，SQLite 数据库 |
| 大模型 | OpenAI 兼容的 `/chat/completions` 接口（本项目用 DeepSeek） |

工作方式：前端静态服务跑在 **8765** 端口，后端 Flask 跑在 **5000** 端口，两者通过 HTTP 跨域通信。前端右上角的状态点探测后端 `/api/health`，亮绿表示后端连通。

---

## 1. 环境要求

- **Python 3.9 或更高**（项目开发环境为 Python 3.13）
- 现代浏览器（Chrome / Edge / Safari 均可）
- 一个可用的大模型 API 账号，例如 DeepSeek（本项目当前使用 `deepseek-flash`）

不需要安装 Node.js，不需要 Docker，不需要单独安装数据库。

---

## 1.1 最省事的启动方式：一键脚本（推荐）

项目根目录提供了 4 个启动脚本，**自动完成虚拟环境创建、依赖安装、建库和启动**，且全部使用相对路径，可与整个项目一起移动。只需先按第 3.2 节配好 `backend/.env`（含大模型密钥），然后：

**macOS / Linux**（在项目根目录打开终端）：

```bash
./start_backend.sh      # 启动后端（自动装依赖到 .venv 并启动 :5000）
```

打开**另一个**终端窗口：

```bash
./start_fronted.sh      # 启动前端（:8765，注意此文件名按需求定义为 fronted）
```

**Windows**（在项目根目录分别双击，或在该目录的 cmd 中执行）：

```bat
start_backend.bat       :: 启动后端（自动装依赖到 .venv 并启动 :5000）
start_frontend.bat      :: 启动前端（:8765）
```

两个脚本各占一个窗口，需同时运行；关闭窗口即停止对应服务。启动后浏览器打开 <http://127.0.0.1:8765>，右上角状态点亮绿即连上后端。

> 脚本已内置「虚拟环境不存在则创建」「依赖缺失则安装」「首次运行自动建库」，因此多数情况下无需手动执行第 3 节的命令。第 3 节仍保留，便于理解每一步在做什么或排查问题。

---

## 2. 目录结构

```
study_assistant/                  ← 项目根目录（本文档所在位置）
├── README.md                     ← 本文档
├── 功能需求文档.md                 ← 需求、接口、表设计、系统提示词
├── claude.md                     ← 项目编程准则
├── start_backend.sh / .bat       ← 一键启动后端（mac / win）
├── start_fronted.sh              ← 一键启动前端（mac，按需求的命名）
├── start_frontend.bat            ← 一键启动前端（win）
├── frontend/                     ← 前端（纯静态）
│   ├── index.html
│   ├── css/    reset / layout / components / pages
│   └── js/     api / app / chat / library / quiz / progress / report
└── backend/                      ← 后端（Flask）
    ├── app.py                    ← 应用入口（启动文件）
    ├── config.py                 ← 配置读取
    ├── init_db.py                ← 建表脚本
    ├── models.py                 ← 9 张表的模型
    ├── llm.py                    ← 大模型调用 + 三套系统提示词
    ├── document_processor.py     ← 文档文字提取与切片
    ├── requirements.txt          ← Python 依赖清单
    ├── .env.example              ← 配置模板
    ├── .env                      ← 你的实际配置（需自己创建，含密钥，勿提交）
    ├── .venv/                    ← Python 虚拟环境（需自己创建）
    ├── study_assistant.db        ← SQLite 数据库（初始化后生成）
    ├── uploads/                  ← 上传文件存放目录（初始化后生成）
    └── api/                      ← 5 个功能的接口实现
```

---

## 3. 后端配置

所有配置都从 `backend/.env` 文件读取；也可通过操作系统环境变量覆盖。**配置项不写死在代码里**。读取优先级：`环境变量` > `backend/.env` > `代码默认值`。

### 3.1 创建虚拟环境并安装依赖

在项目根目录执行：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows 用户把 `.venv/bin/` 换成 `.venv\Scripts\`，即：

```bat
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

依赖包含 Flask、Flask-SQLAlchemy、python-dotenv，以及用于读取 PDF / PPT / Word 文字的 pypdf、python-pptx、python-docx。Markdown 和 TXT 直接读文本，不需要额外库。

### 3.2 创建并填写 `.env`

```bash
cp .env.example .env
```

然后用任意文本编辑器打开 `backend/.env`，按下面说明填写。

**完整配置项说明：**

| 配置项 | 作用 | 默认值 / 留空行为 |
|---|---|---|
| `SECRET_KEY` | Flask 密钥 | `change-me`，本地开发可不管 |
| `DATABASE_URI` | 数据库连接串 | 留空则用 `backend/study_assistant.db`（SQLite） |
| `UPLOAD_FOLDER` | 上传文件存放目录 | 留空则用 `backend/uploads` |
| `MAX_CONTENT_LENGTH` | 单文件大小上限（字节） | `52428800`（50MB） |
| `LLM_BASE_URL` | 大模型接口地址，需带 `/v1` | 留空则无法调用大模型 |
| `LLM_API_KEY` | 大模型密钥 | 留空则无法调用大模型 |
| `LLM_MODEL` | 模型名称 | 默认 `gpt-4o-mini` |
| `LLM_TIMEOUT` | 调用超时（秒） | `60` |

**本项目当前使用的配置示例**（密钥用你自己的替换，切勿把真实密钥写进文档或提交）：

```ini
SECRET_KEY=change-me
DATABASE_URI=
UPLOAD_FOLDER=
MAX_CONTENT_LENGTH=52428800
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=你的DeepSeek密钥
LLM_MODEL=deepseek-flash
LLM_TIMEOUT=60
```

注意两点：

1. `LLM_BASE_URL` 必须是 OpenAI 兼容的 chat completions 服务根地址。用 DeepSeek 就填 `https://api.deepseek.com/v1`，**末尾不要漏掉 `/v1`**。
2. `LLM_MODEL` 必须与你账号可用的模型名一致。DeepSeek 填 `deepseek-flash` 或其他你账号支持的模型名；如果沿用默认的 `gpt-4o-mini`，就要把 `LLM_BASE_URL` 和 `LLM_API_KEY` 换成对应的 OpenAI 配置。

`.env` 已在 `backend/.gitignore` 中忽略，正常情况下不会被提交到代码仓库。**不要把它发给别人或贴到聊天里。**

### 3.3 初始化数据库

在 `backend/` 目录下执行：

```bash
.venv/bin/python init_db.py
```

成功时输出 `建表完成：...`，并列出 9 张表。`init_db.py` 只创建不存在的表，**重复执行不会清空已有数据**，可以放心重跑。

执行后会生成 `backend/study_assistant.db` 和 `backend/uploads/` 目录。

---

## 4. 启动后端程序

在 `backend/` 目录下执行：

```bash
.venv/bin/python app.py
```

服务启动后监听 `127.0.0.1:5000`，控制台会打印 Flask 的启动信息。这是开发模式（`debug=True`），修改代码后会自动重载。

**验证后端是否启动成功：** 浏览器打开 <http://127.0.0.1:5000/api/health>，应返回：

```json
{"status": "ok"}
```

或者用命令行：

```bash
curl http://127.0.0.1:5000/api/health
```

如果返回 `{"status":"ok"}`，说明后端已就绪。

保持这个终端窗口开着，后端需要一直运行。停止服务按 `Ctrl + C`。

> 后端启动前必须完成第 3 节的配置和建表。若 `.env` 里的大模型配置为空，后端仍能启动、上传和解析资料也能用，但聊天、出题、阅卷、周报这些需要调用大模型的功能会报错。

---

## 5. 启动前端程序

前端是纯静态文件，但**必须通过本地 HTTP 服务打开，不能直接双击 `index.html`**。直接用 `file://` 打开会导致跨域请求失败。

在**新的终端窗口**中执行（注意是新开一个窗口，后端那个保持运行）：

```bash
cd frontend
python3 -m http.server 8765
```

Windows 用户把 `python3` 换成 `python`。

然后用浏览器打开：

```
http://127.0.0.1:8765
```

**验证前后端是否连通：** 看页面右上角的圆形状态点。

- 亮绿色：后端连通，可以正常使用。
- 亮红色：后端没连上。检查后端是否在 5000 端口运行、`/api/health` 是否返回 ok。

前端通过 `frontend/js/api.js` 里的 `API_BASE` 常量固定指向 `http://127.0.0.1:5000/api`。如果你改了后端的启动端口，必须同步修改这个常量，否则前端全部接口会失败。

保持前端服务的终端窗口也开着。停止按 `Ctrl + C`。

---

## 6. 完整验证清单（第一次跑起来后照着做）

两个服务都在运行、状态点亮绿后，按这个顺序验证整条链路：

1. **资料库** → 上传一份 `.md` 或 `.txt` 文件 → 状态从「解析中」变为「完成」。
2. **学习** → 顶部下拉框选中刚上传的资料 → 输入一个资料相关的问题 → AI 回复应基于资料作答，消息下方的小箭头可展开查看引用的资料段落。
3. **测评** → 选资料、选题数 → 开始测试 → 答题并提交 → 查看分数圆环、逐题正确答案和 AI 点评。
4. **进度** → 查看统计卡片、雷达图和知识点列表；在资料详情的笔记框里打字，停顿约 1 秒应显示「已自动保存」。
5. **报告** → 选「本周」→ 生成周报 → 点「下载 .md」应能保存文件。

第 2、3、5 步会真实调用大模型，需要联网且 `.env` 配置正确。第 1 步上传解析不需要大模型。

---

## 7. 常见问题

**状态点一直是红色？**
后端没启动，或没在 5000 端口。先在浏览器打开 `http://127.0.0.1:5000/api/health` 确认。若端口被占用，可用 `lsof -ti:5000` 查占用进程；换端口后记得同步改 `frontend/js/api.js` 的 `API_BASE`。

**AI 功能报错「调用大模型失败」？**
检查 `backend/.env`：`LLM_BASE_URL` 是否带 `/v1`、`LLM_API_KEY` 是否正确、`LLM_MODEL` 是否是账号支持的模型名。改完 `.env` 后需要**重启后端**才生效。

**上传后状态变成「失败」？**
看列表里的失败原因。`.doc` 和 `.ppt` 是旧二进制格式，纯 Python 无法读取文字，需另存为 `.docx` / `.pptx` 后重新上传。支持格式为 PDF、PPT、Word（docx）、Markdown、TXT。

**前端页面打开了但什么都不显示？**
确认是用 `http://127.0.0.1:8765` 打开的，不是直接双击文件。确认后端已在 5000 端口启动。

**换了台电脑，虚拟环境怎么办？**
`.venv` 不需要拷贝。在新机器上从第 3.1 步重新创建虚拟环境、安装依赖，再执行 `init_db.py` 建库即可。

**笔记为什么换浏览器就没了？**
功能需求文档里没有笔记接口，笔记暂存在浏览器 localStorage。这是当前版本的已知限制，不影响其他功能。

---

## 8. 安全与范围说明

- `.env` 含真实 API 密钥，已加入 `.gitignore`，请勿提交或外传。
- 本项目是单机单用户的学习演示项目，没有登录鉴权，不适合部署到公网。
- 后端接口共 23 条（含健康检查），路径与字段定义见 `功能需求文档.md` 第 2 节。
