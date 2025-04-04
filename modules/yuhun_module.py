"""
御魂自动化模块
实现御魂副本的自动化
"""

import time
import random
import logging
from typing import Dict, List, Tuple, Optional
import threading
from datetime import datetime
from modules.core import ConfigManager, DeviceManager, ImageProcessor, InputController
from modules.automation_engine import AutomationModule

logger = logging.getLogger("YuhunModule")

class YuhunModule(AutomationModule):
    """
    御魂自动化模块
    主要功能：
    - 自动战斗流程控制
    - 智能检测notupo
    - 特殊按钮处理
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
        self.check_notupo_after_button10 = False
        self.last_button10_click_time = 0
        
    def initialize(self) -> bool:
        """初始化模块"""
        logger.info(f"初始化御魂模块")
        # 可以在这里加载御魂特有的资源
        return True
        
    def run_once(self, stop_event: threading.Event, pause_event: threading.Event) -> bool:
        """运行一次御魂自动化流程"""
        # 添加最大执行时间限制
        max_run_time = self.config.get("device_management.max_single_run_time", 5)  # 最长5秒
        start_time = time.time()
        
        while not stop_event.is_set():
            # 检查是否超过最大执行时间
            if time.time() - start_time > max_run_time:
                return False  # 超过最大执行时间，退出本次run调用
                
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
                    time.sleep(1)
                    continue
                
                # 检查lose和notupo
                lose_pos = self.image_processor.find_template("lose", screen)
                if lose_pos:
                    logger.info(f"{datetime.now().strftime('%H:%M:%S')} - 检测到lose")
                    pause_event.set()
                    return False
                
                # 如果刚点击了button10，立即检查notupo
                if self.check_notupo_after_button10:
                    notupo_pos = self.image_processor.find_template("notupo", screen)
                    if notupo_pos:
                        logger.info(f"{datetime.now().strftime('%H:%M:%S')} - 检测到notupo")
                        pause_event.set()
                        return False
                    # 如果距离点击button10超过1秒还没检测到notupo，就继续正常流程
                    if time.time() - self.last_button10_click_time > 1:
                        self.check_notupo_after_button10 = False
                    else:
                        time.sleep(0.1)
                        continue
                
                # 检测屏幕上的所有按钮
                buttons = self.image_processor.detect_all_buttons(screen, self.template_sets)
                
                # 如果找到了按钮，点击优先级最高的
                if buttons:
                    button = buttons[0]  # 取优先级最高的按钮
                    button_name = button["name"]
                    button_pos = button["position"]
                    
                    # 特殊处理button5和button4
                    if button_name == "button5" and self.last_button_clicked != "button4":
                        logger.info(f"检测到button5，但上一次点击的不是button4，先寻找button4")
                        # 尝试找button4
                        button4_pos = self.image_processor.find_template("button4", screen)
                        if button4_pos:
                            logger.info(f"找到button4，先点击它")
                            self.click_button("button4", button4_pos[0], button4_pos[1])
                            continue
                    
                    # 特殊处理button10
                    if button_name == "button10":
                        if self.click_button(button_name, button_pos[0], button_pos[1]):
                            self.last_button10_click_time = time.time()
                            self.check_notupo_after_button10 = True
                            return True
                    
                    # 特殊处理button7
                    elif button_name == "button7":
                        # 等待特定时间
                        wait_time = random.uniform(0.5, 1.5)
                        # 检查是否会超时
                        if time.time() - start_time + wait_time > max_run_time:
                            return False  # 等待会导致超时，所以直接返回
                        time.sleep(wait_time)
                        
                        if self.click_button(button_name, button_pos[0], button_pos[1]):
                            return True
                    
                    # 处理其他按钮
                    else:
                        if self.click_button(button_name, button_pos[0], button_pos[1]):
                            return True
                
                # 没有找到按钮，等待一小段时间
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"运行出错: {str(e)}")
                time.sleep(1)
                
        return False
        
    def cleanup(self) -> None:
        """清理资源"""
        logger.info("清理御魂模块资源")
        # 清理资源，例如关闭特定的连接等 