# -*- coding: utf-8 -*-
"""
基金管理助手Web界面
"""
import json
import sys
import os
from aiohttp import web, WSMsgType
from aiohttp.web import middleware
import logging
import argparse

from qieman_mcp import main


def load_config():
    """加载配置文件"""
    try:
        with open('config copy.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        return {}

# 配置日志
def setup_logging():
    """设置日志配置，同时输出到控制台和文件"""
    # 创建日志目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建results目录
    results_dir = 'results'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # 配置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 文件处理器（所有日志都写入文件）
    file_handler = logging.FileHandler(
        os.path.join(log_dir, 'server.log'), 
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 控制台处理器（同时输出到控制台）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 重定向print输出到日志
    class LogRedirector:
        def __init__(self, logger, level=logging.INFO):
            self.logger = logger
            self.level = level
            self.terminal = sys.stdout
            
        def write(self, message):
            if message.strip():  # 只记录非空消息
                self.logger.log(self.level, message.rstrip())
            self.terminal.write(message)
            
        def flush(self):
            self.terminal.flush()
    
    # 重定向标准输出和错误输出
    sys.stdout = LogRedirector(root_logger, logging.INFO)
    sys.stderr = LogRedirector(root_logger, logging.ERROR)
    
    return root_logger

# 设置日志
logger = setup_logging()

# 存储WebSocket连接
active_connections = set()

@middleware
async def cors_middleware(request, handler):
    """处理CORS跨域请求"""
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def websocket_handler(request, config):
    """处理WebSocket连接"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    active_connections.add(ws)
    logger.info("WebSocket连接已建立")
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    question = data.get('question', '')
                    logger.info(f"收到问题: {question}")
                    
                    if question:
                        # 发送开始处理信号
                        if ws in active_connections:
                            await ws.send_str(json.dumps({
                                'type': 'intermediate',
                                'message': '开始处理问题...'
                            }))
                        
                        # 创建回调函数用于发送中间输出
                        async def send_intermediate_output(message):
                            logger.info(f"中间输出: {message}")
                            if ws in active_connections:
                                try:
                                    await ws.send_str(json.dumps({
                                        'type': 'intermediate',
                                        'message': message
                                    }))
                                except Exception as e:
                                    logger.error(f"发送中间输出失败: {str(e)}")
                        
                        # 处理用户问题
                        try:
                            logger.info("开始调用main函数处理问题")
                            result = await main(question, send_intermediate_output, config)
                            logger.info(f"main函数返回结果: {result}")
                            
                            # 保存问答记录到文件
                            await save_qa_record(question, result)
                            
                            # 发送最终结果
                            if ws in active_connections:
                                await ws.send_str(json.dumps({
                                    'type': 'result',
                                    'response': result
                                }))
                        except Exception as e:
                            logger.error(f"处理问题时发生错误: {str(e)}", exc_info=True)
                            if ws in active_connections:
                                await ws.send_str(json.dumps({
                                    'type': 'error',
                                    'message': f"处理问题时发生错误: {str(e)}"
                                }))
                    else:
                        logger.warning("收到空问题")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误: {str(e)}")
                    if ws in active_connections:
                        await ws.send_str(json.dumps({
                            'type': 'error',
                            'message': f"消息格式错误: {str(e)}"
                        }))
            
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket连接错误: {ws.exception()}")
    
    finally:
        active_connections.discard(ws)
        logger.info("WebSocket连接已关闭")
    
    return ws

async def save_qa_record(question, answer):
    """保存问答记录到Markdown文件"""
    # 创建results目录（如果不存在）
    results_dir = 'results'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # 生成文件名（使用时间戳）
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.md"
    filepath = os.path.join(results_dir, filename)
    
    # 写入问答记录
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# 问答记录\n\n")
        f.write(f"**时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**问题**:\n\n{question}\n\n")
        f.write(f"**答案**:\n\n{answer}\n\n")
    
    logger.info(f"问答记录已保存: {filepath}")

async def index_handler(request):
    """返回主页"""
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        return web.Response(text=f.read(), content_type='text/html')

async def health_check(request):
    """健康检查接口"""
    return web.Response(text='OK', status=200)

async def history_handler(request):
    """返回历史记录页面"""
    with open('templates/history.html', 'r', encoding='utf-8') as f:
        return web.Response(text=f.read(), content_type='text/html')

async def history_content_handler(request):
    """返回历史记录内容"""
    import glob
    import datetime
    
    # 获取请求参数
    filename = request.query.get('file', None)
    results_dir = 'results'
    
    if filename:
        # 返回指定文件的内容
        filepath = os.path.join(results_dir, filename)
        # 确保文件路径在results目录内，防止路径遍历攻击
        if os.path.commonpath([os.path.abspath(results_dir)]) != os.path.commonpath([os.path.abspath(results_dir), os.path.abspath(filepath)]):
            return web.Response(status=403, text="Forbidden")
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return web.Response(text=content, content_type='text/markdown')
        else:
            return web.Response(status=404, text="File not found")
    else:
        # 返回所有历史记录文件列表
        pattern = os.path.join(results_dir, '*.md')
        files = glob.glob(pattern)
        # 按修改时间排序，最新的在前
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        # 只返回文件名
        filenames = [os.path.basename(f) for f in files]
        
        return web.json_response({'files': filenames})

async def delete_history_handler(request):
    """删除历史记录文件"""
    import json
    import os
    import glob
    
    # 只接受POST请求
    if request.method != 'POST':
        return web.Response(status=405, text="Method Not Allowed")
    
    try:
        # 获取请求体中的文件名列表
        data = await request.json()
        filenames = data.get('files', [])
        
        if not filenames:
            return web.json_response({'success': False, 'message': '未提供要删除的文件名'})
        
        results_dir = 'results'
        deleted_files = []
        failed_files = []
        
        for filename in filenames:
            # 验证文件名格式
            if not filename.endswith('.md'):
                failed_files.append({'filename': filename, 'reason': '文件格式不正确'})
                continue
                
            filepath = os.path.join(results_dir, filename)
            
            # 确保文件路径在results目录内，防止路径遍历攻击
            if os.path.commonpath([os.path.abspath(results_dir)]) != os.path.commonpath([os.path.abspath(results_dir), os.path.abspath(filepath)]):
                failed_files.append({'filename': filename, 'reason': '文件路径无效'})
                continue
            
            # 检查文件是否存在
            if not os.path.exists(filepath):
                failed_files.append({'filename': filename, 'reason': '文件不存在'})
                continue
                
            # 删除文件
            try:
                os.remove(filepath)
                deleted_files.append(filename)
                logger.info(f"已删除历史记录文件: {filepath}")
            except Exception as e:
                failed_files.append({'filename': filename, 'reason': str(e)})
                logger.error(f"删除历史记录文件失败: {filepath}, 错误: {str(e)}")
        
        return web.json_response({
            'success': True,
            'deleted_files': deleted_files,
            'failed_files': failed_files,
            'message': f'成功删除 {len(deleted_files)} 个文件，失败 {len(failed_files)} 个文件'
        })
        
    except json.JSONDecodeError:
        return web.json_response({'success': False, 'message': '请求格式错误'})
    except Exception as e:
        logger.error(f"删除历史记录时发生错误: {str(e)}")
        return web.json_response({'success': False, 'message': f'服务器错误: {str(e)}'})

def create_app(config=None):
    """创建Web应用"""
    # 加载配置
    if config is None:
        config = load_config()
    logger.info(f"加载配置: {config}")
    
    app = web.Application(middlewares=[cors_middleware])
    
    # 添加路由
    app.router.add_get('/', index_handler)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ws', lambda req: websocket_handler(req, config))
    app.router.add_get('/history', history_handler)
    app.router.add_get('/history-content', history_content_handler)
    app.router.add_post('/delete-history', delete_history_handler)

    # 从配置或默认值获取端口
    port = config["web_server"]["port"]
    
    return app, port


def parse_args():
    """
    解析命令行参数，并返回 (port, config) 元组。
    config 包含 mcp、model、web_server 三部分。
    """
    parser = argparse.ArgumentParser(description="启动 Web 服务器")

    # Web 服务监听端口（主端口）
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Web 服务器监听的端口（1024-65535）"
    )

    # MCP URL
    parser.add_argument(
        "--mcp_url",
        type=str,
        required=True,
        help="MCP 服务的 URL"
    )

    # 模型相关参数
    parser.add_argument(
        "--model_name",
        type=str,
        required=True,
        help="模型名称"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        required=True,
        help="API 密钥"
    )
    parser.add_argument(
        "--base_url",
        type=str,
        required=True,
        help="模型 API 的 Base URL"
    )

    # 本地 Web 服务配置端口（可用于内部标识，非监听端口）

    args = parser.parse_args()

    # 验证 --port 范围
    if not (1024 <= args.port <= 65535):
        logger.error(f"监听端口 {args.port} 不在有效范围 (1024-65535)")
        args.port = 8082  # 默认端口

    # 构建 config 字典（后5个参数）
    config = {
        "mcp": {
            "url": args.mcp_url
        },
        "model": {
            "model_name": args.model_name,
            "api_key": args.api_key,
            "base_url": args.base_url
        },
        "web_server": {
            "port": args.port
        }
    }

    return args.port, config

if __name__ == '__main__':
    

    if len(sys.argv) > 1:
        port, config = parse_args()
    else:
        config = None


    app, port = create_app(config)
    logger.info(f"Web服务器已启动: http://localhost:{port}")
    web.run_app(app, host='localhost', port=port)

