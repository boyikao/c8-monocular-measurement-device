import sensor
import image
import time
import math
import lcd

# 初始化LCD
lcd.init()

# 初始化摄像头
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.QVGA)
sensor.set_windowing((200, 240))
sensor.skip_frames(time=2000)

# 创建时钟对象 - 修复的关键行
clock = time.clock()

# 镜头畸变校正参数
LENS_CORRECTION_FACTOR = 0.98

# 中心点定义
CENTER_X = 100
CENTER_Y = 120

# 边框的真实长度（单位mm）
FRAME_WIDTH_MM = 176

# 校准数据
DISTANCE_MM_2 = 250
FRAME_WIDTH_PIXEL_2 = 188

# 多距离校准点
CALIBRATION_POINTS = [
    (300, 175),
    (400, 131),
    (500, 101)
]

def find_center_min_blob(blobs):
    min_area = float('inf')
    candidate = None
    for b in blobs:
        dist = abs(b.cx() - CENTER_X) + abs(b.cy() - CENTER_Y)
        if dist > 50:
            continue
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
        if b.area() > max_area:
            max_area = b.area()
            candidate = b
    return candidate

def find_squares(blobs, min_density=0.85, max_density=1.1, aspect_ratio_range=(0.8, 1.2)):
    squares = []
    for b in blobs:
        aspect_ratio = b.w() / b.h() if b.h() != 0 else 1.0
        if (min_density <= b.density() <= max_density and
            aspect_ratio_range[0] <= aspect_ratio <= aspect_ratio_range[1]):
            squareness = min(b.w()/b.h(), b.h()/b.w()) if b.w() > 0 and b.h() > 0 else 0
            squares.append({
                'blob': b,
                'density': b.density(),
                'aspect_ratio': aspect_ratio,
                'squareness': squareness
            })
    return squares

def find_min_square(squares):
    if not squares:
        return None
    min_area = float('inf')
    min_square = None
    for sq in squares:
        area = sq['blob'].area()
        if area < min_area:
            min_area = area
            min_square = sq
    return min_square

def find_bottom_edge(img, blob):
    roi = (blob.x(), blob.y() + blob.h() - 5, blob.w(), 5)
    lines = img.find_lines(roi=roi, threshold=1000, theta_margin=25, rho_margin=25)
    best_line = None
    max_length = 0
    for line in lines:
        theta = line.theta()
        if abs(theta) < 30 or abs(theta - 180) < 30:
            length = line.length()
            if length > max_length:
                max_length = length
                best_line = line
    return best_line

def get_bottom_width(blob, bottom_line=None):
    if bottom_line is None:
        return blob.w(), (blob.x(), blob.y() + blob.h() - 1), (blob.x() + blob.w(), blob.y() + blob.h() - 1)
    dx = bottom_line.x2() - bottom_line.x1()
    dy = bottom_line.y2() - bottom_line.y1()
    width = math.sqrt(dx*dx + dy*dy)
    return width, (bottom_line.x1(), bottom_line.y1()), (bottom_line.x2(), bottom_line.y2())

def calculate_distance(frame_width_pixels, calibration_points=None):
    """
    使用多点校准计算距离
    """
    # 使用单点校准
    if calibration_points is None or len(calibration_points) < 2:
        distance = DISTANCE_MM_2 * FRAME_WIDTH_PIXEL_2 / frame_width_pixels
        return distance

    # 使用多点校准拟合曲线
    total_weight = 0
    weighted_distance = 0

    for dist_mm, ref_pixels in calibration_points:
        # 计算当前测量与参考点的相似度 (逆距离加权)
        similarity = 1.0 / (1 + abs(frame_width_pixels - ref_pixels))
        weighted_distance += dist_mm * similarity
        total_weight += similarity

    return weighted_distance / total_weight

def apply_lens_correction(blob, center_x=CENTER_X, center_y=CENTER_Y, factor=LENS_CORRECTION_FACTOR):
    """
    应用镜头畸变校正
    """
    # 计算到图像中心的距离
    dx = blob.cx() - center_x
    dy = blob.cy() - center_y
    distance_from_center = math.sqrt(dx*dx + dy*dy)

    # 应用校正因子 (径向畸变校正)
    correction = 1.0 + factor * (distance_from_center / max(center_x, center_y))**2

    # 校正尺寸
    corrected_w = blob.w() * correction
    corrected_h = blob.h() * correction

    # 创建校正后的blob对象 (简化实现)
    class CorrectedBlob:
        def __init__(self, blob, w, h):
            self._blob = blob
            self.w = lambda: w
            self.h = lambda: h
            self.cx = blob.cx
            self.cy = blob.cy
            self.x = blob.x
            self.y = blob.y
            self.area = lambda: w * h
            self.rect = lambda: (blob.x(), blob.y(), w, h)
            self.density = blob.density

    return CorrectedBlob(blob, corrected_w, corrected_h)

def classify_shape(blob, bottom_width, frame_blob):
    density = blob.density()
    obj_w_mm = blob.w() / frame_blob.w() * FRAME_WIDTH_MM

    if density > 0.9:
        actual_size = bottom_width / frame_blob.w() * FRAME_WIDTH_MM
        return "Square", actual_size
    elif density > 0.6:
        actual_size = obj_w_mm
        return "Circle", actual_size
    elif density > 0.4:
        actual_size = bottom_width / frame_blob.w() * FRAME_WIDTH_MM
        return "Triangle", actual_size
    else:
        return "Unknown", obj_w_mm

# 状态变量用于稳定测量
frame_width_history = []
DISTANCE_SMOOTHING_FACTOR = 0.2  # 指数平滑系数

while True:
    clock.tick()  # 现在clock已被正确定义
    img = sensor.snapshot()

    # 图像预处理：中值滤波减少噪声
    img.median(1)

    # 显示帧率
    fps = clock.fps()
    img.draw_string(5, 5, "FPS:%.1f" % fps, color=255, scale=1)

    # 寻找白色边框
    frames = img.find_blobs([(180, 255)], merge=True, margin=10, area_threshold=1000)
    frame_blob = find_center_min_blob(frames)

    if not frame_blob:
        img.draw_string(5, 20, "NO FRAME", color=255, scale=1)
        lcd.display(img)
        print("NO FRAME")
        continue

    # 应用镜头畸变校正
    corrected_frame_blob = apply_lens_correction(frame_blob)

    # 在图像上显示边框像素宽度
    frame_width_str = "FrameW:%dpx" % corrected_frame_blob.w()
    img.draw_string(5, 20, frame_width_str, color=255, scale=1)

    # 显示校准参考值
    calib_str = "Calib:%dpx@%dmm" % (FRAME_WIDTH_PIXEL_2, DISTANCE_MM_2)
    img.draw_string(5, 35, calib_str, color=255, scale=1)

    # 使用多校准点计算距离
    distance = calculate_distance(corrected_frame_blob.w(), CALIBRATION_POINTS)

    # 距离平滑处理 (指数平滑)
    if frame_width_history:
        smoothed_distance = (1 - DISTANCE_SMOOTHING_FACTOR) * frame_width_history[-1] + DISTANCE_SMOOTHING_FACTOR * distance
    else:
        smoothed_distance = distance
    frame_width_history.append(smoothed_distance)
    if len(frame_width_history) > 5:  # 保留最近5个值
        frame_width_history.pop(0)

    # 设置ROI
    frame_roi = (
        frame_blob.x() + 5,
        frame_blob.y() + 5,
        max(10, frame_blob.w() - 10),
        max(10, frame_blob.h() - 10)
    )

    # 寻找所有物体
    objs = img.find_blobs([(0, 100)], roi=frame_roi, merge=False)

    # 识别所有正方形
    squares = find_squares(objs)
    min_square = find_min_square(squares)

    # 绘制所有正方形
    for sq in squares:
        b = sq['blob']
        img.draw_rectangle(b.rect(), color=200)
        sq_str = "SQ:%.2f" % sq['squareness']
        img.draw_string(b.x(), b.y()-10, sq_str, color=200, scale=1)

    # 处理最小正方形
    if min_square:
        obj_blob = min_square['blob']
        img.draw_rectangle(obj_blob.rect(), color=(0, 255, 0), thickness=2)

        bottom_line = find_bottom_edge(img, obj_blob)
        bottom_width, bottom_left, bottom_right = get_bottom_width(obj_blob, bottom_line)

        # 应用镜头畸变校正到物体
        corrected_obj_blob = apply_lens_correction(obj_blob)
        actual_size = bottom_width / corrected_frame_blob.w() * FRAME_WIDTH_MM

        size_str = "MinSQ:%.1fmm" % actual_size
        dist_str = "Dist:%.1fmm" % smoothed_distance

        text_x = max(0, min(obj_blob.x() - 20, img.width() - 100))
        text_y = obj_blob.y() + obj_blob.h() + 5
        if text_y > img.height() - 60:
            text_y = max(60, obj_blob.y() - 60)

        bg_height = 40
        bg_width = max(len(size_str)*10, len(dist_str)*10) + 20
        img.draw_rectangle(text_x, text_y, bg_width, bg_height, color=255, fill=True)
        img.draw_string(text_x + 5, text_y, size_str, color=0, scale=1)
        img.draw_string(text_x + 5, text_y + 20, dist_str, color=0, scale=1)

        print("Min Square: %.1fmm | Dist: %.1fmm | SQ: %.2f" %
              (actual_size, smoothed_distance, min_square['squareness']))
    else:
        # 处理其他形状
        obj_blob = find_center_max_blob(objs)

        if obj_blob:
            bottom_line = find_bottom_edge(img, obj_blob)
            bottom_width, bottom_left, bottom_right = get_bottom_width(obj_blob, bottom_line)

            # 应用镜头畸变校正到物体
            corrected_obj_blob = apply_lens_correction(obj_blob)
            shape_type, actual_size = classify_shape(corrected_obj_blob, bottom_width, corrected_frame_blob)

            size_str = "%s:%.1fmm" % (shape_type, actual_size)
            dist_str = "Dist:%.1fmm" % smoothed_distance

            text_x = max(0, min(obj_blob.x() - 20, img.width() - 100))
            text_y = obj_blob.y() + obj_blob.h() + 5
            if text_y > img.height() - 60:
                text_y = max(60, obj_blob.y() - 60)

            if shape_type == "Circle":
                rect_color = (255, 0, 0)
            elif shape_type == "Triangle":
                rect_color = (0, 0, 255)
            else:
                rect_color = 128

            img.draw_rectangle(obj_blob.rect(), color=rect_color)
            img.draw_line(bottom_left[0], bottom_left[1], bottom_right[0], bottom_right[1], color=(255, 0, 0), thickness=2)
            img.draw_circle(bottom_left[0], bottom_left[1], 3, color=(255, 0, 0), fill=True)
            img.draw_circle(bottom_right[0], bottom_right[1], 3, color=(255, 0, 0), fill=True)

            bg_height = 40
            bg_width = max(len(size_str)*10, len(dist_str)*10) + 20
            img.draw_rectangle(text_x, text_y, bg_width, bg_height, color=255, fill=True)
            img.draw_string(text_x + 5, text_y, size_str, color=0, scale=1)
            img.draw_string(text_x + 5, text_y + 20, dist_str, color=0, scale=1)

            print("%s: %.1fmm | Dist: %.1fmm" % (shape_type, actual_size, smoothed_distance))
        else:
            img.draw_string(5, 50, "NO OBJECT", color=255, scale=1)
            print("NO OBJECT DETECTED")

    # 显示边框
    img.draw_rectangle(frame_blob.rect(), color=255)

    # 显示物体数量
    objs_count_str = "Objects:%d" % len(objs)
    img.draw_string(5, 50, objs_count_str, color=255, scale=1)

    # 显示实际距离与计算距离的偏差
    if len(CALIBRATION_POINTS) > 1:
        estimated_pixel = DISTANCE_MM_2 * FRAME_WIDTH_PIXEL_2 / smoothed_distance
        error_percent = abs(estimated_pixel - corrected_frame_blob.w()) / corrected_frame_blob.w() * 100
        error_str = "Error:%.1f%%" % error_percent
        img.draw_string(5, 65, error_str, color=255, scale=1)

    lcd.display(img)

    print("Frame W:%dpx | Objects:%d | Squares:%d" % (corrected_frame_blob.w(), len(objs), len(squares)))
    print("FPS:%.1f" % fps)
    print("--------------------------------")
