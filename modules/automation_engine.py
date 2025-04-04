"""
自动化引擎模块
负责协调各个模块的运行
"""

import os
import time
import threading
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from modules.core import ConfigManager, DeviceManager, ImageProcessor, InputController

logger = logging.getLogger("AutomationEngine")

class AutomationModule:
    """自动化模块基类，所有具体的自动化模块都应该继承这个类"""
    
    def __init__(self, 
                 config_manager: ConfigManager, 
                 device_manager: DeviceManager,
                 image_processor: ImageProcessor,
                 input_controller: InputController,
                 module_config: Dict):
        self.config = config_manager
        self.device_manager = device_manager
        self.image_processor = image_processor
        self.input_controller = input_controller
        self.module_config = module_config
        self.module_name = module_config.get("module_name", "未命名模块")
        self.template_sets = module_config.get("template_sets", [])
        self.special_logic = module_config.get("special_logic", {})
        
        # 运行状态
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        self.total_runs = 0
        self.last_button_clicked = None
        
    def initialize(self) -> bool:
        """初始化模块，在开始运行前调用"""
        logger.info(f"初始化模块: {self.module_name}")
        return True
        
    def run_once(self, stop_event: threading.Event, pause_event: threading.Event) -> bool:
        """运行一次自动化流程，由子类实现"""
        raise NotImplementedError("子类必须实现run_once方法")
        
    def cleanup(self) -> None:
        """清理资源，在结束运行后调用"""
        logger.info(f"清理模块: {self.module_name}")
        
    def click_button(self, button_name: str, x: int, y: int) -> bool:
        """点击按钮并记录"""
        if self.input_controller.random_click(x, y, button_name):
            self.last_button_clicked = button_name
            logger.info(f"点击按钮: {button_name} 位置: ({x}, {y})")
            
            # 特殊按钮处理
            if button_name in self.module_config.get("special_buttons", {}):
                special_config = self.module_config["special_buttons"][button_name]
                
                # 特殊延迟
                if "delay_after" in special_config:
                    delay_range = special_config["delay_after"]
                    delay = min(delay_range) + random.random() * (max(delay_range) - min(delay_range))
                    time.sleep(delay)
            else:
                # 普通延迟
                self.input_controller.random_delay(button_name)
                
            return True
        return False
        
    def update_state(self, button_name: str) -> None:
        """更新模块状态，基于点击的按钮"""
        self.last_button_clicked = button_name
        
        # 根据按钮更新状态逻辑
        if button_name == "button10":  # 示例：特殊按钮处理
            self.total_runs += 1
            logger.info(f"完成一次运行，总计: {self.total_runs}")
            
class DeviceThread(threading.Thread):
    """设备线程类，管理单个设备的自动化"""
    
    def __init__(self, 
                 device_id: str, 
                 device_info: str, 
                 automation_module: AutomationModule,
                 stop_event: threading.Event,
                 run_duration: int):
        super().__init__(name=f"Device-{device_id}")
        self.device_id = device_id
        self.device_info = device_info
        self.automation_module = automation_module
        self.stop_event = stop_event
        self.pause_event = threading.Event()
        self.start_time = None
        self.run_duration = run_duration  # 运行时长（分钟）
        
        # 设置设备特有的日志
        self.logger = logging.getLogger(f"Device-{device_id}")
        self.setup_logging()
        
    def setup_logging(self) -> None:
        """为设备设置专用日志"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, f"device_{self.device_id.replace(':', '_')}.log")
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
    def run(self) -> None:
        """线程运行函数"""
        try:
            self.start_time = datetime.now()
            end_time = self.start_time + timedelta(minutes=self.run_duration)
            
            self.logger.info(f"设备 {self.device_info} 开始运行")
            self.logger.info(f"计划运行时间: {self.run_duration} 分钟")
            self.logger.info(f"预计结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 初始化模块
            if not self.automation_module.initialize():
                self.logger.error(f"模块初始化失败: {self.automation_module.module_name}")
                return
                
            while not self.stop_event.is_set():
                current_time = datetime.now()
                # 强制检查运行时间，确保不会超过设定时间
                if current_time >= end_time:
                    self.logger.info(f"设备 {self.device_info} 已达到预定运行时间，停止运行")
                    self.stop_event.set()
                    break
                    
                remaining_minutes = (end_time - current_time).total_seconds() / 60
                if int(remaining_minutes) % 10 == 0 and int(remaining_minutes) > 0:  # 每10分钟显示一次剩余时间
                    self.logger.info(f"设备 {self.device_info} 剩余运行时间: {int(remaining_minutes)} 分钟")
                
                # 检查是否需要暂停
                if self.pause_event.is_set():
                    time.sleep(1)
                    continue
                    
                # 运行一次自动化流程
                start_run = datetime.now()
                # 设置最大执行时间限制
                max_run_time = 5  # 最长5秒
                
                try:
                    self.automation_module.run_once(self.stop_event, self.pause_event)
                    
                    # 如果运行时间过长，添加日志记录
                    run_time = (datetime.now() - start_run).total_seconds()
                    if run_time > max_run_time:
                        self.logger.warning(f"设备 {self.device_info} 单次运行耗时 {run_time:.2f} 秒，可能影响时间控制")
                        
                except Exception as e:
                    self.logger.error(f"设备 {self.device_info} 运行出错: {str(e)}")
                    time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"设备 {self.device_info} 线程运行出错: {str(e)}")
        finally:
            # 清理模块资源
            try:
                self.automation_module.cleanup()
            except Exception as e:
                self.logger.error(f"清理模块资源出错: {str(e)}")
                
            run_time = datetime.now() - self.start_time
            hours = run_time.total_seconds() / 3600
            self.logger.info(f"设备 {self.device_info} 实际运行时间: {hours:.2f} 小时")

class AutomationEngine:
    """自动化引擎，负责协调所有模块和设备"""
    
    def __init__(self, config_path: str = "config/settings.json"):
        # 初始化核心组件
        self.config = ConfigManager(config_path)
        self.device_manager = DeviceManager(self.config)
        
        # 模块注册表
        self.modules = {}
        
        # 运行状态
        self.stop_event = threading.Event()
        self.pause_events = {}
        self.threads = []
        self.selected_devices = []
        
    def register_module(self, module_id: str, module_class) -> None:
        """注册模块"""
        self.modules[module_id] = module_class
        
    def load_module(self, module_id: str, device_id: str) -> Optional[AutomationModule]:
        """加载模块实例"""
        if module_id not in self.modules:
            logger.error(f"未找到模块: {module_id}")
            return None
            
        # 获取模块配置
        module_config = self.config.get(f"modules.{module_id}")
        if not module_config:
            logger.error(f"未找到模块配置: {module_id}")
            return None
            
        # 为设备设置核心组件
        image_processor = ImageProcessor(self.config, self.device_manager)
        input_controller = InputController(self.device_manager, self.config)
        
        # 创建模块实例
        try:
            return self.modules[module_id](
                self.config,
                self.device_manager,
                image_processor,
                input_controller,
                module_config
            )
        except Exception as e:
            logger.error(f"创建模块实例失败: {module_id}, {str(e)}")
            return None
            
    def select_devices(self) -> List[Tuple[str, str]]:
        """选择要运行的设备"""
        devices = self.device_manager.list_devices()
        
        if not devices:
            logger.error("未找到任何目标设备")
            return []
            
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
                    self.selected_devices = devices
                    break
                else:
                    indices = [int(x) - 1 for x in choice.split()]
                    self.selected_devices = [devices[i] for i in indices if 0 <= i < len(devices)]
                    if self.selected_devices:
                        break
                    print("无效的选择，请重试")
            except ValueError:
                print("输入格式错误，请重试")
                
        logger.info(f"已选择 {len(self.selected_devices)} 个设备")
        return self.selected_devices
        
    def select_module(self) -> Optional[str]:
        """选择要运行的模块"""
        available_modules = []
        
        # 获取所有已启用的模块
        for module_id, module_config in self.config.get("modules", {}).items():
            if module_config.get("enabled", False):
                available_modules.append((module_id, module_config.get("module_name", module_id)))
                
        if not available_modules:
            logger.error("未找到任何可用模块")
            return None
            
        # 显示模块列表
        print("\n可用模块列表:")
        for i, (module_id, name) in enumerate(available_modules, 1):
            print(f"{i}. {name}")
            
        # 选择模块
        while True:
            try:
                choice = int(input("\n请选择要运行的模块（输入模块编号）: "))
                if 1 <= choice <= len(available_modules):
                    selected_module = available_modules[choice - 1][0]
                    break
                print("无效的选择，请重试")
            except ValueError:
                print("请输入有效的数字")
                
        logger.info(f"已选择模块: {selected_module}")
        return selected_module
        
    def select_run_duration(self) -> int:
        """选择运行时长"""
        default_duration = self.config.get("device_management.default_run_duration", 10)
        
        while True:
            try:
                duration_str = input(f"\n请输入要运行的时间（分钟，默认 {default_duration} 分钟）: ")
                if not duration_str:
                    return default_duration
                    
                duration = int(duration_str)
                if duration > 0:
                    return duration
                print("请输入大于0的数字")
            except ValueError:
                print("请输入有效的数字")
                
    def run(self) -> None:
        """运行自动化引擎"""
        try:
            # 获取运行时长
            run_duration = self.select_run_duration()
            
            # 选择设备
            if not self.select_devices():
                print("错误: 未选择任何设备")
                return
                
            # 选择模块
            module_id = self.select_module()
            if not module_id:
                print("错误: 未选择任何模块")
                return
                
            # 创建控制事件
            self.stop_event.clear()
            self.pause_events = {device_id: threading.Event() for device_id, _ in self.selected_devices}
            
            # 创建并启动线程
            self.threads = []
            for device_id, device_info in self.selected_devices:
                # 为每个设备设置当前设备
                self.device_manager.select_device(next(i for i, d in enumerate(self.device_manager.devices) if d[0] == device_id))
                
                # 加载模块
                module = self.load_module(module_id, device_id)
                if not module:
                    print(f"错误: 加载模块失败，设备 {device_info}")
                    continue
                    
                # 创建设备线程
                thread = DeviceThread(
                    device_id, 
                    device_info, 
                    module,
                    self.stop_event, 
                    run_duration
                )
                thread.pause_event = self.pause_events[device_id]
                
                # 启动线程
                self.threads.append(thread)
                thread.start()
                print(f"已启动设备 {device_info} 的线程")
                
            # 显示控制面板
            self.show_control_panel()
            
            # 主控制循环
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=run_duration)
            print(f"\n程序开始运行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"预计结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            while not self.stop_event.is_set():
                # 检查是否已达到预定运行时间
                current_time = datetime.now()
                if current_time >= end_time:
                    print(f"\n已达到预定运行时间 {run_duration} 分钟，正在停止所有设备...")
                    self.stop_event.set()
                    break
                    
                # 处理用户输入
                self.handle_user_input()
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n正在停止所有设备...")
            self.stop_event.set()
            
        finally:
            # 等待所有线程结束
            for thread in self.threads:
                thread.join()
            print("\n所有设备已停止运行")
            
    def show_control_panel(self) -> None:
        """显示控制面板"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n" + "="*50)
        print("命令控制面板:")
        print("- 按 'q' 暂停/继续所有设备")
        print("- 按 'r' 刷新状态")
        print("- 按 's' 停止所有设备")
        print("- 按 'd' 切换设备（多设备下有效）")
        print("\n当前运行的设备:")
        
        for i, (device_id, info) in enumerate(self.selected_devices, 1):
            status = "暂停中" if self.pause_events[device_id].is_set() else "运行中"
            thread = next((t for t in self.threads if getattr(t, "device_id", None) == device_id), None)
            
            if thread and thread.start_time:
                elapsed_time = datetime.now() - thread.start_time
                remaining_time = timedelta(minutes=thread.run_duration) - elapsed_time
                remaining_minutes = max(0, remaining_time.total_seconds() / 60)
                
                print(f"{i}. {info} [{status}]")
                print(f"   已运行: {elapsed_time.total_seconds()/60:.1f} 分钟")
                print(f"   剩余: {remaining_minutes:.1f} 分钟")
                
            print(f"   按 {i} 暂停/继续此设备")
            
        print("="*50)
        
    def handle_user_input(self) -> None:
        """处理用户输入"""
        import msvcrt
        
        if msvcrt.kbhit():
            try:
                key = msvcrt.getch().decode('utf-8').lower()
                
                if key == 'q':  # 暂停/继续所有
                    all_paused = all(event.is_set() for event in self.pause_events.values())
                    for device_id, device_info in self.selected_devices:
                        if all_paused:
                            self.pause_events[device_id].clear()
                            print(f"\n继续设备: {device_info}")
                        else:
                            self.pause_events[device_id].set()
                            print(f"\n暂停设备: {device_info}")
                            
                elif key == 's':  # 停止所有
                    print("\n正在停止所有设备...")
                    self.stop_event.set()
                    
                elif key == 'r':  # 刷新显示
                    self.show_control_panel()
                    
                elif key == 'd':  # 切换设备
                    if len(self.selected_devices) > 1:
                        for thread in self.threads:
                            if hasattr(thread, 'automation_module') and hasattr(thread.automation_module, 'device_manager'):
                                thread.automation_module.device_manager.switch_device()
                        print("\n已手动切换所有线程的当前设备")
                        
                elif key.isdigit():  # 暂停/继续单个设备
                    device_idx = int(key) - 1
                    if 0 <= device_idx < len(self.selected_devices):
                        device_id, device_info = self.selected_devices[device_idx]
                        if self.pause_events[device_id].is_set():
                            self.pause_events[device_id].clear()
                            print(f"\n继续设备: {device_info}")
                        else:
                            self.pause_events[device_id].set()
                            print(f"\n暂停设备: {device_info}")
                            
            except Exception as e:
                print(f"处理按键时出错: {str(e)}") 