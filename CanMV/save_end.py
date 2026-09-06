# vision distance - By: SingTown - Wed Jul 30 2025

import sensor
import time
from machine import UART

uart = UART(3,9600,timeout_char=1000)


# 设置VGA画面，并裁剪中间的画面
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.VGA)
sensor.set_windowing((200,240))
sensor.skip_frames(time=2000)
clock = time.clock() # Tracks FPS.

CENTER_X = 200//2
CENTER_Y = 240//2

# 边框的真实长度，单位mm
FRAME_WIDTH_MM = 176

# 校准的数据
DISTANCE_MM_2 = 1400
FRAME_WIDTH_PIXEL_2 = 82

def find_center_min_blob(blobs):
    # 找中间最小的色块
    blob = None
    min_area = 100000
    for b in blobs:
        if abs(b.cx()-CENTER_X) + abs(b.cy()-CENTER_Y) > 50:
            continue
        if b.area() > min_area:
            continue
        blob = b
        min_area = b.area()
    return blob

def find_center_max_blob(blobs):
    # 找中间最大的色块
    blob = None
    max_area = 0
    for b in blobs:
        if abs(b.cx()-CENTER_X) + abs(b.cy()-CENTER_Y) > 50:
            continue
        if b.area() < max_area:
            continue
        blob = b
        max_area = b.area()
    return blob



while True:
    clock.tick()
    img = sensor.snapshot()




    # 找白色色块，黑色边框内部
    frames = img.find_blobs([(150,256)])
    frame_blob = find_center_min_blob(frames)
    if not frame_blob:
        print("NO FRAME")
        continue

    # 计算距离
    distance = DISTANCE_MM_2 * FRAME_WIDTH_PIXEL_2 / frame_blob.w()



    # 缩小roi，避免黑框的黑边
    frame_roi = (frame_blob.x()+5, frame_blob.y()+5,
                 frame_blob.w()-10, frame_blob.h()-10)
    if frame_roi[2] <= 0 or frame_roi[3] <= 0:
        print("ROI ERROR")
        continue

    # 找黑色色块，目标物体
    objs = img.find_blobs([(0,150)], roi=frame_roi)
    obj_blob = find_center_max_blob(objs)
    if not obj_blob:
        print("NO OBJS")
        continue

    # 计算物体实际尺寸
    obj_w_mm = obj_blob.w() / frame_blob.w() * FRAME_WIDTH_MM

    # 形状识别和尺寸计算
    density = obj_blob.density()
    size_str = ""

    if density > 0.9:  # 正方形
        size_str = "边长:%.1fmm" % obj_w_mm
    elif density > 0.6:  # 圆形
        size_str = "直径:%.1fmm" % obj_w_mm
    elif density > 0.4:  # 三角形
        # 计算三角形边长（取外接矩形对角线作为最大边长）
        diagonal = (obj_blob.w()**2 + obj_blob.h()**2)**0.5
        triangle_side = diagonal / frame_blob.w() * FRAME_WIDTH_MM
        size_str = "边长:%.1fmm" % triangle_side
    else:  # 未知形状
        size_str = "尺寸:%.1fmm" % obj_w_mm

    # 在物体框上方显示尺寸信息（使用大字体）
    text_x = max(0, obj_blob.cx() - 30)  # 居中显示
    text_y = max(0, obj_blob.y() - 20)   # 显示在物体框上方

    # 绘制物体框（使用白色）
    img.draw_rectangle(frame_blob.rect(), color=255)
    img.draw_rectangle(obj_blob.rect(), color=255)

    # 在物体框上方显示尺寸（使用大字体和黑色）
    img.draw_string(text_x, text_y, size_str, scale=2, color=0)

    # 在图像底部显示距离信息（黑色）
    img.draw_string(10, img.height()-20, "距离:%.1fmm" % distance, scale=1, color=0)

    date=(int)(distance)
    date1=(int)(date%10)
    date2=(int)(date/10%10)
    date3=(int)(date/100%10)
    date=bytes((0xff,date1,date2,date3,0xfe))
    uart.write(date)
    print(date1)
    print(date2)
    print(date3)
    print("\n")