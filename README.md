# 基金管理助手

基于AgentScope框架和qieman-mcp服务的基金管理助手，提供基金信息查询、分析和投资建议功能。

## 功能特点

- 基金管理助手可使用功能，点击查看 [qieman-mcp工具](https://qieman.com/mcp/tools)，[文档说明](https://yingmi.feishu.cn/docx/PRPRds5SBo2MITxHJL2cMPminEf)
- 图形化界面：易于使用的Web界面和桌面应用
- 兼容OpenAI API格式，可直接调用qieman-mcp服务


## Windows可执行文件
[下载Windows可执行文件](https://github.com/mengxiang1117/fund_anagement_assistant/releases/tag/v1.0.0)
## 项目结构

```
.
├── qieman_mcp.py          # 核心功能模块
├── web_server.py          # Web服务端
├── web_server_gui.py      # 带图形界面的Web服务端
├── build_exe.py           # 打包脚本
├── config.json           # 配置文件
├── requirements.txt      # 依赖列表
├── templates/
│   └── index.html        # Web界面模板
└── logs/
    └── server.log        # 服务日志
```

## 配置说明

在 `config.json` 文件中配置以下参数：

- `mcp.url`: qieman-mcp服务的URL和API密钥，且慢mcp的key，[注册地址](https://qieman.com/mcp/landing)        
- `model.model_name`: 使用的大模型名称
- `model.api_key`: 大模型API密钥
- `model.base_url`: 大模型API的基础URL，兼容OpenAI API格式
- `web_server.port`: Web服务监听端口，默认8082

## 依赖说明

- `aiohttp`: 异步HTTP客户端/服务器框架
- `agentscope`: AgentScope框架
- `pyinstaller`: 打包工具

## 安装说明

```bash
python 3.10+
pip install -r requirements.txt
```

## 使用方法

### 1. 命令行模式

直接运行核心模块：

```bash
python qieman_mcp.py
```

### 2. Web服务模式

启动Web服务：

`--port`: Web服务监听端口，默认8082
`--mcp_url`: qieman-mcp服务的URL和API密钥
`--model_name`: 使用的大模型名称
`--api_key`: 大模型API密钥
`--base_url`: 大模型API的基础URL
```bash
python web_server.py --port 8082 --mcp_url "https://stargate.yingmi.com/mcp/sse?apiKey=YOUR_API_KEY" --model_name "qwen3-max" --api_key "YOUR_API_KEY" --base_url "https://apis.iflow.cn/v1"
```

加载config.json配置文件
```bash
python web_server.py
```
然后在浏览器中访问 `http://localhost:8082`

### 3. 图形界面模式

启动带图形界面的Web服务：

```bash
python web_server_gui.py
```

在图形界面中配置参数并启动服务。

## 打包成可执行文件

使用PyInstaller将图形界面应用打包成exe文件：

```bash
python build_exe.py
```
生成的exe文件位于 `dist/` 目录下。


## 许可证

MIT