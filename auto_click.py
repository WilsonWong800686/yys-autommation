"""
阴阳师自动化脚本 v1.1-dev
功能特点：
1. 自动检测并处理御魂战斗流程
2. 智能识别notupo并立即停止
3. 特殊处理button7和button10
4. 多设备并行支持
5. 可配置运行时间
6. [开发中] 更多功能优化...

版本历史：
- v1.0 (2024-03-19): 首个稳定版本，实现基础自动化功能
- v1.1-dev: 开发中，计划添加新功能

作者：Claude
版本：1.1-dev
日期：2024-03-19
"""

import os
import time
import random
import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import logging
import json
import glob
import threading
from queue import Queue
import msvcrt
import re
import subprocess
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'  # 添加线程名称到日志格式
)
logger = logging.getLogger(__name__)

class YuhunAutomation:
    """
    御魂自动化类 v1.0
    主要功能：
    - 自动战斗流程控制
    - 智能检测notupo
    - 特殊按钮处理
    """
    def __init__(self, device_id: str, device_info: str):
        self.device_id = device_id
        self.device_info = device_info
        self.clicker = AutoClicker()
        self.clicker.emulator_address = device_id
        self.is_running = True
        self.total_runs = 0
        
    def run(self, template_configs: Dict[str, Dict], stop_event: threading.Event, pause_event: threading.Event):
        """运行御魂自动化"""
        # 添加最大执行时间限制
        max_run_time = 5  # 最长5秒
        start_time = time.time()
        
        while not stop_event.is_set():
            # 检查是否超过最大执行时间
            if time.time() - start_time > max_run_time:
                return  # 超过最大执行时间，退出本次run调用
                
            try:
                # 检查是否需要暂停
                if pause_event.is_set():
                    time.sleep(1)
                    continue
                
                # 获取屏幕截图
                screen = self.clicker.get_screen()
                if screen is None:
                    time.sleep(1)
                    continue
                
                # 检查lose和notupo
                lose_pos = self.clicker.find_template("lose", screen)
                if lose_pos:
                    logger.info(f"{datetime.now().strftime('%H:%M:%S')} - {self.device_info} 检测到lose")
                    pause_event.set()
                    return
                
                # 如果刚点击了button10，立即检查notupo
                if self.clicker.check_notupo_after_button10:
                    notupo_pos = self.clicker.find_template("notupo", screen)
                    if notupo_pos:
                        logger.info(f"{datetime.now().strftime('%H:%M:%S')} - {self.device_info} 检测到notupo")
                        pause_event.set()
                        return
                    # 如果距离点击button10超过1秒还没检测到notupo，就继续正常流程
                    if time.time() - self.clicker.last_button10_click_time > 1:
                        self.clicker.check_notupo_after_button10 = False
                    else:
                        time.sleep(0.1)
                        continue
                
                # 检查其他按钮
                clicked = False
                for template_name in self.clicker.get_template_names():
                    # 再次检查是否超时
                    if time.time() - start_time > max_run_time:
                        return  # 超过最大执行时间，退出本次run调用
                        
                    if stop_event.is_set() or pause_event.is_set():
                        break
                        
                    pos = self.clicker.find_template(template_name, screen)
                    if pos:
                        x, y = pos
                        
                        # 特殊处理button10
                        if template_name == "button10":
                            if self.clicker.random_click(x, y, template_name):
                                self.clicker.last_button10_click_time = time.time()
                                self.clicker.check_notupo_after_button10 = True
                                logger.info(f"{datetime.now().strftime('%H:%M:%S')} - {self.device_info} 点击 button10")
                                clicked = True
                                break
                        
                        # 特殊处理button7
                        elif template_name == "button7":
                            # 检查是否会超时
                            wait_time = random.uniform(self.clicker.button7_wait_range[0], self.clicker.button7_wait_range[1])
                            if time.time() - start_time + wait_time > max_run_time:
                                return  # 等待会导致超时，所以直接返回
                            time.sleep(wait_time)
                            if self.clicker.random_click(x, y, template_name):
                                logger.info(f"{datetime.now().strftime('%H:%M:%S')} - {self.device_info} 点击 button7")
                                clicked = True
                                # 检查延迟是否会导致超时
                                if time.time() - start_time + 1 > max_run_time:  # 假设延迟最多1秒
                                    return
                                self.clicker.random_delay(template_name)
                                break
                        
                        # 处理其他按钮
                        else:
                            if self.clicker.random_click(x, y, template_name):
                                clicked = True
                                # 检查延迟是否会导致超时
                                if time.time() - start_time + 1 > max_run_time:  # 假设延迟最多1秒
                                    return
                                self.clicker.random_delay(template_name)
                                break
                
                if not clicked:
                    time.sleep(0.2)
                    
            except Exception as e:
                logger.error(f"{datetime.now().strftime('%H:%M:%S')} - {self.device_info} 错误: {str(e)}")
                time.sleep(1)

class DeviceThread(threading.Thread):
    """
    设备线程类 v1.0
    主要功能：
    - 设备独立控制
    - 运行时间管理
    - 状态监控
    """
    def __init__(self, device_id: str, device_info: str, template_configs: Dict[str, Dict], 
                 stop_event: threading.Event, run_duration: int):
        super().__init__(name=f"Device-{device_id}")
        self.device_id = device_id
        self.device_info = device_info
        self.template_configs = template_configs
        self.stop_event = stop_event
        self.pause_event = threading.Event()
        self.automation = YuhunAutomation(device_id, device_info)
        self.start_time = None
        self.run_duration = run_duration  # 运行时长（分钟）
        
    def run(self):
        """线程运行函数"""
        try:
            self.start_time = datetime.now()
            end_time = self.start_time + timedelta(minutes=self.run_duration)
            
            logger.info(f"设备 {self.device_info} 开始运行")
            logger.info(f"计划运行时间: {self.run_duration} 分钟")
            logger.info(f"预计结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            while not self.stop_event.is_set():
                current_time = datetime.now()
                # 强制检查运行时间，确保不会超过设定时间
                if current_time >= end_time:
                    logger.info(f"设备 {self.device_info} 已达到预定运行时间，停止运行")
                    self.stop_event.set()
                    break
                    
                remaining_minutes = (end_time - current_time).total_seconds() / 60
                if int(remaining_minutes) % 10 == 0 and int(remaining_minutes) > 0:  # 每10分钟显示一次剩余时间
                    logger.info(f"设备 {self.device_info} 剩余运行时间: {int(remaining_minutes)} 分钟")
                
                # 运行御魂自动化，但限制单次运行时间，确保能及时检查是否到达结束时间
                start_run = datetime.now()
                self.automation.run(self.template_configs, self.stop_event, self.pause_event)
                # 如果运行时间过长，添加日志记录
                run_time = (datetime.now() - start_run).total_seconds()
                if run_time > 30:  # 如果单次运行超过30秒，记录日志
                    logger.warning(f"设备 {self.device_info} 单次运行耗时 {run_time:.2f} 秒，可能影响时间控制")
                
        except Exception as e:
            logger.error(f"设备 {self.device_info} 线程运行出错: {str(e)}")
        finally:
            run_time = datetime.now() - self.start_time
            hours = run_time.total_seconds() / 3600
            logger.info(f"设备 {self.device_info} 实际运行时间: {hours:.2f} 小时")

class AutoClicker:
    """
    自动点击器类 v1.0
    主要功能：
    - 图像识别与匹配
    - 智能按钮处理
    - 多设备管理
    """
    def __init__(self):
        # ADB路径
        self.adb_path = r"F:\testclinm\platform-tools\adb.exe"
        # 图片目录
        self.image_dir = r"F:\testclinm\templates"
        # 配置文件路径
        self.config_dir = os.path.join(os.path.dirname(self.adb_path), 'config')
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        self.emulator_config_file = os.path.join(self.config_dir, 'emulators.json')
        self.button_config_file = os.path.join(self.image_dir, 'button_config.json')
        
        # 图像匹配阈值
        self.threshold = 0.8  # 默认阈值
        self.moving_threshold = 0.5  # 移动图片的阈值
        # 随机点击范围（像素）
        self.click_range = (10, 40)
        # 随机延迟范围（秒）
        self.delay_range = (1, 3)
        # 移动图片的模板列表
        self.moving_templates = ["button6", "button7"]
        # 模拟器地址
        self.emulator_address = None
        # 按钮配置
        self.button_config = {}
        # 状态管理
        self.waiting_for_button10 = False
        self.button10_wait_time = 0
        self.max_button10_wait_time = 5  # 最大等待时间（秒）
        # 特殊图片配置
        self.button_config['notupo'] = {'threshold': 0.5, 'type': 'special'}
        self.button_config['lose'] = {'threshold': 0.8, 'type': 'special'}  # 修改lose的阈值为0.8
        # 固定流程状态
        self.fixed_sequence_state = 0  # 0: 等待button11, 1: 等待button12, 2: 等待button4
        # 线程控制
        self.is_running = True
        
        # 定时暂停机制
        self.last_pause_time = time.time()  # 上次暂停时间
        self.running_time = 0  # 运行时间（秒）
        self.pause_interval = random.randint(7200, 10800)  # 随机暂停间隔（2-3小时）
        self.pause_duration = random.randint(600, 1800)  # 随机暂停时长（10-30分钟）
        self.is_scheduled_pause = False  # 是否处于定时暂停状态
        
        # button7特殊处理
        self.button7_wait_range = (8, 10)  # button7等待时间范围（秒）
        
        # 添加button10和notupo的状态跟踪
        self.last_button10_click_time = 0  # 记录最后一次点击button10的时间
        self.check_notupo_after_button10 = False  # 是否在点击button10后检查notupo
        
    def save_emulator_config(self, devices: List[Tuple[str, str]]):
        """保存模拟器配置"""
        try:
            config = []
            for device_id, device_info in devices:
                config.append({
                    'device_id': device_id,
                    'device_info': device_info,
                    'last_seen': time.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            with open(self.emulator_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            logger.info("已保存模拟器配置")
        except Exception as e:
            logger.error(f"保存模拟器配置失败: {str(e)}")
            
    def load_emulator_config(self) -> List[Tuple[str, str]]:
        """加载模拟器配置"""
        try:
            if not os.path.exists(self.emulator_config_file):
                return []
                
            with open(self.emulator_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            devices = [(item['device_id'], item['device_info']) for item in config]
            logger.info(f"已加载{len(devices)}个已知模拟器配置")
            return devices
        except Exception as e:
            logger.error(f"加载模拟器配置失败: {str(e)}")
            return []
            
    def execute_adb_command(self, command: str) -> bool:
        """执行ADB命令并检查结果"""
        try:
            full_command = f"{self.adb_path} -s {self.emulator_address} {command}"
            logger.info(f"执行ADB命令: {full_command}")
            
            # 执行命令并获取输出
            result = os.popen(full_command).read()
            
            # 检查命令是否成功
            if "error" in result.lower() or "failed" in result.lower():
                logger.error(f"ADB命令执行失败: {result}")
                return False
                
            logger.info(f"ADB命令执行成功: {result}")
            return True
        except Exception as e:
            logger.error(f"执行ADB命令出错: {str(e)}")
            return False
            
    def get_template_names(self) -> List[str]:
        """获取所有模板图片名称"""
        try:
            # 获取所有png文件
            png_files = glob.glob(os.path.join(self.image_dir, 'button*.png'))
            # 提取文件名（不含扩展名）
            template_names = [os.path.splitext(os.path.basename(f))[0] for f in png_files]
            # 按名称排序
            template_names.sort()
            return template_names
        except Exception as e:
            logger.error(f"获取模板图片列表失败: {str(e)}")
            return []
            
    def update_button_config(self, template_names: List[str]):
        """更新按钮配置"""
        # 加载现有配置
        self.load_button_config()
        
        # 检查新增的按钮
        for name in template_names:
            if name not in self.button_config:
                print(f"\n发现新按钮: {name}")
                while True:
                    try:
                        choice = input("请选择处理方式 (1:普通处理, 2:特殊处理): ")
                        if choice in ['1', '2']:
                            self.button_config[name] = {
                                'threshold': self.threshold if choice == '1' else self.moving_threshold,
                                'type': 'normal' if choice == '1' else 'special'
                            }
                            print(f"已设置 {name} 为{'普通' if choice == '1' else '特殊'}处理")
                            break
                        else:
                            print("无效的选择，请输入1或2")
                    except Exception as e:
                        print(f"输入错误: {str(e)}")
                        print("请重试")
        
        # 检查删除的按钮
        removed_buttons = [name for name in self.button_config.keys() if name not in template_names]
        if removed_buttons:
            print("\n以下按钮已不存在:")
            for name in removed_buttons:
                print(f"- {name}")
            choice = input("是否从配置中删除这些按钮？(y/n): ")
            if choice.lower() == 'y':
                for name in removed_buttons:
                    del self.button_config[name]
                print("已删除不存在的按钮配置")
        
        # 保存更新后的配置
        self.save_button_config()
        
    def load_button_config(self) -> bool:
        """加载按钮配置"""
        try:
            if os.path.exists(self.button_config_file):
                with open(self.button_config_file, 'r', encoding='utf-8') as f:
                    self.button_config = json.load(f)
                logger.info("已加载按钮配置")
                return True
            return False
        except Exception as e:
            logger.error(f"加载按钮配置失败: {str(e)}")
            return False
            
    def save_button_config(self):
        """保存按钮配置"""
        try:
            with open(self.button_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.button_config, f, ensure_ascii=False, indent=4)
            logger.info("已保存按钮配置")
        except Exception as e:
            logger.error(f"保存按钮配置失败: {str(e)}")
        
    def configure_buttons(self, template_names: List[str]):
        """配置按钮处理方式"""
        # 更新按钮配置
        self.update_button_config(template_names)
        
        # 显示当前配置
        print("\n当前按钮配置:")
        for template_name in template_names:
            config = self.button_config.get(template_name, {'type': 'normal'})
            print(f"{template_name}: {'普通' if config['type'] == 'normal' else '特殊'}处理")
        
        choice = input("\n是否要修改配置？(y/n): ")
        if choice.lower() != 'y':
            return
        
        print("\n请为每个按钮选择处理方式：")
        print("1. 普通处理 (匹配阈值: 0.8)")
        print("2. 特殊处理 (匹配阈值: 0.5)")
        
        for template_name in template_names:
            while True:
                try:
                    choice = input(f"\n{template_name} 的处理方式 (1-2): ")
                    if choice in ['1', '2']:
                        self.button_config[template_name] = {
                            'threshold': self.threshold if choice == '1' else self.moving_threshold,
                            'type': 'normal' if choice == '1' else 'special'
                        }
                        print(f"已设置 {template_name} 为{'普通' if choice == '1' else '特殊'}处理")
                        break
                    else:
                        print("无效的选择，请输入1或2")
                except Exception as e:
                    print(f"输入错误: {str(e)}")
                    print("请重试")
        
        # 保存配置
        self.save_button_config()
        
    def get_device_info(self, device: str) -> str:
        """获取设备信息"""
        try:
            # 获取设备型号
            model = os.popen(f"{self.adb_path} -s {device} shell getprop ro.product.model").read().strip()
            # 获取设备品牌
            brand = os.popen(f"{self.adb_path} -s {device} shell getprop ro.product.brand").read().strip()
            # 获取设备名称
            name = os.popen(f"{self.adb_path} -s {device} shell getprop ro.product.name").read().strip()
            # 获取Android版本
            android_ver = os.popen(f"{self.adb_path} -s {device} shell getprop ro.build.version.release").read().strip()
            
            device_info = f"{brand} {model} ({name}) - Android {android_ver}"
            logger.info(f"设备 {device} 的详细信息: {device_info}")
            return device_info
        except Exception as e:
            logger.error(f"获取设备 {device} 信息失败: {str(e)}")
            return device
            
    def verify_device(self, device_id: str) -> bool:
        """验证设备是否可用"""
        try:
            # 检查设备是否在线
            result = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.model").read().strip()
            if not result:
                return False
                
            # 尝试执行一个简单的命令
            result = os.popen(f"{self.adb_path} -s {device_id} shell echo 'test'").read().strip()
            if result != "test":
                return False
                
            return True
        except Exception as e:
            logger.error(f"验证设备 {device_id} 失败: {str(e)}")
            return False

    def identify_emulator(self, device_id: str) -> str:
        """识别模拟器类型"""
        try:
            # 获取设备型号
            model = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.model").read().strip()
            # 获取设备品牌
            brand = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.brand").read().strip()
            # 获取设备制造商
            manufacturer = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.manufacturer").read().strip()
            # 获取设备名称
            name = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.name").read().strip()
            # 获取设备ID
            device_id_prop = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.device").read().strip()
            
            logger.info(f"设备 {device_id} 的详细信息:")
            logger.info(f"型号: {model}")
            logger.info(f"品牌: {brand}")
            logger.info(f"制造商: {manufacturer}")
            logger.info(f"名称: {name}")
            logger.info(f"设备ID: {device_id_prop}")
            
            # 根据特征识别模拟器类型
            if "MuMu" in model or "MuMu" in brand or "MuMu" in manufacturer:
                # 进一步识别MuMu模拟器版本
                if "MuMu12" in model or "MuMu12" in brand:
                    return "MuMu12"
                elif "MuMu" in model or "MuMu" in brand:
                    return "MuMu"
            elif "LDPlayer" in model or "LDPlayer" in brand or "LDPlayer" in manufacturer:
                return "LDPlayer"
            elif "HUAWEI" in model or "HUAWEI" in brand:
                return "HUAWEI"
            elif "Samsung" in model or "Samsung" in brand:
                return "Samsung"
            elif "Xiaomi" in model or "Xiaomi" in brand:
                return "Xiaomi"
            else:
                return "Unknown"
        except Exception as e:
            logger.error(f"识别模拟器类型失败: {str(e)}")
            return "Unknown"

    def find_emulator_processes(self) -> List[Tuple[str, str]]:
        """查找运行中的模拟器进程"""
        try:
            # 定义模拟器进程的特征
            emulator_patterns = {
                "MuMu": ["MuMu", "MuMu12", "MuMu12-2"],
                "LDPlayer": ["LDPlayer", "dnconsole", "dnplayer"],
                "Xiaomi": ["Xiaomi"],
                "HUAWEI": ["HUAWEI"],
                "Samsung": ["Samsung"]
            }
            
            found_processes = []
            print("\n正在搜索模拟器进程...")
            
            # 使用tasklist命令获取进程列表
            result = subprocess.check_output(['tasklist', '/v'], encoding='gbk')
            
            # 遍历进程列表
            for line in result.split('\n'):
                # 检查是否是模拟器进程
                for emulator_type, patterns in emulator_patterns.items():
                    if any(pattern.lower() in line.lower() for pattern in patterns):
                        print(f"\n发现{emulator_type}模拟器进程")
                        print(f"进程信息: {line}")
                        
                        # 尝试从命令行中提取端口信息
                        port_match = re.search(r'port\s*(\d+)', line)
                        if port_match:
                            port = port_match.group(1)
                            device_id = f"127.0.0.1:{port}"
                            print(f"找到端口: {port}")
                            
                            # 验证设备是否可用
                            if self.verify_device(device_id):
                                model = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.model").read().strip()
                                brand = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.brand").read().strip()
                                device_info = f"{brand} {model}"
                                
                                if any(target in device_info for target in ["HUAWEI ALN-AL10", "Samsung SM-S9110", "Xiaomi 12s"]):
                                    print(f"验证成功: {device_info}")
                                    found_processes.append((device_id, device_info))
                                else:
                                    print(f"设备信息不匹配: {device_info}")
                            else:
                                print(f"设备 {device_id} 验证失败")
            
            return found_processes
            
        except Exception as e:
            print(f"查找模拟器进程时出错: {str(e)}")
            return []

    def list_devices(self) -> List[Tuple[str, str]]:
        """列出所有可用的设备"""
        try:
            print("\n正在搜索设备...")
            
            # 重启ADB服务器
            os.system(f"{self.adb_path} kill-server")
            time.sleep(1)
            os.system(f"{self.adb_path} start-server")
            time.sleep(2)
            
            devices = []
            
            # 使用MuMuManager获取模拟器信息
            try:
                print("\n尝试使用MuMuManager获取模拟器信息...")
                mumu_shell_dir = r"F:\MuMu Player 12\shell"
                if not os.path.exists(mumu_shell_dir):
                    print(f"错误: 未找到MuMuManager目录: {mumu_shell_dir}")
                else:
                    # 切换到MuMuManager目录并执行命令
                    current_dir = os.getcwd()
                    os.chdir(mumu_shell_dir)
                    
                    # 尝试不同的编码方式
                    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
                    result = None
                    
                    for encoding in encodings:
                        try:
                            print(f"尝试使用 {encoding} 编码...")
                            result = subprocess.check_output(['MuMuManager.exe', 'info', '-v', 'all'], encoding=encoding, errors='ignore')
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    os.chdir(current_dir)
                    
                    if result is None:
                        print("无法解码MuMuManager输出")
                        return []
                        
                    print(f"MuMuManager输出: {result}")
                    
                    try:
                        # 解析JSON输出
                        emulators = json.loads(result)
                        for index, emu in emulators.items():
                            if emu.get('is_process_started') and emu.get('adb_host_ip') and emu.get('adb_port'):
                                device_id = f"{emu['adb_host_ip']}:{emu['adb_port']}"
                                device_info = f"MuMu模拟器12{'-' + index if index != '0' else ''}"
                                print(f"找到模拟器: {device_info}")
                                print(f"ADB地址: {device_id}")
                                
                                # 连接到模拟器
                                os.system(f"{self.adb_path} connect {device_id}")
                                time.sleep(1)
                                
                                # 检查设备是否可用
                                result = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.model").read().strip()
                                if result:
                                    model = result
                                    brand = os.popen(f"{self.adb_path} -s {device_id} shell getprop ro.product.brand").read().strip()
                                    device_info = f"{brand} {model}"
                                    print(f"设备信息: {device_info}")
                                    
                                    # 直接添加检测到的设备，不再检查特定型号
                                    print(f"添加设备: {device_info}")
                                    devices.append((device_id, device_info))
                                else:
                                    print(f"未能获取设备 {device_id} 的信息")
                        
                        if devices:
                            print(f"\n通过MuMuManager找到 {len(devices)} 个目标设备")
                        else:
                            print("\n未找到任何目标设备")
                    except json.JSONDecodeError:
                        print("解析MuMuManager输出失败")
            except Exception as e:
                print(f"使用MuMuManager获取信息失败: {str(e)}")
            
            # 显示最终的设备列表
            print("\n连接后的设备列表:")
            devices_output = os.popen(f"{self.adb_path} devices").read()
            print(devices_output)
            
            if not devices:
                print("\n未找到任何目标设备")
                print("\n请检查:")
                print("1. 模拟器是否已启动")
                print("2. 模拟器设置中的ADB调试是否已开启")
                print("3. 模拟器设置中的ADB端口是否正确")
                return []
                
            print(f"\n共找到 {len(devices)} 个目标设备")
            return devices
            
        except Exception as e:
            print(f"获取设备列表时出错: {str(e)}")
            return []

    def select_device(self) -> bool:
        """选择要连接的设备"""
        # 获取可用设备列表
        devices = self.list_devices()
        if not devices:
            logger.error("未找到任何可用设备")
            return False
            
        # 显示可用设备
        print("\n可用设备列表:")
        for i, (device, info) in enumerate(devices, 1):
            print(f"{i}. {info}")
            print(f"   设备地址: {device}")
            
        # 让用户选择设备
        while True:
            try:
                choice = int(input("\n请选择要连接的设备编号 (1-{}): ".format(len(devices))))
                if 1 <= choice <= len(devices):
                    self.emulator_address = devices[choice - 1][0]
                    logger.info(f"已选择设备: {devices[choice - 1][1]}")
                    return True
                else:
                    print("无效的选择，请重试")
            except ValueError:
                print("请输入有效的数字")
                
    def connect_emulator(self) -> bool:
        """连接模拟器"""
        try:
            if not self.emulator_address:
                if not self.select_device():
                    return False
                    
            # 连接设备
            os.system(f"{self.adb_path} connect {self.emulator_address}")
            time.sleep(2)
            
            # 检查设备连接状态
            result = os.popen(f"{self.adb_path} devices").read()
            if self.emulator_address in result and "device" in result:
                logger.info(f"成功连接到设备: {self.emulator_address}")
                return True
            else:
                logger.error(f"连接设备失败: {self.emulator_address}")
                return False
        except Exception as e:
            logger.error(f"连接设备出错: {str(e)}")
            return False
            
    def get_screen(self) -> Optional[np.ndarray]:
        """获取屏幕截图"""
        try:
            # 截图并保存
            if not self.execute_adb_command("shell screencap -p /sdcard/screen.png"):
                logger.error("截图命令执行失败")
                return None
                
            if not self.execute_adb_command("pull /sdcard/screen.png screen.png"):
                logger.error("拉取截图失败")
                return None
            
            # 读取截图
            screen = cv2.imread("screen.png")
            if screen is None:
                logger.error("读取截图失败")
                return None
                
            # 删除临时文件
            try:
                os.remove("screen.png")
            except:
                pass
                
            return screen
        except Exception as e:
            logger.error(f"获取屏幕截图出错: {str(e)}")
            return None
            
    def find_template(self, template_name: str, screen: np.ndarray) -> Optional[Tuple[int, int]]:
        """查找模板图片位置"""
        try:
            # 读取模板图片
            template_path = os.path.join(self.image_dir, f"{template_name}.png")
            template = cv2.imread(template_path)
            if template is None:
                logger.error(f"无法读取模板图片: {template_name}")
                return None
                
            # 获取按钮配置的阈值
            threshold = self.button_config.get(template_name, {'threshold': self.threshold})['threshold']
                
            # 模板匹配
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 获取所有匹配位置
            locations = np.where(result >= threshold)
            locations = list(zip(*locations[::-1]))  # 转换为(x, y)格式
            
            if not locations:
                logger.debug(f"未找到匹配的图片: {template_name}, 最大匹配度: {max_val}")
                return None
                
            # 按匹配度排序
            matches = []
            for loc in locations:
                match_val = result[loc[1], loc[0]]
                matches.append((match_val, loc))
            
            # 按匹配度从高到低排序
            matches.sort(reverse=True)
            
            # 选择匹配度最高的位置
            best_match = matches[0]
            h, w = template.shape[:2]
            center_x = best_match[1][0] + w // 2
            center_y = best_match[1][1] + h // 2
            
            logger.info(f"找到图片 {template_name}, 最佳匹配度: {best_match[0]:.2f}")
            return (center_x, center_y)
            
        except Exception as e:
            logger.error(f"查找模板图片出错: {str(e)}")
            return None
            
    def random_click(self, x: int, y: int, template_name: str) -> bool:
        """随机偏移点击"""
        try:
            # 获取图片配置
            config = self.button_config.get(template_name, {})
            click_min = config.get('click_min', self.click_range[0])
            click_max = config.get('click_max', self.click_range[1])
            
            # 计算随机偏移
            offset = random.randint(click_min, click_max)
            angle = random.uniform(0, 2 * np.pi)
            offset_x = int(offset * np.cos(angle))
            offset_y = int(offset * np.sin(angle))
            
            # 执行点击
            click_x = x + offset_x
            click_y = y + offset_y
            
            # 使用新的ADB命令执行方法
            if not self.execute_adb_command(f"shell input tap {click_x} {click_y}"):
                logger.error(f"点击操作失败: ({click_x}, {click_y})")
                return False
            
            logger.info(f"点击坐标: ({click_x}, {click_y}), 偏移量: {offset}")
            return True
        except Exception as e:
            logger.error(f"点击操作失败: {str(e)}")
            return False
            
    def random_delay(self, template_name: str):
        """随机延迟"""
        # 获取图片配置
        config = self.button_config.get(template_name, {})
        delay_min = config.get('delay_min', self.delay_range[0])
        delay_max = config.get('delay_max', self.delay_range[1])
        
        delay = random.uniform(delay_min, delay_max)
        logger.info(f"等待 {delay:.2f} 秒")
        time.sleep(delay)
        
    def random_scroll(self, x: int, y: int):
        """随机滚轮"""
        try:
            # 最多尝试两次
            for attempt in range(2):
                # 计算滑动距离（向上滑动）
                scroll_distance = random.randint(500, 800)  # 随机滑动500-800像素
                # 计算终点坐标
                end_x = x
                end_y = y - scroll_distance  # 向上滑动，所以是减号
                
                # 随机滑动时间（3-6秒）
                swipe_time = random.randint(3000, 6000)
                
                # 执行滑动
                logger.info(f"开始向上滑动: 从({x}, {y})到({end_x}, {end_y}), 滑动时间: {swipe_time/1000:.1f}秒")
                
                # 使用新的ADB命令执行方法
                if not self.execute_adb_command(f"shell input touchscreen swipe {x} {y} {end_x} {end_y} {swipe_time}"):
                    logger.error("滑动命令执行失败")
                    continue
                
                # 随机等待5-6秒
                delay = random.uniform(5, 6)
                logger.info(f"滑动完成，等待 {delay:.2f} 秒")
                time.sleep(delay)
                
                # 检查button12是否出现
                screen = self.get_screen()
                if screen is not None:
                    button12_pos = self.find_template("button12", screen)
                    if button12_pos:
                        logger.info("滑动后检测到button12")
                        return True
                    else:
                        if attempt == 0:  # 第一次尝试失败
                            logger.warning("第一次滑动后未检测到button12，准备重试")
                            # 等待一下再重试
                            time.sleep(2)
                            continue
                        else:  # 第二次尝试也失败
                            logger.warning("两次滑动后仍未检测到button12")
            
            return True
        except Exception as e:
            logger.error(f"滚轮操作失败: {str(e)}")
            return False
            
    def get_number_from_text(self, text: str) -> Optional[int]:
        """从文本中提取数字"""
        try:
            # 移除所有非数字字符
            number = ''.join(filter(str.isdigit, text))
            if number:
                return int(number)
            return None
        except Exception as e:
            logger.error(f"提取数字失败: {str(e)}")
            return None
            
    def run(self, template_configs: Dict[str, Dict], stop_event: threading.Event, pause_event: threading.Event):
        """运行御魂自动化"""
        logger.info("开始运行自动化脚本")
        
        while not stop_event.is_set():
            try:
                # 检查是否需要暂停
                if pause_event.is_set():
                    logger.info("脚本已暂停")
                    time.sleep(1)
                    continue
                
                # 获取屏幕截图
                screen = self.get_screen()
                if screen is None:
                    logger.error("获取屏幕截图失败")
                    time.sleep(1)
                    continue
                
                # 检查lose和notupo
                lose_pos = self.find_template("lose", screen)
                if lose_pos:
                    logger.info(f"{datetime.now().strftime('%H:%M:%S')} - {self.device_info} 检测到lose")
                    stop_event.set()
                    break
                
                # 如果刚点击了button10，立即检查notupo
                if self.check_notupo_after_button10:
                    notupo_pos = self.find_template("notupo", screen)
                    if notupo_pos:
                        logger.info("检测到notupo，立即停止脚本")
                        stop_event.set()  # 直接停止脚本，而不是暂停
                        break  # 跳出主循环
                    # 如果距离点击button10超过1秒还没检测到notupo，就继续正常流程
                    if time.time() - self.last_button10_click_time > 1:
                        self.check_notupo_after_button10 = False
                    else:
                        time.sleep(0.1)  # 快速检测
                        continue  # 继续检测notupo
                
                # 检查其他按钮
                clicked = False
                for template_name in self.get_template_names():
                    # 检查是否需要暂停
                    if stop_event.is_set() or pause_event.is_set():
                        break
                        
                    # 查找模板
                    pos = self.find_template(template_name, screen)
                    if pos:
                        x, y = pos
                        logger.info(f"找到按钮 {template_name}")
                        
                        # 特殊处理button10
                        if template_name == "button10":
                            if self.random_click(x, y, template_name):
                                self.last_button10_click_time = time.time()
                                self.check_notupo_after_button10 = True
                                logger.info("点击了button10，开始检查notupo")
                                clicked = True
                                break  # 点击button10后立即开始检查notupo
                        
                        # 特殊处理button7
                        elif template_name == "button7":
                            wait_time = random.uniform(self.button7_wait_range[0], self.button7_wait_range[1])
                            logger.info(f"检测到button7，等待 {wait_time:.1f} 秒后点击")
                            time.sleep(wait_time)
                            if self.random_click(x, y, template_name):
                                clicked = True
                                self.random_delay(template_name)
                                break
                        
                        # 处理其他按钮
                        else:
                            if self.random_click(x, y, template_name):
                                clicked = True
                                self.random_delay(template_name)
                                break
                
                # 如果没有找到任何可点击的按钮，等待一段时间
                if not clicked:
                    time.sleep(0.2)  # 缩短等待时间以提高响应速度
                    
            except Exception as e:
                logger.error(f"运行出错: {str(e)}")
                time.sleep(1)
        
        logger.info("脚本已停止运行")

def main():
    try:
        # 获取运行时长
        while True:
            try:
                run_duration = int(input("\n请输入要运行的时间（分钟）: "))
                if run_duration > 0:
                    break
                print("请输入大于0的数字")
            except ValueError:
                print("请输入有效的数字")
        
        # 创建自动点击器实例
        clicker = AutoClicker()
        
        # 获取模板图片
        template_names = clicker.get_template_names()
        if not template_names:
            print("错误: 未找到任何模板图片")
            return
            
        # 配置按钮
        clicker.configure_buttons(template_names)
        
        # 创建配置字典
        template_configs = {
            name: clicker.button_config.get(name, {
                'threshold': clicker.threshold,
                'type': 'normal'
            }) for name in template_names
        }
        
        # 获取设备列表
        print("\n正在搜索设备...")
        devices = clicker.list_devices()
        
        if not devices:
            print("错误: 未找到任何目标设备")
            return
            
        # 显示设备列表
        print("\n可用设备列表:")
        for i, (device_id, info) in enumerate(devices, 1):
            print(f"{i}. {info}")
            print(f"   设备ID: {device_id}")
            
        # 选择设备
        while True:
            try:
                choice = input("\n请选择要运行的设备（输入设备编号，多个设备用空格分隔，输入 'all' 运行所有设备）: ").strip()
                if choice.lower() == 'all':
                    selected_devices = devices
                    break
                else:
                    indices = [int(x) - 1 for x in choice.split()]
                    selected_devices = [devices[i] for i in indices if 0 <= i < len(devices)]
                    if selected_devices:
                        break
                    print("无效的选择，请重试")
            except ValueError:
                print("输入格式错误，请重试")
                
        if not selected_devices:
            print("错误: 未选择任何设备")
            return
            
        # 创建控制事件
        stop_event = threading.Event()
        pause_events = {device_id: threading.Event() for device_id, _ in selected_devices}
        
        # 创建并启动线程
        threads = []
        for device_id, device_info in selected_devices:
            thread = DeviceThread(device_id, device_info, template_configs, stop_event, run_duration)
            thread.pause_event = pause_events[device_id]
            threads.append(thread)
            thread.start()
            print(f"已启动设备 {device_info} 的线程")
            
        # 显示控制面板
        def show_control_panel():
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\n" + "="*50)
            print("命令控制面板:")
            print("- 按 'q' 暂停/继续所有设备")
            print("- 按 'r' 刷新状态")
            print("- 按 's' 停止所有设备")
            print("\n当前运行的设备:")
            for i, (device_id, info) in enumerate(selected_devices, 1):
                status = "暂停中" if pause_events[device_id].is_set() else "运行中"
                thread = next(t for t in threads if t.device_id == device_id)
                if thread.start_time:
                    elapsed_time = datetime.now() - thread.start_time
                    remaining_time = timedelta(minutes=run_duration) - elapsed_time
                    remaining_minutes = max(0, remaining_time.total_seconds() / 60)
                    print(f"{i}. {info} [{status}]")
                    print(f"   已运行: {elapsed_time.total_seconds()/60:.1f} 分钟")
                    print(f"   剩余: {remaining_minutes:.1f} 分钟")
                print(f"   按 {i} 暂停/继续此设备")
            print("="*50)
            
        # 显示初始控制面板
        show_control_panel()
        
        # 主控制循环
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=run_duration)
        print(f"\n程序开始运行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"预计结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        while not stop_event.is_set():
            # 检查是否已达到预定运行时间
            current_time = datetime.now()
            if current_time >= end_time:
                print(f"\n已达到预定运行时间 {run_duration} 分钟，正在停止所有设备...")
                stop_event.set()
                break
                
            if msvcrt.kbhit():
                try:
                    key = msvcrt.getch().decode('utf-8').lower()
                    
                    if key == 'q':  # 暂停/继续所有
                        all_paused = all(event.is_set() for event in pause_events.values())
                        for device_id, device_info in selected_devices:
                            if all_paused:
                                pause_events[device_id].clear()
                                print(f"\n继续设备: {device_info}")
                            else:
                                pause_events[device_id].set()
                                print(f"\n暂停设备: {device_info}")
                                
                    elif key == 's':  # 停止所有
                        print("\n正在停止所有设备...")
                        stop_event.set()
                        break
                        
                    elif key == 'r':  # 刷新显示
                        show_control_panel()
                        
                    elif key.isdigit():  # 暂停/继续单个设备
                        device_idx = int(key) - 1
                        if 0 <= device_idx < len(selected_devices):
                            device_id, device_info = selected_devices[device_idx]
                            if pause_events[device_id].is_set():
                                pause_events[device_id].clear()
                                print(f"\n继续设备: {device_info}")
                            else:
                                pause_events[device_id].set()
                                print(f"\n暂停设备: {device_info}")
                                
                except Exception as e:
                    print(f"处理按键时出错: {str(e)}")
                    
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n正在停止所有设备...")
        stop_event.set()
        
    finally:
        # 等待所有线程结束
        for thread in threads:
            thread.join()
        print("\n所有设备已停止运行")
        
if __name__ == "__main__":
    main() 