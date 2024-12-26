HELP = 'Create         : create an conference\n' \
       'Join [conf_id ]: join a conference with conference ID\n' \
       'Quit           : quit an on-going conference\n' \
       'Cancel         : cancel your on-going conference (only the manager)\n\n' \
       'List           : list all on-going conferences\n' \
       '?      : show help information\n' \
       'Switch [type]     : show help information\n\n'

# SERVER_IP = '10.32.157.246'
SERVER_IP = '10.32.37.95'
LOCAL_HOST = '10.32.154.123'
MAIN_SERVER_PORT = 8888
TIMEOUT_SERVER = 5
CLIENT_PORT = 9999
# DGRAM_SIZE = 1500  # UDP
LOG_INTERVAL = 2

CHUNK = 960    # 数据块大小
CHANNELS = 2              # 双声道
RATE = 48000  # Sampling rate for audio capture
BUFFER_SIZE = 960 * 10   # 环形缓冲区大小（可以根据需求调整）
camera_width, camera_height = 480, 480  # resolution for camera capture
screen_resolution = (480, 480)
window_resolution = (480, 480)
BG_PATH = "no_signal_720p.jpg"

# 输入输出流控制API，直接更改变量就可以
voice = False
play = True
screen = False
camare = False