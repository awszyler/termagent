# termagent

> 一个基于终端的 AI 助手：会话隔离、可配置模型接入、带护栏与交互式授权的 bash 执行、MCP 工具集成。
> A terminal AI assistant with session isolation, guard-railed bash execution with interactive authorization, and MCP tool support.

## 免责声明

这是一个**个人项目**，**不是 AWS 官方产品或方案**，不代表任何雇主的立场，不提供官方支持。按 MIT 许可证「原样」提供，使用风险自担。

## 功能特性

- 🤖 **智能对话**: 基于大语言模型的对话系统，兼容 OpenAI Chat Completions 接口
- 🔒 **执行护栏**: bash 命令执行前经过黑名单 + 首命令白名单校验，并按命令类型请求交互式授权（**是护栏，不是沙箱** —— 见[安全机制与已知限制](#安全机制与已知限制)）
- 🎯 **会话隔离**: 每个会话独立运行
- ⚙️ **可配置**: 通过 JSON 文件或环境变量配置模型接入
- 🛠️ **工具集成**: 支持 MCP (Model Context Protocol) 工具
- 📱 **终端友好**: 专为命令行环境设计
- 🌏 **中文支持**: 优化的中文输入体验，中文字符退格只需按一次

## 安装要求

- Python 3.8+
- macOS（当前版本；其他平台未测试）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置模型接入

仓库里**不包含**真实配置文件 —— `config/model.json` 已被 `.gitignore` 忽略，以避免密钥被误提交。请从示例文件复制一份：

```bash
cp config/model.json.example config/model.json
```

然后编辑 `config/model.json`，填入你自己的端点和密钥：

```json
{
  "api_url": "https://your-api-endpoint.example.com/v1/chat/completions",
  "api_key": "your-api-key-here",
  "model_name": "your-model-name",
  "temperature": 0.01,
  "timeout": 30,
  "max_tokens": 4096
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `api_url` | string | ✅ | Chat Completions 端点 URL |
| `api_key` | string | ✅ | API 认证密钥 |
| `model_name` | string | ✅ | 模型名称 |
| `temperature` | number | ❌ | 生成温度（默认 0.01） |
| `timeout` | number | ❌ | 请求超时秒数（默认 30） |
| `max_tokens` | number | ❌ | 最大 token 数 |

> ⚠️ **不要把填好的 `config/model.json` 提交上去。** 它已在 `.gitignore` 中；若你 fork 本项目，请确认这条规则仍然生效（`git check-ignore -v config/model.json` 应有输出）。

#### 方式二：环境变量（推荐用于 CI / 容器）

如果 `config/model.json` 不存在，程序会自动回退到环境变量，从而完全不需要在磁盘上留下密钥文件：

```bash
export AI_API_URL="https://your-api-endpoint.example.com/v1/chat/completions"
export AI_API_KEY="your-api-key"
export AI_MODEL_NAME="your-model-name"
export AI_TEMPERATURE="0.01"   # 可选，默认 0.01
export AI_TIMEOUT="30"         # 可选，默认 30

python -m src.main
```

三个必需变量（`AI_API_URL` / `AI_API_KEY` / `AI_MODEL_NAME`）缺任意一个都会报配置错误。
注意：`max_tokens` 目前只能通过配置文件设置，环境变量方式不读取该项。

配置解析优先级：`config/model.json` 存在则用它 → 不存在则读环境变量 → 两者都没有则报错并提示需要配置什么。

### 3. 运行

```bash
# 正常模式
python -m src.main

# 调试模式
python -m src.main --debug
python -m src.main --debug --log-file debug.log

# 人工测试模式（用于程序调优）
python -m src.main --manual-test
python manual_test.py            # 便捷脚本，等价于上一行
```

## MCP 工具配置

`config/mcp.json`（已含一份默认配置，所有 server 默认 `disabled`）：

```json
{
  "servers": {
    "server_name": {
      "command": "uvx",
      "args": ["package-name"],
      "env": { "ENV_VAR": "value" },
      "disabled": false
    }
  }
}
```

> 若某个 MCP server 需要密钥，**不要**把它写进 `config/mcp.json` 后提交 —— 通过 `env` 引用宿主环境变量，或把该文件也加入本地忽略。

## 使用指南

### 基本对话

```
👤 您: 帮我列出当前目录的文件
🤖 助手: 我来帮您列出当前目录的文件。

🛠️  Using tool: execute_bash
 ⋮
 ● I will run the following shell command:
   ls -la
 ⋮
 ↳ Purpose: 列出当前目录的详细文件信息

Allow this action? Use 't' to trust (always allow) this tool for the session. [y/n/t]: y
```

部分只读命令（`echo`、`pwd`、`whoami`、`ls` 等 15 个）会直接执行、不弹提示；其余命令会请求授权。
完整规则与已知限制见[安全机制与已知限制](#安全机制与已知限制)。

### 退出

输入 `exit` / `quit` / `bye` / `退出`，或按 `Ctrl+C`。

## 安全机制与已知限制

> ⚠️ **先说清楚定位**：下面这套检查是**降低误伤的护栏，不是安全沙箱**。它挡得住常见的手滑和明显的破坏性命令，但**不足以安全地执行不可信输入**。如果你的模型端点或提示词可能被第三方影响，请在容器/虚拟机等真正的隔离环境里运行本工具。

### 实际执行的检查

命令要通过以下全部检查才会执行（`src/tools/bash_tool.py: _validate_command_safety`）：

1. **正则黑名单**（23 条，对整条命令串匹配，大小写不敏感）：
   `rm -rf`、`sudo`、`su`、`chmod 777`、`dd if=`、`mkfs`、`fdisk`、`kill -9`、`killall`、`reboot`、`shutdown`、`init 0/6`、`> /dev/sd*`、`crontab`、`iptables`、`ufw`、`systemctl`、`service`、`mount`、`umount`、`chroot`、`history -c`
2. **危险字符**：命令含 `;`、`$(`、`` ` `` 一律拒绝
3. **首命令白名单**：命令的**第一个词**必须在约 50 个命令的白名单内（`SAFE_COMMANDS`）。注意 `rm` 不在白名单里，所以 `rm foo` 会被拒
4. **绝对路径限制**：以 `/` 开头的命令只允许位于 `/bin/`、`/usr/bin/`、`/usr/local/bin/`
5. **`&&` 逐段校验**：`&&` 连接的每一段都要通过白名单，例如 `ls && rm foo` 会被拒
6. **`||` 限制**：只允许 `||` 后接 `echo` / `true` / `false`
7. **重定向到设备文件**：`> /dev/*`（除 `/dev/null`、`/dev/zero`）与结尾的 `&`（后台执行）被拒

### 已知限制（务必了解）

| 限制 | 后果 | 示例（这些命令**会**被放行） |
|---|---|---|
| **单管道 `\|` 不拆解校验** | 只有第一段命令过白名单，管道右侧不做任何校验（`&&` 会逐段校验，`\|` 不会） | `ls \| rm foo`、`cat f \| sh`、`curl http://… \| bash` |
| **重定向目标不校验** | 白名单内的命令可以覆写任意文件 | `echo bad > ~/.zshrc` |
| **黑名单是正则匹配，不是语义分析** | 变形写法可绕过，例如 `rm -r -f` 不匹配 `rm\s+.*-rf` | — |
| **白名单只看首词** | 参数内容完全不受约束 | `git push --force`、`docker run --privileged …` |

这些限制在测试里有对应记录：`tests/test_bash_tool.py::test_pipe_targets_are_not_validated_known_gap` 以 `xfail` 形式保留，用来标记「期望行为已定义但尚未实现」。修复方向是对管道每一段都跑白名单校验，欢迎 PR。

### 交互式授权

授权判定同样**只看命令的第一个词**（`src/main.py: _command_needs_authorization`）：

- **直接执行、不提示**（15 个）：`echo` `pwd` `whoami` `date` `ls` `cat` `head` `tail` `wc` `sort` `uniq` `basename` `dirname` `uname` `env`
- **其余白名单命令**：弹出授权提示（`git` `curl` `docker` `python` `find` `grep` `ps` `mkdir` `cp` `mv` 等）

⚠️ 两条规则叠加会产生一个需要注意的后果：由于授权判定也只看首词，`ls | rm foo` 这类命令**既通过安全检查、又被判定为免授权**，因而不会弹出任何提示。这是上表第一行限制的直接体现。

授权选项：`y` 允许一次 ／ `n` 拒绝 ／ `t` 信任该工具，当前会话内自动允许（会话级信任，不持久化到磁盘）。

## 人工测试模式

记录完整交互过程并在结束时生成优化建议，用于调优。

```bash
python -m src.main --manual-test    # 或 python manual_test.py
```

生成的文件（**均已加入 `.gitignore`，因为它们会包含真实会话内容**）：

- `manual_test_YYYYMMDD_HHMMSS.log` — 详细测试日志
- `optimization_prompt_YYYYMMDD_HHMMSS.md` — 优化提示文档

详见 [人工测试模式使用指南](MANUAL_TEST_MODE.md) 与 [使用示例](EXAMPLE_USAGE.md)。

## 故障排除

**Q: 启动时提示配置错误**
A: 确认已 `cp config/model.json.example config/model.json` 并填好三个必需字段；或改用环境变量方式。

**Q: API 请求失败**
A: 核对 `api_url` 与 `api_key`，检查网络连通性。

**Q: 命令被拒绝执行**
A: 命令的第一个词必须在白名单内，且整条命令不能命中黑名单或含 `;` `$(` `` ` ``。规则见[安全机制与已知限制](#安全机制与已知限制)。

**Q: 这套安全检查能用来执行不可信输入吗？**
A: **不能。** 它是降低误伤的护栏，存在已知绕过路径（管道右侧不校验、重定向目标不校验）。需要真正隔离时请在容器/虚拟机里运行。

**Q: 响应缓慢**
A: 检查网络，或调大 `timeout`。

**Q: 中文输入退格键异常**
A: 已通过 readline + UTF-8 优化，每个中文字符按一次退格即可删除。

## 项目结构

```
termagent/
├── src/
│   ├── main.py                  程序入口
│   ├── cli/                     CLI 接口
│   ├── core/                    配置 / 会话 / AI 服务 / 推理
│   ├── tools/                   工具管理器 / Bash 工具
│   └── utils/                   错误处理 / 日志
├── config/
│   ├── model.json.example       模型配置模板（复制为 model.json 后使用）
│   └── mcp.json                 MCP 配置
├── tests/
└── requirements.txt
```

## 开发

```bash
python -m pytest tests/ -v
```

添加新工具：实现 `get_tool_definition()` 与 `execute()`，在 `ToolManager` 中注册，并补测试。

## 许可证

MIT，见 [LICENSE](LICENSE)。
