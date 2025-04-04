"""
百鬼夜行自动化模块
实现百鬼夜行的自动化
"""

import time
import random
import logging
from typing import Dict, List, Tuple, Optional
import threading
from datetime import datetime
from modules.core import ConfigManager, DeviceManager, ImageProcessor, InputController
from modules.automation_engine import AutomationModule

logger = logging.getLogger("BaiguiModule")

class BaiguiModule(AutomationModule):
    """
    百鬼夜行自动化模块
    主要功能：
    - 自动进入百鬼夜行
    - 自动开始战斗
    - 自动结算
    """
    
    def __init__(self, 
                 config_manager: ConfigManager, 
                 device_manager: DeviceManager,
                 image_processor: ImageProcessor,
                 input_controller: InputController,
                 module_config: Dict):
        super().__init__(
            config_manager, 
            device_manager,
            image_processor,
            input_controller,
            module_config
        )
        
        # 状态标志
        self.consecutive_errors = 0  # 连续错误计数
        
    def initialize(self) -> bool:
        """初始化模块"""
        logger.info(f"初始化百鬼夜行模块")
        # 可以在这里加载百鬼夜行特有的资源
        return True
        
    def run_once(self, stop_event: threading.Event, pause_event: threading.Event) -> bool:
        """运行一次百鬼夜行自动化流程"""
        # 添加最大执行时间限制
        max_run_time = self.config.get("device_management.max_single_run_time", 5)  # 最长5秒
        start_time = time.time()
        
        try:
            # 检查是否需要暂停
            if pause_event.is_set():
                time.sleep(1)
                return False
            
            # 多设备支持：检查是否需要切换设备
            if self.device_manager.should_switch_device():
                logger.info(f"切换到下一个设备")
                self.device_manager.switch_device()
            
            # 获取屏幕截图
            screen = self.image_processor.get_screen()
            if screen is None:
                self.consecutive_errors += 1
                if self.consecutive_errors > 5:
                    logger.error("连续截图失败5次，暂停运行")
                    pause_event.set()
                    return False
                return False
                
            self.consecutive_errors = 0  # 重置错误计数
            
            # 检查是否超过最大执行时间
            if time.time() - start_time > max_run_time:
                return False  # 超过最大执行时间，退出本次run调用
            
            # 检测屏幕上的所有按钮
            buttons = self.image_processor.detect_all_buttons(screen, self.template_sets)
            
            # 如果找到了按钮，点击优先级最高的
            if buttons:
                button = buttons[0]  # 取优先级最高的按钮
                button_name = button["name"]
                button_pos = button["position"]
                
                # 特殊处理不同按钮
                if button_name == "button1":  # 进入按钮
                    logger.info(f"检测到进入按钮")
                    if self.click_button(button_name, button_pos[0], button_pos[1]):
                        return True
                        
                elif button_name == "button2":  # 开始按钮
                    logger.info(f"检测到开始按钮")
                    if self.click_button(button_name, button_pos[0], button_pos[1]):
                        # 等待一段时间后检查结算按钮
                        wait_time = random.uniform(1, 2)
                        # 检查是否会超时
                        if time.time() - start_time + wait_time > max_run_time:
                            return True  # 等待会导致超时，所以直接返回
                        time.sleep(wait_time)
                        
                        # 获取新的屏幕截图
                        screen = self.image_processor.get_screen()
                        if screen is not None:
                            button3_pos = self.image_processor.find_template("button3", screen)
                            if button3_pos:
                                logger.info(f"检测到结算按钮")
                                self.click_button("button3", button3_pos[0], button3_pos[1])
                        return True
                        
                elif button_name == "button3":  # 结算按钮
                    logger.info(f"检测到结算按钮")
                    if self.click_button(button_name, button_pos[0], button_pos[1]):
                        return True
                        
                else:  # 其他按钮
                    if self.click_button(button_name, button_pos[0], button_pos[1]):
                        return True
            
            # 没有找到按钮，尝试随机点击区域
            if not buttons and time.time() - start_time < max_run_time * 0.8:
                # 随机点击屏幕中间区域
                screen_h, screen_w = screen.shape[:2]
                center_x, center_y = screen_w // 2, screen_h // 2
                
                # 定义随机点击区域
                x1 = center_x - 100
                y1 = center_y - 100
                x2 = center_x + 100
                y2 = center_y + 100
                
                # 偶尔进行随机点击
                if random.random() < 0.2:  # 20%的概率随机点击
                    logger.info("没有找到按钮，进行随机点击")
                    if self.input_controller.random_click_area(x1, y1, x2, y2):
                        return True
            
            # 没有动作，等待一小段时间
            time.sleep(0.2)
                
        except Exception as e:
            logger.error(f"运行出错: {str(e)}")
            time.sleep(1)
            
        return False
        
    def cleanup(self) -> None:
        """清理资源"""
        logger.info("清理百鬼夜行模块资源")
        # 清理资源，例如关闭特定的连接等 