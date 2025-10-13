#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基金管理助手,用户图形化界面自定义配置，启动web界面
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json
import sys
import os
import webbrowser
from aiohttp import web, WSMsgType
from aiohttp.web import middleware
import logging
from qieman_mcp import main
import asyncio


# 配置日志
def setup_logging():
    """设置日志配置，同时输出到控制台和文件"""
    # 创建日志目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
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
                            if main is None:
                                raise ImportError("qieman_mcp模块未正确导入")
                            
                            logger.info("开始调用main函数处理问题")
                            result = await main(question, send_intermediate_output, config)
                            logger.info(f"main函数返回结果: {result}")
                            
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


def resource_path(relative_path):
    """ 获取 PyInstaller 打包后的资源路径 """
    try:
        # 如果是 PyInstaller 打包后的 exe，资源在 _MEIPASS 临时目录
        base_path = sys._MEIPASS
    except AttributeError:
        # 开发环境，使用当前目录
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
async def index_handler(request):
    """返回主页"""
    with open(resource_path('templates/index.html'), 'r', encoding='utf-8') as f:
        return web.Response(text=f.read(), content_type='text/html')

async def health_check(request):
    """健康检查接口"""
    return web.Response(text='OK', status=200)

def create_app(config):
    """创建Web应用"""
    # config = load_config()

    logger.info(f"加载配置: {config}")
    
    app = web.Application(middlewares=[cors_middleware])
    
    # 添加路由
    app.router.add_get('/', index_handler)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ws', lambda req: websocket_handler(req, config))

    # 从配置或默认值获取端口
    port = config["web_server"]["port"]
    
    return app, port


class WebServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("基金管理工具Web服务器")
        self.root.geometry("600x500")
        
        # 服务状态
        self.server_running = False
        self.server_thread = None
        self.app = None
        self.runner = None
        self.site = None
        self.loop = None
        
        # 创建界面
        self.create_widgets()
        
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置参数框架
        config_frame = ttk.LabelFrame(main_frame, text="服务配置参数", padding="10")
        config_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        
        # MCP URL
        ttk.Label(config_frame, text="MCP URL:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.mcp_url_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.mcp_url_var, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # 模型名称
        ttk.Label(config_frame, text="模型名称:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.model_name_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.model_name_var, width=40).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # API密钥
        ttk.Label(config_frame, text="API密钥:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.api_key_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.api_key_var, width=40).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Base URL
        ttk.Label(config_frame, text="Base URL:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.base_url_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.base_url_var, width=40).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # 配置中的Web服务端口
        ttk.Label(config_frame, text="配置端口:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.my_port_var = tk.StringVar(value="8082")
        ttk.Entry(config_frame, textvariable=self.my_port_var, width=20).grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 启动/停止按钮
        self.start_button = ttk.Button(button_frame, text="启动服务", command=self.toggle_server)
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        # 状态标签
        self.status_label = ttk.Label(button_frame, text="服务状态: 未启动")
        self.status_label.grid(row=0, column=1, padx=(10, 0))
        
        # 日志输出框架
        log_frame = ttk.LabelFrame(main_frame, text="服务日志", padding="10")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        config_frame.columnconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def toggle_server(self):
        if not self.server_running:
            self.start_server()
        else:
            self.stop_server()
            
    def start_server(self):
        # 获取参数
        try:
            my_port = int(self.my_port_var.get())
            
                
            if not (1024 <= my_port <= 65535):
                messagebox.showerror("错误", "配置端口必须在1024-65535范围内")
                return
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return
            
        # 检查必需配置项
        mcp_url = self.mcp_url_var.get()
        model_name = self.model_name_var.get()
        api_key = self.api_key_var.get()
        base_url = self.base_url_var.get()
        
        missing_configs = []
        if not mcp_url:
            missing_configs.append("MCP URL")
        if not model_name:
            missing_configs.append("模型名称")
        if not api_key:
            missing_configs.append("API密钥")
        if not base_url:
            missing_configs.append("Base URL")
            
        if missing_configs:
            messagebox.showerror("配置错误", f"以下配置项缺失: {', '.join(missing_configs)}")
            return
            
        # 构建配置
        config = {
            "mcp": {
                "url": mcp_url
            },
            "model": {
                "model_name": model_name,
                "api_key": api_key,
                "base_url": base_url
            },
            "web_server": {
                "port": my_port
            }
        }
        
        # 在新线程中启动服务
        self.server_thread = threading.Thread(target=self.run_server, args=(my_port, config), daemon=True)
        self.server_thread.start()
        
        self.server_running = True
        self.start_button.config(text="停止服务")
        self.status_label.config(text="服务状态: 运行中")
        self.log_message("服务启动中...")
        
    def stop_server(self):
        # 停止服务
        self.server_running = False
        self.log_message("正在停止服务...")
        
        # 停止Web服务器
        if self.runner and self.loop:
            try:
                # 在新线程中停止服务器以避免阻塞UI
                stop_thread = threading.Thread(target=self._stop_server_async, daemon=True)
                stop_thread.start()
            except Exception as e:
                self.log_message(f"停止服务器时出错: {str(e)}")
                # 发生错误时也更新按钮状态
                self._update_stop_button_state()
        else:
            # 如果没有运行的服务器，直接更新按钮状态
            self._update_stop_button_state()
        
    def run_server(self, port, config):
        try:
            # 创建应用
            app, _ = create_app(config)
            
            # 创建runner来管理服务器生命周期
            self.runner = web.AppRunner(app)
            
            # 启动服务
            self.log_message(f"Web服务器已启动: http://localhost:{port}")
            
            # 在新线程中打开浏览器
            def open_browser():
                import time
                time.sleep(1)  # 等待服务器启动
                webbrowser.open(f"http://localhost:{port}")
            
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
            
            # 使用异步方式启动服务器
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.runner.setup())
            self.site = web.TCPSite(self.runner, 'localhost', port)
            self.loop.run_until_complete(self.site.start())
            
            # 保持服务器运行直到被停止
            try:
                self.loop.run_forever()
            except KeyboardInterrupt:
                pass
            finally:
                # 确保资源被正确清理
                if self.site:
                    try:
                        self.loop.run_until_complete(self.site.stop())
                    except:
                        pass  # 忽略停止站点时的错误
                if self.runner:
                    self.loop.run_until_complete(self.runner.cleanup())
                self.loop.close()
                
        except Exception as e:
            self.log_message(f"服务启动失败: {str(e)}")
            self.server_running = False
            self.start_button.config(text="启动服务")
            self.status_label.config(text="服务状态: 启动失败")
            
    def log_message(self, message):
        # 在主线程中更新UI
        self.root.after(0, self._update_log, message)
        
    def _update_stop_button_state(self):
        """更新停止按钮的状态"""
        self.start_button.config(text="启动服务")
        self.status_label.config(text="服务状态: 已停止")
        
    def _update_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def _stop_server_async(self):
        """异步停止服务器"""
        try:
            if self.runner and self.loop:
                # 在服务器运行的同一个事件循环中停止服务器
                def stop_server():
                    # 创建一个异步任务来停止服务器
                    async def shutdown():
                        # 关闭所有活跃的WebSocket连接
                        for ws in list(active_connections):
                            try:
                                await ws.close()
                            except:
                                pass  # 忽略关闭连接时的错误
                        
                        # 停止站点
                        if self.site:
                            try:
                                await self.site.stop()
                            except:
                                pass  # 忽略停止站点时的错误
                        
                        # 停止runner
                        try:
                            await self.runner.shutdown()
                        except:
                            pass  # 忽略关闭runner时的错误
                        
                        # 清理runner
                        try:
                            await self.runner.cleanup()
                        except:
                            pass  # 忽略清理runner时的错误
                    
                    # 在事件循环中运行关闭任务
                    try:
                        future = asyncio.run_coroutine_threadsafe(shutdown(), self.loop)
                        # 等待关闭任务完成，设置超时时间
                        future.result(timeout=5)
                    except Exception:
                        pass  # 即使关闭任务失败，也要继续停止事件循环
                    
                    # 停止事件循环
                    try:
                        self.loop.stop()
                    except:
                        pass  # 忽略停止事件循环时的错误
                
                # 使用服务器的事件循环来停止服务器
                self.loop.call_soon_threadsafe(stop_server)
                
                # 等待事件循环真正停止（最多等待5秒）
                import time
                start_time = time.time()
                while self.loop.is_running() and (time.time() - start_time) < 5:
                    time.sleep(0.1)
                
                # 如果事件循环仍在运行，强制清理
                try:
                    if self.loop.is_running():
                        self.loop.stop()
                except:
                    pass
                
                # 清理资源
                self.site = None
                self.runner = None
                self.loop = None
                self.log_message("Web服务器已完全停止")
                # 更新按钮状态
                self.root.after(0, self._update_stop_button_state)
            else:
                # 如果没有运行的服务器，直接更新按钮状态
                self.root.after(0, self._update_stop_button_state)
        except Exception as e:
            self.log_message(f"停止服务器时出错: {str(e)}")
            # 发生错误时也更新按钮状态
            self.root.after(0, self._update_stop_button_state)


if __name__ == "__main__":
    root = tk.Tk()
    app = WebServerGUI(root)
    root.mainloop()