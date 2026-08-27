"""
测试AI服务层
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
from src.core.ai_service import AIService
from src.core.models import ModelConfig, ToolDefinition
from src.utils.errors import APIError, NetworkError, TimeoutError

class TestAIService:
    """测试AIService类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.config = ModelConfig(
            api_url="https://api.example.com/v1/chat/completions",
            api_key="test-key",
            model_name="test-model",
            temperature=0.5,
            timeout=30
        )
        self.ai_service = AIService(self.config)
    
    def test_build_request_payload_basic(self):
        """测试构建基本请求载荷"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        
        payload = self.ai_service._build_request_payload(messages)
        
        assert payload["model"] == "test-model"
        assert payload["messages"] == messages
        assert payload["temperature"] == 0.5
        assert "tools" not in payload
    
    def test_build_request_payload_with_tools(self):
        """测试构建包含工具的请求载荷"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        
        tools = [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters={"type": "object", "properties": {}}
            )
        ]
        
        payload = self.ai_service._build_request_payload(messages, tools)
        
        assert "tools" in payload
        assert len(payload["tools"]) == 1
        assert payload["tool_choice"] == "auto"
        assert payload["tools"][0]["function"]["name"] == "test_tool"
    
    def test_build_request_payload_with_max_tokens(self):
        """测试构建包含最大token数的请求载荷"""
        config = ModelConfig(
            api_url="https://api.example.com",
            api_key="test-key",
            model_name="test-model",
            max_tokens=1000
        )
        ai_service = AIService(config)
        
        messages = [{"role": "user", "content": "Hello"}]
        payload = ai_service._build_request_payload(messages)
        
        assert payload["max_tokens"] == 1000
    
    def test_validate_response_valid(self):
        """测试验证有效响应"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello back!"
                    }
                }
            ]
        }
        
        assert self.ai_service._validate_response(response_data) is True
    
    def test_validate_response_invalid_structure(self):
        """测试验证无效响应结构"""
        # 缺少choices字段
        response_data = {"error": "Invalid request"}
        assert self.ai_service._validate_response(response_data) is False
        
        # choices为空列表
        response_data = {"choices": []}
        assert self.ai_service._validate_response(response_data) is False
        
        # 缺少message字段
        response_data = {"choices": [{"index": 0}]}
        assert self.ai_service._validate_response(response_data) is False
        
        # message缺少role字段
        response_data = {"choices": [{"message": {"content": "test"}}]}
        assert self.ai_service._validate_response(response_data) is False
    
    def test_extract_message_content(self):
        """测试提取消息内容"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello back!"
                    }
                }
            ]
        }
        
        content = self.ai_service.extract_message_content(response_data)
        assert content == "Hello back!"
    
    def test_extract_message_content_empty(self):
        """测试提取空消息内容"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None
                    }
                }
            ]
        }
        
        content = self.ai_service.extract_message_content(response_data)
        assert content == ""
    
    def test_extract_tool_calls(self):
        """测试提取工具调用"""
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
                                    "name": "test_tool",
                                    "arguments": "{\"param\": \"value\"}"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        tool_calls = self.ai_service.extract_tool_calls(response_data)
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_123"
    
    def test_extract_tool_calls_none(self):
        """测试提取不存在的工具调用"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello back!"
                    }
                }
            ]
        }
        
        tool_calls = self.ai_service.extract_tool_calls(response_data)
        assert tool_calls is None
    
    def test_get_usage_info(self):
        """测试获取使用信息"""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello back!"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        
        usage = self.ai_service.get_usage_info(response_data)
        assert usage is not None
        assert usage["total_tokens"] == 15
    
    @pytest.mark.asyncio
    async def test_make_api_request_success(self):
        """测试成功的API请求"""
        payload = {"model": "test", "messages": []}
        
        # 模拟成功的HTTP响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Test response"
                    }
                }
            ]
        })
        
        # 创建正确的异步上下文管理器mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        # 模拟aiohttp会话
        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_context)
        
        self.ai_service._session = mock_session
        
        result = await self.ai_service._make_api_request(payload)
        
        assert "choices" in result
        assert result["choices"][0]["message"]["content"] == "Test response"
    
    @pytest.mark.asyncio
    async def test_make_api_request_auth_error(self):
        """测试API认证错误"""
        payload = {"model": "test", "messages": []}
        
        # 模拟401认证错误
        mock_response = AsyncMock()
        mock_response.status = 401
        
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_context)
        
        self.ai_service._session = mock_session
        
        with pytest.raises(APIError, match="API认证失败"):
            await self.ai_service._make_api_request(payload)
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试异步上下文管理器"""
        with patch.object(self.ai_service, '_ensure_session') as mock_ensure:
            with patch.object(self.ai_service, 'close') as mock_close:
                async with self.ai_service:
                    pass
                
                mock_ensure.assert_called_once()
                mock_close.assert_called_once()