from util import *
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from aiortc import VideoStreamTrack
from aiortc.mediastreams import VideoFrame
from aiortc import AudioStreamTrack
from aiortc.mediastreams import AudioFrame
from aiortc.contrib.signaling import BYE, TcpSocketSignaling
import sounddevice as sd
import fractions
from datetime import datetime




class ConferenceClient:
    def __init__(self,):
        # sync client
        self.is_working = True
        self.server_addr = None  # server addr
        self.on_meeting = False  # status
        self.conns = None  # you may need to maintain multiple conns for a single conference
        self.support_data_types = []  # for some types of data
        self.share_data = {}

        self.conference_info = None  # you may need to save and update some conference_info regularly

        self.recv_data = None  # you may need to save received streamd data from other clients in conference
        
        self.audio_stream = None

        self.pc = RTCPeerConnection() #WebRTC连接
        self.server_host = SERVER_IP
        self.server_port = MAIN_SERVER_PORT

    async def handle_video_track(self, track):
        """处理远程视频轨道,接受视频帧并显示"""
        while True:
            try:
                frame = await track.recv()  # 接收远程视频帧
                if isinstance(frame, VideoFrame):
                    frame = frame.to_ndarray(format="bgr24")
                cv2.imshow("Received Frame", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except Exception as e:
                print(f"[ERROR] Video track handling failed: {e}")
                break


    async def handle_audio_track(self, track):
        """处理远程音频轨道，播放音频"""
        try:
            # 初始化 sounddevice 音频输出
            if not hasattr(self, "audio_stream") or self.audio_stream is None:
                self.audio_stream = sd.OutputStream(
                    samplerate=16000,  # 与发送端采样率一致
                    channels=1,        # 单声道
                    dtype="int16"      # 数据类型为 16-bit PCM
                )
                self.audio_stream.start()

            while True:
                try:
                    # 接收远程音频帧
                    audio_frame = await track.recv()

                    # 从 AudioFrame 提取 PCM 数据
                    audio_data = b"".join(bytes(plane) for plane in audio_frame.planes)

                    # 转换为 NumPy 数组，指定 dtype 为 int16
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)

                    # 播放音频数据
                    self.audio_stream.write(audio_array)
                    print("[INFO] Audio frame received and played.")
                except Exception as e:
                    print(f"[ERROR] Audio track handling failed: {e}")
                    break

        except Exception as e:
            print(f"[ERROR] Failed to initialize audio output: {e}")
        finally:
            # 停止音频输出并释放资源
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None




    async def connent(self):
        """
        create SDP connection with Server
        与服务器建立连接、发送 SDP提议、以及接收 SDP 答复
        """

        # 创建 SDP 提议
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        # 发送 SDP 提议
        reader, writer = await asyncio.open_connection(self.server_host, self.server_port)
        writer.write(self.pc.localDescription.sdp.encode())
        await writer.drain()

        # 从服务器接收 SDP 答复数据并解码
        data = await reader.read(16384)
        answer_sdp = data.decode()
        # 将服务器的 SDP 答复设置为客户端的远程描述。
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await self.pc.setRemoteDescription(answer)

        print(f"Sent offer to server and received answer.")


    def create_conference(self):
        """
        create a conference: send create-conference request to server and obtain necessary data to
        """
        pass

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        pass

    def quit_conference(self):
        """
        quit your on-going conference
        """
        pass

    def cancel_conference(self):
        """
        cancel your on-going conference (when you are the conference manager): ask server to close all clients
        """
        pass

    def keep_share(self, data_type, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        共享数据
        '''
        pass

    def share_switch(self, data_type):
        '''
        switch for sharing certain type of data (screen, camera, audio, etc.)
        切换共享数据类型
        '''
        pass

    def keep_recv(self, recv_conn, data_type, decompress=None):
        '''
        running task: keep receiving certain type of data (save or output)
        you can create other functions for receiving various kinds of data
        '''

    def output_data(self):
        '''
        running task: output received stream data
        '''

    def start_conference(self):
        '''
        init conns when create or join a conference with necessary conference_info
        and
        start necessary running task for conference
        '''

    def close_conference(self):
        '''
        close all conns to servers or other clients and cancel the running tasks
        pay attention to the exception handling
        '''
    

    async def start(self):
        """
        execute functions based on the command line input
        """
        # 创建WebRTC数据通道 点对点发送，无需服务器转发
        self.channel = self.pc.createDataChannel("chat")
        self.channel.on("open", lambda: print("Text DataChannel open"))
        self.channel.on("message", lambda message: print(f"Received message: {message}"))
        print("text channel initialized")

        # 添加摄像头和音频轨道, 捕获数据，加入到pc连接中
        camera_track = CameraStreamTrack()
        self.pc.addTrack(camera_track)
        print("video channel initialized")

        audio_track = MicrophoneStreamTrack()
        self.pc.addTrack(audio_track)
        print("audio channel initialized")

        # 当服务器创建了数据通道时，开始监听从服务器创建的数据通道
        @self.pc.on('datachannel')
        def on_datachannel(channel):
            print(f"[INFO] DataChannel created by server: {channel.label}")
            @channel.on("message")
            def on_message(message):
                print(f"[DATA] Message from server: {message}")

        # 监听ICE连接状态变化
        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            if self.pc.iceConnectionState == "failed":
                await self.pc.close()
        
        # 处理远程音视频轨道
        @self.pc.on("track")
        def on_track(track):
            print(f"Received remote track: {track.kind}")
            # 判断轨道类型，并启动异步任务处理
            if track.kind == "video":
                print("received video data")
                asyncio.create_task(self.handle_video_track(track))
            elif track.kind == "audio":
                print("received audio data")
                asyncio.create_task(self.handle_audio_track(track))
        
        # 非阻塞地获取用户输入
        async def async_input(prompt):
            """ 非阻塞的 input() 方法 """
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, input, prompt)
        
        # 与服务器连接并处理消息
        await self.connent()

        # 持续监听用户输入并发送消息
        while True:
            message = await async_input("")
            if message.lower() == "exit":
                break
            if self.channel and self.channel.readyState == "open":
                self.channel.send(message)

        await self.pc.close()


class CameraStreamTrack(VideoStreamTrack):
    """
    用于从摄像头帧创建视频轨道的自定义类
    """
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)
        self.frame_count = 0

    async def recv(self):
        self.frame_count += 1
        # print(f"Sending video frame {self.frame_count}")
        ret, frame = self.cap.read()
        if not ret:
            print("Failed to read frame from camera")
            return None
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = self.frame_count
        video_frame.time_base = fractions.Fraction(1, 30)  # Use fractions for time_base
        # Add timestamp to the frame
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Current time with milliseconds
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        return video_frame
    

from av.audio.frame import AudioFrame

class MicrophoneStreamTrack(MediaStreamTrack):
    """
    用于从麦克风创建音频轨道的自定义类
    """
    kind = "audio"  # 声明轨道类型为音频

    def __init__(self):
        super().__init__()  # 初始化父类
        self.audio_interface = pyaudio.PyAudio()
        self.sample_rate = 16000  # 设置采样率
        self.channels = 1         # 单声道
        self.frames_per_buffer = 1024  # 每帧的采样点数
        self.stream = self.audio_interface.open(
            format=pyaudio.paInt16,  # 16-bit PCM
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.frames_per_buffer
        )
        self.frame_count = 0

    async def recv(self):
        """捕获音频数据并生成音频帧"""
        try:
            self.frame_count += 1
            print(f"[INFO] Preparing to send frame {self.frame_count}.")

            # 从麦克风读取 PCM 数据
            audio_data = self.stream.read(self.frames_per_buffer, exception_on_overflow=False)

            # 创建 AudioFrame 对象并设置属性
            audio_frame = AudioFrame(format="s16", layout="mono", samples=self.frames_per_buffer)
            audio_frame.pts = self.frame_count
            audio_frame.time_base = fractions.Fraction(1, self.sample_rate)
            audio_frame.sample_rate = self.sample_rate

            # 将音频数据填充到帧中
            for plane in audio_frame.planes:
                plane.update(audio_data)

            print(f"[INFO] Sending frame {self.frame_count}.")
            return audio_frame

        except Exception as e:
            print(f"[ERROR] Failed to capture audio: {e}")
            return None

    def stop(self):
        """释放音频资源"""
        self.stream.stop_stream()
        self.stream.close()
        self.audio_interface.terminate()

   

if __name__ == '__main__':
    client = ConferenceClient()
    asyncio.run(client.start())


