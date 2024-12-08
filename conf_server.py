import asyncio
from util import *


class ConferenceServer:
    def __init__(self, ):
        # async server
        self.conference_id = None  # conference_id for distinguish difference conference
        self.conf_serve_ports = None
        self.data_serve_ports = {}
        self.data_types = ['screen', 'camera', 'audio']  # example data types in a video conference
        self.clients_info = None
        self.client_conns = None
        self.mode = 'Client-Server'  # or 'P2P' if you want to support peer-to-peer conference mode
        # self.relay = MediaRelay() # 用于复用track向多个用户发送数据
        self.pcs = set() # 用于存储所有pc链接
    async def handle_data(self, reader, writer, data_type):
        """
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """

    async def handle_client(self, reader, writer):
        """
        running task: handle the in-meeting requests or messages from clients
        """

    async def log(self):
        while self.running:
            print('Something about server status')
            await asyncio.sleep(LOG_INTERVAL)

    async def cancel_conference(self):
        """
        handle cancel conference request: disconnect all connections to cancel the conference
        """

    def start(self):
        '''
        start the ConferenceServer and necessary running tasks to handle clients in this conference
        '''



class MainServer:
    def __init__(self, server_ip, main_port):
        # async server
        self.server_ip = server_ip
        self.server_port = main_port
        self.main_server = None

        self.conference_conns = None
        self.conference_servers = {}  # self.conference_servers[conference_id] = ConferenceManager
        self.client_conferences = {}
        self.conference_initiators = {}
        self.next_conference_id = 1

    async def handle_creat_conference(self, reader, writer,cmd):
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
            response = json.dumps({"status": "success", "message": f"Joined conference {conference_id}."})
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
                # If the initiator quits, cancel the conference
                await self.conference_servers[conference_id].cancel_conference()
                del self.conference_servers[conference_id]
                del self.conference_initiators[conference_id]
                response = json.dumps({"status": "success", "message": f"Conference {conference_id} ended by initiator."})
            else:
                if username in self.conference_servers[conference_id].clients_info:
                    del self.conference_servers[conference_id].clients_info[username]  # Remove username from clients_info
                    response = json.dumps({"status": "success", "message": f"Quit conference {conference_id}."})
                else:
                    response = json.dumps({"status": "error", "message": f"Username {username} not found in conference {conference_id}."})
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
            await self.handle_creat_conference(reader, writer,cmd)
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
    # server = MainServer(SERVER_IP, MAIN_SERVER_PORT)
    # asyncio.run(server.start())
    # 测试会议服务器
    server = ConferenceServer()
    asyncio.run(server.start())
    
