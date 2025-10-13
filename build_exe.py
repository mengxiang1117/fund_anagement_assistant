#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将web_server_gui.py打包成exe文件的脚本
"""

import sys
import subprocess
from pathlib import Path

def get_project_root():
    """获取项目根目录"""
    return Path(__file__).parent

def install_requirements():
    """安装项目依赖"""
    project_root = get_project_root()
    requirements_file = project_root / "requirements.txt"
    
    if requirements_file.exists():
        print("正在安装项目依赖...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])
            print("依赖安装完成")
        except subprocess.CalledProcessError as e:
            print(f"依赖安装失败: {e}")
            return False
    else:
        print("未找到requirements.txt文件")
        
    # 确保PyInstaller已安装
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("PyInstaller安装完成")
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller安装失败: {e}")
        return False
        
    return True

def build_exe():
    """使用PyInstaller打包exe文件"""
    project_root = get_project_root()
    # 定义主脚本路径
    main_script = project_root / "web_server_gui.py"
    
    if not main_script.exists():
        print(f"主脚本文件不存在: {main_script}")
        return False
    
    sep = ";" if sys.platform == "win32" else ":"
        
    # 构建PyInstaller命令
    cmd = [
        "pyinstaller",
        "--noconfirm",  # 不需要确认
        "--onefile",    # 打包成单个exe文件
        "--windowed",   # Windows下不显示控制台窗口
        "--name", "基金管理工具",  # exe文件名
        "--icon", "NONE",  # 不使用图标
        "--add-data", f"{project_root / 'templates'}{sep}templates",  # 添加模板目录
        "--hidden-import", "aiohttp",
        "--hidden-import", "agentscope",
        "--hidden-import", "agentscope.agent",
        "--hidden-import", "agentscope.formatter",
        "--hidden-import", "agentscope.mcp",
        "--hidden-import", "agentscope.memory",
        "--hidden-import", "agentscope.message",
        "--hidden-import", "agentscope.model",
        "--hidden-import", "agentscope.tool",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "tkinter.scrolledtext",
        str(main_script)
    ]
    
    print("正在打包exe文件...")
    print("命令:", " ".join(cmd))
    
    try:
        # 运行PyInstaller
        result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("打包成功完成")
            # 显示生成的exe文件位置
            dist_dir = project_root / "dist"
            exe_file = dist_dir / "基金管理工具.exe"
            if exe_file.exists():
                print(f"生成的exe文件位置: {exe_file}")
            return True
        else:
            print("打包失败")
            print("错误输出:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"打包过程中发生错误: {e}")
        return False

def main():
    """主函数"""
    print("开始打包web_server_gui.py为exe文件")
    
    # 安装依赖
    # if not install_requirements():
    #     print("依赖安装失败，退出")
    #     return False
    
    # 打包exe
    if not build_exe():
        print("打包失败，退出")
        return False
        
    print("打包完成")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)