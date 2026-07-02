from __future__ import annotations

import json
import queue
import socket
import threading
import time
#通过UDP广播发现房间，通过TCP建立房间联系

from .config import DISCOVERY_PORT, GAME_PORT
def local_ip():
    try:
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        #表示使用IPV4的地址并使用UDP
        sock.connect(("8.8.8.8",80))
        #不会立即发数据
        ip=sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()
class LanSession:
    #管理双人局域网会话的类
    def __init__(self):
        self.is_host=False
        self.connected=False
        self.status="未连接"
        self.peer_name="对手"
        self.inbox = queue.Queue()
        #网络线程->inbox->主线程
        self.outbox = queue.Queue(maxsize=3)
        #主线程->outbox->网络线程
        self.stop_event = threading.Event()
        #会话停止信号，初始没有设置
        self.sock = None
        self.server = None
        #已经连接的socket和配置的server
        self.threads = []
    def close(self):
        #若停止事件还不存在，就设置这个停止事件
        if hasattr(self, "stop_event"):
            self.stop_event.set()
        for obj in (getattr(self,"sock",None)),getattr(self,"server",None):
            if obj:
                try:
                    obj.close()
                except OSError:
                    pass
        if hasattr(self,"connected"):
            self.connected=False
    def _thread(self,target,*args):
        #统一创建网络线程为守护线程
        #target：新线程要执行的函数
        #args：传递给函数的参数
        thread = threading.Thread(target=target,args=args,daemon=True)
        thread.start()
        self.threads.append(thread)
    def connect(self,address,name="玩家"):
        self.close()
        self.__init__()
        self.status =  f"正在连接 {address}..."
        self._thread(self._connect_worker, address, name, self.stop_event)
    def host(self,name="主机"):
        #关闭旧连接，启动UDP应答线程和TCP监听
        self.close()
        self.__init__()
        self.is_host=True
        self.status=f"房间已创建:{local_ip()}"
        token=self.stop_event
        self._thread(self._advertise,name,token)
        self._thread(self._accept,name,token)
    @staticmethod
    def discover(timeout=1.0):
        #广播一次发现请求，在timeout秒内尝试发现房间
        result=[]
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        sock.settimeout(0.15)
        #要发送的字节数据
        payload=json.dumps({"type":"discover"}).encode()
        try:
            sock.sendto(payload,("255.255.255.255",DISCOVERY_PORT))
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                try:
                    data,addr=sock.recvfrom(1024)
                    message=json.loads(data.decode())
                    if message.get("type")=="room" and addr[0] not in [x[0] for x in result]:
                        result.append((addr[0],message.get("name","房间"))) 
                except socket.timeout:
                    pass
        except OSError:
            pass
        finally:
            sock.close()
        return result
    def _advertise(self,name,token):
        #响应局域网客户端的discover请求
        udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        #复用本地端口
        udp.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            udp.bind(("",DISCOVERY_PORT))
            udp.settimeout(0.3)
            while not token.is_set() and not self.connected:
                try:
                    data,addr=udp.recvfrom(1024)
                    if json.loads(data.decode()).get("type") == "discover":
                        udp.sendto(json.dumps({"type":"room","name":name}).encode(),addr)
                except(socket.timeout,ValueError):
                    pass
        except OSError as exc:
            self.inbox.put({"type":"error","message":str(exc)})
        finally:
            udp.close()
    def _send_now(self,message):
        #把字典转化成JSON并发送
        #注意由于TCP是字节流，所以要加上换行作为消息边界
        if self.sock:
            self.sock.sendall((json.dumps(message,separators=(",", ":")) + "\n").encode())
    
    def send(self,message):
        #将message放进outbox里面，后续由网络线程发送
        if not self.connected:
            return
        try:
            self.outbox.put_nowait(message)
            #一旦满了，丢掉最旧的一个状态
        except queue.Full:
            try:
                self.outbox.get_nowait()
                self.outbox.put_nowait(message)
            except queue.Empty:
                pass
    def poll(self):
        #将所有input中的消息取出
        message=[]
        while True:
            try:
                msg=self.inbox.get_nowait()
                message.append(msg)
            except queue.Empty:
                return message
    def _io_loop(self,token):
        #IO循环，并拆解TCP的字节流信息
        buffer=b""
        try:
            while not token.is_set() and self.connected:
                try:
                    #不断把outbox的信息发送
                    while True:
                        self._send_now(self.outbox.get_nowait())
                except queue.Empty:
                    pass
                try:
                    #每次尝试get一个块
                    chunk=self.sock.recv(65536)
                    if not chunk:
                        raise ConnectionError("对方已经断开")
                    #把块拼到缓冲后面
                    buffer+=chunk
                    while b"\n" in buffer:
                        #有换行符就拆一个JSON出来
                        line, buffer = buffer.split(b"\n", 1)
                        msg = json.loads(line.decode())
                        if msg.get("type") =="hello":
                            self.peer_name=msg.get("name","对手")
                        self.inbox.put(msg)
                except socket.timeout:
                    pass       
        except (OSError, ValueError, ConnectionError) as exc:
            if not token.is_set():
                self.inbox.put({"type": "disconnect", "message": str(exc)})
        if token is self.stop_event:
            self.connected = False
            self.status = "连接已断开"

    def _activate(self,conn,name,token):
        #激活连接并且交换昵称，开io网络线程
        #是旧连接或者要求停止了就关闭
        if token.is_set() or token is not self.stop_event:
            conn.close()
            return
        self.sock=conn
        self.sock.settimeout(0.04)
        self.connected=True
        self.status="玩家已连接"
        self._send_now({"type":"hello","name":name})
        self._thread(self._io_loop,token)
    def _accept(self,name,token):
        #房主创建一个TCP服务器
        try:
            self.server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self.server.bind(("",GAME_PORT))
            #开始监听
            self.server.listen(1)
            self.server.settimeout(0.3)
            while not token.is_set():
                try:
                    conn,_=self.server.accept()
                    self._activate(conn,name,token)
                    return
                except socket.timeout:
                    pass
        except OSError as exc:
            if not token.is_set():
                self.status= f"创建失败：{exc}"
    def _connect_worker(self, address, name, token):
        """客户端连接任务。"""
        try:
            conn = socket.create_connection((address, GAME_PORT), timeout=5)
            if token.is_set():
                conn.close()
                return
            self._activate(conn, name, token)
        except OSError as exc:
            if not token.is_set():
                self.status = f"连接失败：{exc}"