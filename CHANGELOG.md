# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

---

## [Unreleased]

## [v1.1.1] - 2026-05-03

### 🐛 修复

- **JSONDecodeError 崩溃**：修复 `safe_json_load` 抛出 `JSONDecodeError` 时参数错误导致的异常
- **bare except**：将捕获所有异常的裸 `except:` 替换为 `except Exception`
- **Docker 环境 WebUI 无法访问**：Linux 下 `loop.add_signal_handler()` 内部通过 C 层调用 `signal.set_wakeup_fd()`，Python 层补丁无法拦截；改用 `asyncio` 任务在主事件循环中运行，彻底避开非主线程信号限制

### 🔄 优化

- **WebUI 生命周期管理**：提前初始化 `_webui_thread` 为 `None`，简化 `terminate` 方法中的守护线程清理逻辑
- **死代码清理**：移除 `ui_resources_manager.py` 中冗余的 `hasattr` 守卫判断
- **重复导入**：将 `proxy_config.py` 中 `urlparse` 的局部导入提升到模块级别，消除重复
- **未使用参数**：移除 `ResourceLoader.__init__` 中未被使用的 `proxy` 参数

### 💬 日志

- **WebUI 启动日志增强**：添加 WebUI 服务启动、就绪、停止全生命周期的日志输出，便于 Docker 环境下排查连接问题
- **WebUI 双模式切换日志**：`main.py` 根据事件循环状态自动选择 asyncio 任务或线程回退模式，并输出对应的启动日志

---

## [v1.1.0] - 2026-05-03

> [!NOTE]
> 这是一个具有风险的功能性更新，建议通过 AstrBot 仪表盘**重新安装**本插件（勾选「同时删除插件持久化数据」）以确保平滑升级。

### ✨ 新增

- **WebUI 自动启动**：新增 `enable_webui` 配置项，插件加载时自动在后台启动 WebUI 管理界面
- **自定义 WebUI 端口**：新增 `webui_port` 配置项，可自由指定 WebUI 运行端口（范围 1024-65535）
- **便捷物品注册**：WEBUI 物品注册页面支持手动填写表单、从库街区 Wiki 一键同步、从解包源直连获取立绘三种途径结合使用，并内置裁剪 + 渐变透明处理工具（404×560px），注册流程一站式完成

### 🔄 优化

- **Web 框架迁移**：将 Web 框架从 Flask 迁移至 Quart（异步），彻底解决非主线程启动报错问题
- **配置项精简**：移除 `render_output_path` 配置项，简化渲染结果保存逻辑
- **依赖清理**：移除 `flask`、`flask-cors` 依赖

---

## [v1.0.2] - 2026-01-17

### 🔄 优化

- 优化渲染器精灵提取方法，代码可读性提升
- 修复不规范的代码方案，提升代码质量
- 移除允许用户自定义卡池配置路径的功能（卡池配置统一由插件管理）
- 删除插件下的默认持久化卡池路径，修改插件元数据

### 📝 文档

- 更新 README 文档，完善功能说明与使用指引

---

## [v1.0.1] - 2026-01-16

### ✨ 新增

- **物品注册功能**：支持手动填写表单注册抽卡物品
- **Wiki 数据同步**：支持从库街区（Kurobbs）Wiki API 自动拉取角色和武器数据
- **解包源立绘获取**：支持从 TomyJan/WutheringWaves-UIResources 仓库直接获取抽卡立绘
- **立绘裁剪工具**：内置裁剪 + 渐变透明处理，适配抽卡界面比例（404×560px）

### 🔄 优化

- WebUI 界面重构，采用现代化设计语言
- 移除 `src/web/README.md`，功能说明统一归入主 README

---

## [v1.0.0] - 2026-01-08

### ✨ 新增

- **抽卡指令**：支持 `/单抽`、`/十抽`、`/十连` 等指令进行模拟抽卡
- **卡池管理**：
  - `/卡池` 查看所有可用卡池
  - `/唤取 <卡池ID/名称>` 设置用户的默认卡池
  - `/卡池详细 <卡池ID/名称>` 查看指定卡池的详细配置
- **抽卡记录**：`/唤取记录` 支持历史抽卡记录查询与分页浏览
- **保底机制**：内置软保底 + 硬保底机制，真实还原鸣潮抽卡体验
- **图像渲染**：精美的抽卡结果图片渲染，支持单抽、十连、历史记录、卡池详情等多种场景
- **WebUI 配置管理**：通过浏览器可视化创建、编辑、启用/禁用卡池配置
- **多配置组支持**：不同配置组下的物品数据相互隔离，适合多服或多人场景
- **持久化状态**：保底计数、UP 状态跨会话保留
- **配置组自动导入**：首次使用或新建配置组时，自动从 `default.csv` 导入默认物品数据

