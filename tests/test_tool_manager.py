"""
测试工具管理器
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.tools.manager import ToolManager
from src.core.models import ToolDefinition, ToolCall, ToolResult

class MockTool:
    """模拟工具类"""
    
    def __init__(self, name: str, description: str = "Mock tool"):
        self.name = name
        self.description = description
        self.execute_called = False
        self.execute_params = None
    
    def get_tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Input parameter"
                    }
                },
                "required": ["input"]
            }
        )
    
    async def execute(self, parameters: dict) -> ToolResult:
        self.execute_called = True
        self.execute_params = parameters
        
        return ToolResult(
            call_id="",
            success=True,
            result=f"Mock result for {parameters.get('input', 'no input')}"
        )

class TestToolManager:
    """测试ToolManager类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.tool_manager = ToolManager()
    
    async def teardown_method(self):
        """每个测试方法后的清理"""
        if self.tool_manager._running:
            await self.tool_manager.stop()
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """测试启动和停止工具管理器"""
        assert not self.tool_manager._running
        
        await self.tool_manager.start()
        assert self.tool_manager._running
        
        # 应该注册了内置工具
        assert self.tool_manager.has_tool("execute_bash")
        
        await self.tool_manager.stop()
        assert not self.tool_manager._running
    
    @pytest.mark.asyncio
    async def test_register_tool(self):
        """测试注册工具"""
        mock_tool = MockTool("test_tool")
        
        await self.tool_manager.register_tool("test_tool", mock_tool)
        
        assert self.tool_manager.has_tool("test_tool")
        assert "test_tool" in self.tool_manager.get_tool_names()
        
        definition = self.tool_manager.get_tool_definition("test_tool")
        assert definition is not None
        assert definition.name == "test_tool"
    
    @pytest.mark.asyncio
    async def test_register_invalid_tool(self):
        """测试注册无效工具"""
        # 缺少get_tool_definition方法的工具
        invalid_tool = object()
        
        with pytest.raises(ValueError, match="缺少 get_tool_definition 方法"):
            await self.tool_manager.register_tool("invalid_tool", invalid_tool)
        
        # 缺少execute方法的工具
        class IncompleteTool:
            def get_tool_definition(self):
                return ToolDefinition("incomplete", "desc", {})
        
        incomplete_tool = IncompleteTool()
        
        with pytest.raises(ValueError, match="缺少 execute 方法"):
            await self.tool_manager.register_tool("incomplete_tool", incomplete_tool)
    
    @pytest.mark.asyncio
    async def test_unregister_tool(self):
        """测试取消注册工具"""
        mock_tool = MockTool("test_tool")
        
        # 先注册工具
        await self.tool_manager.register_tool("test_tool", mock_tool)
        assert self.tool_manager.has_tool("test_tool")
        
        # 取消注册
        self.tool_manager.unregister_tool("test_tool")
        assert not self.tool_manager.has_tool("test_tool")
    
    @pytest.mark.asyncio
    async def test_get_available_tools(self):
        """测试获取可用工具列表"""
        await self.tool_manager.start()
        
        # 注册额外的工具
        mock_tool = MockTool("test_tool")
        await self.tool_manager.register_tool("test_tool", mock_tool)
        
        tools = self.tool_manager.get_available_tools()
        
        assert len(tools) >= 2  # 至少有execute_bash和test_tool
        tool_names = [tool.name for tool in tools]
        assert "execute_bash" in tool_names
        assert "test_tool" in tool_names
    
    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """测试执行工具"""
        mock_tool = MockTool("test_tool")
        await self.tool_manager.register_tool("test_tool", mock_tool)
        
        tool_call = ToolCall(
            tool_name="test_tool",
            parameters={"input": "test input"},
            call_id="call_123"
        )
        
        result = await self.tool_manager.execute_tool(tool_call)
        
        assert result.success
        assert result.call_id == "call_123"
        assert "test input" in result.result
        assert mock_tool.execute_called
        assert mock_tool.execute_params == {"input": "test input"}
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """测试执行不存在的工具"""
        tool_call = ToolCall(
            tool_name="nonexistent_tool",
            parameters={},
            call_id="call_123"
        )
        
        result = await self.tool_manager.execute_tool(tool_call)
        
        assert not result.success
        assert result.call_id == "call_123"
        assert "不存在" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_multiple_tools(self):
        """测试并行执行多个工具"""
        # 注册多个工具
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        await self.tool_manager.register_tool("tool1", tool1)
        await self.tool_manager.register_tool("tool2", tool2)
        
        tool_calls = [
            ToolCall("tool1", {"input": "input1"}, "call1"),
            ToolCall("tool2", {"input": "input2"}, "call2")
        ]
        
        results = await self.tool_manager.execute_multiple_tools(tool_calls)
        
        assert len(results) == 2
        assert all(result.success for result in results)
        assert results[0].call_id == "call1"
        assert results[1].call_id == "call2"
        assert tool1.execute_called
        assert tool2.execute_called
    
    @pytest.mark.asyncio
    async def test_execute_multiple_tools_empty(self):
        """测试执行空的工具列表"""
        results = await self.tool_manager.execute_multiple_tools([])
        assert results == []
    
    @pytest.mark.asyncio
    async def test_validate_tool_call(self):
        """测试验证工具调用"""
        mock_tool = MockTool("test_tool")
        await self.tool_manager.register_tool("test_tool", mock_tool)
        
        # 有效的工具调用
        valid_call = ToolCall("test_tool", {"input": "test"}, "call1")
        result = await self.tool_manager.validate_tool_call(valid_call)
        assert result["valid"] is True
        assert result["error"] is None
        
        # 缺少必需参数
        invalid_call = ToolCall("test_tool", {}, "call2")
        result = await self.tool_manager.validate_tool_call(invalid_call)
        assert result["valid"] is False
        assert "缺少必需参数" in result["error"]
        
        # 不存在的工具
        nonexistent_call = ToolCall("nonexistent", {"input": "test"}, "call3")
        result = await self.tool_manager.validate_tool_call(nonexistent_call)
        assert result["valid"] is False
        assert "不存在" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_tool_info(self):
        """测试获取工具信息"""
        await self.tool_manager.start()
        
        info = self.tool_manager.get_tool_info("execute_bash")
        
        assert info is not None
        assert info["name"] == "execute_bash"
        assert "description" in info
        assert "parameters" in info
        assert info["type"] == "builtin"
    
    def test_get_tool_info_nonexistent(self):
        """测试获取不存在工具的信息"""
        info = self.tool_manager.get_tool_info("nonexistent")
        assert info is None
    
    @pytest.mark.asyncio
    async def test_list_tools(self):
        """测试列出所有工具"""
        await self.tool_manager.start()
        
        # 注册额外工具
        mock_tool = MockTool("test_tool")
        await self.tool_manager.register_tool("test_tool", mock_tool)
        
        tools_list = self.tool_manager.list_tools()
        
        assert len(tools_list) >= 2
        tool_names = [tool["name"] for tool in tools_list]
        assert "execute_bash" in tool_names
        assert "test_tool" in tool_names
    
    @pytest.mark.asyncio
    async def test_get_tools_by_category(self):
        """测试按类别获取工具"""
        await self.tool_manager.start()
        
        builtin_tools = self.tool_manager.get_tools_by_category("builtin")
        assert "execute_bash" in builtin_tools
        
        mcp_tools = self.tool_manager.get_tools_by_category("mcp")
        assert isinstance(mcp_tools, list)
    
    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """测试获取统计信息"""
        await self.tool_manager.start()
        
        stats = self.tool_manager.get_statistics()
        
        assert "total_tools" in stats
        assert "builtin_tools" in stats
        assert "mcp_tools" in stats
        assert "running" in stats
        assert stats["running"] is True
        assert stats["total_tools"] >= 1  # 至少有execute_bash
        assert "execute_bash" in stats["tool_names"]
    
    @pytest.mark.asyncio
    async def test_tool_execution_exception(self):
        """测试工具执行异常处理"""
        class FailingTool:
            def get_tool_definition(self):
                return ToolDefinition("failing_tool", "A tool that fails", {})
            
            async def execute(self, parameters):
                raise Exception("Tool execution failed")
        
        failing_tool = FailingTool()
        await self.tool_manager.register_tool("failing_tool", failing_tool)
        
        tool_call = ToolCall("failing_tool", {}, "call_123")
        result = await self.tool_manager.execute_tool(tool_call)
        
        assert not result.success
        assert result.call_id == "call_123"
        assert "工具执行异常" in result.error