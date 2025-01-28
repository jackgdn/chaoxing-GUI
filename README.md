# 超星学习通自动化完成任务点（GUI 版）

本项目基于[超星学习通自动化完成任务点(命令行版)](https://github.com/Samueli924/chaoxing)项目创建，并使用 PySide6 模块为原本的命令行版增加了图形界面。

## 使用方法

* 下载项目到本地 `git clone https://github.com/jackgdn/chaoxing-GUI.git --depth=1`
* 进入项目路径 `cd chaoxing-GUI`
* *~~安装依赖 `python -m pip install -r requirements.txt`~~*
* *~~运行程序 `python main.py`~~*
* 运行 `chaoxing-GUI.bat` 或 `chaoxing-GUI.ps1`（Windows）；运行 `chaoxing-GUI.sh`（UNIX）。

## 计划更新路线

+ [x] 添加对文档任务点和阅读任务点的支持
+ [ ] ~~添加倍速学习视频功能~~（不考虑加入）
+ [ ] 使用 Designer 重新绘制 UI
+ [x] 添加记住密码功能
+ [ ] ……

## 更新日志

### 2024.11.9 - 1#

- 创建仓库。
- 添加对视频任务点的支持。

### 2024.11.9 - 2#

- 修复解码任务点时日志重复记录的 bug。
- 修复课程学习完成后 `courseWorker` 实例与 `chaoxing` 实例的信号未断开，导致无法继续学习其他课程的 bug。

### 2024.11.10 - 3#

- 添加对文档任务点和阅读任务点的支持。
- 修改日志文件上限为 10KB。
- 上传二进制文件。

### 2025.1.29 - 4#

- 添加记住密码功能。
- 创建 `chaoxing-GUI.ps1` 和 `chaoxing-GUI.sh`。
- 春节快乐！

# 免责声明

本软件遵循 [GNU 通用公共许可证第三版（GPL-3.0）](https://www.gnu.org/licenses/gpl-3.0.zh-cn.html) 开源许可协议发布。
