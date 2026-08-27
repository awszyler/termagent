"""
Bash工具

安全的bash命令执行工具，支持交互式授权和命令验证。
"""

import asyncio
import subprocess
import shlex
import os
import re
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from ..core.models import ToolDefinition, ToolResult
from ..utils.errors import ToolExecutionError
from ..utils.logging import get_logger

logger = get_logger(__name__)

class BashTool:
    """内置Bash命令执行工具"""
    
    # 危险命令模式列表
    DANGEROUS_PATTERNS = [
        r'\brm\s+.*-rf\b',  # rm -rf
        r'\bsudo\b',        # sudo commands
        r'\bsu\b',          # switch user
        r'\bchmod\s+777\b', # chmod 777
        r'\bdd\s+if=',      # dd command
        r'\bmkfs\b',        # format filesystem
        r'\bfdisk\b',       # disk partitioning
        r'\bkill\s+-9\b',   # force kill
        r'\bkillall\b',     # kill all processes
        r'\breboot\b',      # system reboot
        r'\bshutdown\b',    # system shutdown
        r'\binit\s+0\b',    # system halt
        r'\binit\s+6\b',    # system reboot
        r'>\s*/dev/sd[a-z]', # write to disk devices (但不包括/dev/null)
        r'\bcrontab\b',     # cron job modification
        r'\biptables\b',    # firewall rules
        r'\bufw\b',         # ubuntu firewall
        r'\bsystemctl\b',   # systemd service control
        r'\bservice\b',     # service control
        r'\bmount\b',       # mount filesystems
        r'\bumount\b',      # unmount filesystems
        r'\bchroot\b',      # change root
        r'\bhistory\s+-c\b', # clear command history
    ]
    
    # 允许的安全命令
    SAFE_COMMANDS = {
        'ls', 'pwd', 'whoami', 'date', 'echo', 'cat', 'head', 'tail',
        'grep', 'find', 'which', 'type', 'file', 'wc', 'sort', 'uniq',
        'cut', 'awk', 'sed', 'tr', 'basename', 'dirname', 'realpath',
        'stat', 'du', 'df', 'free', 'uptime', 'uname', 'env', 'printenv',
        'ps', 'top', 'htop', 'jobs', 'history', 'alias', 'man', 'help',
        'git', 'curl', 'wget', 'ping', 'nslookup', 'dig', 'host',
        'python', 'python3', 'pip', 'pip3', 'node', 'npm', 'yarn',
        'java', 'javac', 'gcc', 'make', 'cmake', 'docker', 'kubectl',
        'mkdir', 'touch', 'cp', 'mv',  # 添加常用的文件操作命令
        'sleep'  # 添加sleep命令用于测试
    }
    
    def __init__(self, working_directory: Optional[str] = None, timeout: int = 30):
        """
        初始化Bash工具
        
        Args:
            working_directory: 工作目录，默认为当前目录
            timeout: 命令执行超时时间（秒）
        """
        self.working_directory = Path(working_directory) if working_directory else Path.cwd()
        self.timeout = timeout
        self.name = "execute_bash"
        self.description = "Execute bash commands safely with user authorization"
    
    def get_tool_definition(self) -> ToolDefinition:
        """获取工具定义"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for command execution (optional)"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Brief description of what this command will do"
                    }
                },
                "required": ["command", "purpose"]
            }
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行bash命令
        
        Args:
            parameters: 工具参数，包含command、working_directory、purpose
            
        Returns:
            工具执行结果
        """
        try:
            command = parameters.get("command", "").strip()
            purpose = parameters.get("purpose", "")
            working_dir = parameters.get("working_directory")
            
            if not command:
                return ToolResult(
                    call_id="",
                    success=False,
                    result=None,
                    error="命令不能为空"
                )
            
            # 检查是否用户已授权，如果已授权则跳过安全检查
            user_authorized = parameters.get("_user_authorized", False)
            
            if not user_authorized:
                # 验证命令安全性
                safety_result = self._validate_command_safety(command)
                if not safety_result["safe"]:
                    return ToolResult(
                        call_id="",
                        success=False,
                        result=None,
                        error=f"命令被安全检查拒绝: {safety_result['reason']}"
                    )
            else:
                logger.info(f"用户已授权，跳过安全检查: {command}")
            
            # 确定工作目录
            exec_dir = self._resolve_working_directory(working_dir)
            
            # 执行命令
            result = await self._execute_command(command, exec_dir)
            
            return ToolResult(
                call_id="",
                success=result["success"],
                result=result["output"] if result["success"] else None,
                error=result["error"] if not result["success"] else None,
                execution_time=result.get("execution_time")
            )
            
        except Exception as e:
            logger.error(f"Bash工具执行失败: {e}")
            return ToolResult(
                call_id="",
                success=False,
                result=None,
                error=f"执行失败: {str(e)}"
            )
    
    def _validate_command_safety(self, command: str) -> Dict[str, Any]:
        """
        验证命令安全性
        
        Args:
            command: 要验证的命令
            
        Returns:
            验证结果字典，包含safe和reason字段
        """
        # 检查危险模式
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "safe": False,
                    "reason": f"命令包含危险模式: {pattern}"
                }
        
        # 解析命令的第一个词（主命令）
        try:
            # 尝试使用shlex解析，如果失败则使用简单的空格分割
            try:
                tokens = shlex.split(command)
            except ValueError as e:
                # shlex解析失败，使用简单分割
                logger.warning(f"shlex解析失败，使用简单分割: {e}")
                tokens = command.strip().split()
            
            if not tokens:
                return {"safe": False, "reason": "空命令"}
            
            main_command = tokens[0]
            
            # 检查是否为绝对路径的可执行文件
            if main_command.startswith('/'):
                # 允许一些常见的系统命令路径
                allowed_paths = ['/bin/', '/usr/bin/', '/usr/local/bin/']
                if not any(main_command.startswith(path) for path in allowed_paths):
                    return {
                        "safe": False,
                        "reason": f"不允许执行路径外的命令: {main_command}"
                    }
            
            # 检查命令是否在安全列表中
            base_command = os.path.basename(main_command)
            if base_command not in self.SAFE_COMMANDS:
                return {
                    "safe": False,
                    "reason": f"命令 '{base_command}' 不在安全命令列表中"
                }
            
            # 检查特殊字符和操作符
            dangerous_chars = [';', '$(', '`']  # 移除 & | > >> < 因为它们在很多正常命令中使用
            for char in dangerous_chars:
                if char in command:
                    return {
                        "safe": False,
                        "reason": f"命令包含潜在危险字符: {char}"
                    }
            
            # 更精确的危险模式检查
            dangerous_patterns = [
                r'>\s*/dev/(?!null|zero)',  # 重定向到设备文件（但允许/dev/null和/dev/zero）
                r'<\s*/dev/(?!null|zero|stdin)',  # 从设备文件读取（但允许常见的安全设备）
                r'&\s*$',  # 后台执行
            ]
            
            # 检查命令链接，但允许安全的用法
            if '&&' in command:
                # 检查是否所有链接的命令都是安全的
                parts = command.split('&&')
                for part in parts:
                    part = part.strip()
                    if part:
                        try:
                            tokens = shlex.split(part)
                            if tokens:
                                cmd = os.path.basename(tokens[0])
                                if cmd not in self.SAFE_COMMANDS:
                                    return {
                                        "safe": False,
                                        "reason": f"命令链接中包含不安全的命令: {cmd}"
                                    }
                        except ValueError:
                            return {
                                "safe": False,
                                "reason": "命令链接解析失败"
                            }
            
            # 对于 || 操作符，允许常见的错误处理模式
            if '||' in command:
                # 允许 "command || echo" 这样的错误处理模式
                if not re.search(r'\|\|\s*(echo|true|false)', command):
                    return {
                        "safe": False,
                        "reason": "不安全的 || 操作符用法"
                    }
            
            for pattern in dangerous_patterns:
                if re.search(pattern, command):
                    return {
                        "safe": False,
                        "reason": f"命令包含危险模式: {pattern}"
                    }
            
            return {"safe": True, "reason": "命令通过安全检查"}
            
        except ValueError as e:
            return {"safe": False, "reason": f"命令解析失败: {str(e)}"}
    
    def _resolve_working_directory(self, working_dir: Optional[str]) -> Path:
        """
        解析工作目录
        
        Args:
            working_dir: 指定的工作目录
            
        Returns:
            解析后的工作目录路径
        """
        if working_dir:
            specified_dir = Path(working_dir)
            
            # 如果是相对路径，相对于当前工作目录
            if not specified_dir.is_absolute():
                specified_dir = self.working_directory / specified_dir
            
            # 检查目录是否存在且可访问
            if specified_dir.exists() and specified_dir.is_dir():
                # 安全检查：不允许访问系统敏感目录
                sensitive_dirs = ['/etc', '/boot', '/sys', '/proc', '/dev', '/private/etc', '/private/var/root']
                resolved_path = specified_dir.resolve()
                resolved_str = str(resolved_path)
                
                for sensitive in sensitive_dirs:
                    if resolved_str == sensitive or resolved_str.startswith(sensitive + '/'):
                        logger.warning(f"拒绝访问敏感目录: {resolved_path}")
                        return self.working_directory
                
                return resolved_path
            else:
                logger.warning(f"指定的工作目录不存在或不可访问: {specified_dir}")
                return self.working_directory
        
        return self.working_directory
    
    async def _execute_command(self, command: str, working_dir: Path) -> Dict[str, Any]:
        """
        执行命令
        
        Args:
            command: 要执行的命令
            working_dir: 工作目录
            
        Returns:
            执行结果字典
        """
        import time
        start_time = time.time()
        
        try:
            # 对于多行echo命令，使用特殊处理
            if command.strip().startswith('echo') and '\n' in command:
                # 提取echo的内容
                if command.startswith("echo '") and command.endswith("'"):
                    # 单引号包围的多行内容
                    content = command[6:-1]  # 去掉 "echo '" 和最后的 "'"
                    # 直接返回内容，不需要shell执行
                    execution_time = time.time() - start_time
                    return {
                        "success": True,
                        "output": content,
                        "error": None,
                        "execution_time": execution_time
                    }
                elif command.startswith('echo "') and command.endswith('"'):
                    # 双引号包围的多行内容
                    content = command[6:-1]  # 去掉 'echo "' 和最后的 '"'
                    execution_time = time.time() - start_time
                    return {
                        "success": True,
                        "output": content,
                        "error": None,
                        "execution_time": execution_time
                    }
            
            # 使用asyncio.create_subprocess_shell执行命令
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()
            )
            
            # 等待命令完成，设置超时
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                # 超时，终止进程
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "output": None,
                    "error": f"命令执行超时 ({self.timeout}秒)",
                    "execution_time": execution_time
                }
            
            execution_time = time.time() - start_time
            
            # 解码输出
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()
            
            # 检查返回码
            if process.returncode == 0:
                output = stdout_text if stdout_text else "命令执行成功（无输出）"
                return {
                    "success": True,
                    "output": output,
                    "error": None,
                    "execution_time": execution_time
                }
            else:
                error_msg = stderr_text if stderr_text else f"命令执行失败，返回码: {process.returncode}"
                return {
                    "success": False,
                    "output": stdout_text if stdout_text else None,
                    "error": error_msg,
                    "execution_time": execution_time
                }
                
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": None,
                "error": f"命令执行异常: {str(e)}",
                "execution_time": execution_time
            }
    
    def get_command_info(self, command: str) -> Dict[str, Any]:
        """
        获取命令信息，用于显示给用户
        
        Args:
            command: 命令字符串
            
        Returns:
            命令信息字典
        """
        safety_result = self._validate_command_safety(command)
        
        return {
            "command": command,
            "safe": safety_result["safe"],
            "safety_reason": safety_result["reason"],
            "working_directory": str(self.working_directory),
            "timeout": self.timeout
        }
    
    def add_safe_command(self, command: str) -> None:
        """
        添加安全命令到白名单
        
        Args:
            command: 命令名称
        """
        self.SAFE_COMMANDS.add(command)
        logger.info(f"添加安全命令: {command}")
    
    def remove_safe_command(self, command: str) -> None:
        """
        从安全命令白名单中移除命令
        
        Args:
            command: 命令名称
        """
        if command in self.SAFE_COMMANDS:
            self.SAFE_COMMANDS.remove(command)
            logger.info(f"移除安全命令: {command}")
    
    def get_safe_commands(self) -> Set[str]:
        """获取安全命令列表"""
        return self.SAFE_COMMANDS.copy()