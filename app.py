#coding: utf8
# problem : gevent monkey patch 시 select 를 monkey patch함.
# watchdog 이 select.kqueue을 참조하는데 monkey patch 시엔 이를 찾을 수가 없음.
#from gevent import monkey; monkey.patch_all()
from socketio import SocketIOServer, socketio_manage
from socketio.namespace import BaseNamespace
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def read_partial(filename, start, end):
    with open(filename) as f:
        f.seek(start)
        text = f.read(end)
        return text

class ModifiedEventHandler(FileSystemEventHandler):
    def __init__(self, socket, filename, start_size):
        FileSystemEventHandler.__init__(self)
        self.socket = socket
        self.filename = filename
        self.current_size = start_size

    def on_modified(self,event):
        filesize = os.path.getsize(self.filename)
        data = read_partial(self.filename, self.current_size, filesize).splitlines()
        self.socket.send({'tail':data}, True)
        self.current_size = filesize

#log_dir = '/var/log/'
log_dir = './'
files = [e for e in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir,e))]

backlog_size = 5000

class LogNamespace(BaseNamespace):
    def __init__(self, environ, ns_name, request=None):
        BaseNamespace.__init__(self, environ, ns_name, request)

    def on_connected(self):
        # bug? gevent-socketio 의 경우 event 를 받지 않으면 객체 자체가 만들어지지 않음.
        pass

    def recv_initialize(self):
        self.send({'logs':files}, True)

    def sendFirst(self, filename):
        file_size = os.path.getsize(filename)
        start = file_size-backlog_size if (file_size > backlog_size) else 0
        data = read_partial(filename, start, file_size).splitlines()
        self.send({'tail':data}, True)

    def on_message(self,msg):
        filename = os.path.join(log_dir,msg['log'])
        self.send({'filename':filename}, True)
        self.sendFirst(filename)
        self.watch(filename)

    def watch(self, filename):
        file_size = os.path.getsize(filename)
        event_handler = ModifiedEventHandler(self, filename, file_size)
        observer = Observer()
        observer.schedule(event_handler, path='.', recursive=False)
        observer.start()

class Application:
    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].strip('/')

        if not path:
            start_response('200 OK', [('Content-Type', 'text/html')])
            return ['Hello World']

        if path in ['socket.io.js', 'index.html']:
            try:
                data = open(path).read()
                if path.endswith('.js'):
                    content_type = 'text/javascript'
                else:
                    content_type = 'text/html'
                start_response('200 OK', [('Content-Type', content_type)])
                return [data]
            except Exception:
                return not_found(start_response)

        if path.startswith('socket.io'):
            socketio_manage(environ, {'': LogNamespace})
        else:
            return not_found(start_response)

def not_found(start_response):
    start_response('404 Not Found', [])
    return ['<h1>Not Found</h1>']

if __name__=="__main__":
    print 'open http://localhost:8080/index.html'
    SocketIOServer(('127.0.0.1', 8080), Application(), namespace="socket.io", policy_server=False).serve_forever()
