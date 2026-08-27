"""
工具管理器

管理内置工具和外部MCP工具的注册、发现和执行。
"""

import asyncio
from typing import Dict, List, Optional, Any, Set, Callable
from ..core.models import ToolDefinition, ToolCall, ToolResult
from ..utils.errors import ToolExecutionError
from ..utils.logging import get_logger
from .bash_tool import BashTool

logger = get_logger(__name__)

class ToolManager:
    """工具管理器"""
    
    def __init__(self, ai_service=None):
        """初始化工具管理器"""
        self._tools: Dict[str, Any] = {}  # 工具名称 -> 工具实例
        self._tool_definitions: Dict[str, ToolDefinition] = {}  # 工具名称 -> 工具定义
        self._mcp_clients: Dict[str, Any] = {}  # MCP客户端
        self._running = False
        self.ai_service = ai_service  # 用于推理链记录
    
    async def start(self):
        """启动工具管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 注册内置工具
        await self._register_builtin_tools()
        
        logger.info("工具管理器已启动")
    
    async def stop(self):
        """停止工具管理器"""
        if not self._running:
            return
        
        self._running = False
        
        # 断开MCP客户端连接
        for client_name, client in self._mcp_clients.items():
            try:
                if hasattr(client, 'disconnect'):
                    await client.disconnect()
                logger.info(f"MCP客户端 {client_name} 已断开")
            except Exception as e:
                logger.error(f"断开MCP客户端 {client_name} 失败: {e}")
        
        self._mcp_clients.clear()
        logger.info("工具管理器已停止")
    
    async def _register_builtin_tools(self):
        """注册内置工具"""
        # 注册Bash工具
        bash_tool = BashTool()
        await self.register_tool("execute_bash", bash_tool)
        
        logger.info("内置工具注册完成")
    
    async def register_tool(self, name: str, tool_instance: Any):
        """
        注册工具
        
        Args:
            name: 工具名称
            tool_instance: 工具实例，必须有get_tool_definition()和execute()方法
        """
        if not hasattr(tool_instance, 'get_tool_definition'):
            raise ValueError(f"工具 {name} 缺少 get_tool_definition 方法")
        
        if not hasattr(tool_instance, 'execute'):
            raise ValueError(f"工具 {name} 缺少 execute 方法")
        
        # 获取工具定义
        try:
            definition = tool_instance.get_tool_definition()
            if not isinstance(definition, ToolDefinition):
                raise ValueError(f"工具 {name} 的 get_tool_definition 返回值不是 ToolDefinition 类型")
        except Exception as e:
            raise ValueError(f"获取工具 {name} 定义失败: {e}")
        
        # 注册工具
        self._tools[name] = tool_instance
        self._tool_definitions[name] = definition
        
        logger.info(f"工具 '{name}' 注册成功")
    
    def unregister_tool(self, name: str):
        """
        取消注册工具
        
        Args:
            name: 工具名称
        """
        if name in self._tools:
            del self._tools[name]
            del self._tool_definitions[name]
            logger.info(f"工具 '{name}' 已取消注册")
    
    def get_available_tools(self) -> List[ToolDefinition]:
        """
        获取可用工具列表
        
        Returns:
            工具定义列表
        """
        return list(self._tool_definitions.values())
    
    def get_tool_names(self) -> Set[str]:
        """
        获取工具名称集合
        
        Returns:
            工具名称集合
        """
        return set(self._tools.keys())
    
    def has_tool(self, name: str) -> bool:
        """
        检查工具是否存在
        
        Args:
            name: 工具名称
            
        Returns:
            是否存在
        """
        return name in self._tools
    
    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """
        获取工具定义
        
        Args:
            name: 工具名称
            
        Returns:
            工具定义，如果不存在则返回None
        """
        return self._tool_definitions.get(name)
    
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        执行工具
        
        Args:
            tool_call: 工具调用对象
            
        Returns:
            工具执行结果
        """
        tool_name = tool_call.tool_name
        
        if not self.has_tool(tool_name):
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                result=None,
                error=f"工具 '{tool_name}' 不存在"
            )
        
        tool_instance = self._tools[tool_name]
        
        try:
            # 执行工具
            result = await tool_instance.execute(tool_call.parameters)
            
            # 确保结果包含正确的call_id
            if hasattr(result, 'call_id'):
                result.call_id = tool_call.call_id
            
            logger.debug(f"工具 '{tool_name}' 执行完成: success={result.success}")
            return result
            
        except Exception as e:
            logger.error(f"工具 '{tool_name}' 执行失败: {e}")
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                result=None,
                error=f"工具执行异常: {str(e)}"
            )
    
    async def execute_tool_with_reasoning(
        self, 
        tool_call: ToolCall, 
        reasoning_context: Optional[str] = None
    ) -> ToolResult:
        """
        带推理的工具执行
        
        Args:
            tool_call: 工具调用信息
            reasoning_context: 推理上下文
            
        Returns:
            工具执行结果
        """
        tool_name = tool_call.tool_name
        
        try:
            # 执行工具
            result = await self.execute_tool(tool_call)
            
            # 记录成功的推理步骤
            if self.ai_service and result.success:
                success_reasoning = f"成功执行{tool_name}，获得预期结果"
                if reasoning_context:
                    success_reasoning = f"{reasoning_context} -> {success_reasoning}"
                
                self.ai_service.add_reasoning_step(
                    f"{tool_name}({tool_call.parameters})",
                    result.result,
                    success_reasoning
                )
            elif self.ai_service and not result.success:
                # 记录失败的推理步骤
                error_reasoning = f"{tool_name}执行失败: {result.error}，需要分析原因并调整策略"
                if reasoning_context:
                    error_reasoning = f"{reasoning_context} -> {error_reasoning}"
                
                self.ai_service.add_reasoning_step(
                    f"{tool_name}({tool_call.parameters})",
                    f"错误: {result.error}",
                    error_reasoning
                )
            
            return result
            
        except Exception as e:
            # 记录异常的推理步骤
            if self.ai_service:
                error_reasoning = f"{tool_name}执行异常: {str(e)}，需要分析原因并调整策略"
                if reasoning_context:
                    error_reasoning = f"{reasoning_context} -> {error_reasoning}"
                
                self.ai_service.add_reasoning_step(
                    f"{tool_name}({tool_call.parameters})",
                    f"异常: {e}",
                    error_reasoning
                )
            
            # 重新抛出异常让上层处理
            raise
    
    async def execute_multiple_tools(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        并行执行多个工具
        
        Args:
            tool_calls: 工具调用列表
            
        Returns:
            工具执行结果列表
        """
        if not tool_calls:
            return []
        
        # 创建执行任务
        tasks = [
            self.execute_tool(tool_call)
            for tool_call in tool_calls
        ]
        
        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ToolResult(
                    call_id=tool_calls[i].call_id,
                    success=False,
                    result=None,
                    error=f"工具执行异常: {str(result)}"
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具信息
        
        Args:
            name: 工具名称
            
        Returns:
            工具信息字典
        """
        if not self.has_tool(name):
            return None
        
        definition = self._tool_definitions[name]
        tool_instance = self._tools[name]
        
        info = {
            "name": definition.name,
            "description": definition.description,
            "parameters": definition.parameters,
            "type": "builtin" if name in ["execute_bash"] else "mcp"
        }
        
        # 如果工具有额外信息方法，调用它
        if hasattr(tool_instance, 'get_tool_info'):
            try:
                extra_info = tool_instance.get_tool_info()
                if isinstance(extra_info, dict):
                    info.update(extra_info)
            except Exception as e:
                logger.warning(f"获取工具 {name} 额外信息失败: {e}")
        
        return info
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有工具的信息
        
        Returns:
            工具信息列表
        """
        tools_info = []
        for name in self._tools.keys():
            info = self.get_tool_info(name)
            if info:
                tools_info.append(info)
        
        return tools_info
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """
        按类别获取工具
        
        Args:
            category: 工具类别 ("builtin", "mcp")
            
        Returns:
            工具名称列表
        """
        tools = []
        for name in self._tools.keys():
            info = self.get_tool_info(name)
            if info and info.get("type") == category:
                tools.append(name)
        
        return tools
    
    async def validate_tool_call(self, tool_call: ToolCall) -> Dict[str, Any]:
        """
        验证工具调用
        
        Args:
            tool_call: 工具调用对象
            
        Returns:
            验证结果字典
        """
        tool_name = tool_call.tool_name
        
        # 检查工具是否存在
        if not self.has_tool(tool_name):
            return {
                "valid": False,
                "error": f"工具 '{tool_name}' 不存在"
            }
        
        # 获取工具定义
        definition = self._tool_definitions[tool_name]
        
        # 验证参数
        try:
            required_params = definition.parameters.get("required", [])
            provided_params = set(tool_call.parameters.keys())
            required_params_set = set(required_params)
            
            # 检查必需参数
            missing_params = required_params_set - provided_params
            if missing_params:
                return {
                    "valid": False,
                    "error": f"缺少必需参数: {', '.join(missing_params)}"
                }
            
            # 检查参数类型（简单验证）
            properties = definition.parameters.get("properties", {})
            for param_name, param_value in tool_call.parameters.items():
                if param_name in properties:
                    expected_type = properties[param_name].get("type")
                    if expected_type == "string" and not isinstance(param_value, str):
                        return {
                            "valid": False,
                            "error": f"参数 '{param_name}' 应该是字符串类型"
                        }
                    elif expected_type == "number" and not isinstance(param_value, (int, float)):
                        return {
                            "valid": False,
                            "error": f"参数 '{param_name}' 应该是数字类型"
                        }
                    elif expected_type == "boolean" and not isinstance(param_value, bool):
                        return {
                            "valid": False,
                            "error": f"参数 '{param_name}' 应该是布尔类型"
                        }
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"参数验证失败: {str(e)}"
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取工具管理器统计信息
        
        Returns:
            统计信息字典
        """
        builtin_tools = self.get_tools_by_category("builtin")
        mcp_tools = self.get_tools_by_category("mcp")
        
        return {
            "total_tools": len(self._tools),
            "builtin_tools": len(builtin_tools),
            "mcp_tools": len(mcp_tools),
            "mcp_clients": len(self._mcp_clients),
            "running": self._running,
            "tool_names": list(self._tools.keys())
        }