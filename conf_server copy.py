import asyncio
from util import *
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling
from aiortc.contrib.signaling import BYE, TcpSocketSignaling
from datetime import datetime, timedelta
from aiortc import VideoStreamTrack
from aiortc.mediastreams import VideoFrame
from aiortc import AudioStreamTrack
from aiortc.mediastreams import AudioFrame

class ConferenceServer:
    def __init__(self, ):
        # async server
        self.conference_id = None  # conference_id for distinguish difference conference
        self.conf_serve_ports = None
        self.data_serve_ports = {}
        self.data_types = ['screen', 'camera', 'audio']  # example data types in a video conference
        self.clients_info = None
        self.client_conns = {}
        self.mode = 'Client-Server'  # or 'P2P' if you want to support peer-to-peer conference mode


    async def handle_video(self, track, server_video_track):
        """
        接收来自客户端的共享流数据，并决定如何将它们转发给其余的客户端
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """
        frame_count = 0
        while True:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=5.0)   
                frame_count += 1
                await server_video_track.queue.put(frame)

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
                print(f"[INFO] Received audio frame {frame_count}")

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

        # 添加音频、视频轨道
        server_video_track = ProcessedVideoStreamTrack()
        pc.addTrack(server_video_track)
        
        server_audio_track = ProcessedAudioStreamTrack()  
        pc.addTrack(server_audio_track)

        # 存储连接信息
        self.client_conns[addr] = channel
        
        # 监听音视频轨道
        @pc.on("track")
        def on_track(track):
            if isinstance(track, MediaStreamTrack):
                print(f"Receiving {track.kind} track")
                if(track.kind == "video"):
                    print("received video data")
                    asyncio.ensure_future(self.handle_video(track,server_video_track))
                elif(track.kind == "audio"):
                    print("[INFO] Received audio track from client.")
                    asyncio.ensure_future(self.handle_audio(track,server_audio_track))

        # 监听文本数据通道
        @pc.on('datachannel')
        def on_datachannel(channel):
            print(f"DataChannel created: {channel.label}")

            # Listen for messages from the data channel
            @channel.on("message")
            def on_message(message):
                print(f"Message from {channel.label}: {message}")
                # 向所有连接的客户端广播消息
                for other_addr, other_channel in self.client_conns.items():
                    try:
                        other_channel.send(message)
                        print(f"Broadcasting message to {other_addr}: {message}")
                    except Exception as e:
                        print(f"Error sending message to {other_addr}: {e}")

        # 处理连接状态变化    
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"Connection state is {pc.connectionState}")
            if pc.connectionState == "connected":
                print("WebRTC connection established successfully")


        # 处理客户端的 SDP Offer
        offer_sdp = await reader.read(16384)  # Read the offer (assuming it's small)
        offer = RTCSessionDescription(sdp=offer_sdp.decode(), type='offer')
        
        # 设置远端 SDP 描述
        await pc.setRemoteDescription(offer)

        # 创建本地 SDP Answer 并发送给客户端
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        writer.write(pc.localDescription.sdp.encode())
        await writer.drain()
        print(f"Sent SDP answer to {addr}")




    async def log(self):
        while self.running:
            print('Something about server status')
            await asyncio.sleep(LOG_INTERVAL)

    async def cancel_conference(self):
        """
        handle cancel conference request: disconnect all connections to cancel the conference
        """


    async def handle_offer(self, pc, offer):
        """处理客户端的 SDP Offer"""
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        return pc.localDescription

    async def broadcast_message(self, sender, message):
        """广播 DataChannel 消息到所有客户端"""
        for pc in self.peer_connections:
            # if pc != sender:
                for channel in pc.getTransceivers():
                    if channel.sender and channel.sender.track.kind == "application":
                        channel.sender.send(message)

    async def broadcast_track(self, sender, track):
        """广播视频或音频轨道到所有客户端"""
        for pc in self.peer_connections:
            pc.addTrack(track)
            # if pc != sender:
            #     pc.addTrack(track)


    def start(self):
        '''
        启动会议服务器，处理客户端连接
        Start the ConferenceServer and necessary running tasks to handle clients in this conference
        '''
        loop = asyncio.get_event_loop()
        # Start server on a specific host and port for the conference
        server = loop.run_until_complete(
            asyncio.start_server(self.handle_client, SERVER_IP, MAIN_SERVER_PORT)
        )
        print("Server started, awaiting client connections...")
        # loop.create_task(self.log())  # Start logging task
        loop.run_until_complete(server.serve_forever())


    

class ProcessedVideoStreamTrack(VideoStreamTrack):
    """
    自定义视频轨道，用于服务器向客户端发送处理后的视频帧。
    """
    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()

    async def recv(self):
        # 从队列中获取帧
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
            frame = await self.queue.get()
            print(f"Sending audio frame from queue: {frame}")
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

        self.conference_conns = None
        self.conference_servers = {}  # self.conference_servers[conference_id] = ConferenceManager

    def handle_creat_conference(self,):
        """
        create conference: create and start the corresponding ConferenceServer, and reply necessary info to client
        """

    def handle_join_conference(self, conference_id):
        """
        join conference: search corresponding conference_info and ConferenceServer, and reply necessary info to client
        """

    def handle_quit_conference(self):
        """
        quit conference (in-meeting request & or no need to request)
        """
        pass

    def handle_cancel_conference(self):
        """
        cancel conference (in-meeting request, a ConferenceServer should be closed by the MainServer)
        """
        pass

    async def request_handler(self, reader, writer):
        """
        running task: handle out-meeting (or also in-meeting) requests from clients
        """
        pass

    def start(self):
        """
        start MainServer
        """
        pass


if __name__ == '__main__':
    # server = MainServer(SERVER_IP, MAIN_SERVER_PORT)
    # server.start()

    server = ConferenceServer()
    asyncio.run(server.start())
    
