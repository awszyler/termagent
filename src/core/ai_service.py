"""
AI服务层

处理与AI模型API的通信和响应处理。
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from .models import ModelConfig, ToolDefinition
from .reasoning import ReasoningChain
from ..utils.errors import APIError, NetworkError, TimeoutError as CustomTimeoutError
from ..utils.logging import get_logger

logger = get_logger(__name__)

class AIService:
    """AI模型服务接口"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        
        # 推理链
        self.reasoning_chain = ReasoningChain()
        
        # 增强的系统提示
        self.enhanced_system_prompt = """你是一个智能AI助手，具备强大的推理能力：

1. 系统性思考：
   - 将复杂问题分解为子步骤
   - 每步验证结果，根据反馈调整策略
   - 保持目标导向，灵活调整方法

2. 错误恢复：
   - 分析错误原因，不是简单重试
   - 寻找替代方案和工具
   - 从失败中学习，优化后续步骤

3. 结果整合：
   - 将分散的信息组织成有意义的洞察
   - 提供可执行的建议和具体步骤
   - 量化影响和预期结果

请用中文回复，保持友好和专业的语调。"""
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.config.api_key}'
                }
            )
    
    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def generate_response(
        self, 
        messages: List[Dict], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> Dict:
        """
        生成AI响应
        
        Args:
            messages: 对话消息列表
            tools: 可用工具列表
            
        Returns:
            AI响应字典
        """
        await self._ensure_session()
        
        # 增强消息以包含推理上下文
        enhanced_messages = self._enhance_messages_with_reasoning(messages)
        
        payload = self._build_request_payload(enhanced_messages, tools)
        
        try:
            response_data = await self._make_api_request(payload)
            logger.debug(f"AI响应: {response_data}")
            return response_data
            
        except asyncio.TimeoutError:
            raise CustomTimeoutError(
                "AI API请求超时",
                timeout_seconds=self.config.timeout,
                details=f"请求超过 {self.config.timeout} 秒未响应"
            )
        except aiohttp.ClientError as e:
            raise NetworkError(
                f"网络连接失败: {str(e)}",
                details="请检查网络连接和API端点是否可访问"
            )
        except Exception as e:
            raise APIError(
                f"AI API调用失败: {str(e)}",
                details="请检查API配置和网络连接"
            )
    
    def _enhance_messages_with_reasoning(self, messages: List[Dict]) -> List[Dict]:
        """使用推理上下文增强消息"""
        enhanced_messages = messages.copy()
        
        # 如果有推理历史，添加到系统消息中
        reasoning_context = self.reasoning_chain.get_context_prompt()
        if reasoning_context and enhanced_messages:
            # 找到系统消息或创建一个
            system_message_found = False
            for msg in enhanced_messages:
                if msg.get('role') == 'system':
                    msg['content'] = f"{self.enhanced_system_prompt}\n\n{reasoning_context}\n{msg['content']}"
                    system_message_found = True
                    break
            
            if not system_message_found:
                # 在开头插入系统消息
                enhanced_messages.insert(0, {
                    'role': 'system',
                    'content': f"{self.enhanced_system_prompt}\n\n{reasoning_context}"
                })
        
        return enhanced_messages
    
    def add_reasoning_step(self, action: str, result: Any, reasoning: str):
        """添加推理步骤"""
        self.reasoning_chain.add_step(action, result, reasoning)
    
    def clear_reasoning_chain(self):
        """清空推理链"""
        self.reasoning_chain.clear()
    
    def _build_request_payload(
        self, 
        messages: List[Dict], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> Dict:
        """
        构建API请求载荷
        
        Args:
            messages: 对话消息列表
            tools: 可用工具列表
            
        Returns:
            请求载荷字典
        """
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature
        }
        
        # 添加最大token数限制
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens
        
        # 添加工具定义
        if tools:
            payload["tools"] = [tool.to_dict() for tool in tools]
            payload["tool_choice"] = "auto"  # 让模型自动决定是否使用工具
        
        logger.debug(f"API请求载荷: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        return payload
    
    async def _make_api_request(self, payload: Dict) -> Dict:
        """
        发送API请求
        
        Args:
            payload: 请求载荷
            
        Returns:
            API响应数据
        """
        if not self._session:
            raise RuntimeError("HTTP会话未初始化")
        
        try:
            async with self._session.post(
                self.config.api_url,
                json=payload
            ) as response:
                
                # 检查HTTP状态码
                if response.status == 401:
                    raise APIError(
                        "API认证失败",
                        status_code=401,
                        details="请检查API密钥是否正确"
                    )
                elif response.status == 403:
                    raise APIError(
                        "API访问被拒绝",
                        status_code=403,
                        details="请检查API密钥权限"
                    )
                elif response.status == 429:
                    raise APIError(
                        "API请求频率限制",
                        status_code=429,
                        details="请稍后重试"
                    )
                elif response.status >= 500:
                    raise APIError(
                        "API服务器错误",
                        status_code=response.status,
                        details="API服务器暂时不可用"
                    )
                elif response.status != 200:
                    error_text = await response.text()
                    raise APIError(
                        f"API请求失败",
                        status_code=response.status,
                        details=error_text
                    )
                
                # 解析响应
                try:
                    response_data = await response.json()
                except json.JSONDecodeError as e:
                    response_text = await response.text()
                    raise APIError(
                        "API响应格式错误",
                        details=f"无法解析JSON响应: {response_text[:200]}"
                    )
                
                # 验证响应结构
                if not self._validate_response(response_data):
                    raise APIError(
                        "API响应结构无效",
                        details=f"响应缺少必要字段: {response_data}"
                    )
                
                return response_data
                
        except aiohttp.ClientError as e:
            raise NetworkError(
                f"HTTP请求失败: {str(e)}",
                details="请检查网络连接和API端点"
            )
    
    def _validate_response(self, response_data: Dict) -> bool:
        """
        验证API响应结构
        
        Args:
            response_data: API响应数据
            
        Returns:
            是否有效
        """
        # 检查基本结构
        if not isinstance(response_data, dict):
            return False
        
        # 检查choices字段
        if 'choices' not in response_data:
            return False
        
        choices = response_data['choices']
        if not isinstance(choices, list) or len(choices) == 0:
            return False
        
        # 检查第一个choice的结构
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return False
        
        # 检查message字段
        if 'message' not in first_choice:
            return False
        
        message = first_choice['message']
        if not isinstance(message, dict):
            return False
        
        # 检查role和content字段
        if 'role' not in message:
            return False
        
        # content可能为空（当有工具调用时）
        # tool_calls是可选的
        
        return True
    
    def extract_message_content(self, response_data: Dict) -> str:
        """
        从API响应中提取消息内容
        
        Args:
            response_data: API响应数据
            
        Returns:
            消息内容
        """
        try:
            message = response_data['choices'][0]['message']
            return message.get('content', '') or ''
        except (KeyError, IndexError, TypeError):
            return ''
    
    def extract_tool_calls(self, response_data: Dict) -> Optional[List[Dict]]:
        """
        从API响应中提取工具调用
        
        Args:
            response_data: API响应数据
            
        Returns:
            工具调用列表，如果没有则返回None
        """
        try:
            message = response_data['choices'][0]['message']
            return message.get('tool_calls')
        except (KeyError, IndexError, TypeError):
            return None
    
    def get_usage_info(self, response_data: Dict) -> Optional[Dict]:
        """
        从API响应中提取使用信息
        
        Args:
            response_data: API响应数据
            
        Returns:
            使用信息字典
        """
        return response_data.get('usage')