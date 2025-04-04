#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
阴阳师自动化脚本 - 模块化版本
支持多设备协同运行，动态配置
"""

import os
import logging
from modules.core import ConfigManager
from modules.automation_engine import AutomationEngine
from modules.yuhun_module import YuhunModule
from modules.baigui_module import BaiguiModule

# 创建日志目录
if not os.path.exists("logs"):
    os.makedirs("logs")

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/auto_click.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("AutoClick")

def setup_directories():
    """确保必要的目录存在"""
    directories = ["logs", "images", "config"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"创建目录: {directory}")

def main():
    """主函数"""
    try:
        # 确保目录结构正确
        setup_directories()
        
        # 初始化自动化引擎
        engine = AutomationEngine("config/settings.json")
        
        # 注册模块
        engine.register_module("yuhun", YuhunModule)
        engine.register_module("baigui", BaiguiModule)
        
        # 启动引擎
        engine.run()
    except Exception as e:
        logger.error(f"运行出错: {str(e)}", exc_info=True)
    finally:
        logger.info("程序退出")

if __name__ == "__main__":
    main() 