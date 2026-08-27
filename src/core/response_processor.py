"""
AI响应处理器

处理AI模型响应的解析、验证和转换。
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from .models import Message, MessageRole, ToolCall, ToolResult
from ..utils.errors import APIError
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ResponseProcessor:
    """AI响应处理器"""
    
    def __init__(self):
        pass
    
    def process_response(self, response_data: Dict) -> Tuple[Optional[Message], Optional[List[ToolCall]]]:
        """
        处理AI响应，返回消息和工具调用
        
        Args:
            response_data: AI API响应数据
            
        Returns:
            (消息对象, 工具调用列表) 的元组
        """
        if not self._validate_response_structure(response_data):
            raise APIError(
                "AI响应结构无效",
                details=f"响应格式不正确: {response_data}"
            )
        
        try:
            choice = response_data['choices'][0]
            message_data = choice['message']
            
            # 提取消息内容
            content = message_data.get('content', '') or ''
            
            # 创建消息对象
            message = Message(
                role=MessageRole.ASSISTANT,
                content=content
            ) if content else None
            
            # 提取工具调用
            tool_calls = self._extract_tool_calls(message_data)
            
            # 记录使用信息
            usage = response_data.get('usage')
            if usage:
                logger.debug(f"Token使用情况: {usage}")
            
            return message, tool_calls
            
        except (KeyError, IndexError, TypeError) as e:
            raise APIError(
                f"解析AI响应失败: {str(e)}",
                details=f"响应数据: {response_data}"
            )
    
    def _validate_response_structure(self, response_data: Dict) -> bool:
        """
        验证响应结构的完整性
        
        Args:
            response_data: 响应数据
            
        Returns:
            是否有效
        """
        if not isinstance(response_data, dict):
            return False
        
        # 检查choices字段
        if 'choices' not in response_data:
            return False
        
        choices = response_data['choices']
        if not isinstance(choices, list) or len(choices) == 0:
            return False
        
        # 检查第一个choice
        choice = choices[0]
        if not isinstance(choice, dict):
            return False
        
        # 检查message字段
        if 'message' not in choice:
            return False
        
        message = choice['message']
        if not isinstance(message, dict):
            return False
        
        # 检查role字段（必需）
        if 'role' not in message:
            return False
        
        return True
    
    def _extract_tool_calls(self, message_data: Dict) -> Optional[List[ToolCall]]:
        """
        从消息数据中提取工具调用
        
        Args:
            message_data: 消息数据
            
        Returns:
            工具调用列表，如果没有则返回None
        """
        tool_calls_data = message_data.get('tool_calls')
        if not tool_calls_data:
            return None
        
        tool_calls = []
        for tool_call_data in tool_calls_data:
            try:
                call_id = tool_call_data['id']
                function_data = tool_call_data['function']
                tool_name = function_data['name']
                
                # 解析参数
                arguments_str = function_data.get('arguments', '{}')
                try:
                    parameters = json.loads(arguments_str) if arguments_str else {}
                except json.JSONDecodeError:
                    logger.warning(f"工具调用参数JSON格式错误: {arguments_str}")
                    parameters = {}
                
                tool_call = ToolCall(
                    tool_name=tool_name,
                    parameters=parameters,
                    call_id=call_id
                )
                tool_calls.append(tool_call)
                
            except (KeyError, TypeError) as e:
                logger.error(f"解析工具调用失败: {e}, 数据: {tool_call_data}")
                continue
        
        return tool_calls if tool_calls else None
    
    def create_tool_response_message(self, tool_result: ToolResult) -> Message:
        """
        创建工具响应消息
        
        Args:
            tool_result: 工具执行结果
            
        Returns:
            工具响应消息
        """
        if tool_result.success:
            content = str(tool_result.result) if tool_result.result is not None else "操作完成"
        else:
            content = f"错误: {tool_result.error}" if tool_result.error else "操作失败"
        
        return Message(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_result.call_id
        )
    
    def format_streaming_response(self, chunk: Dict) -> Optional[str]:
        """
        处理流式响应块
        
        Args:
            chunk: 响应块数据
            
        Returns:
            内容片段，如果没有则返回None
        """
        try:
            if 'choices' not in chunk:
                return None
            
            choices = chunk['choices']
            if not choices:
                return None
            
            delta = choices[0].get('delta', {})
            content = delta.get('content')
            
            return content
            
        except (KeyError, IndexError, TypeError):
            return None
    
    def extract_finish_reason(self, response_data: Dict) -> Optional[str]:
        """
        提取完成原因
        
        Args:
            response_data: 响应数据
            
        Returns:
            完成原因字符串
        """
        try:
            choice = response_data['choices'][0]
            return choice.get('finish_reason')
        except (KeyError, IndexError, TypeError):
            return None
    
    def extract_usage_info(self, response_data: Dict) -> Optional[Dict[str, Any]]:
        """
        提取使用信息
        
        Args:
            response_data: 响应数据
            
        Returns:
            使用信息字典
        """
        return response_data.get('usage')
    
    def validate_tool_call_format(self, tool_call: Dict) -> bool:
        """
        验证工具调用格式
        
        Args:
            tool_call: 工具调用数据
            
        Returns:
            是否有效
        """
        required_fields = ['id', 'type', 'function']
        if not all(field in tool_call for field in required_fields):
            return False
        
        if tool_call['type'] != 'function':
            return False
        
        function_data = tool_call['function']
        if not isinstance(function_data, dict):
            return False
        
        if 'name' not in function_data:
            return False
        
        return True