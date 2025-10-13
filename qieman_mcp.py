# -*- coding: utf-8 -*-
"""
基金管理工具
基于AgentScope框架和qieman-mcp服务
"""

import asyncio
import json
from typing import Dict, Any


from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.mcp import HttpStatelessClient
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit


def load_config():
    """加载配置文件 config.json"""
    config = {}
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("警告：未找到 config.json 文件")
    except json.JSONDecodeError:
        print("警告：config.json 文件格式错误")
    
    return config

class QiemanFundManager:
    """基金管理助手"""

    def __init__(self, config=None):
        # 使用传入的配置或默认空配置
        self.config = config
        
        # 初始化MCP客户端：指向qieman-mcp服务
        self.mcp_client = HttpStatelessClient(
            name="qieman_mcp",
            transport="sse",
            url=self.config["mcp"]["url"],
        )

        self.toolkit = Toolkit()
        self.agent = None

    async def initialize_tools(self) -> None:
        """初始化基金管理MCP工具"""
        await self.toolkit.register_mcp_client(self.mcp_client)
        #tools = self.toolkit.get_json_schemas()
        # print(f"已注册 {len(tools)} 个基金管理MCP工具")
        # for tool in tools:
        #     name = tool["function"]["name"]
        #     desc = tool["function"].get("description", "")
        #     print(f"- {name}: {desc}")

    async def initialize_agent(self) -> None:
        """初始化基金管理Agent"""
        if not self.toolkit.get_json_schemas():
            await self.initialize_tools()

        # 如果agent已存在，不需要重新创建
        if self.agent is not None:
            return
        
        model_config = self.config["model"]

        self.agent = ReActAgent(
            name="FundManager",
            sys_prompt=(
                "你是一位专业的基金管理顾问，擅长基金分析、投资组合管理和投资建议。\n"
                "你的任务是：\n"
                "1. 帮助用户查询基金信息、净值、涨跌幅等数据；\n"
                "2. 分析用户的基金持仓情况，提供投资建议；\n"
                "3. 根据市场情况，推荐合适的基金产品；\n"
                "4. 提供基金投资策略和风险管理建议；\n"
                "5. 你**必须先调用工具获取最新数据**，再进行分析和建议。\n"
                "6. 输出要求：Markdown格式。\n"
                "可用工具：\n"
                "\n".join([f"- {tool['function']['name']}: {tool['function'].get('description', '')}"
                           for tool in self.toolkit.get_json_schemas()])
            ),
            model=OpenAIChatModel(
                model_name=model_config["model_name"],
                api_key=model_config["api_key"],
                client_args={"base_url": model_config["base_url"]},
            ),
            memory=InMemoryMemory(),
            formatter=OpenAIChatFormatter(),
            toolkit=self.toolkit,
            parallel_tool_calls=True,
        )

    async def process_user_query(
        self,
        user_question: str,
    ) -> Dict[str, Any]:
        """处理用户关于基金的任何问题"""
        if self.agent is None:
            await self.initialize_agent()
            
        res = await self.agent(
            Msg("user", user_question, "user"),
        )

        return {"status": "completed", "response": res.content}

async def main(question: str, callback=None, config=None):
    """
    处理用户问题并返回结果
    
    Args:
        question: 用户问题
        callback: 回调函数，用于接收中间输出
        config: 配置参数
    
    Returns:
        str: 最终结果
    """
    try:
        fund_manager = QiemanFundManager(config)
        
        # 发送开始处理信号
        if callback:
            await callback("开始分析，请稍等，预测等待2分钟...")
        
        # 处理用户问题    
        res = await fund_manager.process_user_query(
            user_question=question
            )
        
        # 发送完成信号
        if callback:
            await callback("分析完成，生成回复...")
            
        return res["response"]
        
    except Exception as e:
        error_msg = f"处理过程中发生错误: {str(e)}"
        if callback:
            await callback(error_msg)
        return error_msg



if __name__ == "__main__":
    question = "查询易方达蓝筹精选基金的规模和持有人结构，然后输出pdf"
    question = "查询易方达蓝筹精选基金的业绩表现"
    config = load_config()
    res = asyncio.run(main(question, None, config))
    print(res)

