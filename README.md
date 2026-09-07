# 基于 C8 单目视觉的目标物测量装置

2025 年全国大学生电子设计竞赛 C 题项目。该装置基于 CanMV C8 单目视觉模组识别测量框与目标物，并通过串口将测量结果发送给 STM32F103C8T6；STM32 使用 OLED 显示数据。

## 项目内容

- `CanMV/`：运行在 CanMV C8 上的 MicroPython 视觉测量脚本。
- `uart/`：STM32F103C8T6 串口通信与显示的 Keil MDK 工程。
- `uart_key/`：带按键交互的 STM32F103C8T6 Keil MDK 工程。
- `单目测距装置设计与实现.pptx`：项目答辩演示文稿。
- `基于c8单目视觉的目标物测量装置设计报告(1).docx`：设计报告。
- `39-08-本-C.pdf`：竞赛题目文件。

## 演示视频

点击下方播放器观看演示：

<video controls preload="metadata" width="720" src="https://github.com/boyikao/c8-monocular-measurement-device/raw/refs/heads/main/%E6%BC%94%E7%A4%BA%E8%A7%86%E9%A2%91.mp4"></video>

如果当前 GitHub 页面不显示播放器，可直接打开[视频文件](https://github.com/boyikao/c8-monocular-measurement-device/raw/refs/heads/main/%E6%BC%94%E7%A4%BA%E8%A7%86%E9%A2%91.mp4)。

## 功能概述

视觉端在灰度 VGA 图像中定位白色测量框和黑色目标物，通过测量框像素宽度估算距离，并根据目标物相对测量框的尺寸计算实际大小。测得距离以 5 字节帧 `0xFF + 百/十/个位 + 0xFE` 经 UART3（9600 bps）发送。

## 使用说明

1. 将 `CanMV/save_end.py` 部署到 CanMV C8，并根据实际测量框尺寸和标定距离调整脚本中的校准常量。
2. 使用 Keil MDK 打开 `uart/Project.uvprojx` 或 `uart_key/Project.uvprojx`，选择对应 STM32F103C8T6 硬件配置编译下载。
3. 连接视觉模组与 STM32 的串口，并接入 OLED 观察测量结果。

## 开源说明

本仓库保留项目原创代码、工程配置、技术资料和演示视频；不提交构建产物、本地 Keil 配置、压缩包及报销材料。第三方 STM32 标准外设库和启动文件保留其原有版权与许可。

PDF 题目与设计报告作为 GitHub Release 附件发布，便于下载和归档。
