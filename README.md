# 阴阳师自动化脚本

## 功能特点
1. 自动检测并处理御魂战斗流程
2. 智能识别notupo并立即停止
3. 特殊处理button7和button10
4. 多设备并行支持
5. 可配置运行时间

## 版本历史
- v1.0 (2024-03-19): 稳定版本
  - 实现基础自动化功能
  - 支持多设备并行运行
  - 智能检测notupo和lose状态
  - 特殊处理button7和button10
  - 可配置运行时间

## 环境要求
- Python 3.8+
- OpenCV
- ADB工具

## 目录结构
```
.
├── auto_click.py      # 主程序
├── auto_click_v1.0.py # 稳定版本备份
├── templates/         # 图片模板目录
└── platform-tools/    # ADB工具目录
```

## 使用说明
1. 确保已安装所需的Python包：
```bash
pip install opencv-python
```

2. 配置ADB环境：
   - 将ADB工具放在platform-tools目录下
   - 确保模拟器已开启ADB调试

3. 准备图片模板：
   - 将所需的按钮图片放在templates目录下
   - 图片格式为PNG

4. 运行程序：
```bash
python auto_click.py
```

## 注意事项
1. 运行前请确保模拟器已正确启动
2. 检查ADB连接是否正常
3. 确保图片模板与游戏界面匹配

## 1. 安装必需软件

1. 下载并安装 Python 3.8 或更高版本
   - 访问 https://www.python.org/downloads/
   - 下载 Python 3.8 Windows 安装包
   - 运行安装程序，**重要：安装时勾选 "Add Python to PATH"**

2. 下载并安装 MuMu模拟器
   - 确保开启 ADB 调试模式
   - 设置模拟器分辨率为 1280x720

## 2. 安装脚本

1. 解压下载的压缩包到任意文件夹
2. 打开命令提示符（按 Win+R，输入 cmd）
3. 进入脚本所在目录：
   ```bash
   cd 脚本所在路径
   ```
4. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 3. 配置模拟器

1. 打开MuMu模拟器
2. 进入模拟器设置
3. 开启 ADB 调试：
   - 点击"其他设置"
   - 找到"ADB调试"选项并开启
4. 确认ADB端口（默认为7555）

## 4. 运行脚本

1. 确保模拟器已启动并运行阴阳师
2. 在命令提示符中运行：
   ```bash
   python auto_click.py
   ```

## 常见问题

1. 如果提示缺少依赖，请运行：
   ```bash
   pip install -r requirements.txt
   ```

2. 如果提示找不到设备：
   - 检查模拟器是否正常运行
   - 确认ADB调试是否开启
   - 检查platform-tools文件夹是否在正确位置

3. 如果提示权限问题：
   - 以管理员身份运行命令提示符

## 注意事项

1. 请确保模拟器分辨率设置为1280x720
2. 游戏内画面需要设置为默认布局
3. 运行脚本前请确保已登录游戏
4. 首次运行可能需要允许防火墙权限 