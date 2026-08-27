"""
测试响应处理器
"""

import pytest
import json
from src.core.response_processor import ResponseProcessor
from src.core.models import MessageRole, ToolResult
from src.utils.errors import APIError

class TestResponseProcessor:
    """测试ResponseProcessor类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.processor = ResponseProcessor()
    
    def test_process_response_text_only(self):
        """测试处理纯文本响应"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello, how can I help you?"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18
            }
        }
        
        message, tool_calls = self.processor.process_response(response_data)
        
        assert message is not None
        assert message.role == MessageRole.ASSISTANT
        assert message.content == "Hello, how can I help you?"
        assert tool_calls is None
    
    def test_process_response_with_tool_calls(self):
        """测试处理包含工具调用的响应"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "execute_bash",
                                    "arguments": "{\"command\": \"ls -la\"}"
                                }
                            }
                        ]
                    },
                    "finish_reason": "tool_calls"
                }
            ]
        }
        
        message, tool_calls = self.processor.process_response(response_data)
        
        assert message is None  # 没有文本内容
        assert tool_calls is not None
        assert len(tool_calls) == 1
        
        tool_call = tool_calls[0]
        assert tool_call.call_id == "call_123"
        assert tool_call.tool_name == "execute_bash"
        assert tool_call.parameters == {"command": "ls -la"}
    
    def test_process_response_mixed_content(self):
        """测试处理包含文本和工具调用的响应"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "I'll help you list the files.",
                        "tool_calls": [
                            {
                                "id": "call_456",
                                "type": "function",
                                "function": {
                                    "name": "execute_bash",
                                    "arguments": "{\"command\": \"ls\"}"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        message, tool_calls = self.processor.process_response(response_data)
        
        assert message is not None
        assert message.content == "I'll help you list the files."
        assert tool_calls is not None
        assert len(tool_calls) == 1
    
    def test_process_response_invalid_structure(self):
        """测试处理无效结构的响应"""
        # 缺少choices字段
        response_data = {"error": "Invalid request"}
        
        with pytest.raises(APIError, match="AI响应结构无效"):
            self.processor.process_response(response_data)
    
    def test_process_response_empty_choices(self):
        """测试处理空choices的响应"""
        response_data = {"choices": []}
        
        with pytest.raises(APIError, match="AI响应结构无效"):
            self.processor.process_response(response_data)
    
    def test_extract_tool_calls_invalid_json(self):
        """测试提取包含无效JSON参数的工具调用"""
        message_data = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_789",
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "arguments": "invalid json"
                    }
                }
            ]
        }
        
        tool_calls = self.processor._extract_tool_calls(message_data)
        
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0].parameters == {}  # 应该回退到空字典
    
    def test_extract_tool_calls_missing_fields(self):
        """测试提取缺少字段的工具调用"""
        message_data = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_incomplete",
                    "type": "function",
                    # 缺少function字段
                }
            ]
        }
        
        tool_calls = self.processor._extract_tool_calls(message_data)
        
        # 应该跳过无效的工具调用
        assert tool_calls is None
    
    def test_create_tool_response_message_success(self):
        """测试创建成功的工具响应消息"""
        tool_result = ToolResult(
            call_id="call_123",
            success=True,
            result="file1.txt\nfile2.txt"
        )
        
        message = self.processor.create_tool_response_message(tool_result)
        
        assert message.role == MessageRole.TOOL
        assert message.content == "file1.txt\nfile2.txt"
        assert message.tool_call_id == "call_123"
    
    def test_create_tool_response_message_error(self):
        """测试创建错误的工具响应消息"""
        tool_result = ToolResult(
            call_id="call_456",
            success=False,
            result=None,
            error="Command not found"
        )
        
        message = self.processor.create_tool_response_message(tool_result)
        
        assert message.role == MessageRole.TOOL
        assert message.content == "错误: Command not found"
        assert message.tool_call_id == "call_456"
    
    def test_format_streaming_response(self):
        """测试格式化流式响应"""
        chunk = {
            "choices": [
                {
                    "delta": {
                        "content": "Hello"
                    }
                }
            ]
        }
        
        content = self.processor.format_streaming_response(chunk)
        assert content == "Hello"
    
    def test_format_streaming_response_no_content(self):
        """测试格式化没有内容的流式响应"""
        chunk = {
            "choices": [
                {
                    "delta": {}
                }
            ]
        }
        
        content = self.processor.format_streaming_response(chunk)
        assert content is None
    
    def test_extract_finish_reason(self):
        """测试提取完成原因"""
        response_data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop"
                }
            ]
        }
        
        reason = self.processor.extract_finish_reason(response_data)
        assert reason == "stop"
    
    def test_extract_usage_info(self):
        """测试提取使用信息"""
        response_data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello"}
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        
        usage = self.processor.extract_usage_info(response_data)
        assert usage is not None
        assert usage["total_tokens"] == 15
    
    def test_validate_tool_call_format_valid(self):
        """测试验证有效的工具调用格式"""
        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": "{}"
            }
        }
        
        assert self.processor.validate_tool_call_format(tool_call) is True
    
    def test_validate_tool_call_format_invalid(self):
        """测试验证无效的工具调用格式"""
        # 缺少必需字段
        tool_call = {
            "id": "call_123",
            "type": "function"
            # 缺少function字段
        }
        
        assert self.processor.validate_tool_call_format(tool_call) is False
        
        # 错误的type
        tool_call = {
            "id": "call_123",
            "type": "invalid_type",
            "function": {"name": "test"}
        }
        
        assert self.processor.validate_tool_call_format(tool_call) is False
        
        # function字段格式错误
        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": "invalid_function_data"
        }
        
        assert self.processor.validate_tool_call_format(tool_call) is False