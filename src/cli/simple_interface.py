"""
简化的CLI交互界面

使用标准input()函数，避免事件循环冲突问题。
"""

import sys
from typing import Optional
from ..utils.logging import get_logger

logger = get_logger(__name__)

class SimpleCLIInterface:
    """简化的终端交互接口"""
    
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
            # 使用readline来改善中文输入体验
            import readline
            
            # 设置输入编码为UTF-8
            import sys
            if hasattr(sys.stdin, 'reconfigure'):
                sys.stdin.reconfigure(encoding='utf-8')
            
            user_input = input("👤 您: ").strip()
            
            # 检查退出命令
            if user_input.lower() in ['exit', 'quit', 'bye', '退出']:
                return None
            
            return user_input
            
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 再见！")
            return None
        except Exception as e:
            print(f"❌ 输入错误: {e}")
            return ""
    
    def display_response(self, response: str) -> None:
        """显示AI响应"""
        if response:
            print(f"🤖 助手: {response}")
        print()
    
    def display_tool_usage(self, tool_name: str, command: str, purpose: str) -> None:
        """显示工具使用信息"""
        print(f"🛠️  Using tool: {tool_name}")
        print(" ⋮")
        print(" ● I will run the following shell command:")
        print(f"   {command}")
        print(" ⋮")
        print(f" ↳ Purpose: {purpose}")
    
    def prompt_authorization(self, tool_name: str) -> str:
        """提示用户授权工具使用"""
        while True:
            try:
                choice = input("Allow this action? Use 't' to trust (always allow) this tool for the session. [y/n/t]: ").strip().lower()
                
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
    
    def display_error(self, error_message: str) -> None:
        """显示错误信息"""
        print(f"❌ 错误: {error_message}")
        print()
    
    def display_info(self, info_message: str) -> None:
        """显示信息"""
        print(f"ℹ️  {info_message}")
        print()
    
    def display_thinking(self) -> None:
        """显示思考中的提示"""
        print("🤔 思考中...", end="", flush=True)
    
    def clear_thinking(self) -> None:
        """清除思考提示"""
        print("\r" + " " * 20 + "\r", end="", flush=True)
    
    def display_session_info(self, session_id: str, message_count: int) -> None:
        """显示会话信息"""
        short_id = session_id[:8] if session_id else "unknown"
        print(f"📝 会话 {short_id} | 消息数: {message_count}")
        print()
    
    def confirm_action(self, message: str) -> bool:
        """确认操作"""
        try:
            choice = input(f"{message} [y/N]: ").strip().lower()
            return choice in ['y', 'yes', '是']
        except (KeyboardInterrupt, EOFError):
            return False
    
    def display_loading(self, message: str = "处理中") -> None:
        """显示加载提示"""
        print(f"⏳ {message}...", end="", flush=True)
    
    def clear_loading(self) -> None:
        """清除加载提示"""
        print("\r" + " " * 30 + "\r", end="", flush=True)
    
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