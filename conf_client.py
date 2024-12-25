from util import *
import fractions
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from aiortc.contrib.signaling import BYE, TcpSocketSignaling
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk
import asyncio
import config
import sys
import asyncio


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
        
        self.pc = RTCPeerConnection() #WebRTC连接
        self.username=None

        self.play_buffer = asyncio.Queue()
        self.received_audio_track = None
        self.received_video_tracks = []
        self.window_names = {}  # 用于保存每个视频的窗口名称
        self.reader = None
        self.writer = None


    def set_username(self):
        self.username = input("Please enter your username: ").strip()
        if not self.username:
            print("Username cannot be empty. Please enter a valid username.")
            self.set_username()

    async def create_conference(self):
        """
        create a conference: send create-conference request to server and obtain necessary data to
        """

        # 检查摄像头是否已经打开
        if not cap.isOpened():
            print("Camera not opened, trying to open the camera...")
            # 尝试重新打开摄像头
            cap.open(0)  # 重新尝试打开摄像头
            if not cap.isOpened():
                raise Exception("Failed to open camera after retry")


        if self.on_meeting:
            print("You are already in a conference.")
            return
        reader, writer = await asyncio.open_connection(*self.server_addr)
        # Send create request with username
        create_cmd = f"create {self.username}"
        writer.write(create_cmd.encode())
        await writer.drain()
        data = await reader.read(100)
        response = data.decode()
        print(f"Received: {response}")

        writer.close()
        await writer.wait_closed()

        # 如果成功创建会议，则自动加入会议
        reader, writer = await asyncio.open_connection(*self.server_addr)
        if "created" in response:
            # 将 response 字符串解析为字典
            response_data = json.loads(response)
            self.conference_info = response_data["message"].split()[1]  # Save the conference ID
            print(f"Created conference: {self.conference_info}")

            join_cmd = f"join {self.conference_info} {self.username}"
            writer.write(join_cmd.encode())
            await writer.drain()
            data = await reader.read(100)
            response = data.decode()
            print(f"Received: {response}")

            if "Joined" in response:
                # Update client state to reflect that the client has joined the conference
                self.on_meeting = True
                print(f"Now in meeting: {self.conference_info}")

                response_data = json.loads(response)
                ip = SERVER_IP
                port = response_data["port"]
                await self.start_conference(ip, port)

        writer.close()
        await writer.wait_closed()

    async def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data
        """

        # 检查摄像头是否已经打开
        if not cap.isOpened():
            print("Camera not opened, trying to open the camera...")
            # 尝试重新打开摄像头
            cap.open(0)  # 重新尝试打开摄像头
            if not cap.isOpened():
                raise Exception("Failed to open camera after retry")
        
        if self.on_meeting:
            print("You are already in a conference.")
            return
        reader, writer = await asyncio.open_connection(*self.server_addr)
        # Send join request with conference_id and username
        join_cmd = f"join {conference_id} {self.username}"
        writer.write(join_cmd.encode())
        await writer.drain()
        data = await reader.read(100)
        response = data.decode()
        print(f"Received: {response}")

        if "Joined" in response:
            # Update client state to reflect that the client has joined the conference
            self.on_meeting = True
            self.conference_info = conference_id  # Save the conference ID
            print(f"Now in meeting: {self.conference_info}")

            # 将 response 字符串解析为字典
            response_data = json.loads(response)
            ip = SERVER_IP
            port = response_data["port"]
            await self.start_conference(ip, port)

        writer.close()
        await writer.wait_closed()


    async def quit_conference(self):
        """
        quit your on-going conference
        """
        if not self.on_meeting:
            print("You are not in any conference.")
            return
        try:
            if self.on_meeting and self.username:
                reader, writer = await asyncio.open_connection(*self.server_addr)
                # Send quit request with username
                quit_cmd = f"quit {self.username}"
                writer.write(quit_cmd.encode())
                await writer.drain()
                data = await reader.read(100)
                print(f"Received: {data.decode()}")
                self.on_meeting = False
                self.conference_info = None
                writer.close()
                await writer.wait_closed()

                # 关闭 RTCPeerConnection
                if self.pc:
                    print("[INFO] Closing RTCPeerConnection.")
                    await self.pc.close()  # 关闭RTCPeerConnection

                # 关闭数据通道
                if hasattr(self, 'channel') and self.channel:
                    if self.channel.readyState == 'open':
                        print("[INFO] Closing data channel.")
                        await self.channel.close()  # 关闭data channel
                    else:
                        print("[INFO] Data channel is already closed.")
                else:
                    print("[INFO] No data channel to close.")
                # 关闭 OpenCV 视频窗口
                cv2.destroyAllWindows()  # 关闭所有 OpenCV 视频窗口
                

                # 释放摄像头资源
                cap.release()
                self.received_audio_track = None
                self.received_video_tracks = []
            else:
                print("You are not in any conference.")
        except Exception as e:
            print(f"[ERROR] An error occurred while quitting the conference: {e}")

    async def cancel_conference(self):
        """
        cancel your on-going conference (when you are the conference manager): ask server to close all clients
        """
        if not self.on_meeting:
            print("You cannot cancel a conference when you are not in one.")
            return
        reader, writer = await asyncio.open_connection(*self.server_addr)
        # Send cancel request with conference_id and username
        cancel_cmd = f"cancel {self.conference_info} {self.username}"
        writer.write(cancel_cmd.encode())
        await writer.drain()
        data = await reader.read(100)
        response = data.decode()
        print(f"Received: {response}")

        # if "success" in response:
            # self.on_meeting = False
            # self.conference_info = None
        cv2.destroyAllWindows()  # 关闭所有 OpenCV 视频窗口
        # 释放摄像头资源
        cap.release()
        self.received_audio_track = None
        self.received_video_tracks = []
        cv2.destroyAllWindows()
        writer.close()
        await writer.wait_closed()
        
        


    async def list_conferences(self):
        reader, writer = await asyncio.open_connection(*self.server_addr)
        writer.write(b"list")
        await writer.drain()
        data = await reader.read(100)
        response = data.decode()
        print(f"Available conferences: {response}")

        # 在GUI中显示消息
        self.gui.display_received_message(response)

        writer.close()
        await writer.wait_closed()
    
    def keep_share(self, data_type, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        '''
        pass

    def share_switch(self, data_type):
        '''
        switch for sharing certain type of data (screen, camera, audio, etc.)
        '''
        # 直接设置util.py里audio, screen, camare的True,False
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

    async def start_conference(self, ip, port):
        '''
        init conns when create or join a conference with necessary conference_info
        and
        start necessary running task for conference
        '''

        # Create new RTCPeerConnection and DataChannel
        self.pc = RTCPeerConnection()  # Create a new peer connection

         # 创建WebRTC数据通道,监听open和message实践
        self.channel = self.pc.createDataChannel("chat")
        self.channel.on("open")
        self.channel.on("message", lambda message: print(f"Received message: {message}"))

        # 创建音视频轨道
        self.video_track = VideoStreamTrack()
        self.pc.addTrack(self.video_track)
        print("[INFO] Video DataChannel open")

        self.audio_track = MicrophoneStreamTrack()
        self.pc.addTrack(self.audio_track)
        print("[INFO] Audio DataChannel open")
        

        # 当服务器创建了数据通道时，开始监听从服务器创建的数据通道
        @self.pc.on('datachannel')
        def on_datachannel(channel):
            print(f"DataChannel created by server: {channel.label}")

            @channel.on("message")
            async def on_message(message):
                if(message == 'quit'):
                    await self.quit_conference()
                else:
                    try:
                        # 如果接收到的是 JSON 格式的消息
                        message_data = json.loads(message)  # 解析 JSON 字符串

                        # 从字典中提取发送人、时间戳和消息内容
                        username = message_data.get("username", "Unknown")  # 提取发送人，若没有则默认"Unknown"
                        timestamp = message_data.get("timestamp", "Unknown")  # 提取时间戳，若没有则默认"Unknown"
                        content = message_data.get("message", "No message")  # 提取消息内容，若没有则默认"无消息"

                        # 打印接收到的消息
                        print(f"Message from {username} at {timestamp}: {content}")

                        # 在GUI中显示消息
                        self.gui.display_received_message(f"Message from {username} at {timestamp}: {content}")

                    except json.JSONDecodeError:
                        print(f"Received invalid message format: {message}")

        # 监听ICE连接状态变化
        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            if self.pc.iceConnectionState == "failed":
                await self.pc.close()

        # 处理远程音视频轨道
        @self.pc.on("track")
        def on_track(track):
            print(f"[INFO] Received remote track: {track.kind}")
            if track.kind == "video":
                self.received_video_tracks.append(track)
                asyncio.create_task(self.handle_video_track())
            elif track.kind == "audio":
                self.received_audio_track = track
                asyncio.create_task(self.handle_audio_track())


        # 与服务器连接并处理消息
        await self.connect(ip, port)



    def close_conference(self):
        '''
        close all conns to servers or other clients and cancel the running tasks
        pay attention to the exception handling
        '''

    async def handle_video_track(self):
        """
        处理远程视频轨道，接受视频帧并显示在不同的窗口中
        """
        while True:
            try:
                for idx, track in enumerate(self.received_video_tracks):
                    # 生成窗口名称
                    if track not in self.window_names:
                        self.window_names[track] = f"Track {idx}"

                    # 接收视频帧
                    if track is None:
                        break
                    
                    frame = await track.recv()
                    if isinstance(frame, VideoFrame):
                        # 转换为 numpy 数组，格式为 BGR
                        frame_ndarray = frame.to_ndarray(format="bgr24")
                        # 在对应窗口中显示
                        cv2.imshow(self.window_names[track], frame_ndarray)

                    # 按键退出逻辑
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
            # except Exception as e:
            #     print(f"[ERROR] Handling video track {idx} failed: {e}")
            #     cv2.destroyAllWindows()
            #     break
            finally:pass

    async def handle_audio_track(self):
        """处理远程音频轨道"""
        while True:
            try:
                track = self.received_audio_track
                frame = await track.recv()
                pcm_data = audio_frame_to_data(frame)
                streamout.write(pcm_data)
            except Exception as e:
                print(f"[ERROR] Audio track handling failed: {e}")
                break

    async def play_audio(self, play_buffer):
        """处理远程音频轨道"""
        while True:
            try:
                if play_buffer:
                    new_frame = play_buffer.popleft()
                    pcm_data = audio_frame_to_data(new_frame)
                    streamout.write(pcm_data)
                    print(f"[INFO] play frame data {new_frame}")

            except Exception as e:
                print(f"[ERROR] Audio track handling failed: {e}")
                break

    async def start(self):
        """
        execute functions based on the command line input
        """
        self.set_username()

        # 非阻塞地获取用户输入
        async def async_input(prompt):
            """ 非阻塞的 input() 方法 """
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, input, prompt)
        

        while True:
            if not self.on_meeting:
                status = 'Free'
            else:
                status = f'OnMeeting-{self.conference_info}'

            recognized = True
            # cmd_input = input(f'({status}) Please enter a operation (enter "?" to help): ').strip().lower()
            cmd_input = await async_input(f'({status}) Please enter an operation (enter "?" to help): ')
            cmd_input = cmd_input.strip().lower()

            fields = cmd_input.split(maxsplit=1)
            if len(fields) == 1:
                if cmd_input in ('?', '？', 'help'):
                    print(HELP)
                elif cmd_input == 'create':
                    await self.create_conference()  # Directly await the asynchronous method
                elif cmd_input == 'quit':
                    await self.quit_conference()
                elif cmd_input == 'cancel':
                    await self.cancel_conference()
                elif cmd_input == 'list':
                    await self.list_conferences()
                else:
                    print(f'[Warn]: Unrecognized cmd_input {cmd_input}')
            elif len(fields) == 2 and fields[0] == 'join':
                input_conf_id = fields[1]
                if input_conf_id.isdigit():
                    await self.join_conference(input_conf_id)  # Directly await the asynchronous method
                else:
                    print('[Warn]: Input conference ID must be in digital form')
            elif len(fields) == 2 and fields[0] == 'send':
                if self.channel and self.channel.readyState == "open":
                    self.channel.send(fields[1])
                else:
                    print("data channel has been closed")
            elif len(fields) == 2 and fields[0] == 'switch':
                # print(f"voice: {voice},play: {play},screen:{screen},camare:{camare}")
                global screen, camare, voice, play
                if(fields[1] == 'voice'):
                    voice = not voice
                elif(fields[1] == 'screen'):
                    screen = not screen
                elif(fields[1] == 'camare'):
                    camare = not camare
                    print(f"camare: {camare}")
                elif(fields[1] == 'play'):
                    play = not play
                else:
                    print(f'[Warn]: Unrecognized cmd_input {cmd_input}')
            else:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')
        


    async def connect(self, ip, port):
        """
        与会议服务器建立连接、发送 SDP提议、以及接收 SDP 答复
        """
        reader, writer = await asyncio.open_connection(ip, port)

        writer.write(self.username.encode())
        await writer.drain()

        # 创建 SDP Offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        # 发送 SDP Offer
        writer.write(self.pc.localDescription.sdp.encode())
        await writer.drain()

        # 从服务器接收 SDP Answer 数据并解码
        data = await reader.read(16384)
        answer_sdp = data.decode()
        # 将服务器的 SDP Answer 设置为客户端的远程描述。
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await self.pc.setRemoteDescription(answer)

        # 保存 reader 和 writer 用于信令通信
        self.reader = reader
        self.writer = writer

        # 启动监听服务器信令的任务
        asyncio.create_task(self.listen_signaling())

    async def listen_signaling(self):
        """
        监听服务器发送的 SDP Offer，并完成重新协商流程
        """
        while True:
            try:
                # 监听服务器发送的 SDP Offer
                data = await self.reader.read(16384)
                if not data:
                    break

                offer_sdp = data.decode()
                offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
                await self.pc.setRemoteDescription(offer)

                # 生成 SDP Answer 并发送回服务器
                answer = await self.pc.createAnswer()
                await self.pc.setLocalDescription(answer)
                self.writer.write(self.pc.localDescription.sdp.encode())
                await self.writer.drain()

                print("[INFO] SDP renegotiation completed.")
            except Exception as e:
                print(f"[ERROR] Error during signaling: {e}")
                break


class VideoStreamTrack(VideoStreamTrack):
    """
    自定义视频track
    """
    kind = "video"
    def __init__(self):
        super().__init__()
        self.frame_count = 0

    async def recv(self):
        """捕获图像数据并生成图像帧"""
        try:
            await asyncio.sleep(0.1)
            self.frame_count += 1

            # video_frame = capture_video_frame()

            global screen,camare,voice,play  # 明确声明这是全局变量

            # print(f"camare:{camare}")
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

            video_frame.pts = self.frame_count
            video_frame.time_base = fractions.Fraction(1, 30)
            return video_frame
        except Exception as e:
            print(f"[Error] Video capture error: {e}")



class MicrophoneStreamTrack(AudioStreamTrack):
    """
    自定义音频track
    """
    kind = "audio"
    def __init__(self):
        super().__init__()
        self.frame_count = 0  
    
    async def recv(self):
        """捕获音频数据并生成音频帧"""
        try:
            await asyncio.sleep(0.01)
            self.frame_count += 1
            if voice:
                data = streamin.read(CHUNK, exception_on_overflow=False)
            else:
                data = b'\x00' * CHUNK * CHANNELS * 2\

            # 将 PCM 数据封装为 AudioFrame
            audio_frame = data_to_audio_frame(data, sample_rate=RATE, channels=CHANNELS)

            audio_frame.pts = self.frame_count
            audio_frame.sample_rate = RATE
            audio_frame.time_base = fractions.Fraction(1, RATE)

            # pcm_data = audio_frame_to_data(audio_frame)
            # streamout.write(pcm_data)
            # print(f"[INFO] Sending audio frame {self.frame_count}.")

            return audio_frame
        except Exception as e:
            print(f"[Error] Audio capture error: {e}")


# if __name__ == '__main__':
#     client1 = ConferenceClient()
#     client1.server_addr = (SERVER_IP, MAIN_SERVER_PORT)
#     asyncio.run(client1.start())  # Start the event loop with asyncio.run()

class ConferenceClientGUI:
    def __init__(self, root, client, loop):
        self.root = root
        self.client = client
        self.loop = loop
        self.root.title("Conference Client")
        self.client.gui = self  # 将GUI对象传递给ConferenceClient
        self.create_widgets()

    def create_widgets(self):
        self.username_label = tk.Label(self.root, text="Username:")
        self.username_label.grid(row=0, column=0, padx=10, pady=10)
        self.username_entry = tk.Entry(self.root)
        self.username_entry.grid(row=0, column=1, padx=10, pady=10)

        self.conference_id_label = tk.Label(self.root, text="Conference ID:")
        self.conference_id_label.grid(row=1, column=0, padx=10, pady=10)
        self.conference_id_entry = tk.Entry(self.root)
        self.conference_id_entry.grid(row=1, column=1, padx=10, pady=10)

        self.create_button = tk.Button(self.root, text="Create Conference", command=self.create_conference_wrapper)
        self.create_button.grid(row=2, column=0, padx=10, pady=10)

        self.join_button = tk.Button(self.root, text="Join Conference", command=self.join_conference_wrapper)
        self.join_button.grid(row=2, column=1, padx=10, pady=10)

        self.quit_button = tk.Button(self.root, text="Quit Conference", command=self.quit_conference_wrapper)
        self.quit_button.grid(row=3, column=0, padx=10, pady=10)

        self.cancel_button = tk.Button(self.root, text="Cancel Conference", command=self.cancel_conference_wrapper)
        self.cancel_button.grid(row=3, column=1, padx=10, pady=10)

        self.list_button = tk.Button(self.root, text="List Conferences", command=self.list_conferences_wrapper)
        self.list_button.grid(row=4, column=0, padx=10, pady=10)

        self.switch_audio_button = tk.Button(self.root, text="Switch Audio", command=lambda: self.switch_data('voice'))
        self.switch_audio_button.grid(row=4,  column=1, padx=10, pady=10)

        self.switch_screen_button = tk.Button(self.root, text="Switch Screen", command=lambda: self.switch_data('screen'))
        self.switch_screen_button.grid(row=5, column=0, padx=10, pady=10)

        self.switch_camera_button = tk.Button(self.root, text="Switch Camera", command=lambda: self.switch_data('camare'))
        self.switch_camera_button.grid(row=5, column=1, padx=10, pady=10)


        # 新增消息发送功能
        self.message_label = tk.Label(self.root, text="Message to send:")
        self.message_label.grid(row=6, column=0, padx=10, pady=10)

        self.message_entry = tk.Entry(self.root)
        self.message_entry.grid(row=6, column=1, padx=10, pady=10)

        self.send_button = tk.Button(self.root, text="Send Message", command=self.send_message_wrapper)
        self.send_button.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

        self.response_label = tk.Label(self.root, text="Server Response:")
        self.response_label.grid(row=8, column=0, padx=10, pady=10)

        self.response_text = tk.Text(self.root, height=10, width=50)
        self.response_text.grid(row=8, column=1, padx=10, pady=10)




    async def send_message(self):
        message = self.message_entry.get().strip()
        if not message:
            messagebox.showerror("Error", "Message cannot be empty.")
            return

        # 发送消息到服务器，并获取响应
        # await self.client.send_message(message)
        if self.client.channel and self.client.channel.readyState == "open":
            self.client.channel.send(message)
        else:
            print("data channel has been closed")

    def send_message_wrapper(self):
        # 将异步任务包装成同步任务执行
        asyncio.run_coroutine_threadsafe(self.send_message(), self.loop)

    def display_received_message(self, message):
        self.response_text.insert(tk.END, message + "\n")




    async def create_conference(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showerror("Error", "Username cannot be empty.")
            return
        self.client.username = username
        await self.client.create_conference()

    async def join_conference(self):
        username = self.username_entry.get().strip()
        conference_id = self.conference_id_entry.get().strip()
        if not username or not conference_id:
            messagebox.showerror("Error", "Username and Conference ID cannot be empty.")
            return
        self.client.username = username
        await self.client.join_conference(conference_id)

    async def quit_conference(self):
        await self.client.quit_conference()

    async def cancel_conference(self):
        await self.client.cancel_conference()

    async def list_conferences(self):
        await self.client.list_conferences()

    def switch_data(self, data_type):
        global screen, camare, voice, play
        if(data_type == 'voice'):
            voice = not voice
        elif(data_type == 'screen'):
            screen = not screen
        elif(data_type == 'camare'):
            camare = not camare
            print(f"camare: {camare}")

        

    def create_conference_wrapper(self):
        asyncio.run_coroutine_threadsafe(self.create_conference(), self.loop)

    def join_conference_wrapper(self):
        asyncio.run_coroutine_threadsafe(self.join_conference(), self.loop)

    def quit_conference_wrapper(self):
        asyncio.run_coroutine_threadsafe(self.quit_conference(), self.loop)

    def cancel_conference_wrapper(self):
        asyncio.run_coroutine_threadsafe(self.cancel_conference(), self.loop)

    def list_conferences_wrapper(self):
        asyncio.run_coroutine_threadsafe(self.list_conferences(), self.loop)


def main():
    loop = asyncio.get_event_loop()
    client = ConferenceClient()
    client.server_addr = (config.SERVER_IP, config.MAIN_SERVER_PORT)
    root = tk.Tk()
    gui = ConferenceClientGUI(root, client, loop)

    def run_asyncio():
        try:
            loop.call_soon(loop.stop)
            loop.run_forever()
        except Exception as e:
            print(f"Error in asyncio loop: {e}")
        finally:
            root.after(1, run_asyncio)

    root.after(1, run_asyncio)
    root.mainloop()
    loop.close()

if __name__ == '__main__':
    main()