"""
测试核心数据模型
"""

import pytest
from datetime import datetime
from src.core.models import (
    ModelConfig, MCPConfig, MCPServerConfig, 
    Message, Session, ToolCall, ToolResult, MessageRole
)

class TestModelConfig:
    """测试ModelConfig类"""
    
    def test_valid_config(self):
        """测试有效配置"""
        config = ModelConfig(
            api_url="https://api.example.com",
            api_key="test-key",
            model_name="test-model",
            temperature=0.5,
            timeout=60
        )
        assert config.api_url == "https://api.example.com"
        assert config.api_key == "test-key"
        assert config.model_name == "test-model"
        assert config.temperature == 0.5
        assert config.timeout == 60
    
    def test_default_values(self):
        """测试默认值"""
        config = ModelConfig(
            api_url="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )
        assert config.temperature == 0.01
        assert config.timeout == 30
        assert config.max_tokens is None
    
    def test_invalid_temperature(self):
        """测试无效的temperature值"""
        with pytest.raises(ValueError, match="Temperature必须在0-2之间"):
            ModelConfig(
                api_url="https://api.example.com",
                api_key="test-key",
                model_name="test-model",
                temperature=3.0
            )
    
    def test_empty_api_url(self):
        """测试空的API URL"""
        with pytest.raises(ValueError, match="API URL不能为空"):
            ModelConfig(
                api_url="",
                api_key="test-key",
                model_name="test-model"
            )
    
    def test_invalid_timeout(self):
        """测试无效的超时时间"""
        with pytest.raises(ValueError, match="超时时间必须大于0"):
            ModelConfig(
                api_url="https://api.example.com",
                api_key="test-key",
                model_name="test-model",
                timeout=0
            )

class TestMCPServerConfig:
    """测试MCPServerConfig类"""
    
    def test_valid_config(self):
        """测试有效配置"""
        config = MCPServerConfig(
            name="test-server",
            command="uvx",
            args=["test-package"],
            env={"TEST": "value"},
            disabled=False
        )
        assert config.name == "test-server"
        assert config.command == "uvx"
        assert config.args == ["test-package"]
        assert config.env == {"TEST": "value"}
        assert config.disabled is False
    
    def test_empty_name(self):
        """测试空的服务器名称"""
        with pytest.raises(ValueError, match="MCP服务器名称不能为空"):
            MCPServerConfig(
                name="",
                command="uvx",
                args=["test-package"]
            )

class TestMessage:
    """测试Message类"""
    
    def test_message_creation(self):
        """测试消息创建"""
        msg = Message(
            role=MessageRole.USER,
            content="Hello, world!"
        )
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello, world!"
        assert isinstance(msg.timestamp, datetime)
    
    def test_message_to_dict(self):
        """测试消息转换为字典"""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Hello back!"
        )
        result = msg.to_dict()
        assert result["role"] == "assistant"
        assert result["content"] == "Hello back!"
    
    def test_tool_message(self):
        """测试工具消息"""
        msg = Message(
            role=MessageRole.TOOL,
            content="Command executed",
            tool_call_id="call_123"
        )
        result = msg.to_dict()
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_123"

class TestSession:
    """测试Session类"""
    
    def test_session_creation(self):
        """测试会话创建"""
        session = Session(session_id="test-session")
        assert session.session_id == "test-session"
        assert len(session.messages) == 0
        assert len(session.trusted_tools) == 0
    
    def test_add_message(self):
        """测试添加消息"""
        session = Session(session_id="test-session")
        msg = Message(role=MessageRole.USER, content="Test")
        
        session.add_message(msg)
        assert len(session.messages) == 1
        assert session.messages[0] == msg
    
    def test_get_context_messages(self):
        """测试获取上下文消息"""
        session = Session(session_id="test-session")
        
        # 添加多条消息
        for i in range(5):
            msg = Message(role=MessageRole.USER, content=f"Message {i}")
            session.add_message(msg)
        
        context = session.get_context_messages(max_messages=3)
        assert len(context) == 3
        assert context[0]["content"] == "Message 2"  # 最近的3条消息

class TestToolCall:
    """测试ToolCall类"""
    
    def test_tool_call_creation(self):
        """测试工具调用创建"""
        call = ToolCall(
            tool_name="bash",
            parameters={"command": "ls -la"},
            call_id="call_123"
        )
        assert call.tool_name == "bash"
        assert call.parameters == {"command": "ls -la"}
        assert call.call_id == "call_123"
    
    def test_tool_call_to_dict(self):
        """测试工具调用转换为字典"""
        call = ToolCall(
            tool_name="bash",
            parameters={"command": "ls -la"},
            call_id="call_123"
        )
        result = call.to_dict()
        assert result["id"] == "call_123"
        assert result["type"] == "function"
        assert result["function"]["name"] == "bash"

class TestToolResult:
    """测试ToolResult类"""
    
    def test_successful_result(self):
        """测试成功的工具结果"""
        result = ToolResult(
            call_id="call_123",
            success=True,
            result="Command output"
        )
        assert result.success is True
        assert result.result == "Command output"
        assert result.error is None
    
    def test_failed_result(self):
        """测试失败的工具结果"""
        result = ToolResult(
            call_id="call_123",
            success=False,
            result=None,
            error="Command failed"
        )
        assert result.success is False
        assert result.error == "Command failed"
    
    def test_to_message(self):
        """测试转换为消息"""
        result = ToolResult(
            call_id="call_123",
            success=True,
            result="Success output"
        )
        msg = result.to_message()
        assert msg.role == MessageRole.TOOL
        assert msg.content == "Success output"
        assert msg.tool_call_id == "call_123"