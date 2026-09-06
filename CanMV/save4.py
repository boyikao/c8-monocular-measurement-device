import sensor
import image
import time
import math
import lcd

# 初始化LCD
lcd.init()

# 初始化摄像头
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)  # 灰度模式
sensor.set_framesize(sensor.QVGA)       # 使用QVGA分辨率(320x240)
sensor.set_windowing((200, 240))        # 设置ROI窗口
sensor.skip_frames(time=2000)           # 跳过初始帧

# 检查摄像头是否初始化成功
if sensor.get_id() == sensor.OV2640:
    print("OV2640 detected")
elif sensor.get_id() == sensor.OV7740:
    print("OV7740 detected")
else:
    print("Unknown sensor")

clock = time.clock()
CENTER_X = 100  # 200//2
CENTER_Y = 120  # 240//2

# 边框的真实长度（单位mm）
FRAME_WIDTH_MM = 176

# 校准数据
DISTANCE_MM_2 = 250
FRAME_WIDTH_PIXEL_2 = 182

def find_center_min_blob(blobs):
    min_area = 100000  # 使用大数初始化
    candidate = None
    for b in blobs:
        # 计算与中心点的曼哈顿距离
        dist = abs(b.cx() - CENTER_X) + abs(b.cy() - CENTER_Y)
        if dist > 50:
            continue
        # 寻找最小面积的色块
        if b.area() < min_area:
            min_area = b.area()
            candidate = b
    return candidate

def find_center_max_blob(blobs):
    max_area = 0
    candidate = None
    for b in blobs:
        dist = abs(b.cx() - CENTER_X) + abs(b.cy() - CENTER_Y)
        if dist > 50:
            continue
        # 寻找最大面积的色块
        if b.area() > max_area:
            max_area = b.area()
            candidate = b
    return candidate

def find_bottom_edge(img, blob):
    # 在物体底部区域寻找水平线
    roi = (blob.x(), blob.y() + blob.h() - 5, blob.w(), 5)
    lines = img.find_lines(roi=roi, threshold=1000, theta_margin=25, rho_margin=25)

    best_line = None
    max_length = 0
    for line in lines:
        # 检查是否为水平线 (theta在0°或180°附近)
        theta = line.theta()
        if abs(theta) < 30 or abs(theta - 180) < 30:
            length = line.length()
            if length > max_length:
                max_length = length
                best_line = line
    return best_line

def get_bottom_width(blob, bottom_line=None):
    if bottom_line is None:
        # 使用blob的底部宽度
        left_point = (blob.x(), blob.y() + blob.h() - 1)
        right_point = (blob.x() + blob.w(), blob.y() + blob.h() - 1)
        return blob.w(), left_point, right_point

    # 计算线段长度
    dx = bottom_line.x2() - bottom_line.x1()
    dy = bottom_line.y2() - bottom_line.y1()
    width = math.sqrt(dx*dx + dy*dy)
    return width, (bottom_line.x1(), bottom_line.y1()), (bottom_line.x2(), bottom_line.y2())

while True:
    clock.tick()
    img = sensor.snapshot()

    # 显示帧率
    fps = clock.fps()
    img.draw_string(5, 5, "FPS:%.1f" % fps, color=255, scale=1)

    # 寻找白色边框（黑色物体内部）
    frames = img.find_blobs([(180, 255)], merge=True, margin=10)
    frame_blob = find_center_min_blob(frames)

    if not frame_blob:
        img.draw_string(5, 20, "NO FRAME", color=255, scale=1)
        img.draw_string(5, 35, "Adjust Threshold", color=255, scale=1)
        lcd.display(img)
        print("NO FRAME")
        continue

    # 在图像上显示边框像素宽度（重要校准信息）
    frame_width_str = "FrameW:%dpx" % frame_blob.w()
    img.draw_string(5, 20, frame_width_str, color=255, scale=1)

    # 显示校准参考值
    calib_str = "Calib:%dpx@%dmm" % (FRAME_WIDTH_PIXEL_2, DISTANCE_MM_2)
    img.draw_string(5, 35, calib_str, color=255, scale=1)

    # 计算距离
    distance = DISTANCE_MM_2 * FRAME_WIDTH_PIXEL_2 / frame_blob.w()

    # 设置ROI（避开黑框边缘）
    frame_roi = (
        frame_blob.x() + 5,
        frame_blob.y() + 5,
        max(10, frame_blob.w() - 10),
        max(10, frame_blob.h() - 10)
    )

    # 寻找黑色物体
    objs = img.find_blobs([(0, 100)], roi=frame_roi, merge=True)
    obj_blob = find_center_max_blob(objs)

    if not obj_blob:
        img.draw_string(5, 50, "NO OBJ", color=255, scale=1)
        lcd.display(img)
        print("NO OBJECT")
        continue

    # 计算物体尺寸
    obj_w_mm = obj_blob.w() / frame_blob.w() * FRAME_WIDTH_MM

    # 形状识别
    density = obj_blob.density()
    size_str = ""

    # 查找底部边缘
    bottom_line = find_bottom_edge(img, obj_blob)
    bottom_width, bottom_left, bottom_right = get_bottom_width(obj_blob, bottom_line)

    # 根据密度判断形状
    if density > 0.9:
        actual_size = bottom_width / frame_blob.w() * FRAME_WIDTH_MM
        size_str = "Square:%.1fmm" % actual_size
    elif density > 0.6:
        actual_size = obj_w_mm
        size_str = "Circle:%.1fmm" % actual_size
    elif density > 0.4:
        actual_size = bottom_width / frame_blob.w() * FRAME_WIDTH_MM
        size_str = "Triangle:%.1fmm" % actual_size
    else:
        size_str = "Size:%.1fmm" % obj_w_mm
        actual_size = obj_w_mm

    dist_str = "Dist:%.1fmm" % distance

    # 显示位置计算
    text_x = max(0, min(obj_blob.x() - 20, img.width() - 100))
    text_y = obj_blob.y() + obj_blob.h() + 5
    if text_y > img.height() - 60:  # 更大的空间
        text_y = max(60, obj_blob.y() - 60)

    # 绘制UI元素
    img.draw_rectangle(frame_blob.rect(), color=255)
    img.draw_rectangle(obj_blob.rect(), color=128)

    if bottom_line:
        img.draw_line(bottom_left[0], bottom_left[1], bottom_right[0], bottom_right[1], color=255, thickness=2)
        img.draw_circle(bottom_left[0], bottom_left[1], 3, color=255, fill=True)
        img.draw_circle(bottom_right[0], bottom_right[1], 3, color=255, fill=True)

    # 绘制文本背景
    bg_height = 40
    bg_width = max(len(size_str)*10, len(dist_str)*10) + 10
    img.draw_rectangle(text_x, text_y, bg_width, bg_height, color=255, fill=True)

    # 绘制物体信息
    img.draw_string(text_x + 5, text_y, size_str, color=0, scale=1)
    img.draw_string(text_x + 5, text_y + 20, dist_str, color=0, scale=1)

    # 显示到LCD
    lcd.display(img)

    # 打印调试信息
    print("Frame W:%dpx | Obj Density:%.2f" % (frame_blob.w(), density))
    print("%s | %s" % (size_str, dist_str))
    print("FPS:%.1f" % fps)
    print("--------------------------------")
