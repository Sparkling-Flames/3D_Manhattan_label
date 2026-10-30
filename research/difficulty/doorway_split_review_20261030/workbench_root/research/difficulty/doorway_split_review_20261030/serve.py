#!/usr/bin/env python3
"""门洞交界 · 空间审核：本地静态服务器（HTTP/1.1 keep-alive，避免首访偶发连接重置）。

用法：python3 serve.py [端口]（默认 8787）
根目录固定为 3D_Manhattan_label（本文件向上三级），以保证页面里的相对路径可用。
"""
import functools
import http.server
import os
import socket
import sys
import threading


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'          # 关键：keep-alive，避免 Chrome 首访连接被重置
    server_version = 'DoorwayReview/1.0'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def send_head(self):
        # 简单处理：不存在的路径返回 404，不要触发目录遍历异常刷屏
        try:
            return super().send_head()
        except (BrokenPipeError, ConnectionResetError):
            return None


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
    handler = functools.partial(Handler, directory=root)
    httpd = Server(('127.0.0.1', port), handler)
    print('serving %s at http://127.0.0.1:%d/research/difficulty/doorway_split_review_20261030/index.html' % (root, port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
