"""
主程序入口

终端AI助手的主程序。
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path
from typing import Optional

from .core.config import ConfigManager
from .core.session import SessionManager
from .core.ai_service import AIService
from .core.response_processor import ResponseProcessor
from .tools.manager import ToolManager
from .cli.simple_interface import SimpleCLIInterface
from .core.models import ToolCall, MessageRole
from .utils.logging import setup_logging, get_logger
from .utils.errors import AIAssistantError, ConfigurationError
from .utils.error_handler import global_error_handler

logger = get_logger(__name__)

class TerminalAIAssistant:
    """终端AI助手主应用"""
    
    def __init__(self, config_dir: str = "config", manual_test_mode: bool = False):
        self.config_manager = ConfigManager(config_dir)
        self.session_manager = SessionManager()
        self.tool_manager = None  # 将在initialize中创建，需要AI服务
        self.cli = SimpleCLIInterface()
        self.response_processor = ResponseProcessor()
        
        self.ai_service: Optional[AIService] = None
        self.current_session_id: Optional[str] = None
        self.running = False
        
        # 任务持续执行控制
        self.max_error_recovery_depth = 10  # 最大错误恢复深度（仅用于错误恢复）
        self.current_error_recovery_depth = 0  # 当前错误恢复深度
        # 正常任务执行不设深度限制，让AI自然完成任务
        
        # 人工测试模式
        self.manual_test_mode = manual_test_mode
        self.test_log_file = None
        self.session_start_time = None
        self.test_logger = None
        if manual_test_mode:
            self._setup_manual_test_logging()
    
    def _setup_manual_test_logging(self):
        """设置人工测试模式的日志记录"""
        import datetime
        import logging
        
        # 记录测试开始时间
        self.session_start_time = datetime.datetime.now()
        
        # 生成测试日志文件名
        timestamp = self.session_start_time.strftime("%Y%m%d_%H%M%S")
        self.test_log_file = f"manual_test_{timestamp}.log"
        
        # 创建专门的测试日志记录器
        self.test_logger = logging.getLogger('manual_test')
        self.test_logger.setLevel(logging.INFO)
        
        # 清除之前的处理器（避免重复）
        for handler in self.test_logger.handlers[:]:
            self.test_logger.removeHandler(handler)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(self.test_log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.INFO)
        
        # 创建详细的格式化器
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.test_logger.addHandler(file_handler)
        
        # 记录测试开始
        self.test_logger.info("=" * 80)
        self.test_logger.info("人工测试模式启动")
        self.test_logger.info(f"测试开始时间: {self.session_start_time}")
        self.test_logger.info(f"日志文件: {self.test_log_file}")
        self.test_logger.info("=" * 80)
        
        logger.info(f"人工测试模式已启用，日志文件: {self.test_log_file}")
    
    def _log_user_input(self, user_input: str):
        """记录用户输入"""
        if self.manual_test_mode and self.test_logger:
            self.test_logger.info(f"👤 用户输入: {user_input}")
            self.test_logger.info(f"会话ID: {self.current_session_id}")
            self.test_logger.info(f"当前错误恢复深度: {self.current_error_recovery_depth}")
    
    def _log_ai_response(self, response_content: str, context_count: int = 0):
        """记录AI响应"""
        if self.manual_test_mode and self.test_logger:
            self.test_logger.info("🤖 AI响应接收完成")
            if response_content:
                # 限制日志长度，避免过长
                preview = response_content[:500] + "..." if len(response_content) > 500 else response_content
                self.test_logger.info(f"🤖 AI响应内容: {preview}")
            self.test_logger.info(f"🤖 上下文消息数量: {context_count}")
    
    def _log_tool_execution(self, tool_name: str, parameters: dict, result: any):
        """记录工具执行"""
        if self.manual_test_mode and self.test_logger:
            self.test_logger.info(f"🛠️  开始执行工具: {tool_name}")
            self.test_logger.info(f"🛠️  工具参数: {parameters}")
            
            if hasattr(result, 'success'):
                self.test_logger.info(f"🛠️  执行成功: {result.success}")
                if result.success:
                    result_str = str(result.result) if result.result else "无输出"
                    # 增加日志长度限制，但提供更多信息
                    if len(result_str) > 500:
                        result_preview = result_str[:500] + f"... (截断，总长度: {len(result_str)} 字符)"
                    else:
                        result_preview = result_str
                    self.test_logger.info(f"🛠️  执行结果: {result_preview}")
                else:
                    self.test_logger.info(f"🛠️  执行错误: {result.error}")
            else:
                result_str = str(result) if result else "无输出"
                if len(result_str) > 500:
                    result_preview = result_str[:500] + f"... (截断，总长度: {len(result_str)} 字符)"
                else:
                    result_preview = result_str
                self.test_logger.info(f"🛠️  执行结果: {result_preview}")
    
    def _log_error(self, error: Exception, context: str = ""):
        """记录错误信息"""
        if self.manual_test_mode and self.test_logger:
            self.test_logger.error(f"❌ {context}: {error}")
            self.test_logger.error(f"❌ 错误类型: {type(error).__name__}")
            import traceback
            self.test_logger.error(f"❌ 错误堆栈: {traceback.format_exc()}")
    
    def generate_optimization_prompt(self) -> str:
        """生成用于下次优化的提示信息"""
        if not self.manual_test_mode:
            return "请先启用人工测试模式才能生成优化提示"
        
        import datetime
        current_time = datetime.datetime.now()
        test_duration = current_time - self.session_start_time if self.session_start_time else None
        
        prompt = f"""# 终端AI助手优化请求

## 测试会话信息
- 测试开始时间: {self.session_start_time}
- 测试结束时间: {current_time}
- 测试持续时间: {test_duration}
- 会话ID: {self.current_session_id}
- 日志文件: {self.test_log_file}

## 优化请求
我刚完成了一轮人工测试，发现了一些需要优化的问题。请帮我分析日志文件并进行相应的优化。

## 需要你做的事情
1. 首先读取并分析日志文件: {self.test_log_file}
2. 识别测试过程中出现的问题和异常
3. 分析用户输入和AI响应的质量
4. 检查工具执行的效率和准确性
5. 识别任务持续执行和错误恢复的表现
6. 提出具体的优化建议和代码修改方案

## 关注重点
- 用户体验问题（响应时间、交互流畅度）
- 功能准确性问题（命令执行、结果处理）
- 错误处理问题（恢复机制、错误提示）
- 性能问题（资源使用、执行效率）
- 安全问题（权限控制、命令验证）

## 期望输出
- 问题分析报告
- 具体的代码修改建议
- 测试验证方案

请开始分析日志文件并提供优化方案。
"""
        
        # 同时记录到测试日志
        if self.test_logger:
            self.test_logger.info("=" * 80)
            self.test_logger.info("测试会话结束")
            self.test_logger.info(f"测试结束时间: {current_time}")
            self.test_logger.info(f"测试持续时间: {test_duration}")
            self.test_logger.info("优化提示已生成")
            self.test_logger.info("=" * 80)
        
        return prompt.strip()
    
    async def initialize(self):
        """初始化应用程序"""
        try:
            # 加载配置
            model_config = self.config_manager.load_model_config()
            logger.info(f"已加载模型配置: {model_config.model_name}")
            
            # 初始化AI服务
            self.ai_service = AIService(model_config)
            
            # 更新工具管理器以支持推理（传入AI服务）
            self.tool_manager = ToolManager(ai_service=self.ai_service)
            
            # 启动各个管理器
            await self.session_manager.start()
            await self.tool_manager.start()
            
            # 创建会话
            self.current_session_id = self.session_manager.create_session()
            
            logger.info("应用程序初始化完成")
            
        except ConfigurationError as e:
            self.cli.display_error(f"配置错误: {e.message}")
            if e.details:
                self.cli.display_info(f"详情: {e.details}")
            raise
        except Exception as e:
            self.cli.display_error(f"初始化失败: {str(e)}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.ai_service:
                await self.ai_service.close()
            
            await self.session_manager.stop()
            await self.tool_manager.stop()
            
            logger.info("应用程序清理完成")
            
        except Exception as e:
            logger.error(f"清理过程中出错: {e}")
    
    async def process_user_input(self, user_input: str) -> None:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入的文本
        """
        try:
            # 人工测试模式日志记录
            self._log_user_input(user_input)
            
            # 重置错误恢复深度（新的用户输入）
            self.current_error_recovery_depth = 0
            
            # 添加用户消息到会话
            self.session_manager.add_user_message(self.current_session_id, user_input)
            
            # 显示思考提示
            self.cli.display_thinking()
            
            # 获取会话上下文
            context_messages = self.session_manager.get_session_context(self.current_session_id)
            
            # 获取可用工具
            available_tools = self.tool_manager.get_available_tools()
            
            # 调用AI服务
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🤖 开始调用AI服务")
                self.test_logger.info(f"上下文消息数量: {len(context_messages)}")
                self.test_logger.info(f"可用工具数量: {len(available_tools)}")
            
            async with self.ai_service as ai:
                response_data = await ai.generate_response(context_messages, available_tools)
            
            # 清除思考提示
            self.cli.clear_thinking()
            
            # 记录AI响应
            if response_data and 'choices' in response_data and response_data['choices']:
                message = response_data['choices'][0].get('message', {})
                content = message.get('content', '')
                self._log_ai_response(content, len(context_messages))
            
            # 处理AI响应
            await self._handle_ai_response(response_data)
            
        except Exception as e:
            self.cli.clear_thinking()
            # 人工测试模式记录错误
            self._log_error(e, "处理用户输入")
            await global_error_handler.handle_error(e, "处理用户输入")
    
    async def _handle_ai_response(self, response_data: dict) -> None:
        """
        处理AI响应
        
        Args:
            response_data: AI API响应数据
        """
        # 解析响应
        message, tool_calls = self.response_processor.process_response(response_data)
        
        # 如果有文本消息，显示并添加到会话
        if message and message.content:
            self.cli.display_response(message.content)
            self.session_manager.add_assistant_message(
                self.current_session_id, 
                message.content,
                [tc.to_dict() for tc in tool_calls] if tool_calls else None
            )
        
        # 如果有工具调用，处理它们
        if tool_calls:
            await self._handle_tool_calls(tool_calls)
        else:
            # 即使没有工具调用，也要检查是否需要继续任务
            # 这是关键修复：确保任务持续执行机制始终被触发
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🔄 AI响应无工具调用，但仍检查是否需要继续任务")
            await self._continue_task_if_needed()
    
    async def _handle_tool_calls(self, tool_calls: list) -> None:
        """
        处理工具调用
        
        Args:
            tool_calls: 工具调用列表
        """
        try:
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info(f"🛠️  开始处理 {len(tool_calls)} 个工具调用")
            
            for i, tool_call in enumerate(tool_calls, 1):
                if self.manual_test_mode and self.test_logger:
                    self.test_logger.info(f"🛠️  处理工具调用 {i}/{len(tool_calls)}: {tool_call.tool_name}")
                await self._execute_single_tool_call(tool_call)
            
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🛠️  所有工具调用处理完成，准备继续任务")
            
            # 工具执行完成后，继续思考是否需要进一步行动
            await self._continue_task_if_needed()
            
        except Exception as e:
            logger.error(f"处理工具调用时出错: {e}")
            if self.manual_test_mode and self.test_logger:
                self.test_logger.error(f"🛠️  ❌ 处理工具调用时出错: {e}")
                self.test_logger.error(f"🛠️  ❌ 错误类型: {type(e).__name__}")
                import traceback
                self.test_logger.error(f"🛠️  ❌ 错误堆栈: {traceback.format_exc()}")
            
            # 即使出错也尝试继续任务
            try:
                await self._continue_task_if_needed()
            except Exception as continue_error:
                logger.error(f"继续任务也失败: {continue_error}")
                if self.manual_test_mode and self.test_logger:
                    self.test_logger.error(f"🔄 ❌ 继续任务也失败: {continue_error}")
    
    async def _execute_single_tool_call(self, tool_call: ToolCall) -> None:
        """
        执行单个工具调用
        
        Args:
            tool_call: 工具调用对象
        """
        try:
            # 检查是否为不需要授权的安全命令
            command = tool_call.parameters.get('command', '')
            needs_authorization = self._command_needs_authorization(command)
            user_authorized = False
            
            # 检查工具是否需要授权
            if needs_authorization and not self.session_manager.is_tool_trusted(self.current_session_id, tool_call.tool_name):
                # 显示工具调用信息
                purpose = tool_call.parameters.get('purpose', '执行工具操作')
                
                self.cli.display_tool_usage(tool_call.tool_name, command, purpose)
                
                # 请求用户授权
                choice = self.cli.prompt_authorization(tool_call.tool_name)
                
                if choice == 'n':
                    self.cli.display_info("操作已取消")
                    return
                elif choice == 't':
                    self.session_manager.trust_tool(self.current_session_id, tool_call.tool_name)
                    self.cli.display_info(f"工具 '{tool_call.tool_name}' 已在此会话中被信任")
                    user_authorized = True
                elif choice == 'y':
                    user_authorized = True
            elif not needs_authorization or self.session_manager.is_tool_trusted(self.current_session_id, tool_call.tool_name):
                user_authorized = True
            
            # 如果用户已授权或工具被信任，添加绕过安全检查的标记
            if user_authorized:
                tool_call.parameters['_user_authorized'] = True
            
            # 执行工具（使用推理版本）
            self.cli.display_loading("执行命令")
            result = await self.tool_manager.execute_tool_with_reasoning(
                tool_call, 
                reasoning_context=f"用户请求: {tool_call.tool_name}"
            )
            self.cli.clear_loading()
            
            # 记录工具执行
            self._log_tool_execution(tool_call.tool_name, tool_call.parameters, result)
            
            # 显示结果
            if result.success:
                # 直接显示工具执行结果，不需要额外的echo输出
                if result.result and str(result.result).strip():
                    print(str(result.result))
                else:
                    print("✅ 命令执行成功")
                
                # 工具执行成功后重置错误恢复深度，为下一个问题提供完整的错误恢复机会
                if self.current_error_recovery_depth > 0:
                    logger.info(f"工具执行成功，重置错误恢复深度: {self.current_error_recovery_depth} → 0")
                    self.current_error_recovery_depth = 0
            else:
                self.cli.display_error(f"命令执行失败: {result.error}")
            
            # 添加工具结果到会话
            tool_message = self.response_processor.create_tool_response_message(result)
            self.session_manager.add_message(self.current_session_id, tool_message)
            
            
        except Exception as e:
            self.cli.clear_loading()
            self.cli.display_error(f"工具执行失败: {str(e)}")
    
    async def _continue_task_if_needed(self) -> None:
        """
        检查是否需要继续执行任务
        
        在工具执行完成后，AI会自动思考是否需要进一步的行动来完成用户的原始请求
        """
        try:
            # 正常任务执行不设深度限制，让AI自然完成任务
            logger.info("继续执行任务以完成用户请求")
            
            # 人工测试模式记录
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🔄 检查是否需要继续执行任务")
            
            # 获取当前会话上下文
            context_messages = self.session_manager.get_session_context(self.current_session_id)
            
            # 如果没有足够的上下文，不继续
            if len(context_messages) < 2:
                if self.manual_test_mode and self.test_logger:
                    self.test_logger.info("🔄 上下文消息不足，停止继续执行")
                return
            
            # 分析最近的消息，判断是否需要继续
            recent_messages = context_messages[-5:] if len(context_messages) >= 5 else context_messages
            
            # 获取可用工具
            available_tools = self.tool_manager.get_available_tools()
            
            # 让AI智能判断是否应该停止继续执行
            should_continue = await self._ai_should_continue_task(context_messages, available_tools)
            if not should_continue:
                if self.manual_test_mode and self.test_logger:
                    self.test_logger.info("🔄 AI判断任务已完成，停止继续执行")
                return
            
            # 构建更智能的继续任务提示
            continue_prompt = """
请继续完成用户的原始请求。

重要分析要点：
1. 用户的原始请求是什么？是否已经完全满足？
2. 刚才执行的工具获得了什么结果？
   - 如果命令没有输出，可能是命令有问题，需要调整
   - 如果有错误，需要分析原因并尝试修复
   - 如果输出不完整，需要继续获取更多信息
3. 如果遇到命令执行问题，请：
   - 分析命令语法是否正确
   - 尝试更简单的命令
   - 分步骤执行而不是使用复杂管道
   - 检查权限和参数

行动指南：
- 如果之前的命令失败或无输出，请分析原因并调整方法
- 如果需要更多信息，请继续执行（修正后的）命令
- 如果信息已经足够，请提供完整、详细的回答
- 遇到错误时，不要放弃，要尝试替代方案
- 只有在确实无法完成时才说明无法完成

目标：不轻易放弃，通过分析和调整方法来完全满足用户的原始请求。
"""
            
            # 添加继续任务的消息
            self.session_manager.add_user_message(self.current_session_id, continue_prompt)
            
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🔄 添加继续任务提示，准备调用AI服务")
            
            # 显示思考提示
            self.cli.display_thinking()
            
            # 获取更新后的上下文
            updated_context = self.session_manager.get_session_context(self.current_session_id)
            
            # 获取可用工具
            available_tools = self.tool_manager.get_available_tools()
            
            # 调用AI服务继续思考
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🔄 开始调用AI服务继续任务")
            
            async with self.ai_service as ai:
                response_data = await ai.generate_response(updated_context, available_tools)
            
            # 清除思考提示
            self.cli.clear_thinking()
            
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🔄 AI服务响应完成，开始处理继续任务的响应")
            
            # 处理AI的继续响应
            await self._handle_ai_response(response_data)
            
        except Exception as e:
            self.cli.clear_thinking()
            logger.error(f"继续任务时出错: {e}")
            
            # 人工测试模式记录错误
            if self.manual_test_mode and self.test_logger:
                self.test_logger.error(f"🔄 ❌ 继续任务时出错: {e}")
                self.test_logger.error(f"🔄 ❌ 错误类型: {type(e).__name__}")
                import traceback
                self.test_logger.error(f"🔄 ❌ 错误堆栈: {traceback.format_exc()}")
            
            # 尝试错误恢复和分析
            await self._handle_continuation_error(e)
    
    async def _handle_continuation_error(self, error: Exception) -> None:
        """
        处理任务继续执行时的错误，让AI智能分析和恢复
        
        Args:
            error: 发生的异常
        """
        try:
            error_message = str(error)
            error_type = type(error).__name__
            logger.info(f"尝试从继续任务错误中恢复: {error_message}")
            
            # 人工测试模式记录
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info(f"🔄 ⚠️  开始智能错误恢复: {error_message}")
                self.test_logger.info(f"🔄 ⚠️  错误类型: {error_type}")
            
            # 检查是否还有错误恢复的机会
            if self.current_error_recovery_depth >= self.max_error_recovery_depth:
                logger.info(f"已达到最大错误恢复深度 {self.max_error_recovery_depth}，停止错误恢复")
                if self.manual_test_mode and self.test_logger:
                    self.test_logger.info(f"🔄 ⚠️  已达到最大错误恢复深度，停止恢复")
                
                # 显示最终错误信息
                self.cli.display_error(f"任务执行遇到问题且已达到最大重试次数: {error_message}")
                return
            
            # 增加错误恢复深度
            self.current_error_recovery_depth += 1
            logger.info(f"尝试智能错误恢复，当前深度: {self.current_error_recovery_depth}/{self.max_error_recovery_depth}")
            
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info(f"🔄 ⚠️  尝试智能错误恢复，深度: {self.current_error_recovery_depth}/{self.max_error_recovery_depth}")
            
            # 构建智能错误分析提示，让AI来分析错误并决定恢复策略
            recovery_prompt = self._build_intelligent_error_recovery_prompt(error_type, error_message)
            
            # 添加错误分析消息
            self.session_manager.add_user_message(self.current_session_id, recovery_prompt)
            
            # 显示思考提示
            self.cli.display_thinking()
            
            # 获取上下文
            context = self.session_manager.get_session_context(self.current_session_id)
            available_tools = self.tool_manager.get_available_tools()
            
            # 让AI分析错误并尝试恢复
            async with self.ai_service as ai:
                response_data = await ai.generate_response(context, available_tools)
            
            # 清除思考提示
            self.cli.clear_thinking()
            
            # 处理恢复响应
            await self._handle_ai_response(response_data)
            
            logger.info("智能错误恢复尝试完成")
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🔄 ✅ 智能错误恢复尝试完成")
            
        except Exception as recovery_error:
            logger.error(f"智能错误恢复失败: {recovery_error}")
            if self.manual_test_mode and self.test_logger:
                self.test_logger.error(f"🔄 ❌ 智能错误恢复失败: {recovery_error}")
            
            # 如果是API相关错误，给出友好提示
            if "API" in str(recovery_error) or "超时" in str(recovery_error) or "timeout" in str(recovery_error).lower():
                self.cli.display_error("遇到API服务问题，请稍后重试或检查网络连接。")
            else:
                self.cli.display_error(f"错误恢复失败: {recovery_error}")
            
            # 最终失败，不再尝试
    
    def _should_stop_continuation(self, recent_messages: list) -> bool:
        """
        保守的智能判断是否应该停止任务持续执行
        
        Args:
            recent_messages: 最近的消息列表
            
        Returns:
            如果应该停止返回True
        """
        # 检查最近几条AI消息
        ai_messages = []
        for msg in reversed(recent_messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                ai_messages.append(msg["content"])
                if len(ai_messages) >= 3:  # 检查最近3条AI消息
                    break
        
        if not ai_messages:
            return False
        
        last_message = ai_messages[0].lower()
        
        # 1. 只检查非常明确的完成信号（更保守）
        strong_completion_signals = [
            "任务完成", "已完成", "分析完毕", "总结完成",
            "以上就是", "综上所述", "总的来说", 
            "无法继续", "无法执行", "不支持"
        ]
        
        for signal in strong_completion_signals:
            if signal in last_message:
                logger.info(f"检测到强完成信号: {signal}")
                return True
        
        # 2. 检查是否是详细的最终报告（需要同时满足多个条件）
        if len(last_message) > 800:  # 提高长度阈值，确保是真正的详细报告
            # 检查是否包含大量统计数据和结论性内容
            import re
            numbers = re.findall(r'\d+', last_message)
            percentages = re.findall(r'\d+%', last_message)
            
            # 检查结论性词汇
            conclusion_indicators = [
                "建议", "推荐", "应该", "可以考虑", "优化方案",
                "总计", "总共", "合计"
            ]
            
            conclusion_count = sum(1 for indicator in conclusion_indicators if indicator in last_message)
            
            # 需要同时满足：长消息 + 大量数据 + 多个结论性指标
            if len(numbers) >= 8 and conclusion_count >= 4:
                logger.info(f"检测到详细分析报告: 数字{len(numbers)}个, 结论指标{conclusion_count}个")
                return True
        
        # 3. 检查连续的详细分析（需要更严格的条件）
        if len(ai_messages) >= 2:
            # 两条消息都很长，且都包含结论性内容
            if all(len(msg) > 400 for msg in ai_messages[:2]):
                conclusion_in_both = all(
                    any(indicator in msg.lower() for indicator in ["建议", "优化", "总结", "分析结果"])
                    for msg in ai_messages[:2]
                )
                if conclusion_in_both:
                    logger.info("检测到连续的详细分析消息")
                    return True
        
        # 4. 检查是否包含明确的结束语句
        ending_phrases = [
            "希望这些信息对您有帮助", "如果您需要更多信息", "还有其他问题吗",
            "这就是我的分析", "分析完成", "报告结束"
        ]
        
        for phrase in ending_phrases:
            if phrase in last_message:
                logger.info(f"检测到结束语句: {phrase}")
                return True
        
        return False
    
    async def _ai_should_continue_task(self, context_messages: list, available_tools: list) -> bool:
        """
        让AI智能判断是否应该继续执行任务
        
        Args:
            context_messages: 当前会话上下文
            available_tools: 可用工具列表
            
        Returns:
            如果应该继续返回True，如果任务已完成返回False
        """
        try:
            # 构建任务完成度评估提示
            evaluation_prompt = """
请仔细分析当前的对话历史，判断用户的原始请求是否已经得到充分满足。

## 评估要点：
1. **用户的原始请求是什么？** 
   - 明确识别用户想要解决的具体问题
   - 理解用户期望得到什么样的结果

2. **当前已经完成了什么？**
   - 回顾已经执行的操作和获得的信息
   - 分析这些信息是否足够回答用户的问题

3. **是否还需要更多信息？**
   - 判断是否还缺少关键数据或分析
   - 评估是否需要执行更多命令或工具

4. **用户问题是否已经得到完整回答？**
   - 检查是否已经提供了用户需要的所有信息
   - 确认是否已经给出了具体的建议或解决方案

## 判断标准：
- 如果用户的问题已经得到完整、详细的回答，包含了所需的数据、分析和建议 → 回答"COMPLETE"
- 如果还需要收集更多信息、执行更多分析或提供更详细的建议 → 回答"CONTINUE"

## 重要提醒：
- 不要因为可能还有更多可做的事情就选择继续
- 重点关注用户的原始需求是否已经满足
- 如果已经提供了充分的信息和建议，就应该完成

请仔细思考后，只回答一个词：COMPLETE 或 CONTINUE
"""
            
            # 创建评估上下文
            evaluation_context = context_messages + [
                {"role": "user", "content": evaluation_prompt}
            ]
            
            if self.manual_test_mode and self.test_logger:
                self.test_logger.info("🔄 🤔 请求AI评估任务完成度")
            
            # 调用AI进行评估（不使用工具，只需要判断）
            async with self.ai_service as ai:
                response_data = await ai.generate_response(evaluation_context, [])
            
            # 解析AI的判断
            if response_data and 'choices' in response_data and response_data['choices']:
                ai_judgment = response_data['choices'][0].get('message', {}).get('content', '').strip().upper()
                
                if self.manual_test_mode and self.test_logger:
                    self.test_logger.info(f"🔄 🤔 AI评估结果: {ai_judgment}")
                
                # 解析AI的判断
                if "COMPLETE" in ai_judgment:
                    logger.info("AI判断任务已完成")
                    return False  # 不需要继续
                elif "CONTINUE" in ai_judgment:
                    logger.info("AI判断任务需要继续")
                    return True   # 需要继续
                else:
                    # 如果AI的回答不明确，默认继续（保守策略）
                    logger.info(f"AI判断不明确: {ai_judgment}，默认继续")
                    return True
            
            # 如果无法获取AI判断，默认继续
            logger.info("无法获取AI判断，默认继续")
            return True
            
        except Exception as e:
            logger.error(f"AI任务评估失败: {e}")
            if self.manual_test_mode and self.test_logger:
                self.test_logger.error(f"🔄 ❌ AI任务评估失败: {e}")
            # 出错时默认继续，避免任务意外中断
            return True
    
    def _build_intelligent_error_recovery_prompt(self, error_type: str, error_message: str) -> str:
        """
        构建智能错误恢复提示，让AI分析错误并决定恢复策略
        
        Args:
            error_type: 错误类型名称
            error_message: 错误消息
            
        Returns:
            智能错误分析提示
        """
        return f"""
## 错误分析与恢复请求

刚才在继续执行任务时遇到了一个错误，需要你分析并尝试恢复：

**错误类型**: {error_type}
**错误信息**: {error_message}

请你作为一个智能助手，分析这个错误并决定最佳的恢复策略：

### 分析要点：
1. **错误性质判断**：
   - 这是什么类型的错误？（网络、API、命令执行、权限、语法等）
   - 错误是临时性的还是持续性的？
   - 错误是否可以通过调整方法来解决？

2. **上下文分析**：
   - 回顾之前执行的操作和命令
   - 分析可能导致这个错误的原因
   - 检查是否有遗漏或错误的步骤

3. **恢复策略决定**：
   - 如果是网络/API错误：评估是否应该重试，还是暂停任务
   - 如果是命令错误：分析如何修正命令或使用替代方案
   - 如果是权限错误：检查权限设置或使用其他方法
   - 如果是数据/参数错误：调整参数或处理方式

### 行动指南：
- **可恢复错误**：请调整方法并继续执行，说明你的调整策略
- **临时性错误**：可以尝试重新执行，但要说明原因
- **不可恢复错误**：请说明原因，并尽可能提供替代方案或部分结果
- **需要用户干预的错误**：请明确说明需要用户做什么

### 目标：
继续完成用户的原始请求。如果当前方法不可行，请尝试替代方案。只有在确实无法继续时，才说明无法完成的原因。

请基于你的分析，决定下一步行动。
"""
    
    def _command_needs_authorization(self, command: str) -> bool:
        """
        判断命令是否需要授权
        
        Args:
            command: 要检查的命令
            
        Returns:
            是否需要授权
        """
        # 不需要授权的安全命令列表
        no_auth_commands = {
            'echo', 'pwd', 'whoami', 'date', 'ls', 'cat', 'head', 'tail',
            'wc', 'sort', 'uniq', 'basename', 'dirname', 'uname', 'env'
        }
        
        try:
            # 更简单的命令解析，避免复杂引号问题
            command_stripped = command.strip()
            if not command_stripped:
                return True
            
            # 获取第一个单词作为命令名
            first_word = command_stripped.split()[0]
            main_command = first_word.split('/')[-1]  # 获取命令名（去掉路径）
            
            return main_command not in no_auth_commands
        except Exception as e:
            # 如果解析失败，默认需要授权
            logger.warning(f"命令解析失败: {command}, 错误: {e}")
            return True
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.cli.handle_interrupt()
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    async def run(self):
        """运行主程序循环"""
        self.running = True
        self._setup_signal_handlers()
        
        try:
            # 初始化
            await self.initialize()
            
            # 启动CLI会话
            self.cli.start_session()
            
            # 显示会话信息
            stats = self.session_manager.get_session_stats(self.current_session_id)
            if stats:
                self.cli.display_session_info(self.current_session_id, stats['message_count'])
            
            # 主循环
            while self.running and self.cli.running:
                try:
                    user_input = self.cli.get_user_input()
                    
                    if user_input is None:  # 用户要退出
                        self.running = False
                        break
                    
                    if not user_input.strip():  # 空输入
                        self.cli.display_info("请输入您的问题或命令")
                        continue
                    
                    await self.process_user_input(user_input)
                    
                except KeyboardInterrupt:
                    print("\n程序被中断")
                    self.running = False
                    break
                except EOFError:
                    print("\n输入结束，退出程序")
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"主循环错误: {e}")
                    self.cli.display_error(f"处理过程中出现错误: {str(e)}")
                    # 继续运行，不退出程序
            
        except Exception as e:
            await global_error_handler.handle_error(e, "应用程序运行")
        finally:
            # 清理
            self.cli.stop_session()
            await self.cleanup()

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="终端AI助手")
    parser.add_argument(
        "--config-dir", 
        default="config",
        help="配置文件目录 (默认: config)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="启用调试模式"
    )
    parser.add_argument(
        "--log-file",
        help="日志文件路径"
    )
    parser.add_argument(
        "--manual-test",
        action="store_true",
        help="启用人工测试模式，记录详细的交互日志用于程序调优"
    )
    
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置日志
    setup_logging(debug=args.debug, log_file=args.log_file)
    
    # 创建并运行应用
    app = TerminalAIAssistant(config_dir=args.config_dir, manual_test_mode=args.manual_test)
    
    try:
        if args.manual_test:
            print("🧪 人工测试模式已启用")
            print(f"📝 测试日志文件: {app.test_log_file}")
            print("💡 测试完成后将自动生成优化提示")
            print("🔧 按 Ctrl+C 结束测试并生成优化提示")
            print("=" * 60)
        
        await app.run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        
        # 如果是人工测试模式，生成优化提示
        if args.manual_test and app.manual_test_mode:
            print("\n" + "=" * 60)
            print("🧪 人工测试会话结束")
            print("📝 正在生成优化提示...")
            optimization_prompt = app.generate_optimization_prompt()
            
            # 保存优化提示到文件
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            prompt_file = f"optimization_prompt_{timestamp}.md"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(optimization_prompt)
            
            print(f"✅ 优化提示已保存到: {prompt_file}")
            print(f"📊 测试日志文件: {app.test_log_file}")
            print("\n💡 下次优化时，请将以上文件内容提供给AI助手")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        
        # 人工测试模式下记录异常
        if args.manual_test and hasattr(app, 'manual_test_mode') and app.manual_test_mode:
            app._log_error(e, "程序异常退出")
        
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())