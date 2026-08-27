"""
测试配置管理
"""

import json
import pytest
import tempfile
import os
from pathlib import Path
from src.core.config import ConfigManager
from src.core.models import ModelConfig, MCPConfig, MCPServerConfig
from src.utils.errors import ConfigurationError

class TestConfigManager:
    """测试ConfigManager类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager(self.temp_dir)
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_valid_model_config(self):
        """测试加载有效的模型配置"""
        config_data = {
            "api_url": "https://api.example.com",
            "api_key": "test-key",
            "model_name": "test-model",
            "temperature": 0.5,
            "timeout": 60
        }
        
        config_file = Path(self.temp_dir) / "model.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = self.config_manager.load_model_config()
        assert config.api_url == "https://api.example.com"
        assert config.api_key == "test-key"
        assert config.model_name == "test-model"
        assert config.temperature == 0.5
        assert config.timeout == 60
    
    def test_load_model_config_missing_file(self):
        """测试加载不存在的模型配置文件"""
        # 设置环境变量作为默认配置
        os.environ['AI_API_URL'] = 'https://default.api.com'
        os.environ['AI_API_KEY'] = 'default-key'
        os.environ['AI_MODEL_NAME'] = 'default-model'
        
        try:
            config = self.config_manager.load_model_config()
            assert config.api_url == 'https://default.api.com'
            assert config.api_key == 'default-key'
            assert config.model_name == 'default-model'
        finally:
            # 清理环境变量
            for key in ['AI_API_URL', 'AI_API_KEY', 'AI_MODEL_NAME']:
                os.environ.pop(key, None)
    
    def test_load_model_config_invalid_json(self):
        """测试加载无效JSON格式的配置文件"""
        config_file = Path(self.temp_dir) / "model.json"
        with open(config_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ConfigurationError, match="配置文件JSON格式错误"):
            self.config_manager.load_model_config()
    
    def test_load_model_config_missing_required_fields(self):
        """测试加载缺少必需字段的配置文件"""
        config_data = {
            "api_url": "https://api.example.com",
            # 缺少 api_key 和 model_name
        }
        
        config_file = Path(self.temp_dir) / "model.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        with pytest.raises(ConfigurationError, match="配置文件缺少必需字段"):
            self.config_manager.load_model_config()
    
    def test_load_valid_mcp_config(self):
        """测试加载有效的MCP配置"""
        config_data = {
            "servers": {
                "filesystem": {
                    "command": "uvx",
                    "args": ["mcp-server-filesystem"],
                    "env": {"TEST": "value"},
                    "disabled": False
                }
            }
        }
        
        config_file = Path(self.temp_dir) / "mcp.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = self.config_manager.load_mcp_config()
        assert "filesystem" in config.servers
        server = config.servers["filesystem"]
        assert server.command == "uvx"
        assert server.args == ["mcp-server-filesystem"]
        assert server.env == {"TEST": "value"}
        assert server.disabled is False
    
    def test_load_mcp_config_missing_file(self):
        """测试加载不存在的MCP配置文件"""
        config = self.config_manager.load_mcp_config()
        assert isinstance(config, MCPConfig)
        assert len(config.servers) == 0
    
    def test_load_mcp_config_invalid_server(self):
        """测试加载包含无效服务器配置的MCP文件"""
        config_data = {
            "servers": {
                "valid_server": {
                    "command": "uvx",
                    "args": ["valid-package"]
                },
                "invalid_server": {
                    # 缺少必需的 command 字段
                    "args": ["invalid-package"]
                }
            }
        }
        
        config_file = Path(self.temp_dir) / "mcp.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = self.config_manager.load_mcp_config()
        # 应该只加载有效的服务器
        assert "valid_server" in config.servers
        assert "invalid_server" not in config.servers
    
    def test_save_model_config(self):
        """测试保存模型配置"""
        config = ModelConfig(
            api_url="https://api.example.com",
            api_key="test-key",
            model_name="test-model",
            temperature=0.7,
            timeout=45
        )
        
        self.config_manager.save_model_config(config)
        
        # 验证文件是否正确保存
        config_file = Path(self.temp_dir) / "model.json"
        assert config_file.exists()
        
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["api_url"] == "https://api.example.com"
        assert saved_data["api_key"] == "test-key"
        assert saved_data["model_name"] == "test-model"
        assert saved_data["temperature"] == 0.7
        assert saved_data["timeout"] == 45
    
    def test_save_mcp_config(self):
        """测试保存MCP配置"""
        server_config = MCPServerConfig(
            name="test-server",
            command="uvx",
            args=["test-package"],
            env={"TEST": "value"}
        )
        
        config = MCPConfig(servers={"test-server": server_config})
        
        self.config_manager.save_mcp_config(config)
        
        # 验证文件是否正确保存
        config_file = Path(self.temp_dir) / "mcp.json"
        assert config_file.exists()
        
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert "servers" in saved_data
        assert "test-server" in saved_data["servers"]
        server_data = saved_data["servers"]["test-server"]
        assert server_data["command"] == "uvx"
        assert server_data["args"] == ["test-package"]
        assert server_data["env"] == {"TEST": "value"}
    
    def test_resolve_absolute_path(self):
        """测试解析绝对路径"""
        absolute_path = "/tmp/test_config.json"
        resolved = self.config_manager._resolve_config_path(absolute_path)
        assert str(resolved) == absolute_path
    
    def test_resolve_relative_path(self):
        """测试解析相对路径"""
        relative_path = "test_config.json"
        resolved = self.config_manager._resolve_config_path(relative_path)
        expected = Path(self.temp_dir) / relative_path
        assert resolved == expected
    
    def test_reload_configs(self):
        """测试重新加载配置"""
        # 先加载一次配置
        config_data = {
            "api_url": "https://api.example.com",
            "api_key": "test-key",
            "model_name": "test-model"
        }
        
        config_file = Path(self.temp_dir) / "model.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config1 = self.config_manager.load_model_config()
        
        # 重新加载配置
        self.config_manager.reload_configs()
        
        # 再次加载应该重新读取文件
        config2 = self.config_manager.load_model_config()
        
        # 虽然内容相同，但应该是不同的对象实例
        assert config1 is not config2
        assert config1.api_url == config2.api_url