# NomadHub General3 V1.6.1

## A-06统一认证、GLB数字房车、UV车身皮肤与自适应入场取景

本工程覆盖“一般3”的职责边界：统一认证与 Web 基础工程，以及后续 Web 控制、监控页面的承载与接口占位。V1.6.1 保留 Linux C 后端、SQLite 用户体系、HTTP/Raw TCP 通信和全部业务页面，重点重构三维房车的模型结构、车身皮肤、四轮联动与入场摄像机。

## V1.6.1 核心升级

### 加载、法线与首帧稳定修复

- 修复 V1.6 GLB 全部网格缺少 `NORMAL` 导致整车黑色剪影的问题；
- 117/117 个 GLB Primitive 现均包含有效单位顶点法线；
- Shader 增加法线回退，第三方网格漏法线时不会直接变黑；
- Vue 改为等待三维引擎真实 `ready`，删除双重加载遮罩；
- 新增房车加载海报，模型未就绪时不再显示纯黑屏；
- 模型首帧完成后才启动入场动画，网络与解析耗时不再计入动画；
- 模型加载超时固定为 2500 ms，失败自动进入静态降级视图；
- 可见入场动画缩短为约 3200 ms；
- 静态资源增加版本参数，C 后端支持 Query String、WebP 与 GLB MIME。

### V1.6 结构能力继续保留

- 主视觉由程序化方盒组合升级为标准 `glTF 2.0 / GLB` 模型资产；
- GLB 内包含 117 个命名节点，可独立识别车身、玻璃、门、空调、太阳能板、灯具与四组车轮；
- 四轮采用独立 `FL / FR / RL / RR` 节点族，轮胎、轮毂、制动盘、轮毂中心与八根辐条共同联动；
- 下车身拆分为前、中、后板件并为车轮留出真实可见区域，避免连续车壳遮挡近侧轮胎；
- 左右车身分别使用透明 UV 皮肤贴图，品牌文字方向独立绘制，不再使用带厚度的几何贴条；
- Nomad Silver 皮肤包含珍珠银车漆、深灰腰线、双青色速度条纹、N 标志和 NomadHub 字标；
- GLB 内嵌左右两张皮肤纹理，部署时不依赖公网或外部模型服务；
- 新三维运行时支持 GLB、POSITION/NORMAL/TEXCOORD_0、PBR 材质参数、透明纹理和分层绘制；
- 入场摄像机基于模型包围球和浏览器宽高比自动计算距离，避免车顶、轮胎或车尾在不同分辨率下被裁切；
- 入场采用车辆曲线路径、四轮滚动、前轮转向、独立摄像机轨迹和构图安全边距；
- 入场结束后同一个 Canvas 直接交接给总览页，支持拖动旋转、滚轮缩放、模块聚焦和自动环绕；
- 保留总览、设备监控、场景模式、安全告警、网关状态、历史数据、用户管理全部页面；
- 工程包自带 `webui/dist`，Ubuntu 18.04 运行阶段无需 Node.js。

## 三维资产结构

```text
webui/public/models/
├── nomadhub-rv-v161.glb
├── nomad-silver-left.png
└── nomad-silver-right.png

GLB节点示意：
BODY_SHELL
GLASS_WINDSHIELD
LIVERY_LEFT / LIVERY_RIGHT
DOOR_MAIN
SOLAR_PANEL
ROOF_AC
WHEEL_FL_*
WHEEL_FR_*
WHEEL_RL_*
WHEEL_RR_*
```

模型和皮肤均由工程内 `tools/generate_v16_model.py` 生成，来源可追溯，无第三方网络模型授权风险。

## 技术结构

```text
Vue 3 / TypeScript 页面源码
        │
        ├── 自包含 WebGL2 GLB 运行时
        ├── GLB模型 + UV车身皮肤
        ├── 自适应摄像机与入场导演
        ├── 模块热点、主题与完整业务路由
        └── 可直接部署的 webui/dist
                    │
Linux C HTTP + Raw TCP + SQLite + OpenSSL
                    │
U5 / RCT6 / Linux runtime_status
```

> V1.6.1 方案原计划使用 Three.js。为了保持发布包完全离线、避免 Ubuntu 网关运行阶段依赖 CDN，并规避当前构建镜像无法完整安装 npm 依赖的问题，本次交付采用自包含 WebGL2 GLB 运行时实现同一组核心能力。GLB、UV、模型层级和摄像机模块已经解耦，后续替换为 Three.js 渲染器时无需重做模型和皮肤资产。

## Ubuntu 18.04 一键部署

```bash
cd ~/26033/NomadHub_Web_General3
chmod +x scripts/*.sh scripts/*.py
sudo ./scripts/deploy_ubuntu18.sh
```

部署完成后：

```text
本机：http://127.0.0.1:8080
局域网：http://Ubuntu网关IP:8080
账号：admin
密码：123456
```

日常管理：

```bash
./scripts/status.sh
./scripts/restart.sh
sudo journalctl -u nomadhub.service -f
sudo ./scripts/rollback.sh
```

## Windows 重新构建 Vue 源码

工程包已经带可部署 `dist`。只有修改 Vue 源码后才需要在 Windows 执行：

```cmd
cd /d D:\NomadHub_Web_General3\webui
npm install
npm run build
```

Vite 会把 `public/models` 和 `public/vehicle3d` 原样复制到 `dist`。

## 自动验收

```bash
python3 scripts/audit_release.py
python3 scripts/test_acceptance.py
python3 scripts/health_check.py
```

详细说明：

```text
docs/15_V1.6.1_加载法线与首帧稳定修复审查.md
docs/16_V1.6.1_自动验证报告.md
```
