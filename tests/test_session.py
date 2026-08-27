"""
测试会话管理
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.core.session import SessionManager
from src.core.models import Message, MessageRole
from src.utils.errors import SessionError

class TestSessionManager:
    """测试SessionManager类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.session_manager = SessionManager(max_sessions=5, session_timeout=60)
    
    async def teardown_method(self):
        """每个测试方法后的清理"""
        if self.session_manager._running:
            await self.session_manager.stop()
    
    def test_create_session(self):
        """测试创建会话"""
        session_id = self.session_manager.create_session()
        
        assert session_id is not None
        assert len(session_id) > 0
        assert self.session_manager.session_exists(session_id)
        assert self.session_manager.get_active_session_count() == 1
    
    def test_create_multiple_sessions(self):
        """测试创建多个会话"""
        session_ids = []
        for i in range(3):
            session_id = self.session_manager.create_session()
            session_ids.append(session_id)
        
        assert len(set(session_ids)) == 3  # 确保ID唯一
        assert self.session_manager.get_active_session_count() == 3
    
    def test_get_session(self):
        """测试获取会话"""
        session_id = self.session_manager.create_session()
        
        session = self.session_manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
        
        # 测试不存在的会话
        non_existent = self.session_manager.get_session("non-existent")
        assert non_existent is None
    
    def test_add_user_message(self):
        """测试添加用户消息"""
        session_id = self.session_manager.create_session()
        
        self.session_manager.add_user_message(session_id, "Hello, world!")
        
        session = self.session_manager.get_session(session_id)
        assert len(session.messages) == 1
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[0].content == "Hello, world!"
    
    def test_add_assistant_message(self):
        """测试添加助手消息"""
        session_id = self.session_manager.create_session()
        
        tool_calls = [{"id": "call_123", "function": {"name": "test_tool"}}]
        self.session_manager.add_assistant_message(
            session_id, 
            "I'll help you with that.",
            tool_calls
        )
        
        session = self.session_manager.get_session(session_id)
        assert len(session.messages) == 1
        message = session.messages[0]
        assert message.role == MessageRole.ASSISTANT
        assert message.content == "I'll help you with that."
        assert message.tool_calls == tool_calls
    
    def test_add_tool_message(self):
        """测试添加工具消息"""
        session_id = self.session_manager.create_session()
        
        self.session_manager.add_tool_message(
            session_id,
            "Command executed successfully",
            "call_123"
        )
        
        session = self.session_manager.get_session(session_id)
        assert len(session.messages) == 1
        message = session.messages[0]
        assert message.role == MessageRole.TOOL
        assert message.content == "Command executed successfully"
        assert message.tool_call_id == "call_123"
    
    def test_get_session_context(self):
        """测试获取会话上下文"""
        session_id = self.session_manager.create_session()
        
        # 添加多条消息
        self.session_manager.add_user_message(session_id, "Hello")
        self.session_manager.add_assistant_message(session_id, "Hi there!")
        self.session_manager.add_user_message(session_id, "How are you?")
        
        context = self.session_manager.get_session_context(session_id)
        
        assert len(context) == 3
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Hello"
        assert context[1]["role"] == "assistant"
        assert context[1]["content"] == "Hi there!"
        assert context[2]["role"] == "user"
        assert context[2]["content"] == "How are you?"
    
    def test_get_session_context_limit(self):
        """测试获取会话上下文的消息数量限制"""
        session_id = self.session_manager.create_session()
        
        # 添加5条消息
        for i in range(5):
            self.session_manager.add_user_message(session_id, f"Message {i}")
        
        # 限制为3条消息
        context = self.session_manager.get_session_context(session_id, max_messages=3)
        
        assert len(context) == 3
        # 应该返回最近的3条消息
        assert context[0]["content"] == "Message 2"
        assert context[1]["content"] == "Message 3"
        assert context[2]["content"] == "Message 4"
    
    def test_get_session_context_nonexistent(self):
        """测试获取不存在会话的上下文"""
        with pytest.raises(SessionError, match="会话不存在"):
            self.session_manager.get_session_context("non-existent")
    
    def test_tool_trust_management(self):
        """测试工具信任管理"""
        session_id = self.session_manager.create_session()
        
        # 初始状态：工具未被信任
        assert not self.session_manager.is_tool_trusted(session_id, "bash")
        assert len(self.session_manager.get_trusted_tools(session_id)) == 0
        
        # 信任工具
        self.session_manager.trust_tool(session_id, "bash")
        assert self.session_manager.is_tool_trusted(session_id, "bash")
        assert "bash" in self.session_manager.get_trusted_tools(session_id)
        
        # 信任多个工具
        self.session_manager.trust_tool(session_id, "file_manager")
        trusted_tools = self.session_manager.get_trusted_tools(session_id)
        assert len(trusted_tools) == 2
        assert "bash" in trusted_tools
        assert "file_manager" in trusted_tools
        
        # 取消信任
        self.session_manager.untrust_tool(session_id, "bash")
        assert not self.session_manager.is_tool_trusted(session_id, "bash")
        assert self.session_manager.is_tool_trusted(session_id, "file_manager")
    
    def test_tool_trust_nonexistent_session(self):
        """测试在不存在的会话中管理工具信任"""
        # 检查不存在的会话
        assert not self.session_manager.is_tool_trusted("non-existent", "bash")
        assert len(self.session_manager.get_trusted_tools("non-existent")) == 0
        
        # 尝试在不存在的会话中信任工具
        with pytest.raises(SessionError, match="会话不存在"):
            self.session_manager.trust_tool("non-existent", "bash")
    
    @pytest.mark.asyncio
    async def test_cleanup_session(self):
        """测试清理会话"""
        session_id = self.session_manager.create_session()
        self.session_manager.add_user_message(session_id, "Test message")
        
        assert self.session_manager.session_exists(session_id)
        
        await self.session_manager.cleanup_session(session_id)
        
        assert not self.session_manager.session_exists(session_id)
        assert self.session_manager.get_active_session_count() == 0
    
    def test_get_session_stats(self):
        """测试获取会话统计信息"""
        session_id = self.session_manager.create_session()
        self.session_manager.add_user_message(session_id, "Test")
        self.session_manager.trust_tool(session_id, "bash")
        
        stats = self.session_manager.get_session_stats(session_id)
        
        assert stats is not None
        assert stats["session_id"] == session_id
        assert stats["message_count"] == 1
        assert "bash" in stats["trusted_tools"]
        assert "created_at" in stats
        assert "last_activity" in stats
        assert "duration_seconds" in stats
        assert "idle_seconds" in stats
    
    def test_list_sessions(self):
        """测试列出所有会话"""
        # 创建多个会话
        session_ids = []
        for i in range(3):
            session_id = self.session_manager.create_session()
            session_ids.append(session_id)
            self.session_manager.add_user_message(session_id, f"Message {i}")
        
        sessions_list = self.session_manager.list_sessions()
        
        assert len(sessions_list) == 3
        returned_ids = [s["session_id"] for s in sessions_list]
        assert set(returned_ids) == set(session_ids)
    
    def test_max_sessions_limit(self):
        """测试最大会话数量限制"""
        # 创建最大数量的会话
        session_ids = []
        for i in range(5):  # max_sessions = 5
            session_id = self.session_manager.create_session()
            session_ids.append(session_id)
        
        assert self.session_manager.get_active_session_count() == 5
        
        # 创建第6个会话应该触发清理
        new_session_id = self.session_manager.create_session()
        
        # 应该仍然只有5个会话（最旧的被清理了）
        assert self.session_manager.get_active_session_count() == 5
        assert self.session_manager.session_exists(new_session_id)
    
    @pytest.mark.asyncio
    async def test_session_manager_lifecycle(self):
        """测试会话管理器生命周期"""
        assert not self.session_manager._running
        
        await self.session_manager.start()
        assert self.session_manager._running
        assert self.session_manager._cleanup_task is not None
        
        await self.session_manager.stop()
        assert not self.session_manager._running
        assert self.session_manager._cleanup_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_expired_session_cleanup(self):
        """测试过期会话清理"""
        # 创建会话管理器，超时时间很短
        short_timeout_manager = SessionManager(session_timeout=1)
        
        try:
            session_id = short_timeout_manager.create_session()
            session = short_timeout_manager.get_session(session_id)
            
            # 手动设置会话为过期状态
            session.last_activity = datetime.now() - timedelta(seconds=2)
            
            # 触发过期会话清理
            await short_timeout_manager._cleanup_expired_sessions()
            
            # 会话应该被清理
            assert not short_timeout_manager.session_exists(session_id)
            
        finally:
            if short_timeout_manager._running:
                await short_timeout_manager.stop()