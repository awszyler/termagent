"""
配置管理

处理配置文件的加载、验证和管理。
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from .models import ModelConfig, MCPConfig, MCPServerConfig
from ..utils.errors import ConfigurationError
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._model_config: Optional[ModelConfig] = None
        self._mcp_config: Optional[MCPConfig] = None
    
    def load_model_config(self, config_file: str = "model.json") -> ModelConfig:
        """加载AI模型配置"""
        if self._model_config is not None:
            return self._model_config
        
        config_path = self._resolve_config_path(config_file)
        
        try:
            if not config_path.exists():
                logger.warning(f"模型配置文件不存在: {config_path}")
                return self._get_default_model_config()
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 验证必需字段
            required_fields = ['api_url', 'api_key', 'model_name']
            missing_fields = [field for field in required_fields if field not in config_data]
            if missing_fields:
                raise ConfigurationError(
                    f"配置文件缺少必需字段: {', '.join(missing_fields)}",
                    f"文件: {config_path}"
                )
            
            self._model_config = ModelConfig(**config_data)
            logger.info(f"成功加载模型配置: {config_path}")
            return self._model_config
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"配置文件JSON格式错误: {str(e)}",
                f"文件: {config_path}"
            )
        except TypeError as e:
            raise ConfigurationError(
                f"配置参数类型错误: {str(e)}",
                f"文件: {config_path}"
            )
        except Exception as e:
            raise ConfigurationError(
                f"加载配置文件失败: {str(e)}",
                f"文件: {config_path}"
            )
    
    def load_mcp_config(self, config_file: str = "mcp.json") -> MCPConfig:
        """加载MCP配置"""
        if self._mcp_config is not None:
            return self._mcp_config
        
        config_path = self._resolve_config_path(config_file)
        
        try:
            if not config_path.exists():
                logger.info(f"MCP配置文件不存在，使用空配置: {config_path}")
                self._mcp_config = MCPConfig()
                return self._mcp_config
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 解析MCP服务器配置
            servers = {}
            if 'servers' in config_data:
                for name, server_data in config_data['servers'].items():
                    try:
                        servers[name] = MCPServerConfig(name=name, **server_data)
                    except Exception as e:
                        logger.error(f"解析MCP服务器配置失败 '{name}': {e}")
                        continue
            
            self._mcp_config = MCPConfig(servers=servers)
            logger.info(f"成功加载MCP配置: {config_path}")
            return self._mcp_config
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"MCP配置文件JSON格式错误: {str(e)}",
                f"文件: {config_path}"
            )
        except Exception as e:
            logger.error(f"加载MCP配置失败: {e}")
            # MCP配置失败不应该阻止程序运行
            self._mcp_config = MCPConfig()
            return self._mcp_config
    
    def _resolve_config_path(self, config_file: str) -> Path:
        """解析配置文件路径"""
        # 如果是绝对路径，直接使用
        if os.path.isabs(config_file):
            return Path(config_file)
        
        # 相对路径，相对于配置目录
        return self.config_dir / config_file
    
    def _get_default_model_config(self) -> ModelConfig:
        """获取默认模型配置"""
        logger.warning("使用默认模型配置")
        
        # 尝试从环境变量获取配置
        api_url = os.getenv('AI_API_URL')
        api_key = os.getenv('AI_API_KEY')
        model_name = os.getenv('AI_MODEL_NAME')
        
        if not all([api_url, api_key, model_name]):
            raise ConfigurationError(
                "未找到模型配置文件，且环境变量不完整",
                "请创建config/model.json文件或设置环境变量: AI_API_URL, AI_API_KEY, AI_MODEL_NAME"
            )
        
        return ModelConfig(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            temperature=float(os.getenv('AI_TEMPERATURE', '0.01')),
            timeout=int(os.getenv('AI_TIMEOUT', '30'))
        )
    
    def save_model_config(self, config: ModelConfig, config_file: str = "model.json") -> None:
        """保存模型配置到文件"""
        config_path = self._resolve_config_path(config_file)
        
        # 确保配置目录存在
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'api_url': config.api_url,
            'api_key': config.api_key,
            'model_name': config.model_name,
            'temperature': config.temperature,
            'timeout': config.timeout
        }
        
        if config.max_tokens is not None:
            config_data['max_tokens'] = config.max_tokens
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置已保存到: {config_path}")
            
        except Exception as e:
            raise ConfigurationError(
                f"保存配置文件失败: {str(e)}",
                f"文件: {config_path}"
            )
    
    def save_mcp_config(self, config: MCPConfig, config_file: str = "mcp.json") -> None:
        """保存MCP配置到文件"""
        config_path = self._resolve_config_path(config_file)
        
        # 确保配置目录存在
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'servers': {}
        }
        
        for name, server_config in config.servers.items():
            config_data['servers'][name] = {
                'command': server_config.command,
                'args': server_config.args,
                'env': server_config.env,
                'disabled': server_config.disabled
            }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"MCP配置已保存到: {config_path}")
            
        except Exception as e:
            raise ConfigurationError(
                f"保存MCP配置文件失败: {str(e)}",
                f"文件: {config_path}"
            )
    
    def reload_configs(self) -> None:
        """重新加载所有配置"""
        self._model_config = None
        self._mcp_config = None
        logger.info("配置已重置，下次访问时将重新加载")

# 全局配置管理器实例
config_manager = ConfigManager()