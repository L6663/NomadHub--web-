# NomadHub General3 V1.7 — 真实 Blender 母版重建验证

## 结论

本次已生成并验证一个真正由 Blender 4.2.0 创建和保存的 `.blend` 工程。

该结果解决了此前只有 Python/trimesh GLB、没有可核验 Blender 源工程的问题。它是可编辑 Blender 原生基线，但不宣称已经完成手工重拓扑、A级曲面或产品级精模。

## 构建证据

- GitHub Actions 工作流：`Build Genuine Blender Project`
- 成功运行：`30739094276`，run #7
- 构建提交：`9c35d47594659b919201b0640b1bc4e50f31fcaa`
- 合并提交：`9759854d533dd14832b13c13fb57ed99523e7c9a`
- Artifact：`NomadHub-General3-V1.7-REAL-BLEND`
- Artifact ID：`8830670607`
- Artifact SHA-256：`6f39daceae542aa8f83ddfff9eddc852da0c1ad72712530a7740fd33b37acecb`

## Blender 工程

- 文件：`NomadHub_General3_V1.7_REAL.blend`
- 大小：135245 bytes
- SHA-256：`3fbc91023fbd1a3ca03f513a086fdfb405a4e00a1a2892223fab0a2e4ee9f46d`
- Blender：4.2.0
- 单位：米
- 对象：78
- Mesh：50
- 材质：7
- Blender Actions：13

## 回导验证

- 文件：`NomadHub_General3_V1.7_BlenderRoundtrip.glb`
- SHA-256：`aefc4241b96470f17db4976171add1723af88c6adf87a7dad7338d5100caf1e9`
- glTF：2.0
- 动画：13
- 动画包含三扇车门、六个检修舱和四个轮组。

## 强制验证

工作流执行了：

1. 使用官方 Blender 4.2.0 运行构建脚本；
2. Blender 原生保存 `.blend`；
3. Blender 再次打开该 `.blend`；
4. 检查 `RV_ROOT`、动作数量和米制单位；
5. 导出回导 GLB；
6. 核对 manifest 与 SHA-256；
7. 生成 Eevee 预览图；
8. 上传完整工作流 Artifact。

## 适用范围

当前工程可用于：

- 继续在 Blender 中编辑；
- 保留语义层级；
- 调整车身、门舱、轮组和车顶设备；
- 播放门舱与轮组关键帧；
- 继续重拓扑和材质开发。

当前工程不代表：

- 最终产品级房车模型；
- 手工四边面重拓扑已完成；
- 车身曲面已达到汽车工业曲面标准；
- S1、S2、S3 已重新通过；
- 可直接进入正式 UV 与皮肤阶段。
