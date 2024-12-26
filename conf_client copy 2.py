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
        
        self.conference_info = None  # you may need to save and update some conference_info regularly

        self.server_pc = None #WebRTC连接
        self.username=None
        self.pcs = {}

        self.received_audio_tracks = {}
        self.received_video_tracks = {}
        self.user_tasks = {}  # 记录每个用户的音视频任务
        self.audio_track = None
        self.video_track = None
        self.window_names = {}  # 用于保存每个视频的窗口名称
        self.reader = None
        self.writer = None
        self.audio_relay = MediaRelay()
        self.video_relay = MediaRelay()
        self.peers = {}
        self.server_on = False


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
                server_ip = SERVER_IP
                server_port = response_data["port"]
                await self.start_conference(server_ip, server_port)

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
                if self.server_pc:
                    print("[INFO] Closing RTCPeerConnection.")
                    await self.server_pc.close()  # 关闭RTCPeerConnection
                for pc in self.pcs:
                    if pc:
                        await self.pc.close()
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

    async def start_conference(self, server_ip, server_port):
        '''
        init conns when create or join a conference with necessary conference_info
        and
        start necessary running task for conference
        '''
        if not self.server_on:
            asyncio.create_task(self.listen_for_clients(host="0.0.0.0", port=CLIENT_PORT))
        
        self.server_pc = RTCPeerConnection()

         # 创建WebRTC数据通道,监听open和message实践
        self.channel = self.server_pc.createDataChannel("chat")
        self.channel.on("open")
        self.channel.on("message", lambda message: print(f"Received message: {message}"))

        # 创建音视频轨道
        self.video_track = VideoStreamTrack()
        print("[INFO] Video DataChannel open")

        self.audio_track = MicrophoneStreamTrack()
        print("[INFO] Audio DataChannel open")
        
        # 与服务器连接并处理消息
        await self.connect(server_ip, server_port)
        
        
        # 当服务器创建了数据通道时，开始监听从服务器创建的数据通道
        @self.server_pc.on('datachannel')
        def on_datachannel(channel):
            print(f"DataChannel created by server: {channel.label}")
            @channel.on("message")
            async def on_message(message):
                if(message == 'quit'):
                    await self.quit_conference()
                else:
                    await self.handle_datachannel_message(message)

        # 监听ICE连接状态变化
        @self.server_pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            if self.server_pc.iceConnectionState == "failed":
                await self.server_pc.close()

    async def connect_client(self, username, addr):
        """
        与新用户建立RTC连接并发送音视频轨道。
        :param username: 新用户的用户名
        :param addr: 新用户的地址 (IP:PORT)
        """
        # try:
        if isinstance(addr, list):
            ip, port = addr
            addr = f"{ip}:{port}"
        username = ip
        self.peers[username] = addr  
        print(username)
        print(addr)
        print(f"[INFO] Connecting to new client: {username} at {addr}")
        ip, port = addr.split(":")
        port = CLIENT_PORT
        # 创建新的 RTCPeerConnection
        pc = RTCPeerConnection()

        # 添加音视频轨道
        pc.addTrack(self.audio_relay.subscribe(self.audio_track))  # 发送音频轨道
        pc.addTrack(self.video_relay.subscribe(self.video_track))  # 发送视频轨道

        # 保存 PeerConnection 实例
        self.pcs[username] = pc

        # 创建 DataChannel
        data_channel = pc.createDataChannel("chat")
        data_channel.on("open", lambda: print(f"[INFO] DataChannel open with {username}"))
        data_channel.on("message", lambda message: print(f"[INFO] Message from {username}: {message}"))

        # 处理远程音视频轨道
        @self.pc.on("track")
        def on_track(track):
            print(f"Received remote track: {track.kind}")
            if track.kind == "video":
                print(f"received video data from {username}")
                self.received_video_tracks[username] = track
                task = asyncio.create_task(self.handle_video_track(username, track))
                self.user_tasks[username] = self.user_tasks.get(username, []) + [task]
            elif track.kind == "audio":
                print(f"received audio data from {username}")
                self.received_audio_track[username] = track
                task = asyncio.create_task(self.handle_audio_track(username,track))
                self.user_tasks[username] = self.user_tasks.get(username, []) + [task]

        # 与服务器连接并处理消息
        await self.connect(ip, port)

        # except Exception as e:
        #     print(f"[ERROR] Failed to connect to {username} at {addr}: {e}")
    
    async def disconnect_user(self, username):
        if username in self.user_tasks:
            for task in self.user_tasks[username]:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    print(f"[INFO] Task for {username} cancelled.")
            del self.user_tasks[username]

        # 关闭 RTC 连接
        if username in self.pcs:
            pc = self.pcs.pop(username)
            await pc.close()
            print(f"[INFO] RTC connection with {username} closed.")

        # 删除音视频轨道
        if username in self.received_audio_tracks:
            del self.received_audio_tracks[username]
            print(f"[INFO] Removed audio track for {username}.")
        if username in self.received_video_tracks:
            del self.received_video_tracks[username]
            print(f"[INFO] Removed video track for {username}.")

        # 删除窗口名称
        if username in self.window_names:
            del self.window_names[username]
            print(f"[INFO] Removed window name for {username}.")

        # 删除用户地址信息
        if username in self.peers:
            del self.peers[username]
            print(f"[INFO] Removed peer info for {username}.")

        print(f"[INFO] User {username} fully disconnected.")
        
    async def handle_datachannel_message(self, message):
        """
        Handle incoming messages from the DataChannel.
        Distinguish between user messages, new user join, and user disconnect messages.
        """
        try:
            # 尝试解析为 JSON 数据
            data = json.loads(message)
            action = data.get("action")

            if action == "new_client":
                # 处理新用户加入信息
                username = data.get("username", "Unknown")
                addr = data.get("addr", "Unknown")
                print(f"[INFO] New user joined: {username} at {addr}")
                await self.connect_client(username,addr)
                self.gui.display_received_message(f"New user joined: {username} at {addr}")
            
            elif action == "client_disconnected":
                # 处理用户断开连接信息
                username = data.get("username", "Unknown")
                print(f"[INFO] User disconnected: {username}")
                await self.disconnect_user(username)
                self.gui.display_received_message(f"User disconnected: {username}")

            elif action == "user_message":
                # 处理用户发送的普通消息
                sender = data.get("username", "Unknown")
                content = data.get("message", "No message")
                print(f"[INFO] Message from {sender}: {content}")
                self.gui.display_received_message(f"Message from {sender}: {content}")

            else:
                print(f"[WARN] Unknown action received: {action}")

        except json.JSONDecodeError:
            # 如果不是 JSON 数据，则处理为普通文本消息
            print(f"[INFO] Received raw message: {message}")
            self.gui.display_received_message(message)

    async def handle_video_track(self, username, track):
        """
        处理远程视频轨道，接收视频帧并显示。
        """
        try:
            while True:
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
                print(f"[INFO] Processing video frame from {username}")
        except asyncio.CancelledError:
            print(f"[INFO] Video track task for {username} cancelled.")
        except Exception as e:
            print(f"[ERROR] Video track handling failed for {username}: {e}")

    async def handle_audio_track(self, username, track):
        """
        处理远程音频轨道。
        """
        try:
            while True:
                frame = await track.recv()
                pcm_data = audio_frame_to_data(frame)
                streamout.write(pcm_data)
                print(f"[INFO] Processing audio frame from {username}")
        except asyncio.CancelledError:
            print(f"[INFO] Audio track task for {username} cancelled.")
        except Exception as e:
            print(f"[ERROR] Audio track handling failed for {username}: {e}")

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

        # writer.write(self.username.encode())
        # await writer.drain()

        # 创建 SDP Offer
        offer = await self.server_pc.createOffer()
        await self.server_pc.setLocalDescription(offer)

        # 发送 SDP Offer
        writer.write(self.server_pc.localDescription.sdp.encode())
        await writer.drain()

        # 从服务器接收 SDP Answer 数据并解码
        data = await reader.read(16384)
        answer_sdp = data.decode()
        # 将服务器的 SDP Answer 设置为客户端的远程描述。
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await self.server_pc.setRemoteDescription(answer)
        print("link to conference server success.")

    async def listen_for_clients(self, host="0.0.0.0", port=CLIENT_PORT):
        """
        监听其他客户端的连接请求。
        :param host: 监听的主机地址
        :param port: 监听的端口号
        """
        print(f"[INFO] Listening for incoming client connections on {host}:{port}...")
        async def disconnect_user(self, client_id):
            """
            清理与断开客户端的资源。
            """
            print(f"[INFO] Disconnecting user: {client_id}")
            
            # 关闭 PeerConnection
            if client_id in self.pcs:
                pc = self.pcs.pop(client_id)
                await pc.close()
                print(f"[INFO] RTC connection with {client_id} closed.")

            # 删除其他相关资源
            if client_id in self.received_audio_tracks:
                del self.received_audio_tracks[client_id]
                print(f"[INFO] Removed audio track for {client_id}.")
            if client_id in self.received_video_tracks:
                del self.received_video_tracks[client_id]
                print(f"[INFO] Removed video track for {client_id}.")

            if client_id in self.window_names:
                del self.window_names[client_id]
                print(f"[INFO] Removed window name for {client_id}.")

        async def handle_user(reader, writer):
            """
            Handle the in-meeting requests or messages from clients
            """
            addr = writer.get_extra_info("peername")
            # 处理客户端的 SDP Offer
            offer_sdp = await reader.read(16384)  # Read the offer (assuming it's small)
            offer = RTCSessionDescription(sdp=offer_sdp.decode(), type='offer')
            
            # 创建 RTCPeerConnection
            pc = RTCPeerConnection()
            self.pcs[addr] = pc
            # 添加音视频轨道
            pc.addTrack(self.audio_relay.subscribe(self.audio_track))
            pc.addTrack(self.video_relay.subscribe(self.video_track))
            
            username = addr
            @self.pc.on("track")
            def on_track(track):
                print(f"Received remote track: {track.kind}")
                if track.kind == "video":
                    print(f"received video data from {username}")
                    self.received_video_tracks[username] = track
                    task = asyncio.create_task(self.handle_video_track(username, track))
                    self.user_tasks[username] = self.user_tasks.get(username, []) + [task]
                elif track.kind == "audio":
                    print(f"received audio data from {username}")
                    self.received_audio_track[username] = track
                    task = asyncio.create_task(self.handle_audio_track(username,track))
                    self.user_tasks[username] = self.user_tasks.get(username, []) + [task]
            
            # 监听连接状态变化
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                print(f"[INFO] Connection state with {username}: {pc.connectionState}")
                if pc.connectionState in {"closed", "disconnected", "failed"}:
                    print(f"[WARN] Connection with {username} is {pc.connectionState}. Cleaning up...")
                    await disconnect_user(username)
            
            # 设置远端 SDP 描述
            await pc.setRemoteDescription(offer)

            # 创建本地 SDP Answer 并发送给客户端
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            writer.write(pc.localDescription.sdp.encode())
            await writer.drain()
            
            print(f"Sent SDP answer to {addr}")

        # 启动服务器监听
        server = await asyncio.start_server(handle_user, host, port)
        print(f"[INFO] Server started on {host}:{port}")
        await server.serve_forever()



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