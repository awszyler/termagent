"""
会话管理

处理会话的创建、维护和清理。
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from .models import Session, Message, MessageRole
from ..utils.errors import SessionError
from ..utils.logging import get_logger

logger = get_logger(__name__)

class SessionManager:
    """会话管理器"""
    
    def __init__(self, max_sessions: int = 100, session_timeout: int = 3600):
        """
        初始化会话管理器
        
        Args:
            max_sessions: 最大会话数量
            session_timeout: 会话超时时间（秒）
        """
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self._sessions: Dict[str, Session] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """启动会话管理器"""
        if self._running:
            return
        
        self._running = True
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("会话管理器已启动")
    
    async def stop(self):
        """停止会话管理器"""
        if not self._running:
            return
        
        self._running = False
        
        # 取消清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 清理所有会话
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.cleanup_session(session_id)
        
        logger.info("会话管理器已停止")
    
    def create_session(self) -> str:
        """
        创建新会话
        
        Returns:
            会话ID
        """
        # 检查会话数量限制
        if len(self._sessions) >= self.max_sessions:
            # 清理最旧的会话
            oldest_session_id = min(
                self._sessions.keys(),
                key=lambda sid: self._sessions[sid].last_activity
            )
            logger.warning(f"达到最大会话数量，清理最旧会话: {oldest_session_id}")
            # 同步清理会话（在创建新会话时）
            if oldest_session_id in self._sessions:
                session = self._sessions[oldest_session_id]
                message_count = len(session.messages)
                duration = datetime.now() - session.created_at
                logger.info(
                    f"清理会话 {oldest_session_id}: "
                    f"消息数量={message_count}, "
                    f"持续时间={duration.total_seconds():.1f}秒"
                )
                del self._sessions[oldest_session_id]
        
        # 生成唯一会话ID
        session_id = str(uuid.uuid4())
        
        # 创建会话对象
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        
        logger.info(f"创建新会话: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        获取会话对象
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话对象，如果不存在则返回None
        """
        session = self._sessions.get(session_id)
        if session:
            # 更新最后活动时间
            session.last_activity = datetime.now()
        return session
    
    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否存在
        """
        return session_id in self._sessions
    
    def get_session_context(self, session_id: str, max_messages: int = 50) -> List[Dict]:
        """
        获取会话对话历史
        
        Args:
            session_id: 会话ID
            max_messages: 最大消息数量
            
        Returns:
            消息列表（API格式）
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(
                f"会话不存在: {session_id}",
                session_id=session_id
            )
        
        return session.get_context_messages(max_messages)
    
    def add_message(self, session_id: str, message: Message) -> None:
        """
        添加消息到会话
        
        Args:
            session_id: 会话ID
            message: 消息对象
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(
                f"会话不存在: {session_id}",
                session_id=session_id
            )
        
        session.add_message(message)
        logger.debug(f"添加消息到会话 {session_id}: {message.role.value}")
    
    def add_user_message(self, session_id: str, content: str) -> None:
        """
        添加用户消息到会话
        
        Args:
            session_id: 会话ID
            content: 消息内容
        """
        message = Message(role=MessageRole.USER, content=content)
        self.add_message(session_id, message)
    
    def add_assistant_message(self, session_id: str, content: str, tool_calls: Optional[List[Dict]] = None) -> None:
        """
        添加助手消息到会话
        
        Args:
            session_id: 会话ID
            content: 消息内容
            tool_calls: 工具调用列表
        """
        message = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls
        )
        self.add_message(session_id, message)
    
    def add_tool_message(self, session_id: str, content: str, tool_call_id: str) -> None:
        """
        添加工具消息到会话
        
        Args:
            session_id: 会话ID
            content: 消息内容
            tool_call_id: 工具调用ID
        """
        message = Message(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id
        )
        self.add_message(session_id, message)
    
    async def cleanup_session(self, session_id: str) -> None:
        """
        清理会话
        
        Args:
            session_id: 会话ID
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            
            # 记录会话统计信息
            message_count = len(session.messages)
            duration = datetime.now() - session.created_at
            
            logger.info(
                f"清理会话 {session_id}: "
                f"消息数量={message_count}, "
                f"持续时间={duration.total_seconds():.1f}秒"
            )
            
            # 删除会话
            del self._sessions[session_id]
    
    def get_session_stats(self, session_id: str) -> Optional[Dict]:
        """
        获取会话统计信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            统计信息字典
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        now = datetime.now()
        duration = now - session.created_at
        idle_time = now - session.last_activity
        
        return {
            "session_id": session_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "duration_seconds": duration.total_seconds(),
            "idle_seconds": idle_time.total_seconds(),
            "message_count": len(session.messages),
            "trusted_tools": list(session.trusted_tools)
        }
    
    def list_sessions(self) -> List[Dict]:
        """
        列出所有会话的统计信息
        
        Returns:
            会话统计信息列表
        """
        return [
            self.get_session_stats(session_id)
            for session_id in self._sessions.keys()
        ]
    
    def get_active_session_count(self) -> int:
        """
        获取活跃会话数量
        
        Returns:
            活跃会话数量
        """
        return len(self._sessions)
    
    async def _cleanup_loop(self):
        """清理循环，定期清理超时会话"""
        while self._running:
            try:
                await asyncio.sleep(300)  # 每5分钟检查一次
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"会话清理循环错误: {e}")
    
    async def _cleanup_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        timeout_threshold = now - timedelta(seconds=self.session_timeout)
        
        expired_sessions = []
        for session_id, session in self._sessions.items():
            if session.last_activity < timeout_threshold:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            logger.info(f"清理过期会话: {session_id}")
            await self.cleanup_session(session_id)
    
    def is_tool_trusted(self, session_id: str, tool_name: str) -> bool:
        """
        检查工具是否在会话中被信任
        
        Args:
            session_id: 会话ID
            tool_name: 工具名称
            
        Returns:
            是否被信任
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        return tool_name in session.trusted_tools
    
    def trust_tool(self, session_id: str, tool_name: str) -> None:
        """
        标记工具为会话信任
        
        Args:
            session_id: 会话ID
            tool_name: 工具名称
        """
        session = self.get_session(session_id)
        if not session:
            raise SessionError(
                f"会话不存在: {session_id}",
                session_id=session_id
            )
        
        session.trusted_tools.add(tool_name)
        logger.info(f"工具 '{tool_name}' 已在会话 {session_id} 中被信任")
    
    def untrust_tool(self, session_id: str, tool_name: str) -> None:
        """
        取消工具的会话信任
        
        Args:
            session_id: 会话ID
            tool_name: 工具名称
        """
        session = self.get_session(session_id)
        if session and tool_name in session.trusted_tools:
            session.trusted_tools.remove(tool_name)
            logger.info(f"工具 '{tool_name}' 在会话 {session_id} 中的信任已取消")
    
    def get_trusted_tools(self, session_id: str) -> Set[str]:
        """
        获取会话中被信任的工具列表
        
        Args:
            session_id: 会话ID
            
        Returns:
            被信任的工具名称集合
        """
        session = self.get_session(session_id)
        if not session:
            return set()
        
        return session.trusted_tools.copy()