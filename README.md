# NomadHub Web V1.6.1

NomadHub 智能房车边缘协同系统 Web 端。包含 Vue 3 + TypeScript 前端源码、自包含 WebGL2 GLB 数字房车运行时、UV 车身皮肤、完整业务页面与可复现的模型生成工具。

## 页面

- 总览 Dashboard
- 设备监控
- 场景模式
- 安全告警
- 网关状态
- 历史数据
- 用户管理
- 登录 / 注册

## 技术栈

Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios、ECharts、SCSS、自包含 WebGL2 GLB 运行时。

## 本地构建

```cmd
cd webui
npm install
python ..\tools\generate_v16_model.py
npm run build
```

Ubuntu 网关部署时，构建后的 `webui/dist` 由 Linux C HTTP 服务托管。

## 版本

当前版本：V1.6.1
