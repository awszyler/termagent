"""
错误处理框架

提供统一的错误处理和恢复机制。
"""

import asyncio
import logging
from typing import Optional, Callable, Any
from .errors import (
    AIAssistantError, ConfigurationError, APIError, 
    ToolExecutionError, SessionError, NetworkError, TimeoutError
)

logger = logging.getLogger(__name__)

class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.error_callbacks = {}
    
    def register_callback(self, error_type: type, callback: Callable):
        """注册错误回调函数"""
        self.error_callbacks[error_type] = callback
    
    async def handle_error(self, error: Exception, context: str = None) -> Optional[Any]:
        """处理错误并尝试恢复"""
        error_type = type(error)
        
        # 记录错误
        logger.error(f"Error in {context}: {error}", exc_info=True)
        
        # 查找并执行回调
        if error_type in self.error_callbacks:
            try:
                return await self.error_callbacks[error_type](error, context)
            except Exception as callback_error:
                logger.error(f"Error in callback for {error_type}: {callback_error}")
        
        # 默认处理
        return await self._default_error_handling(error, context)
    
    async def _default_error_handling(self, error: Exception, context: str = None) -> None:
        """默认错误处理"""
        if isinstance(error, ConfigurationError):
            print(f"❌ 配置错误: {error.message}")
            if error.details:
                print(f"   详情: {error.details}")
        
        elif isinstance(error, APIError):
            print(f"❌ API调用失败: {error.message}")
            if error.status_code:
                print(f"   状态码: {error.status_code}")
        
        elif isinstance(error, NetworkError):
            print(f"❌ 网络连接失败: {error.message}")
            print("   请检查网络连接并重试")
        
        elif isinstance(error, TimeoutError):
            print(f"❌ 操作超时: {error.message}")
            if error.timeout_seconds:
                print(f"   超时时间: {error.timeout_seconds}秒")
        
        elif isinstance(error, ToolExecutionError):
            print(f"❌ 工具执行失败: {error.message}")
            if error.tool_name:
                print(f"   工具: {error.tool_name}")
        
        elif isinstance(error, SessionError):
            print(f"❌ 会话错误: {error.message}")
            if error.session_id:
                print(f"   会话ID: {error.session_id}")
        
        else:
            print(f"❌ 未知错误: {str(error)}")
    
    def handle_api_timeout(self, error: asyncio.TimeoutError, context: str = None) -> None:
        """处理API超时"""
        print("⏰ API请求超时，请稍后重试")
        print("   如果问题持续存在，请检查网络连接或增加超时时间")
    
    def handle_network_error(self, error: Exception, context: str = None) -> None:
        """处理网络错误"""
        print("🌐 网络连接失败")
        print("   请检查:")
        print("   - 网络连接是否正常")
        print("   - API端点是否可访问")
        print("   - 防火墙设置是否正确")
    
    def handle_tool_error(self, tool_name: str, error: Exception, context: str = None) -> None:
        """处理工具执行错误"""
        print(f"🔧 工具 '{tool_name}' 执行失败: {str(error)}")
    
    def handle_config_error(self, error: ConfigurationError, context: str = None) -> None:
        """处理配置错误"""
        print("⚙️ 配置文件错误:")
        print(f"   {error.message}")
        if error.details:
            print(f"   详情: {error.details}")
        print("   请检查配置文件格式和内容")

# 全局错误处理器实例
global_error_handler = ErrorHandler()