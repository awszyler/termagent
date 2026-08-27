"""推理链管理模块"""
import time
from typing import List, Dict, Any, Optional


class ReasoningStep:
    """推理步骤"""
    def __init__(self, action: str, result: Any, reasoning: str):
        self.action = action
        self.result = result
        self.reasoning = reasoning
        self.timestamp = time.time()


class ReasoningChain:
    """推理链管理器"""
    
    def __init__(self, max_steps: int = 5):
        self.steps: List[ReasoningStep] = []
        self.max_steps = max_steps
    
    def add_step(self, action: str, result: Any, reasoning: str):
        """添加推理步骤"""
        step = ReasoningStep(action, result, reasoning)
        self.steps.append(step)
        
        # 保持最大步骤数限制
        if len(self.steps) > self.max_steps:
            self.steps.pop(0)
    
    def get_context_prompt(self) -> str:
        """生成推理上下文提示"""
        if not self.steps:
            return ""
        
        context_lines = ["之前的尝试和结果："]
        for step in self.steps[-3:]:  # 最近3步
            context_lines.append(f"- {step.reasoning}")
        
        return "\n".join(context_lines) + "\n"
    
    def clear(self):
        """清空推理链"""
        self.steps.clear()
    
    def has_failed_attempts(self) -> bool:
        """检查是否有失败的尝试"""
        return any("错误" in step.reasoning or "失败" in step.reasoning 
                  for step in self.steps)
