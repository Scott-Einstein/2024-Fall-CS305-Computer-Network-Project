from util import *


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


    def set_username(self):
            self.username = input("Please enter your username: ").strip()

    async def create_conference(self):
        """
        create a conference: send create-conference request to server and obtain necessary data to
        """
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

    async def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data
        """
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
        # port = 8080
        # self.start_conference(port)
        writer.close()
        await writer.wait_closed()


    async def quit_conference(self):
        """
        quit your on-going conference
        """
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
        else:
            print("You are not in any conference.")

    async def cancel_conference(self,conference_id):
        """
        cancel your on-going conference (when you are the conference manager): ask server to close all clients
        """
        reader, writer = await asyncio.open_connection(*self.server_addr)
            # Send cancel request with conference_id and username
        cancel_cmd = f"cancel {conference_id} {self.username}"
        writer.write(cancel_cmd.encode())
        await writer.drain()
        data = await reader.read(100)
        response = data.decode()
        print(f"Received: {response}")
        if "success" in response:
            self.on_meeting = False
            self.conference_info = None
        writer.close()
        await writer.wait_closed()

    async def list_conferences(self):
        reader, writer = await asyncio.open_connection(*self.server_addr)
        writer.write(b"list")
        await writer.drain()
        data = await reader.read(100)
        response = data.decode()
        print(f"Available conferences: {response}")
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

    async def start_conference(self,port):
        '''
        init conns when create or join a conference with necessary conference_info
        and
        start necessary running task for conference
        '''

        # 当服务器创建了数据通道时，开始监听从服务器创建的数据通道
        @self.pc.on('datachannel')
        def on_datachannel(channel):
            print(f"DataChannel created by server: {channel.label}")

            @channel.on("message")
            def on_message(message):
                print(f"Message from server: {message}")

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
                asyncio.create_task(self.handle_video_track(track))
            elif track.kind == "audio":
                asyncio.create_task(play_audio())
                asyncio.create_task(self.handle_audio_track(track))

        # 创建WebRTC数据通道,监听open和message实践
        self.channel = self.pc.createDataChannel("chat")
        self.channel.on("open", lambda: print("[INFO] Text DataChannel open"))
        self.channel.on("message", lambda message: print(f"Received message: {message}"))

        # 创建音视频轨道
        video_track = VideoStreamTrack()
        self.pc.addTrack(video_track)
        print("[INFO] Video DataChannel open")
        audio_track = MicrophoneStreamTrack()
        self.pc.addTrack(audio_track)
        print("[INFO] Audio DataChannel open")

        # 与服务器连接并处理消息
        await self.connect()
        # 等待断开
        await self.pc.close()

    def close_conference(self):
        '''
        close all conns to servers or other clients and cancel the running tasks
        pay attention to the exception handling
        '''
    async def handle_video_track(self, track):
        """处理远程视频轨道"""
        while True:
            try:
                frame = await track.recv() 
                play_video(frame)
            except Exception as e:
                print(f"[ERROR] Video track handling failed: {e}")
                break

    async def handle_audio_track(self, track):
        """处理远程音频轨道"""
        while True:
            try:
                frame = await track.recv()
                play_buffer.append(frame)
            except Exception as e:
                print(f"[ERROR] Audio track handling failed: {e}")
                break

    async def start(self):
        """
        execute functions based on the command line input
        """
        self.set_username()
        while True:
            if not self.on_meeting:
                status = 'Free'
            else:
                status = f'OnMeeting-{self.conference_info}'

            recognized = True
            cmd_input = input(f'({status}) Please enter a operation (enter "?" to help): ').strip().lower()
            fields = cmd_input.split(maxsplit=1)
            if len(fields) == 1:
                if cmd_input in ('?', '？'):
                    print(HELP)
                elif cmd_input == 'create':
                    await self.create_conference()  # Directly await the asynchronous method
                elif cmd_input == 'quit':
                    await self.quit_conference()
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
            elif len(fields) == 2 and fields[0] == 'cancel':
                input_conf_id = fields[1]
                if input_conf_id.isdigit():
                    await self.cancel_conference(input_conf_id)
            else:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')
        


    async def connect(self):
        """
        与服务器建立连接、发送 SDP提议、以及接收 SDP 答复
        """

        # 创建 SDP Offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        # 发送 SDP Offer
        reader, writer = await asyncio.open_connection(SERVER_IP, MAIN_SERVER_PORT)
        writer.write(self.pc.localDescription.sdp.encode())
        await writer.drain()

        # 从服务器接收 SDP Answer 数据并解码
        data = await reader.read(16384)
        answer_sdp = data.decode()
        # 将服务器的 SDP Answer 设置为客户端的远程描述。
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await self.pc.setRemoteDescription(answer)

        print(f"[INFO] Sent offer to server and received answer.")
    

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
            self.frame_count += 1
            video_frame = capture_video_frame()
            print(f"[INFO] Sending video frame {self.frame_count}.")
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
            self.frame_count += 1
            audio_frame = capture_voice_frame()
            print(f"[INFO] Sending audio frame {self.frame_count}.")
            return audio_frame
        except Exception as e:
            print(f"[Error] Audio capture error: {e}")


if __name__ == '__main__':
    client1 = ConferenceClient()
    client1.server_addr = (SERVER_IP, MAIN_SERVER_PORT)
    asyncio.run(client1.start())  # Start the event loop with asyncio.run()
