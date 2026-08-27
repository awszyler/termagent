#!/usr/bin/env python3
"""
人工测试模式启动脚本

这是一个便捷的启动脚本，直接启动终端AI助手的人工测试模式。
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from src.main import TerminalAIAssistant
from src.utils.logging import setup_logging

async def main():
    """人工测试模式主函数"""
    print("🧪 终端AI助手 - 人工测试模式")
    print("=" * 60)
    
    # 设置详细日志
    setup_logging(debug=True)
    
    # 创建应用实例
    app = TerminalAIAssistant(manual_test_mode=True)
    
    try:
        print(f"📝 测试日志文件: {app.test_log_file}")
        print(f"⏰ 测试开始时间: {app.session_start_time}")
        print("💡 测试完成后将自动生成优化提示")
        print("🔧 按 Ctrl+C 结束测试并生成优化提示")
        print("=" * 60)
        
        # 运行应用
        await app.run()
        
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("🧪 人工测试会话结束")
        print("📝 正在生成优化提示...")
        
        # 生成优化提示
        optimization_prompt = app.generate_optimization_prompt()
        
        # 保存优化提示到文件
        import datetime
        timestamp = app.session_start_time.strftime("%Y%m%d_%H%M%S")
        prompt_file = f"optimization_prompt_{timestamp}.md"
        
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(optimization_prompt)
        
        print(f"✅ 优化提示已保存到: {prompt_file}")
        print(f"📊 测试日志文件: {app.test_log_file}")
        
        print("\n💡 下次优化时的提示:")
        print("=" * 60)
        print("请将以下文件提供给AI助手进行分析:")
        print(f"1. 测试日志: {app.test_log_file}")
        print(f"2. 优化提示: {prompt_file}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 记录异常到测试日志
        if hasattr(app, 'manual_test_mode') and app.manual_test_mode:
            app._log_error(e, "程序异常退出")
    
    finally:
        # 清理资源
        if hasattr(app, 'cleanup'):
            await app.cleanup()

if __name__ == "__main__":
    print("🚀 启动人工测试模式...")
    print("📖 使用说明请查看: MANUAL_TEST_MODE.md")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"\n💥 启动失败: {e}")
        sys.exit(1)