'''
Simple util implementation for video conference
Including data capture, image compression and image overlap
Note that you can use your own implementation as well :)
'''
from io import BytesIO
import pyaudio
import cv2
import pyautogui
import numpy as np
from PIL import Image, ImageGrab
from config import *
from collections import deque
import time
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack,VideoStreamTrack,AudioStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from aiortc.contrib.media import MediaRelay
from aiortc.mediastreams import VideoFrame,AudioFrame

# from av import AudioFrame


import json
import fractions
import threading

# audio setting
FORMAT = pyaudio.paInt16
audio = pyaudio.PyAudio()
is_running = True
# 录制环形缓冲区
record_buffer = deque(maxlen=BUFFER_SIZE)  # 使用双端队列实现环形缓冲区
play_buffer = deque(maxlen=BUFFER_SIZE)
streamin = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    start=True,
)
streamout = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    output=True,
    start=True,
)
cap = cv2.VideoCapture(0)  # 0 表示使用默认的摄像头
if cap.isOpened():
    can_capture_camera = True
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
else:
    can_capture_camera = False

my_screen_size = pyautogui.size()

def resize_image_to_fit_screen(image, my_screen_size):
    screen_width, screen_height = my_screen_size

    original_width, original_height = image.size

    aspect_ratio = original_width / original_height

    if screen_width / screen_height > aspect_ratio:
        # resize according to height
        new_height = screen_height
        new_width = int(new_height * aspect_ratio)
    else:
        # resize according to width
        new_width = screen_width
        new_height = int(new_width / aspect_ratio)

    # resize the image
    resized_image = image.resize((new_width, new_height), Image.LANCZOS)

    return resized_image

def overlay_camera_images(screen_image, camera_images):
    """
    screen_image: PIL.Image
    camera_images: list[PIL.Image]
    """
    if screen_image is None and camera_images is None:
        print('[Warn]: cannot display when screen and camera are both None')
        return None
    if screen_image is not None:
        screen_image = resize_image_to_fit_screen(screen_image, my_screen_size)

    if camera_images is not None:
        # make sure same camera images
        if not all(img.size == camera_images[0].size for img in camera_images):
            raise ValueError("All camera images must have the same size")

        screen_width, screen_height = my_screen_size if screen_image is None else screen_image.size
        camera_width, camera_height = camera_images[0].size

        # calculate num_cameras_per_row
        num_cameras_per_row = screen_width // camera_width

        # adjust camera_imgs
        if len(camera_images) > num_cameras_per_row:
            adjusted_camera_width = screen_width // len(camera_images)
            adjusted_camera_height = (adjusted_camera_width * camera_height) // camera_width
            camera_images = [img.resize((adjusted_camera_width, adjusted_camera_height), Image.LANCZOS) for img in
                             camera_images]
            camera_width, camera_height = adjusted_camera_width, adjusted_camera_height
            num_cameras_per_row = len(camera_images)

        # if no screen_img, create a container
        if screen_image is None:
            display_image = Image.fromarray(np.zeros((camera_width, my_screen_size[1], 3), dtype=np.uint8))
        else:
            display_image = screen_image
        # cover screen_img using camera_images
        for i, camera_image in enumerate(camera_images):
            row = i // num_cameras_per_row
            col = i % num_cameras_per_row
            x = col * camera_width
            y = row * camera_height
            display_image.paste(camera_image, (x, y))

        return display_image
    else:
        return screen_image

# 把摄像头显示在screen的左上角
def overlay_camera_image(camera_image, screen_image):
    """
    将 camera_image 叠加在 screen_image 上，返回一个 720p 图像（1280x720）。
    下层为 screen_image，右上角为 camera_image。
    """
    # 目标分辨率
    window_resolution = (1280, 720)

    # 调整 screen_image 到目标分辨率
    screen_frame = cv2.resize(cv2.cvtColor(np.array(screen_image), cv2.COLOR_RGB2BGR), window_resolution, interpolation=cv2.INTER_LINEAR)
    
    # 计算右上角相机图像的分辨率
    cam_res = (1280 // 4, 720 // 4)  # 占总画布的 1/4
    
    # 调整 camera_image 到右上角大小
    camera_frame = cv2.resize(np.array(camera_image), cam_res, interpolation=cv2.INTER_LINEAR)
    
    # 计算 camera_frame 的放置位置
    x_offset = 1280 - cam_res[0]  # 右上角 x 起点
    y_offset = 0                  # 右上角 y 起点
    
    # 将 camera_frame 叠加到 screen_frame 的右上角
    screen_frame[y_offset:y_offset + cam_res[1], x_offset:x_offset + cam_res[0]] = camera_frame

    return screen_frame

# 返回截图作为 PIL.Image 对象
def capture_screen():
    img = ImageGrab.grab()
    return img

# 从相机中读取一帧图像，返回 PIL.Image 对象
def capture_camera():
    # capture frame of camera
    ret, frame = cap.read()
    if not ret:
        raise Exception('Fail to capture frame from camera')
    return Image.fromarray(frame)

# 持续录音
def record_audio():
    """
    持续录制音频,转化为音频帧，并写入缓冲区
    """
    global is_running
    while is_running:
        try:
            data = streamin.read(CHUNK, exception_on_overflow=False)
            frame = data_to_audio_frame(data, sample_rate=RATE, channels=CHANNELS)
            if voice:
                record_buffer.append(frame) # 如果打开声音，才将录制的数据放入队列
        except Exception as e:
            print(f"[音频录制错误] {e}")
    print("[INFO] End recording audio from microphone.")

# 返回原始 PCM 音频数据
def capture_voice_frame():
    """
    从缓冲区读取音频数据，如果缓冲区为空，返回空白音频帧
    """
    try:
        # 从缓冲区读取音频数据
        return record_buffer.popleft()
    except IndexError:
        # 如果缓冲区为空，返回空白帧
        return b'\x00' * CHUNK * CHANNELS * 2  # 每个样本16-bit，占2字节
    
# 返回处理的图像
def capture_video_frame():
    if camare and not screen:
        # camare 不需要BGR转换
        frame_bgr = np.array(capture_camera())
    elif not camare and screen:
        # screen 需要bgr转换
        frame_np = np.array(capture_screen())
        # 转换为 BGR 格式
        frame_bgr = cv2.cvtColor(frame_np, cv2.COLOR_RGB2BGR)
    elif camare and screen:
        # cv2 均衡化亮度
        camare_img = capture_camera()
        screen_img = capture_screen()
        frame_bgr =  overlay_camera_image(camare_img, screen_img)
    else:
        frame_bgr = cv2.imread(BG_PATH)

    # 调整为 720p 分辨率
    frame_resized = cv2.resize(frame_bgr, window_resolution, interpolation=cv2.INTER_LINEAR)
    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
    video_frame = VideoFrame.from_ndarray(frame_rgb)
    return video_frame

# 测试录制后的视频
def test_play_video():
    """
    捕获视频帧并以 720p 分辨率播放
    """

    try:
        while True:
            # 捕获视频帧
            video_frame = capture_video_frame()
            frame = video_frame.to_ndarray(format="bgr24")
            # 显示视频帧
            cv2.imshow("Video - 720p", frame)

            # 检测键盘输入，如果按下 'q' 键，则退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("视频播放测试结束")
                break

    except Exception as e:
        print(f"[Error] Video capture error: {e}")
    finally:
        # 关闭窗口
        cv2.destroyAllWindows()

# 测试录制后的音频
def test_play_audio():
    global is_running
    while is_running:
        try:
            data = streamin.read(CHUNK, exception_on_overflow=False)
            # frame = AudioFrame(format="s16", samples = CHUNK)
            # pcm_array = np.frombuffer(data, dtype=np.int16)
            # frame.planes[0].update(pcm_array.tobytes())
            if voice:
                record_buffer.append(data) # 如果打开声音，才将录制的数据放入队列
            play_buffer.append(record_buffer.popleft())
            if play:
                data = play_buffer.popleft()
                # data = frame.to_ndarray(format="s16")
                streamout.write(data) # 当开启声音的时候播放
        # except Exception as e:
        #     print(f"[音频录制错误] {e}")    
        finally:
            pass

def test_play_audioframe():
    global is_running
    while is_running:
        try:
            # 从音频输入流读取 PCM 数据
            data = streamin.read(CHUNK, exception_on_overflow=False)

            # 将 PCM 数据封装为 AudioFrame
            frame = data_to_audio_frame(data, sample_rate=RATE, channels=CHANNELS)
            
            # 如果打开声音，存入录制缓冲区
            if voice:
                record_buffer.append(frame)

            # 存入播放缓冲区
            play_buffer.append(frame)

            # 播放音频
            if play and play_buffer:
                frame_to_play = play_buffer.popleft()
                pcm_data = audio_frame_to_data(frame_to_play)  # 解包 AudioFrame 为 PCM 数据
                streamout.write(pcm_data)  # 播放解包后的 PCM 数据
        # except Exception as e:
        #     print(f"[音频录制错误] {e}")
        finally:
            pass

def audio_frame_to_data(frame):
    """
    将 AudioFrame 解包为 PCM 数据。
    :param frame: PyAV 的 AudioFrame 对象
    :return: 原始 PCM 数据
    """

    if frame is None:
        return b'\x00' * CHUNK * CHANNELS * 2  # 返回空白音频帧
    return b"".join(bytes(plane) for plane in frame.planes)  # 获取音频数据的缓冲区



def data_to_audio_frame(data, sample_rate, channels):
    """
    将 PCM 数据封装为 AudioFrame。
    :param data: 原始 PCM 音频数据
    :param sample_rate: 音频采样率
    :param channels: 音频通道数
    :return: 封装后的 AudioFrame
    """
    try:
        # 每个样本占用字节数
        bytes_per_sample = 2  # 16-bit PCM 数据

        # 计算样本数
        samples = len(data) // (bytes_per_sample * channels)

        # 创建 AudioFrame
        frame = AudioFrame(format="s16", layout="stereo", samples=samples)

        # 填充帧数据
        frame.planes[0].update(data)

        # 设置时间基准
        frame.sample_rate = sample_rate
        frame.time_base = fractions.Fraction(1, RATE)

        return frame
    except Exception as e:
        print(f"[ERROR] Failed to create AudioFrame: {e}")
        return None



# 向streamout写入audio_buffer的frame
def play_audio():
    global is_running
    while is_running:
        try:
            if play_buffer:
                # 从缓冲区获取音频数据并播放
                frame_to_play = play_buffer.popleft()
                pcm_data = audio_frame_to_data(frame_to_play)  # 解包 AudioFrame 为 PCM 数据
                if play:
                    streamout.write(pcm_data) # 当开启声音的时候播放
            else:
                time.sleep(0.01)  # 缓冲区为空时稍作等待
        except Exception as e:
            print(f"[音频播放错误] {e}")


# 播放视频帧
def play_video(frame):
    try:
        frame = frame.to_ndarray(format="bgr24")
        cv2.imshow("Video - 720p", frame)
    except Exception as e:
        print(f"[Error] Video playing error: {e}")

# 将 PIL.Image 对象压缩为JPEG
def compress_image(image, format='JPEG', quality=85):
    """
    compress image and output Bytes

    :param image: PIL.Image, input image
    :param format: str, output format ('JPEG', 'PNG', 'WEBP', ...)
    :param quality: int, compress quality (0-100), 85 default
    :return: bytes, compressed image data
    """
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format=format, quality=quality)
    img_byte_arr = img_byte_arr.getvalue()

    return img_byte_arr

# 将压缩后的图像字节数据解压为 PIL.Image 
def decompress_image(image_bytes):
    """
    decompress bytes to PIL.Image
    :param image_bytes: bytes, compressed data
    :return: PIL.Image
    """
    img_byte_arr = BytesIO(image_bytes)
    image = Image.open(img_byte_arr)

    return image

def close():
    cv2.destroyAllWindows()
    streamin.stop_stream()
    streamin.close()
    streamout.stop_stream()
    streamout.close()
    audio.terminate()


if __name__ == "__main__":
    try:
        test_play_audioframe()
    except KeyboardInterrupt:
        print("程序中断")
    finally:
        close()  # 确保资源被正确关闭
