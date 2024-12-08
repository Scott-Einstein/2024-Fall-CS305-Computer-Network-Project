HELP = 'Create         : create an conference\n' \
       'Join [conf_id ]: join a conference with conference ID\n' \
       'Quit           : quit an on-going conference\n' \
       'Cancel         : cancel your on-going conference (only the manager)\n\n'

SERVER_IP = '127.0.0.1'
MAIN_SERVER_PORT = 8888
TIMEOUT_SERVER = 5
# DGRAM_SIZE = 1500  # UDP
LOG_INTERVAL = 2

CHUNK = 4096
CHANNELS = 2              # 双声道
RATE = 48000  # Sampling rate for audio capture
CHUNK = 1024              # 数据块大小
BUFFER_SIZE = 1024 * 10   # 环形缓冲区大小（可以根据需求调整）
camera_width, camera_height = 1280, 720  # resolution for camera capture
screen_resolution = (1280, 720)
window_resolution = (1280, 720)
BG_PATH = "no_signal_720p.jpg"

# 输入输出流控制API，直接更改变量就可以
voice = True
play = True
screen = False
camare = True