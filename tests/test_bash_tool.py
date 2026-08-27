"""
测试Bash工具
"""

import pytest
import tempfile
import os
from pathlib import Path
from src.tools.bash_tool import BashTool
from src.core.models import ToolResult

class TestBashTool:
    """测试BashTool类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.bash_tool = BashTool(working_directory=self.temp_dir, timeout=10)
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_tool_definition(self):
        """测试获取工具定义"""
        definition = self.bash_tool.get_tool_definition()
        
        assert definition.name == "execute_bash"
        assert "bash" in definition.description.lower()
        assert "command" in definition.parameters["properties"]
        assert "purpose" in definition.parameters["properties"]
        assert "command" in definition.parameters["required"]
        assert "purpose" in definition.parameters["required"]
    
    def test_validate_safe_command(self):
        """测试验证安全命令"""
        # 安全命令
        safe_commands = [
            "ls -la",
            "pwd",
            "echo 'Hello World'",
            "cat /etc/passwd",
            "grep 'pattern' file.txt",
            "find . -name '*.py'",
            "ps aux",
            "git status"
        ]
        
        for command in safe_commands:
            result = self.bash_tool._validate_command_safety(command)
            assert result["safe"], f"命令应该是安全的: {command}, 原因: {result['reason']}"
    
    def test_validate_dangerous_command(self):
        """测试验证危险命令"""
        # 危险命令
        dangerous_commands = [
            "rm -rf /",
            "sudo rm file.txt",
            "chmod 777 /etc/passwd",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
            "kill -9 1",
            "killall python",
            "reboot",
            "shutdown now",
            "crontab -e",
            "iptables -F",
            "systemctl stop ssh",
            "mount /dev/sda1 /mnt",
            "chroot /mnt"
        ]
        
        for command in dangerous_commands:
            result = self.bash_tool._validate_command_safety(command)
            assert not result["safe"], f"命令应该是危险的: {command}"
    
    def test_validate_unknown_command(self):
        """测试验证未知命令"""
        unknown_commands = [
            "unknown_command",
            "malicious_script",
            "/usr/local/bin/suspicious_tool"
        ]
        
        for command in unknown_commands:
            result = self.bash_tool._validate_command_safety(command)
            assert not result["safe"], f"未知命令应该被拒绝: {command}"
    
    def test_validate_command_with_dangerous_chars(self):
        """测试包含危险字符的命令"""
        dangerous_char_commands = [
            "ls; rm file.txt",
            "echo test && rm file.txt",
            "echo $(rm file.txt)",
            "echo `rm file.txt`",
            "ls > /dev/sda1"
            # 注意：管道右侧的命令（如 "ls | rm"）目前不会被校验。
            # 见下方 test_pipe_targets_are_not_validated_known_gap（已知缺口，xfail）。
        ]

        for command in dangerous_char_commands:
            result = self.bash_tool._validate_command_safety(command)
            assert not result["safe"], f"包含危险字符的命令应该被拒绝: {command}"

    @pytest.mark.xfail(
        strict=True,
        reason="已知缺口：单管道 | 不会被拆解，只有第一段命令会做白名单校验。"
               "'&&' 会逐段校验，'|' 不会。修复方式是对管道每一段都跑白名单，"
               "目前尚未实现，README 的安全说明里已如实记录该限制。"
    )
    def test_pipe_targets_are_not_validated_known_gap(self):
        """管道右侧命令应当同样受白名单约束（目前未实现）"""
        result = self.bash_tool._validate_command_safety("ls | rm")
        assert not result["safe"], "管道右侧的 rm 应该被拒绝"
    
    def test_validate_safe_pipes(self):
        """测试安全的管道命令"""
        safe_pipe_commands = [
            "ls -la | grep .py",
            "cat file.txt | head -10",
            "ps aux | grep python",
            "find . -name '*.txt' | wc -l"
        ]
        
        for command in safe_pipe_commands:
            result = self.bash_tool._validate_command_safety(command)
            assert result["safe"], f"安全的管道命令应该被允许: {command}"
    
    @pytest.mark.asyncio
    async def test_execute_simple_command(self):
        """测试执行简单命令"""
        parameters = {
            "command": "echo 'Hello World'",
            "purpose": "Test echo command"
        }
        
        result = await self.bash_tool.execute(parameters)
        
        assert result.success
        assert "Hello World" in result.result
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_execute_ls_command(self):
        """测试执行ls命令"""
        # 在临时目录中创建一个文件
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")
        
        parameters = {
            "command": "ls -la",
            "purpose": "List directory contents"
        }
        
        result = await self.bash_tool.execute(parameters)
        
        assert result.success
        assert "test.txt" in result.result
    
    @pytest.mark.asyncio
    async def test_execute_with_working_directory(self):
        """测试在指定工作目录中执行命令"""
        # 创建子目录
        sub_dir = Path(self.temp_dir) / "subdir"
        sub_dir.mkdir()
        
        parameters = {
            "command": "pwd",
            "purpose": "Check current directory",
            "working_directory": str(sub_dir)
        }
        
        result = await self.bash_tool.execute(parameters)
        
        assert result.success
        assert str(sub_dir) in result.result
    
    @pytest.mark.asyncio
    async def test_execute_dangerous_command(self):
        """测试执行危险命令被拒绝"""
        parameters = {
            "command": "rm -rf /",
            "purpose": "Dangerous command test"
        }
        
        result = await self.bash_tool.execute(parameters)
        
        assert not result.success
        assert "安全检查拒绝" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_empty_command(self):
        """测试执行空命令"""
        parameters = {
            "command": "",
            "purpose": "Empty command test"
        }
        
        result = await self.bash_tool.execute(parameters)
        
        assert not result.success
        assert "命令不能为空" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_command(self):
        """测试执行不存在的命令"""
        parameters = {
            "command": "nonexistent_command_12345",
            "purpose": "Test nonexistent command"
        }
        
        result = await self.bash_tool.execute(parameters)
        
        assert not result.success
        assert "不在安全命令列表中" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_command_with_error(self):
        """测试执行会产生错误的命令"""
        parameters = {
            "command": "cat nonexistent_file.txt",
            "purpose": "Test command that produces error"
        }
        
        result = await self.bash_tool.execute(parameters)
        
        assert not result.success
        assert result.error is not None
    
    def test_resolve_working_directory(self):
        """测试解析工作目录"""
        # 测试绝对路径
        abs_path = self.bash_tool._resolve_working_directory(self.temp_dir)
        assert abs_path.resolve() == Path(self.temp_dir).resolve()
        
        # 测试相对路径
        sub_dir = Path(self.temp_dir) / "subdir"
        sub_dir.mkdir()
        rel_path = self.bash_tool._resolve_working_directory("subdir")
        assert rel_path.resolve() == sub_dir.resolve()
        
        # 测试不存在的目录
        nonexistent = self.bash_tool._resolve_working_directory("nonexistent")
        assert nonexistent.resolve() == Path(self.temp_dir).resolve()
    
    def test_resolve_sensitive_directory(self):
        """测试拒绝访问敏感目录"""
        sensitive_dirs = ["/etc", "/boot", "/sys", "/proc", "/dev"]
        
        for sensitive_dir in sensitive_dirs:
            if Path(sensitive_dir).exists():
                resolved = self.bash_tool._resolve_working_directory(sensitive_dir)
                # 应该回退到默认工作目录
                assert resolved.resolve() == Path(self.temp_dir).resolve()
    
    def test_get_command_info(self):
        """测试获取命令信息"""
        command = "ls -la"
        info = self.bash_tool.get_command_info(command)
        
        assert info["command"] == command
        assert info["safe"] is True
        assert "working_directory" in info
        assert "timeout" in info
    
    def test_safe_command_management(self):
        """测试安全命令管理"""
        # 添加新的安全命令
        self.bash_tool.add_safe_command("custom_tool")
        assert "custom_tool" in self.bash_tool.get_safe_commands()
        
        # 验证新命令现在是安全的
        result = self.bash_tool._validate_command_safety("custom_tool --help")
        assert result["safe"]
        
        # 移除安全命令
        self.bash_tool.remove_safe_command("custom_tool")
        assert "custom_tool" not in self.bash_tool.get_safe_commands()
        
        # 验证命令现在不安全
        result = self.bash_tool._validate_command_safety("custom_tool --help")
        assert not result["safe"]
    
    @pytest.mark.asyncio
    async def test_command_timeout(self):
        """测试命令超时"""
        # 创建一个超时时间很短的工具
        short_timeout_tool = BashTool(working_directory=self.temp_dir, timeout=1)
        
        parameters = {
            "command": "sleep 5",  # 睡眠5秒，但超时时间只有1秒
            "purpose": "Test command timeout"
        }
        
        result = await short_timeout_tool.execute(parameters)
        
        assert not result.success
        assert "超时" in result.error
    
    def test_command_parsing_edge_cases(self):
        """测试命令解析的边界情况"""
        # 测试带引号的命令
        result = self.bash_tool._validate_command_safety('echo "hello world"')
        assert result["safe"]
        
        # 测试带单引号的命令
        result = self.bash_tool._validate_command_safety("echo 'hello world'")
        assert result["safe"]
        
        # 测试复杂的引号嵌套
        result = self.bash_tool._validate_command_safety('echo "It\'s a test"')
        assert result["safe"]