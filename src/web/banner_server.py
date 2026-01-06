import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
import json


class BannerServer:
    """横幅/公告服务器"""
    
    def __init__(self, host: str = "localhost", port: int = 8080, data_dir: str = "server_data"):
        """
        初始化服务器
        
        Args:
            host: 服务器主机地址
            port: 服务器端口
            data_dir: 数据目录
        """
        self.host = host
        self.port = port
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # 初始化数据文件
        self.banner_file = self.data_dir / "banners.json"
        self._init_data_files()
    
    def _init_data_files(self):
        """初始化数据文件"""
        # 初始化横幅数据
        if not self.banner_file.exists():
            default_banners = {
                "active_banners": [],
                "history_banners": []
            }
            with open(self.banner_file, 'w', encoding='utf-8') as f:
                json.dump(default_banners, f, ensure_ascii=False, indent=2)
    
    def start(self):
        """启动服务器"""
        if self.is_running:
            print("服务器已在运行中")
            return
        
        self.server = HTTPServer((self.host, self.port), BannerRequestHandler)
        # 设置处理器的数据目录
        self.server.data_dir = self.data_dir
        
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.is_running = True
        print(f"横幅服务器已在 http://{self.host}:{self.port} 启动")
    
    def _run_server(self):
        """运行服务器"""
        try:
            self.server.serve_forever()
        except Exception as e:
            print(f"服务器运行出错: {e}")
    
    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        if self.server_thread:
            self.server_thread.join(timeout=5)
        
        self.is_running = False
        print("横幅服务器已停止")
    
    def add_banner(self, title: str, content: str, priority: int = 1, expire_time: Optional[int] = None):
        """
        添加横幅
        
        Args:
            title: 标题
            content: 内容
            priority: 优先级
            expire_time: 过期时间戳（可选）
        """
        with open(self.banner_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        banner = {
            "id": int(time.time() * 1000),  # 使用时间戳作为ID
            "title": title,
            "content": content,
            "priority": priority,
            "created_at": int(time.time()),
            "expire_at": expire_time
        }
        
        data["active_banners"].append(banner)
        
        # 按优先级排序
        data["active_banners"].sort(key=lambda x: x["priority"], reverse=True)
        
        with open(self.banner_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_active_banners(self) -> list:
        """获取活动横幅"""
        with open(self.banner_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        current_time = int(time.time())
        active_banners = []
        
        for banner in data["active_banners"]:
            # 检查是否过期
            if banner.get("expire_at") and banner["expire_at"] < current_time:
                # 移动到历史横幅
                data["history_banners"].append(banner)
            else:
                active_banners.append(banner)
        
        # 更新文件
        data["active_banners"] = [b for b in data["active_banners"] 
                                  if not b.get("expire_at") or b["expire_at"] >= current_time]
        
        with open(self.banner_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return active_banners


class BannerRequestHandler(BaseHTTPRequestHandler):
    """横幅请求处理器"""
    
    def do_GET(self):
        """处理GET请求"""
        if self.path == '/api/banners' or self.path == '/banners':
            self._send_banners()
        elif self.path == '/api/status' or self.path == '/status':
            self._send_status()
        else:
            self._send_404()
    
    def _send_banners(self):
        """发送横幅数据"""
        try:
            data_file = Path(self.server.data_dir) / "banners.json"
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                active_banners = []
                current_time = int(time.time())
                
                # 过滤过期横幅
                for banner in data.get("active_banners", []):
                    if banner.get("expire_at") and banner["expire_at"] < current_time:
                        continue
                    active_banners.append(banner)
                
                response = {
                    "status": "success",
                    "data": active_banners,
                    "count": len(active_banners)
                }
            else:
                response = {
                    "status": "success", 
                    "data": [],
                    "count": 0
                }
            
            self._send_json_response(response)
        except Exception as e:
            error_response = {
                "status": "error",
                "message": str(e)
            }
            self._send_json_response(error_response, 500)
    
    def _send_status(self):
        """发送服务器状态"""
        response = {
            "status": "success",
            "server": "Banner Server",
            "version": "1.0.0",
            "timestamp": int(time.time())
        }
        self._send_json_response(response)
    
    def _send_404(self):
        """发送404响应"""
        self.send_response(404)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {"status": "error", "message": "Not Found"}
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def _send_json_response(self, data, status_code=200):
        """发送JSON响应"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # 支持跨域
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args):
        """重写日志方法以自定义日志格式"""
        print(f"[BannerServer] {self.address_string()} - {format % args}")