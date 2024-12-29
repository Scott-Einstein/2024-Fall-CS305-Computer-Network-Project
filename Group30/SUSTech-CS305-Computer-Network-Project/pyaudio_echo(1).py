import pyaudio
from av import AudioFrame
import numpy as np

# Set up the parameters for audio stream
FORMAT = pyaudio.paInt16  # 16-bit audio
CHANNELS = 1             # Mono audio (1 channel)
RATE = 44100             # 16kHz sample rate
CHUNK = 1024             # Number of frames per buffer (size of each audio chunk)
DEVICE_INDEX = None      # Use the default audio device

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open an input stream (from microphone) and output stream (to speakers)
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                output=True,
                frames_per_buffer=CHUNK,
                input_device_index=DEVICE_INDEX,
                output_device_index=DEVICE_INDEX)

print("Starting audio echo... Press Ctrl+C to stop.")

def warp_audio_data(audio_data):
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    audio_array = audio_array.reshape(CHANNELS, -1)
    audio_frame = AudioFrame.from_ndarray(audio_array, format="s16", layout="mono")
    return audio_frame

def unwrap_audio_data(audio_frame):
    audio_data = audio_frame.to_ndarray()
    return audio_data.tobytes()

try:
    # 获取输入和输出设备索引
    # input_device_index = p.get_default_input_device_info()['index']
    # output_device_index = p.get_default_output_device_info()['index']
    # print(input_device_index)
    # print(output_device_index)
    # 获取可用的设备数量

    # device_count = p.get_device_count()

    # # 输出所有设备的详细信息
    # for i in range(device_count):
    #     device_info = p.get_device_info_by_index(i)
    #     print(f"设备 {i}: {device_info['name']}")
    #     print(f"  输入设备: {device_info['maxInputChannels']}")
    #     print(f"  输出设备: {device_info['maxOutputChannels']}")
    #     print(f"  设备描述: {device_info['defaultSampleRate']} Hz\n")

    while True:
        # Read data from microphone (input stream)
        audio_data = stream.read(CHUNK)
        audio_frame = warp_audio_data(audio_data)
        
        # Play the captured audio data (output stream)
        audio_data = unwrap_audio_data(audio_frame)
        stream.write(audio_data)

except KeyboardInterrupt:
    print("Stopping audio echo...")

finally:
    # Close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()
