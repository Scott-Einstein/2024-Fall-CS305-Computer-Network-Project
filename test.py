import pyaudio
import threading
from collections import deque
import time

# 音频参数配置
FORMAT = pyaudio.paInt16  # 16-bit 音频格式
CHANNELS = 2              # 单声道
RATE = 48000              # 采样率
BUFFER_SIZE = 1024 * 10   # 环形缓冲区大小（可以根据需求调整）
CHUNK = 1024              # 数据块大小
INPUT_DEVICE_INDEX = None  # 替换为你设备的索引（如需要）

# 初始化 PyAudio
audio = pyaudio.PyAudio()

# 环形缓冲区
audio_buffer = deque(maxlen=BUFFER_SIZE)  # 使用双端队列实现环形缓冲区

# 输入流（录制）
streamin = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    start=True,
    input_device_index=INPUT_DEVICE_INDEX
)

# 输出流（播放）
streamout = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    output=True,
    start=True
)

# 控制标志
is_running = True


def record_audio():
    """
    持续录制音频，并写入缓冲区
    """
    global is_running
    while is_running:
        try:
            data = streamin.read(CHUNK, exception_on_overflow=False)
            audio_buffer.append(data)
        except Exception as e:
            print(f"[录制错误] {e}")


def play_audio():
    """
    持续从缓冲区读取音频数据并播放
    """
    global is_running
    while is_running:
        try:
            if audio_buffer:
                # 从缓冲区获取音频数据并播放
                data = audio_buffer.popleft()
                streamout.write(data)
            else:
                time.sleep(0.01)  # 缓冲区为空时稍作等待
        except Exception as e:
            print(f"[播放错误] {e}")


# 启动线程
record_thread = threading.Thread(target=record_audio)
play_thread = threading.Thread(target=play_audio)

record_thread.start()
play_thread.start()

print("开始录制并播放音频（按 Ctrl+C 停止）")

# 主线程等待用户停止
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n停止录制和播放...")
    is_running = False

# 等待线程结束
record_thread.join()
play_thread.join()

# 关闭流和 PyAudio 实例
streamin.stop_stream()
streamin.close()
streamout.stop_stream()
streamout.close()
audio.terminate()
