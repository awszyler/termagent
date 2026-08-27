"""
核心数据模型

定义了系统中使用的所有数据结构和模型类。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from enum import Enum

@dataclass
class ModelConfig:
    """AI模型配置"""
    api_url: str
    api_key: str
    model_name: str
    temperature: float = 0.01
    timeout: int = 30
    max_tokens: Optional[int] = None
    
    def __post_init__(self):
        """验证配置参数"""
        if not self.api_url:
            raise ValueError("API URL不能为空")
        if not self.api_key:
            raise ValueError("API密钥不能为空")
        if not self.model_name:
            raise ValueError("模型名称不能为空")
        if not 0 <= self.temperature <= 2:
            raise ValueError("Temperature必须在0-2之间")
        if self.timeout <= 0:
            raise ValueError("超时时间必须大于0")

@dataclass
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    disabled: bool = False
    
    def __post_init__(self):
        """验证配置参数"""
        if not self.name:
            raise ValueError("MCP服务器名称不能为空")
        if not self.command:
            raise ValueError("MCP服务器命令不能为空")

@dataclass
class MCPConfig:
    """MCP配置"""
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)

class MessageRole(Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"

@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典格式，用于API调用"""
        result = {
            "role": self.role.value,
            "content": self.content
        }
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result

@dataclass
class Session:
    """会话数据"""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    trusted_tools: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    def add_message(self, message: Message) -> None:
        """添加消息到会话"""
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_context_messages(self, max_messages: int = 50) -> List[Dict]:
        """获取用于API调用的消息上下文"""
        # 获取最近的消息，但保持对话的完整性
        recent_messages = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [msg.to_dict() for msg in recent_messages]

@dataclass
class ToolCall:
    """工具调用"""
    tool_name: str
    parameters: Dict[str, Any]
    call_id: str
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "id": self.call_id,
            "type": "function",
            "function": {
                "name": self.tool_name,
                "arguments": self.parameters
            }
        }

@dataclass
class ToolResult:
    """工具执行结果"""
    call_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: Optional[float] = None
    
    def to_message(self) -> Message:
        """转换为工具消息"""
        content = str(self.result) if self.success else f"Error: {self.error}"
        return Message(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=self.call_id
        )

class ToolDefinition:
    """工具定义"""
    def __init__(self, name: str, description: str, parameters: Dict):
        self.name = name
        self.description = description
        self.parameters = parameters
    
    def to_dict(self) -> Dict:
        """转换为API格式的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }