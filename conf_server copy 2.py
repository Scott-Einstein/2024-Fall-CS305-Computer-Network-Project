import asyncio
import json
from config import *
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from aiortc.contrib.signaling import BYE, TcpSocketSignaling
from datetime import datetime, timedelta
from aiortc import VideoStreamTrack
from aiortc.mediastreams import VideoFrame
from aiortc import AudioStreamTrack
from aiortc.mediastreams import AudioFrame
import random
from aiortc.contrib.media import MediaRelay

class ConferenceServer:
    def __init__(self, ):
        # async server
        self.conference_id = None  # conference_id for distinguish difference conference
        self.conf_serve_ports = None
        self.data_types = ['screen', 'camera', 'audio']  # example data types in a video conference
        self.clients_info = None
        self.channels = dict()
        self.mode = 'Client-Server'  # or 'P2P' if you want to support peer-to-peer conference mode

        self.pcs = dict()
        self.addrs = dict()
        self.writers = dict()
        self.readers = dict()

    async def handle_video(self, track, broadcast_video_track):
        """
        接收来自客户端的共享流数据，并决定如何将它们转发给其余的客户端
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """
        frame_count = 0
        while True:
            try:
                await asyncio.sleep(0.05)
                frame = await asyncio.wait_for(track.recv(), timeout=5.0)
                frame_count += 1
                await broadcast_video_track.queue.put(frame)

            except asyncio.TimeoutError:
                print("Timeout waiting for frame, continuing...")
            except Exception as e:
                print(f"Error in handle_track: {str(e)}")
                break
        print("Exiting handle_track")
    

    async def handle_audio(self, track, server_audio_track):
        """
        接收来自客户端的共享音频流数据，并决定如何将它们转发给其余的客户端
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """
        frame_count = 0
        while True:
            try:
                # 从音频轨道中接收音频帧
                frame = await asyncio.wait_for(track.recv(), timeout=5.0)   
                frame_count += 1
                # 将接收到的音频帧放入服务器音频轨道的队列中以便进一步转发
                await server_audio_track.queue.put(frame)
                # print(f"[INFO] Received audio frame {frame_count} {frame}")

            except asyncio.TimeoutError:
                print("Timeout waiting for audio frame, continuing...")
            except Exception as e:
                print(f"Error in handle_audio: {str(e)}")
                break
        print("Exiting handle_audio")


    async def handle_client(self, reader, writer):
        """
        Handle the in-meeting requests or messages from clients
        """
        addr = writer.get_extra_info('peername')
        print(f"Received connection from {addr}")

        # 创建 RTCPeerConnection 对象（WebRTC连接）
        pc = RTCPeerConnection()

        # 创建文本传输通道
        channel = pc.createDataChannel("chat")
        username = addr
        
        # 存储连接信息
        self.channels[username] = channel
        self.pcs[username] = pc
        self.writers[username] = writer
        self.readers[username] = reader
        self.addrs[username] = addr

        # 处理客户端的 SDP Offer
        offer_sdp = await reader.read(16384)  
        offer = RTCSessionDescription(sdp=offer_sdp.decode(), type='offer')
        
        # 设置远端 SDP 描述
        await pc.setRemoteDescription(offer)

        # 创建本地 SDP Answer 并发送给客户端
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        writer.write(pc.localDescription.sdp.encode())
        await writer.drain()
        print(f"Sent SDP answer to {addr}")

        # 监听文本数据通道
        @pc.on('datachannel')
        def on_datachannel(channel):
            # print(f"DataChannel created: {channel.label}")

            # Listen for messages from the data channel
            @channel.on("message")
            def on_message(message):
                print(f"Message from {username}: {message}")

                # 获取当前时间
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 格式化时间为可读字符串

                # 创建包含发送人和时间戳的消息内容
                enhanced_message = {
                    "username": username,  # 发送人
                    "timestamp": timestamp,  # 时间戳
                    "message": message  # 原始消息
                }
                # 将消息转换为 JSON 格式
                enhanced_message_json = json.dumps(enhanced_message)

                
                # 向所有连接的客户端广播消息
                for other_username, other_channel in self.channels.items():
                    try:
                        # other_channel.send(message)
                        # 向其他客户端发送 JSON 字符串
                        other_channel.send(enhanced_message_json)
                        
                        print(f"Broadcasting message to {other_username}: {message}")
                    except Exception as e:
                        print(f"Error sending message to {other_username}: {e}")

        # 处理连接状态变化    
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            # print(f"Connection state is {pc.connectionState}")
            if pc.connectionState == "connected":
                print("WebRTC connection established successfully")
                new_client_info = json.dumps({"action": "new_client", "username": username, "addr": addr})
                for other_username, other_channel in self.client_conns.items():
                    if other_username != username:  # 不向自己广播
                        try:
                            other_channel.send(new_client_info)
                            print(f"[INFO] Notified {other_username} about new client: {username}")
                        except Exception as e:
                            print(f"[ERROR] Failed to notify {other_username} about {username}: {e}")
            elif pc.connectionState in {"closed", "failed", "disconnected"}:
                print(f"[WARN] Connection state changed for {username}: {pc.connectionState}")
                await self.cleanup_client(username)


    async def cleanup_client(self, username):
        """
        清理断开连接的客户端资源并广播断开信息。
        """
        if username in self.client_conns:
            # 广播断开消息
            disconnect_message = json.dumps({"action": "client_disconnected", "username": username})
            for other_username, other_channel in self.client_conns.items():
                if other_username != username:  # 不向断开的用户发送消息
                    try:
                        other_channel.send(disconnect_message)
                        print(f"[INFO] Notified {other_username} about {username} disconnection")
                    except Exception as e:
                        print(f"[ERROR] Failed to notify {other_username} about {username} disconnection: {e}")

            # 删除相关资源
            del self.client_conns[username]
        if username in self.addrs:
            del self.addrs[username]
        if username in self.pcs:
            pc = self.pcs.pop(username)
            await pc.close()

        print(f"[INFO] Cleaned up resources for {username}")

    async def log(self):
        while self.running:
            print('Something about server status')
            await asyncio.sleep(LOG_INTERVAL)


    async def cancel_conference(self):
        """
        handle cancel conference request: disconnect all connections to cancel the conference
        """
        # 向所有连接的客户端广播消息
        for other_username, other_channel in self.channels.items():
            try:
                # other_channel.send(message)
                # 向其他客户端发送 JSON 字符串
                other_channel.send("quit")
                print(f"Broadcasting message to {other_username}:quit")
            except Exception as e:
                print(f"Error sending message to {other_username}: {e}")
        

    async def start(self):
        '''
        启动会议服务器，处理客户端连接
        Start the ConferenceServer and necessary running tasks to handle clients in this conference
        '''
        # loop = asyncio.get_event_loop()
        
        # 启动服务器并等待客户端连接
        server = await asyncio.start_server(self.handle_client, SERVER_IP, self.conf_serve_ports)

        print(f"(Meeting {self.conference_id}) Server started, awaiting client connections...")

        # 直接等待服务器的生命周期，不需要再使用 run_until_complete
        await server.serve_forever()

    async def send_user_info(self, datachannel, user_info_dict):
        """
        通过DataChannel发送用户信息字典。
        :param datachannel: aiortc创建的DataChannel实例
        :param user_info_dict: 用户信息字典 (dict(username: addr))
        """
        try:
            # 将字典转换为JSON字符串
            user_info_json = json.dumps(user_info_dict)
            
            # 发送数据
            datachannel.send(user_info_json)
            print("[INFO] Sent user info via DataChannel:", user_info_json)
        except Exception as e:
            print(f"[ERROR] Failed to send user info: {e}")

class ProcessedVideoStreamTrack(VideoStreamTrack):
    """
    自定义视频轨道，用于服务器向客户端发送处理后的视频帧。
    """
    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.max_queue_size = 10

    async def recv(self):
        # 从队列中获取帧
        if self.queue.qsize() > self.max_queue_size:
            print(f"[WARNING] Video queue size exceeded {self.max_queue_size}. Clearing queue.")
            self.queue = asyncio.Queue() 
        frame = await self.queue.get()
        return frame
    

class ProcessedAudioStreamTrack(AudioStreamTrack):
    """
    自定义音频轨道，用于服务器向客户端发送处理后的音频流。
    """
    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()  # 创建一个队列用于存储音频帧

    async def recv(self):
        try:
            if(self.queue):
                frame = await self.queue.get()
            # print(f"Sending audio frame from queue: {frame}")
            return frame
        except Exception as e:
            print(f"[ERROR] Failed to process audio frame: {e}")
            return None

class MainServer:
    def __init__(self, server_ip, main_port):
        # async server
        self.server_ip = server_ip
        self.server_port = main_port
        self.main_server = None

        self.used_ports = set()  # 用于存储已使用的端口号

        self.conference_conns = None
        self.conference_servers = {}  # self.conference_servers[conference_id] = ConferenceManager
        self.client_conferences = {}  # {'user1': 1, 'user2': 2}
        self.conference_initiators = {}
        self.next_conference_id = 1


    def generate_unique_port(self):
        while True:
            port = random.randint(1024, 2000)  # 随机生成端口号，范围为1024到65535
            if port not in self.used_ports:  # 确保端口没有被使用过
                self.used_ports.add(port)
                return port

    async def handle_create_conference(self, reader, writer,cmd):

        """
        create conference: create and start the corresponding ConferenceServer, and reply necessary info to client
        """
        parts = cmd.split(" ")
        if len(parts) < 2:
            response = json.dumps({"status": "error", "message": "Missing username."})
            writer.write(response.encode())
            await writer.drain()
            return
        username = parts[1]
        conference_id = str(self.next_conference_id)
        self.next_conference_id += 1
        conference_server = ConferenceServer()
        conference_server.conference_id = conference_id
        conference_server.clients_info = {username: True}

        conference_server.conf_serve_ports = self.generate_unique_port()
        # 使用 asyncio.create_task 启动 conference_server.start()，避免阻塞当前事件循环
        asyncio.create_task(conference_server.start())


        self.conference_servers[conference_id] = conference_server
        self.conference_initiators[conference_id] = username
        response = json.dumps({"status": "success", "message": f"Conference {conference_id} created."})
        writer.write(response.encode())
        await writer.drain()

    async def handle_join_conference(self, reader, writer, cmd):
        """
        join conference: search corresponding conference_info and ConferenceServer, and reply necessary info to client
        """
        parts = cmd.split(" ")
        if len(parts) < 3:
            response = json.dumps({"status": "error", "message": "Missing conference ID or username."})
            writer.write(response.encode())
            await writer.drain()
            return
        conference_id = parts[1]
        username = parts[2]  # Extract the username


        print(f"Client {username} wants to join conference {conference_id}")
        if conference_id in self.conference_servers:
            self.conference_servers[conference_id].clients_info[username] = writer.get_extra_info('peername')
            response = json.dumps({"status": "success", "message": f"Joined conference {conference_id}.","port": f"{self.conference_servers[conference_id].conf_serve_ports}"})
            self.client_conferences[username] = conference_id
        else:
            response = json.dumps({"status": "error", "message": f"Conference {conference_id} does not exist."})
        writer.write(response.encode())
        await writer.drain()


    async def handle_quit_conference(self, reader, writer, cmd):
        """
        quit conference (in-meeting request & or no need to request)
        """
        parts = cmd.split(" ")
        if len(parts) < 2:
            response = json.dumps({"status": "error", "message": "Missing username."})
            writer.write(response.encode())
            await writer.drain()
            return
        username = parts[1]  # Extract the username
        print(f"Client {username} wants to quit conference")
        if username in self.client_conferences:
            conference_id = self.client_conferences.pop(username)  # Remove client from the current conference

            if username == self.conference_initiators.get(conference_id):
                # If the initiator quits, reassign a new initiator
                conference_server = self.conference_servers[conference_id]
                del conference_server.clients_info[username]
                del conference_server.client_conns[username]

                if conference_server.clients_info:
                    new_initiator = random.choice(list(conference_server.clients_info.keys()))
                    self.conference_initiators[conference_id] = new_initiator
                    response = json.dumps({"status": "success", "message": f"New initiator {new_initiator} assigned for conference {conference_id}."})
                else:
                    # If no clients left, cancel the conference
                    await self.conference_servers[conference_id].cancel_conference()
                    del self.conference_servers[conference_id]
                    del self.conference_initiators[conference_id]
                    response = json.dumps({"status": "success", "message": f"Conference {conference_id} ended as no members left."})
            else:
                if self.conference_servers.get(conference_id):

                    if username in self.conference_servers[conference_id].clients_info:
                        del self.conference_servers[conference_id].clients_info[username]  # Remove username from clients_info
                        response = json.dumps({"status": "success", "message": f"Quit conference {conference_id}."})

                        conference_server = self.conference_servers[conference_id]
                        del conference_server.client_conns[username]

                    else:
                        response = json.dumps({"status": "error","message": f"Username {username} not found in conference {conference_id}."})

                else:
                    response = json.dumps({"status": "success","message": f"conference {conference_id} is canceled."})
        else:
            response = json.dumps({"status": "error", "message": "You are not in any conference."})
        writer.write(response.encode())
        await writer.drain()


    async def handle_cancel_conference(self, reader, writer, cmd):
        parts = cmd.split(" ")
        if len(parts) < 2:
            response = json.dumps({"status": "error", "message": "Missing conference ID or username."})
            writer.write(response.encode())
            await writer.drain()
            return
        conference_id = parts[1]
        username = parts[2]
        if conference_id in self.conference_servers and username == self.conference_initiators.get(conference_id):

            
            await self.conference_servers[conference_id].cancel_conference()
            del self.conference_servers[conference_id]
            del self.conference_initiators[conference_id]

            # self.client_conferences = {key: value for key, value in self.client_conferences.items() if value != conference_id}

            print(self.conference_servers)
            print(self.conference_initiators)
            print(self.client_conferences)
            
            response = json.dumps({"status": "success", "message": f"Conference {conference_id} canceled by initiator."})
        else:
            response = json.dumps({"status": "error", "message": "You are not the initiator of this conference or conference not found."})
        writer.write(response.encode())
        await writer.drain()

    async def handle_list_conferences(self, reader, writer):
        conference_ids = list(self.conference_servers.keys())
        response = json.dumps({"status": "success", "conferences": conference_ids})
        writer.write(response.encode())
        await writer.drain()

    async def request_handler(self, reader, writer):
        """
        running task: handle out-meeting (or also in-meeting) requests from clients
        """
        data = await reader.read(100)
        cmd = data.decode().strip().lower()
        print(cmd)
        if cmd.startswith("create"):
            await self.handle_create_conference(reader, writer,cmd)
        elif cmd.startswith("join"):
            await self.handle_join_conference(reader, writer,cmd)
        elif cmd.startswith("quit"):
            await self.handle_quit_conference(reader, writer,cmd)
        elif cmd.startswith("cancel"):
            await self.handle_cancel_conference(reader, writer,cmd)
        elif cmd == "list":
            await self.handle_list_conferences(reader, writer)
        else:
            writer.write(b"Invalid command.")
            await writer.drain()

    async def start(self):
        """
        start MainServer
        """
        server = await asyncio.start_server(self.request_handler, self.server_ip, self.server_port)
        print(f"MainServer started on {self.server_ip}:{self.server_port}")
        try:
            await server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.close()
            await server.wait_closed()

if __name__ == '__main__':
    server = MainServer(SERVER_IP, MAIN_SERVER_PORT)
    asyncio.run(server.start())
    # 测试会议服务器
    # server = ConferenceServer()
    # asyncio.run(server.start())
    
