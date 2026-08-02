# NomadHub General3 V1.7 — S1C 验收记录

## 结论

- **阶段：** S1C 轴距、轮拱、门舱结构闭环
- **结果：** `PASS`
- **S2 准入：** `READY_TO_START`
- **验收构建：** GitHub Actions Run `30742199911` / Run #21
- **源提交：** `dc3c03dafe2a8492edc8559a5dc499db559d32aa`
- **Blender：** 4.2.0
- **交付物：** `NomadHub-General3-V1.7-S1C-ACCEPTED`

本结论只证明 S1C 的工程坐标、静态净距、父子层级、动画扫掠和 GLB 回导可靠。它不代表 S2 连续车身、手工四边面重拓扑、A级曲面、正式 UV 或产品级材质已经完成。

## 冻结参数

| 参数 | 验收值 |
|---|---:|
| 整车长度 | 8.990 m |
| 整车宽度 | 2.350 m |
| 整车高度 | 3.050 m |
| 前轴 X | -3.245 m |
| 后轴 X | 1.905 m |
| 轴距 | 5.150 m |
| 轮拱最小净距门禁 | 0.080 m |
| 门缝最小净距门禁 | 0.060 m |

## 检修舱验收

| 节点 | 中心 X | 最近轮拱净距 | 最近门缝净距 | 结果 |
|---|---:|---:|---:|---|
| HATCH_L_1 | -1.950 m | 0.235 m | 1.405 m | PASS |
| HATCH_L_2 | 0.350 m | 0.495 m | 3.705 m | PASS |
| HATCH_L_3 | 3.050 m | 0.085 m | 6.405 m | PASS |
| HATCH_R_1 | -1.950 m | 0.235 m | 0.605 m | PASS |
| HATCH_R_2 | 0.750 m | 0.095 m | 0.265 m | PASS |
| HATCH_R_3 | 3.050 m | 0.085 m | 2.565 m | PASS |

六个检修舱均无轮拱或主门投影重叠。

## 动态与回导验证

验证帧：`1, 12, 24, 36, 48, 60, 72, 84, 96`

| 验证对象 | 母版检查对数 | 母版碰撞 | GLB 检查对数 | GLB 碰撞 |
|---|---:|---:|---:|---:|
| 主门、检修舱、后视镜与静态结构 | 2106 | 0 | 2106 | 0 |
| 三块随门运动玻璃与静态结构 | 486 | 0 | 486 | 0 |

Blender 母版与全新场景 GLB 回导均保留 13 个 Action。GLB 使用合并的 Active Actions 导出，使多个对象的当前动作能在同一动画时间轴内同步播放。

### 门玻璃层级与回导位移

| 玻璃节点 | 父节点 | GLB Frame 1→48 位移 |
|---|---|---:|
| DOOR_DRIVER_L_GLASS | DOOR_DRIVER_L_ROOT | 0.294201 m |
| DOOR_PASSENGER_R_GLASS | DOOR_PASSENGER_R_ROOT | 0.294201 m |
| DOOR_LIVING_R_GLASS | DOOR_LIVING_R_ROOT | 0.514411 m |

## 交付内容

- `NomadHub_General3_V1.7_S1C.blend`
- `NomadHub_General3_V1.7_S1C_Roundtrip.glb`
- `NomadHub_General3_V1.7_S1C_Preview.png`
- `S1C_Left_Orthographic.png`
- `S1C_Right_Orthographic.png`
- `S1C_Top_Orthographic.png`
- `S1C_Left_Open.png`
- `S1C_Right_Open.png`
- `S1C_Collision_Clearance.json`
- `S1C_VERIFICATION_REPORT.json`
- `BLENDER_BUILD_MANIFEST.json`
- `SHA256SUMS.txt`

所有文件均通过交付包内的 SHA-256 清单复核。

## 关键哈希

| 文件 | SHA-256 |
|---|---|
| `.blend` | `487ad6ae50e54190df0156f1994b33276f82ca7d8554efa2017d34d0bc809ba3` |
| 回导 GLB | `2b738568546f7af653c7d23b58d5f0e34e86294029475043889a4dde9ef0e0af` |
| 验证报告 | `f5b2e2ba6e2155872394d9b8f6d8770ae45cea82496c5b56668e36cd6b019131` |
| 净距报告 | `a74b357f40bb5f5418755df61b7fdd59b25266440f99725146b4c007a45b51cb` |
| Actions Artifact | `a17e38de7e09ee96af0c90714888025a461c32b9a802448125d035971e795eb7` |

## S2 冻结输入

S2 不得任意改变：

- 整车长宽高；
- 前后轴及四轮中心；
- 四轮拱中心；
- 三扇主门位置和铰链轴；
- 六扇检修舱位置和铰链轴。

S2 的任务是以该冻结基线重建单一连续车身控制笼、四边面拓扑流和门窗轮拱控制环，而不是重新调整 S1C 坐标。
