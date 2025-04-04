"""
核心自动化引擎模块
包含所有基础的自动化功能，包括图像处理、设备连接等
"""

import os
import json
import time
import random
import logging
import subprocess
import threading
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional, Union, Any
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/automation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AutomationCore")

class ConfigManager:
    """配置管理器，负责加载和提供配置信息"""
    
    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return {}
            
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
            
    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False
            
    def update(self, key: str, value: Any) -> None:
        """更新配置项"""
        keys = key.split('.')
        current = self.config
        
        # 遍历到最后一个键之前的所有键
        for i in range(len(keys) - 1):
            k = keys[i]
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
            
        # 设置最后一个键的值
        current[keys[-1]] = value

class DeviceManager:
    """设备管理器，负责设备连接和管理"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.adb_path = self.config.get("adb_path", "adb")
        self.devices = []  # [(device_id, device_info), ...]
        self.active_device = None
        self.last_device_switch_time = 0
        self.switch_interval = self.config.get("device_management.switch_interval", 30)
        
    def restart_adb_server(self) -> bool:
        """重启ADB服务器"""
        try:
            subprocess.run([self.adb_path, "kill-server"], check=True, encoding='utf-8', errors='ignore')
            time.sleep(1)
            subprocess.run([self.adb_path, "start-server"], check=True, encoding='utf-8', errors='ignore')
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"重启ADB服务器失败: {str(e)}")
            return False
            
    def disconnect_all(self) -> None:
        """断开所有设备连接"""
        try:
            subprocess.run([self.adb_path, "disconnect"], check=True, encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"断开所有设备连接失败: {str(e)}")
            
    def list_devices(self) -> List[Tuple[str, str]]:
        """列出所有已连接的设备"""
        print("正在搜索设备...")
        self.devices = []
        
        # 尝试重启ADB服务器并断开所有连接
        self.disconnect_all()
        self.restart_adb_server()
        
        # 获取当前已连接设备
        try:
            result = subprocess.run(
                [self.adb_path, "devices"], 
                capture_output=True, 
                text=True, 
                check=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            device_lines = result.stdout.strip().split('\n')[1:]
            for line in device_lines:
                if line.strip() and '\t' in line:
                    device_id, status = line.split('\t')
                    if status == 'device':
                        if not any(d[0] == device_id for d in self.devices):
                            self.devices.append((device_id, f"设备 {device_id}"))
        except Exception as e:
            logger.error(f"获取设备列表失败: {str(e)}")
            
        # 尝试连接常见的模拟器端口
        common_ports = [5555, 5556, 5557, 5558, 7555, 62001, 62025, 62026, 16384, 16416]
        for port in common_ports:
            device_id = f"127.0.0.1:{port}"
            if not any(d[0] == device_id for d in self.devices):
                try:
                    connect_result = subprocess.run(
                        [self.adb_path, "connect", device_id], 
                        capture_output=True, 
                        text=True,
                        encoding='utf-8',
                        errors='ignore'
                    )
                    if "connected" in connect_result.stdout:
                        # 获取设备信息
                        try:
                            model_result = subprocess.run(
                                [self.adb_path, "-s", device_id, "shell", "getprop ro.product.model"], 
                                capture_output=True, 
                                text=True,
                                encoding='utf-8',
                                errors='ignore'
                            )
                            model = model_result.stdout.strip() or f"未知设备"
                            self.devices.append((device_id, f"{model} ({device_id})"))
                        except:
                            self.devices.append((device_id, f"设备 {device_id}"))
                except Exception as e:
                    logger.debug(f"连接设备 {device_id} 失败: {str(e)}")
                    
        print(f"找到 {len(self.devices)} 个目标设备")
        return self.devices
        
    def select_device(self, index: Optional[int] = None) -> Optional[Tuple[str, str]]:
        """选择一个设备"""
        if not self.devices:
            self.list_devices()
            
        if not self.devices:
            logger.error("没有可用设备")
            return None
            
        if index is None:
            # 如果没有指定索引，返回第一个设备
            self.active_device = self.devices[0]
        elif 0 <= index < len(self.devices):
            # 如果指定了有效索引，返回指定设备
            self.active_device = self.devices[index]
        else:
            logger.error(f"无效的设备索引: {index}")
            return None
            
        logger.info(f"已选择设备: {self.active_device[1]}")
        return self.active_device
        
    def get_active_device(self) -> Optional[Tuple[str, str]]:
        """获取当前活动设备"""
        return self.active_device
        
    def switch_device(self) -> Optional[Tuple[str, str]]:
        """切换到下一个设备"""
        if not self.devices or len(self.devices) <= 1:
            return self.active_device
            
        # 获取当前设备索引
        current_index = next((i for i, d in enumerate(self.devices) 
                             if d[0] == self.active_device[0]), 0)
        
        # 切换到下一个设备
        next_index = (current_index + 1) % len(self.devices)
        self.active_device = self.devices[next_index]
        self.last_device_switch_time = time.time()
        
        logger.info(f"已切换到设备: {self.active_device[1]}")
        return self.active_device
        
    def should_switch_device(self) -> bool:
        """判断是否应该切换设备"""
        if len(self.devices) <= 1:
            return False
            
        return time.time() - self.last_device_switch_time >= self.switch_interval
        
    def get_device_id(self) -> Optional[str]:
        """获取当前活动设备ID"""
        if self.active_device:
            return self.active_device[0]
        return None

class ImageProcessor:
    """图像处理器，负责屏幕截图和图像识别"""
    
    def __init__(self, config_manager: ConfigManager, device_manager: DeviceManager):
        self.config = config_manager
        self.device_manager = device_manager
        self.images_dir = self.config.get("images_dir", "images")
        self.templates = {}  # 缓存加载的模板图像
        self.template_configs = {}  # 模板配置
        self.load_template_configs()
        
    def load_template_configs(self) -> None:
        """加载模板配置"""
        self.template_configs = self.config.get("templates", {})
        
    def get_screen(self) -> Optional[np.ndarray]:
        """获取屏幕截图"""
        device_id = self.device_manager.get_device_id()
        if not device_id:
            logger.error("未选择设备，无法获取屏幕截图")
            return None
            
        try:
            # 使用ADB截图
            subprocess.run(
                [self.device_manager.adb_path, "-s", device_id, "shell", "screencap", "-p", "/sdcard/screen.png"],
                check=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            # 将截图拉取到本地
            subprocess.run(
                [self.device_manager.adb_path, "-s", device_id, "pull", "/sdcard/screen.png", "screen.png"],
                check=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            # 读取截图
            screen = cv2.imread("screen.png")
            return screen
        except Exception as e:
            logger.error(f"获取屏幕截图失败: {str(e)}")
            return None
            
    def load_template(self, template_name: str) -> Optional[np.ndarray]:
        """加载模板图像"""
        if template_name in self.templates:
            return self.templates[template_name]
            
        template_path = os.path.join(self.images_dir, f"{template_name}.png")
        if not os.path.exists(template_path):
            logger.error(f"模板图像不存在: {template_path}")
            return None
            
        try:
            template = cv2.imread(template_path)
            self.templates[template_name] = template
            return template
        except Exception as e:
            logger.error(f"加载模板图像失败: {template_path}, {str(e)}")
            return None
            
    def find_template(self, template_name: str, screen: np.ndarray) -> Optional[Tuple[int, int]]:
        """在屏幕中查找模板"""
        template = self.load_template(template_name)
        if template is None or screen is None:
            return None
            
        # 获取阈值配置
        threshold = self.template_configs.get(template_name, {}).get("threshold", 0.8)
        
        # 使用模板匹配
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            # 计算中心点坐标
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y)
            
        return None
        
    def detect_all_buttons(self, screen: np.ndarray, template_names: List[str]) -> List[Dict]:
        """检测屏幕上的所有按钮"""
        results = []
        
        for template_name in template_names:
            pos = self.find_template(template_name, screen)
            if pos:
                # 获取匹配分数
                template = self.load_template(template_name)
                result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                # 获取优先级
                priority = self.template_configs.get(template_name, {}).get("priority", 0)
                
                results.append({
                    "name": template_name,
                    "position": pos,
                    "score": max_val,
                    "priority": priority
                })
                
        # 按优先级排序，优先级高（数值小）的排在前面
        results.sort(key=lambda x: x["priority"])
        return results

class InputController:
    """输入控制器，负责模拟点击和输入"""
    
    def __init__(self, device_manager: DeviceManager, config_manager: ConfigManager):
        self.device_manager = device_manager
        self.config = config_manager
        self.last_click = None
        
    def click(self, x: int, y: int) -> bool:
        """模拟点击屏幕"""
        device_id = self.device_manager.get_device_id()
        if not device_id:
            logger.error("未选择设备，无法执行点击")
            return False
            
        try:
            subprocess.run(
                [self.device_manager.adb_path, "-s", device_id, "shell", "input", "tap", str(x), str(y)],
                check=True,
                encoding='utf-8',
                errors='ignore'
            )
            self.last_click = (x, y, time.time())
            return True
        except Exception as e:
            logger.error(f"点击屏幕失败: {str(e)}")
            return False
            
    def random_click(self, x: int, y: int, template_name: str = None) -> bool:
        """在按钮周围随机位置点击"""
        # 默认随机偏移范围
        offset_range = 10
        
        # 计算随机偏移
        offset_x = random.randint(-offset_range, offset_range)
        offset_y = random.randint(-offset_range, offset_range)
        
        # 添加偏移后的坐标
        target_x = x + offset_x
        target_y = y + offset_y
        
        # 记录点击信息
        if template_name:
            logger.debug(f"随机点击 {template_name}: ({target_x}, {target_y})")
        else:
            logger.debug(f"随机点击: ({target_x}, {target_y})")
            
        return self.click(target_x, target_y)
        
    def random_delay(self, template_name: str = None) -> None:
        """执行随机延迟"""
        # 获取模板特定的延迟配置或使用默认值
        if template_name:
            delay_range = self.config.get(f"templates.{template_name}.delay_after", [0.5, 1.0])
        else:
            delay_range = [0.5, 1.0]
            
        delay = random.uniform(delay_range[0], delay_range[1])
        time.sleep(delay)
        
    def random_click_area(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """在指定区域内随机点击"""
        random_x = random.randint(x1, x2)
        random_y = random.randint(y1, y2)
        return self.click(random_x, random_y) 