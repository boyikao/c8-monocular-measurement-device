import sensor
import image
import time
import math
import lcd

# 初始化LCD
lcd.init(freq=15000000)
lcd.clear(lcd.WHITE)

# 初始化摄像头
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.set_windowing((200, 240))
sensor.skip_frames(time=2000)

clock = time.clock()
CENTER_X = 100
CENTER_Y = 120

# 边框的真实长度（单位mm）
FRAME_WIDTH_MM = 176

# 校准数据
DISTANCE_MM_2 = 360
FRAME_WIDTH_PIXEL_2 = 127

# 阈值设置
WHITE_THRESHOLD = (145, 255)
BLACK_THRESHOLD = (0, 150)

# 修复：创建一个简单的矩形类
class SimpleRect:
    def __init__(self, x, y, w, h):
        self.x = int(x)
        self.y = int(y)
        self.w = int(w)
        self.h = int(h)
        self.cx = int(x + w // 2)
        self.cy = int(y + h // 2)
        self.area = w * h

    def rect(self):
        return (self.x, self.y, self.w, self.h)

# 改进1: 添加距离相关的阈值调整
def get_adaptive_threshold(distance):
    """根据距离动态调整阈值"""
    if distance > 1000:  # 远距离
        return (WHITE_THRESHOLD[0] - 10, WHITE_THRESHOLD[1]), (0, BLACK_THRESHOLD[1] + 20)
    elif distance > 500:  # 中距离
        return WHITE_THRESHOLD, (0, BLACK_THRESHOLD[1] + 10)
    else:  # 近距离
        return WHITE_THRESHOLD, BLACK_THRESHOLD

# 改进2: 增强色块过滤条件
def is_valid_blob(blob, distance):
    """验证色块是否有效"""
    # 基本尺寸过滤
    min_size = max(20, 1000 / distance)  # 距离越大，最小尺寸要求越小
    if blob.w() < min_size or blob.h() < min_size:
        return False

    # 宽高比过滤
    aspect_ratio = blob.w() / blob.h()
    if aspect_ratio < 0.3 or aspect_ratio > 3.0:
        return False

    # 密度过滤
    if blob.density() < 0.3:
        return False

    return True

def find_center_min_blob(blobs, distance):
    min_area = 100000
    candidate = None
    for b in blobs:
        # 添加有效性检查
        if not is_valid_blob(b, distance):
            continue

        dist = abs(b.cx() - CENTER_X) + abs(b.cy() - CENTER_Y)
        if dist > 50:
            continue
        if b.area() < min_area:
            min_area = b.area()
            candidate = b
    return candidate

def find_center_max_blob(blobs, distance):
    max_area = 0
    candidate = None
    for b in blobs:
        # 添加有效性检查
        if not is_valid_blob(b, distance):
            continue

        dist = abs(b.cx() - CENTER_X) + abs(b.cy() - CENTER_Y)
        if dist > 50:
            continue
        if b.area() > max_area:
            max_area = b.area()
            candidate = b
    return candidate

# 改进3: 增强边缘检测算法 (修复类型错误)
def find_bottom_edge(img, rect, distance):
    """使用矩形而不是blob对象"""
    # 确保所有坐标都是整数
    x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])

    # 计算ROI位置
    bottom_y = y + h - 5
    if bottom_y < 0:
        bottom_y = 0
    roi_height = 5
    if bottom_y + roi_height > img.height():
        roi_height = img.height() - bottom_y
    if roi_height <= 0:  # 确保高度有效
        return None

    # 创建ROI区域
    roi = (x, bottom_y, w, roi_height)

    # 根据距离调整阈值
    edge_threshold = max(500, 2000 - distance)  # 远距离使用更低阈值
    # 关键修复：转换为整数
    edge_threshold = int(edge_threshold)

    # 确保阈值在合理范围内
    edge_threshold = max(100, min(2000, edge_threshold))

    lines = img.find_lines(roi=roi, threshold=edge_threshold, theta_margin=25, rho_margin=25)

    best_line = None
    max_length = 0
    for line in lines:
        theta = line.theta()
        if abs(theta) < 30 or abs(theta - 180) < 30:
            length = line.length()
            if length > max_length and length > w * 0.7:  # 长度至少为宽度的70%
                max_length = length
                best_line = line
    return best_line

def get_bottom_width(rect, bottom_line=None):
    """使用矩形而不是blob对象"""
    x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
    if bottom_line is None:
        left_point = (x, y + h - 1)
        right_point = (x + w, y + h - 1)
        return w, left_point, right_point

    dx = bottom_line.x2() - bottom_line.x1()
    dy = bottom_line.y2() - bottom_line.y1()
    width = math.sqrt(dx*dx + dy*dy)
    return width, (int(bottom_line.x1()), int(bottom_line.y1())), (int(bottom_line.x2()), int(bottom_line.y2()))

# 改进4: 添加多帧稳定性检测
frame_history = []
obj_history = []

def update_history(frame, obj, max_history=5):
    """更新检测历史"""
    global frame_history, obj_history

    # 添加当前检测结果
    if frame and obj:
        frame_history.append((frame.cx(), frame.cy(), frame.w(), frame.h()))
        obj_history.append((obj.cx(), obj.cy(), obj.w(), obj.h()))
    else:
        frame_history.append(None)
        obj_history.append(None)

    # 保持历史长度
    if len(frame_history) > max_history:
        frame_history = frame_history[-max_history:]
        obj_history = obj_history[-max_history:]

def get_stable_detection():
    """获取稳定的检测结果"""
    # 只考虑最近的有效检测
    valid_frames = [f for f in frame_history if f is not None]
    valid_objs = [o for o in obj_history if o is not None]

    if not valid_frames or not valid_objs:
        return None, None

    # 计算平均位置和尺寸
    avg_frame = (
        sum(f[0] for f in valid_frames) / len(valid_frames),
        sum(f[1] for f in valid_frames) / len(valid_frames),
        sum(f[2] for f in valid_frames) / len(valid_frames),
        sum(f[3] for f in valid_frames) / len(valid_frames)
    )

    avg_obj = (
        sum(o[0] for o in valid_objs) / len(valid_objs),
        sum(o[1] for o in valid_objs) / len(valid_objs),
        sum(o[2] for o in valid_objs) / len(valid_objs),
        sum(o[3] for o in valid_objs) / len(valid_objs)
    )

    return avg_frame, avg_obj

# 主循环
while True:
    clock.tick()
    img = sensor.snapshot()
    gray = img.to_grayscale(copy=True)

    # 初始距离估计（使用上一次的距离或默认值）
    last_distance = frame_history[-1][2] if frame_history and frame_history[-1] else 1000
    w_thresh, b_thresh = get_adaptive_threshold(last_distance)

    # 寻找白色边框
    frames = gray.find_blobs([w_thresh], merge=True, margin=10, area_threshold=100)
    frame_blob = find_center_min_blob(frames, last_distance) if frames else None

    if frame_blob:
        # 计算距离
        distance = DISTANCE_MM_2 * FRAME_WIDTH_PIXEL_2 / frame_blob.w()

        # 设置ROI
        frame_roi = (
            frame_blob.x() + 5,
            frame_blob.y() + 5,
            max(10, frame_blob.w() - 10),
            max(10, frame_blob.h() - 10)
        )

        # 寻找黑色物体
        objs = gray.find_blobs([b_thresh], roi=frame_roi, merge=True, area_threshold=50)
        obj_blob = find_center_max_blob(objs, distance) if objs else None
    else:
        distance = last_distance
        obj_blob = None

    # 更新历史记录
    update_history(frame_blob, obj_blob)

    # 获取稳定的检测结果
    stable_frame, stable_obj = get_stable_detection()

    if stable_frame and stable_obj:
        # 使用稳定的检测结果
        frame_cx, frame_cy, frame_w, frame_h = stable_frame
        obj_cx, obj_cy, obj_w, obj_h = stable_obj

        # 计算距离
        distance = DISTANCE_MM_2 * FRAME_WIDTH_PIXEL_2 / frame_w

        # 计算物体尺寸
        obj_w_mm = obj_w / frame_w * FRAME_WIDTH_MM

        # 创建矩形对象用于绘制
        frame_rect = (int(frame_cx - frame_w/2), int(frame_cy - frame_h/2), int(frame_w), int(frame_h))
        obj_rect_tuple = (int(obj_cx - obj_w/2), int(obj_cy - obj_h/2), int(obj_w), int(obj_h))

        # 创建简单的矩形对象用于计算
        obj_rect = SimpleRect(*obj_rect_tuple)

        img.draw_rectangle(frame_rect, color=(255, 255, 255))
        img.draw_rectangle(obj_rect.rect(), color=(128, 128, 128))

        # 查找底部边缘
        bottom_line = find_bottom_edge(gray, obj_rect_tuple, distance)

        # 获取底边宽度
        if bottom_line:
            bottom_width, bottom_left, bottom_right = get_bottom_width(obj_rect_tuple, bottom_line)
        else:
            bottom_width = obj_rect.w
            bottom_left = (obj_rect.x, obj_rect.y + obj_rect.h - 1)
            bottom_right = (obj_rect.x + obj_rect.w, obj_rect.y + obj_rect.h - 1)

        # 形状识别（简化版）
        size_str = "Size:%.1fmm" % obj_w_mm

        # 像素宽度显示
        pixel_str = "Pix:%dpx" % int(frame_w)
        dist_str = "Dist:%.1fmm" % distance

        # 显示位置
        text_x = max(0, min(obj_rect.x - 20, img.width() - 100))
        text_y = obj_rect.y + obj_rect.h + 5
        if text_y > img.height() - 60:  # 增加高度以适应三行文本
            text_y = max(10, obj_rect.y - 60)

        # 绘制文本背景
        bg_height = 60
        bg_width = max(len(size_str)*10, len(dist_str)*10, len(pixel_str)*10) + 10
        img.draw_rectangle(text_x, text_y, bg_width, bg_height, color=(255, 255, 255), fill=True)

        # 绘制文本
        img.draw_string(text_x + 5, text_y, size_str, color=(0, 0, 0), scale=1)
        img.draw_string(text_x + 5, text_y + 20, dist_str, color=(0, 0, 0), scale=1)
        img.draw_string(text_x + 5, text_y + 40, pixel_str, color=(0, 0, 0), scale=1)

        # 绘制底边（如果找到）
        if bottom_line:
            img.draw_line(bottom_left[0], bottom_left[1], bottom_right[0], bottom_right[1], color=(255, 0, 0), thickness=2)
            img.draw_circle(bottom_left[0], bottom_left[1], 3, color=(255, 0, 0), fill=True)
            img.draw_circle(bottom_right[0], bottom_right[1], 3, color=(255, 0, 0), fill=True)

        # 打印信息
        print("Stable Frame W:%dpx" % int(frame_w))
        print("%s %s" % (size_str, dist_str))

    elif frame_blob and obj_blob:
        # 当前帧有效但历史不足，绘制当前检测结果
        img.draw_rectangle(frame_blob.rect(), color=(255, 255, 255))
        img.draw_rectangle(obj_blob.rect(), color=(128, 128, 128))
        img.draw_string(10, 10, "Initializing...", color=(255, 0, 0))

        # 计算并显示当前帧的信息
        distance = DISTANCE_MM_2 * FRAME_WIDTH_PIXEL_2 / frame_blob.w()
        obj_w_mm = obj_blob.w() / frame_blob.w() * FRAME_WIDTH_MM
        pixel_str = "Pix:%dpx" % frame_blob.w()
        dist_str = "Dist:%.1fmm" % distance

        # 显示位置
        text_x = max(0, min(obj_blob.x() - 20, img.width() - 100))
        text_y = obj_blob.y() + obj_blob.h() + 5
        if text_y > img.height() - 60:  # 增加高度以适应三行文本
            text_y = max(10, obj_blob.y() - 60)

        # 绘制文本背景
        bg_height = 60
        bg_width = max(len("Size:%.1fmm" % obj_w_mm)*10, len(dist_str)*10, len(pixel_str)*10) + 10
        img.draw_rectangle(text_x, text_y, bg_width, bg_height, color=(255, 255, 255), fill=True)

        # 绘制文本
        img.draw_string(text_x + 5, text_y, "Size:%.1fmm" % obj_w_mm, color=(0, 0, 0), scale=1)
        img.draw_string(text_x + 5, text_y + 20, dist_str, color=(0, 0, 0), scale=1)
        img.draw_string(text_x + 5, text_y + 40, pixel_str, color=(0, 0, 0), scale=1)
    else:
        img.draw_string(10, 10, "NO TARGET", color=(255, 0, 0))

    # 显示帧率
    fps_str = "FPS:%.1f" % clock.fps()
    img.draw_string(img.width() - 80, 10, fps_str, color=(0, 255, 0))

    # 显示图像
    lcd.display(img)
    print(fps_str)
