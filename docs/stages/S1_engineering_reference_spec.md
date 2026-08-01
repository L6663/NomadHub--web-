# S1 工程参考规范统一

## 阶段状态

- 项目：NomadHub General3
- 版本：V1.7
- 状态：`IN_PROGRESS`
- 启动时间：2026-08-01 22:08（UTC+8）
- 前置阶段：S0 视觉方向冻结，已通过
- 后续阶段：S2 Blender 连续车身灰模，当前被 S1 阻塞

## 阶段目标

把权威外观参考图转化为唯一、无冲突、可直接用于 Blender 建模的工程规范。S1 不制作正式网格，不修改网页动画，只锁定车辆坐标、部件位置、尺寸和皮肤锚点。

## 任务清单

- [ ] S1-01 车辆坐标与基准尺寸
- [ ] S1-02 轮轴、轮拱和轮胎坐标
- [ ] S1-03 全部车窗位置表
- [ ] S1-04 车门与检修舱位置表
- [ ] S1-05 车顶设备坐标表
- [ ] S1-06 皮肤控制线锚点表
- [ ] S1-07 工程规范冲突检查
- [ ] S1-08 S1 阶段总审查

## 固定基准

```text
车辆原点：几何中心在地面的投影点
X轴：车头 → 车尾
Y轴：车辆左侧 → 右侧
Z轴：地面 → 车顶
单位：米
总长：8.990 m
总宽：2.350 m
总高：3.050 m
轴距：4.500 m
```

## 阶段交付物

1. `RV_Master_Dimensions`
2. `RV_Wheel_Arch_Spec`
3. `RV_Window_Position_Table`
4. `RV_Door_Hatch_Table`
5. `RV_Roof_Equipment_Map`
6. `RV_Livery_Anchor_Map`
7. `RV_Node_Naming_Spec`
8. `RV_Conflict_Check_Report`

## 验收门禁

S1 只有满足以下条件才允许标记为 `PASSED`：

- 左右视图轮轴完全一致；
- 所有车窗数量、位置和尺寸固定；
- 生活舱门位置唯一；
- 检修舱不与轮拱、车门和皮肤冲突；
- 车顶设备位置固定；
- 皮肤控制线能在前、侧和尾部连续；
- 全部尺寸能够转换为 Blender 坐标；
- 冲突检查报告无未解决关键项。

## Git 提交规则

- 阶段开始：`chore(stage): start S1 ...`
- 单项完成：`docs(stage-s1): complete S1-0x ...`
- 阶段阻塞：`chore(stage-s1): block ...`
- 阶段通过：`chore(stage): pass S1 and unlock S2`

完整工程批量上传保持暂停；当前只提交阶段状态、规范、审查和必要产物。
