"""
错误定义和异常类

定义了系统中使用的所有自定义异常类型。
"""

class AIAssistantError(Exception):
    """基础异常类"""
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class ConfigurationError(AIAssistantError):
    """配置错误 - 当配置文件格式错误或缺少必要配置时抛出"""
    pass

class APIError(AIAssistantError):
    """API调用错误 - 当AI模型API调用失败时抛出"""
    def __init__(self, message: str, status_code: int = None, details: str = None):
        self.status_code = status_code
        super().__init__(message, details)

class ToolExecutionError(AIAssistantError):
    """工具执行错误 - 当工具执行失败时抛出"""
    def __init__(self, message: str, tool_name: str = None, details: str = None):
        self.tool_name = tool_name
        super().__init__(message, details)

class SessionError(AIAssistantError):
    """会话错误 - 当会话管理出现问题时抛出"""
    def __init__(self, message: str, session_id: str = None, details: str = None):
        self.session_id = session_id
        super().__init__(message, details)

class NetworkError(AIAssistantError):
    """网络错误 - 当网络连接失败时抛出"""
    pass

class TimeoutError(AIAssistantError):
    """超时错误 - 当操作超时时抛出"""
    def __init__(self, message: str, timeout_seconds: int = None, details: str = None):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, details)