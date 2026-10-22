# 接收电脑技术自检

1. 安装后运行portable.py doctor。基础剪辑与高级动效分别报告，缺项先按官方渠道补齐。
2. 用FFmpeg生成四秒无私人素材的测试片：

```text
ffmpeg -n -f lavfi -i color=c=0x68747e:s=1080x1920:r=30:d=4 -f lavfi -i sine=frequency=440:sample_rate=48000:duration=4 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest technical-input.mp4
```

3. 在安装后的总入口目录找到 `capabilities/motion`，使用本机真实路径运行下例。B、C版分别把 `--variant A` 改为 `B`、`C`，并给 `--out-dir` 新目录：

```text
python <总入口>/capabilities/motion/scripts/render_overlays.py --input technical-input.mp4 --plan <总入口>/capabilities/motion/examples/transparent-board-plan.json --out-dir technical-A --variant A
```

核对全屏、后文不预露、字幕居中、四秒/同画幅/同源音轨内容；每种方案输出ASS、参数和MP4。这个匿名技术样例只验证工具链，不验证真实口播判断。
4. 高级图形需要MOTION/scripts/pipeline.py setup；执行packs与auto-capabilities检查完整目录、版本及画幅。已有源RC/experimental范围保留。
5. 当前助手再用接收者自己的原片制作代表段，验证真实剪辑与风格。只有实际听校才写humanListeningChecked=true，当前尚未发生的接收电脑结果保留待验收。
