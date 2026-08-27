"""
CLI交互界面

处理用户输入输出和终端交互。
"""

import sys
from typing import Optional
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import confirm
from prompt_toolkit.formatted_text import HTML
from ..utils.logging import get_logger

logger = get_logger(__name__)

class CLIInterface:
    """终端交互接口"""
    
    def __init__(self):
        self.running = False
    
    def display_welcome(self) -> None:
        """显示欢迎信息"""
        print("🤖 终端AI助手")
        print("=" * 50)
        print("欢迎使用智能终端助手！")
        print("输入您的问题或命令，我将为您提供帮助。")
        print("输入 'exit' 或 'quit' 退出程序。")
        print("=" * 50)
        print()
    
    def get_user_input(self) -> Optional[str]:
        """
        获取用户输入
        
        Returns:
            用户输入的字符串，如果用户要退出则返回None
        """
        try:
            # 检查是否在事件循环中运行
            import asyncio
            try:
                # 如果已经在事件循环中，使用标准input
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    user_input = input("👤 您: ").strip()
                else:
                    # 使用 prompt_toolkit
                    user_input = prompt(
                        HTML('<ansiblue>👤 您: </ansiblue>'),
                        enable_history_search=True
                    ).strip()
            except RuntimeError:
                # 没有运行的事件循环，可以安全使用 prompt_toolkit
                user_input = prompt(
                    HTML('<ansiblue>👤 您: </ansiblue>'),
                    enable_history_search=True
                ).strip()
            
            # 检查退出命令
            if user_input.lower() in ['exit', 'quit', 'bye', '退出']:
                return None
            
            return user_input
            
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 再见！")
            return None
        except Exception as e:
            print(f"❌ 输入错误: {e}")
            # 发生错误时返回空字符串而不是None，避免退出
            return ""
    
    def display_response(self, response: str) -> None:
        """
        显示AI响应
        
        Args:
            response: AI响应内容
        """
        if response:
            print(f"🤖 助手: {response}")
        print()
    
    def display_tool_usage(self, tool_name: str, command: str, purpose: str) -> None:
        """
        显示工具使用信息
        
        Args:
            tool_name: 工具名称
            command: 要执行的命令
            purpose: 执行目的
        """
        print(f"🛠️  Using tool: {tool_name}")
        print(" ⋮")
        print(f" ● I will run the following shell command:")
        print(f"   {command}")
        print(" ⋮")
        print(f" ↳ Purpose: {purpose}")
    
    def prompt_authorization(self, tool_name: str) -> str:
        """
        提示用户授权工具使用
        
        Args:
            tool_name: 工具名称
            
        Returns:
            用户选择 ('y', 'n', 't')
        """
        while True:
            try:
                # 检查是否在事件循环中运行
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        # 使用标准input
                        choice = input("Allow this action? Use 't' to trust (always allow) this tool for the session. [y/n/t]: ").strip().lower()
                    else:
                        # 使用 prompt_toolkit
                        choice = prompt(
                            "Allow this action? Use 't' to trust (always allow) this tool for the session. [y/n/t]: "
                        ).strip().lower()
                except RuntimeError:
                    # 没有运行的事件循环
                    choice = prompt(
                        "Allow this action? Use 't' to trust (always allow) this tool for the session. [y/n/t]: "
                    ).strip().lower()
                
                if choice in ['y', 'yes', '是']:
                    return 'y'
                if choice in ['n', 'no', '否']:
                    return 'n'
                if choice in ['t', 'trust', '信任']:
                    return 't'
                print("请输入 'y' (允许), 'n' (拒绝), 或 't' (信任)")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n操作已取消")
                return 'n'
    
    def display_tool_result(self, result: str, success: bool = True) -> None:
        """
        显示工具执行结果（简化版本）
        
        Args:
            result: 执行结果
            success: 是否成功
        """
        if result and result.strip():
            # 如果结果很长，进行适当的格式化
            lines = result.split('\n')
            if len(lines) > 20:
                print('\n'.join(lines[:10]))
                print(f"... (省略 {len(lines) - 20} 行) ...")
                print('\n'.join(lines[-10:]))
            else:
                print(result)
        elif success:
            print("✅ 命令执行成功")
        print()
    
    def display_error(self, error_message: str) -> None:
        """
        显示错误信息
        
        Args:
            error_message: 错误消息
        """
        print(f"❌ 错误: {error_message}")
        print()
    
    def display_warning(self, warning_message: str) -> None:
        """
        显示警告信息
        
        Args:
            warning_message: 警告消息
        """
        print(f"⚠️  警告: {warning_message}")
        print()
    
    def display_info(self, info_message: str) -> None:
        """
        显示信息
        
        Args:
            info_message: 信息内容
        """
        print(f"ℹ️  {info_message}")
        print()
    
    def display_thinking(self) -> None:
        """显示思考中的提示"""
        print("🤔 思考中...")
    
    def clear_thinking(self) -> None:
        """清除思考提示"""
        # 使用足够的空格来清除中文字符（中文字符占用更多空间）
        print("\r" + " " * 50 + "\r", end="", flush=True)
    
    def display_session_info(self, session_id: str, message_count: int) -> None:
        """
        显示会话信息
        
        Args:
            session_id: 会话ID
            message_count: 消息数量
        """
        short_id = session_id[:8] if session_id else "unknown"
        print(f"📝 会话 {short_id} | 消息数: {message_count}")
        print()
    
    def confirm_action(self, message: str) -> bool:
        """
        确认操作
        
        Args:
            message: 确认消息
            
        Returns:
            用户是否确认
        """
        try:
            # 使用简单的input避免事件循环问题
            choice = input(f"{message} [y/N]: ").strip().lower()
            return choice in ['y', 'yes', '是']
        except (KeyboardInterrupt, EOFError):
            return False
    
    def display_loading(self, message: str = "处理中") -> None:
        """
        显示加载提示
        
        Args:
            message: 加载消息
        """
        print(f"⏳ {message}...", end="", flush=True)
    
    def clear_loading(self) -> None:
        """清除加载提示"""
        print("\r" + " " * 50 + "\r", end="", flush=True)
    
    def display_goodbye(self) -> None:
        """显示告别信息"""
        print("👋 感谢使用终端AI助手，再见！")
    
    def handle_interrupt(self) -> None:
        """处理中断信号"""
        print("\n\n⚠️  检测到中断信号")
        if self.confirm_action("确定要退出吗？"):
            self.running = False
            self.display_goodbye()
            sys.exit(0)
        else:
            print("继续运行...")
    
    def start_session(self) -> None:
        """启动交互会话"""
        self.running = True
        self.display_welcome()
    
    def stop_session(self) -> None:
        """停止交互会话"""
        self.running = False
        self.display_goodbye()