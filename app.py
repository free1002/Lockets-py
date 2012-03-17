#coding: utf8

# problem : gevent monkey patch 시 select 를 monkey patch함.
# watchdog 이 select.kqueue을 참조하는데 monkey patch 시엔 이를 찾을 수가 없음.

#from gevent import monkey; monkey.patch_all()
from socketio import SocketIOServer, socketio_manage
from socketio.namespace import BaseNamespace
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MyEventHandler(FileSystemEventHandler):
    def __init__(self, socket, filename, startSize):
        FileSystemEventHandler.__init__(self)
        self.socket = socket
        self.filename = filename
        self.currentSize = startSize

    def on_modified(self,event):
        print 'on modified ', event
        filesize = os.path.getsize(self.filename)
        data = self.readPartial(self.filename, self.currentSize, filesize).splitlines()
        self.socket.send({'tail':data}, True)

        self.currentSize = filesize

    def readPartial(self, filename, start, end):
        f=open(filename)
        f.seek(start)
        text = f.read(end)
        f.close()
        return text

#log_dir = '/var/log/'
log_dir = './'
files = [e for e in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir,e))]

class LogNamespace(BaseNamespace):
    def __init__(self, environ, ns_name, request=None):
        BaseNamespace.__init__(self, environ, ns_name, request)

    def on_connected(self):
        # bug? event 를 받지 않으면 객체 자체가 만들어지지 않음.
        print 'on connected'
        pass

    def recv_initialize(self):
        print 'on initialize'
        self.send({'logs':files}, True)

    def readPartial(self, filename, start, end):
        f=open(filename)
        f.seek(start)
        text = f.read(end)
        f.close()
        return text

    def sendFirst(self, filename):
        file_size = os.path.getsize(filename)
        backlog_size = 5000
        start = file_size-backlog_size if (file_size > backlog_size) else 0
        data = self.readPartial(filename, start, file_size).splitlines()
        self.send({'tail':data}, True)
#        print filename, start, file_size, data

    def on_message(self,msg):
        filename = os.path.join(log_dir,msg['log'])
#        print 'file : ', filename
        self.send({'filename':filename}, True)
        self.sendFirst(filename)
        self.watch(filename)

    def watch(self, filename):
        file_size = os.path.getsize(filename)
        event_handler = MyEventHandler(self, filename, file_size)
        observer = Observer()
        observer.schedule(event_handler, path='.', recursive=False)
        observer.start()

class Application:
    def __init__(self):
        self.buffer = []

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].strip('/')
        environ['nicknames'] = []

        if not path:
            start_response('200 OK', [('Content-Type', 'text/html')])
            return ['Hello World']

        if path in ['socket.io.js', 'index.html']:
            try:
                data = open(path).read()
            except Exception:
                return not_found(start_response)

            if path.endswith('.js'):
                content_type = 'text/javascript'
            else:
                content_type = 'text/html'

            start_response('200 OK', [('Content-Type', content_type)])
            return [data]

        if path.startswith('socket.io'):
            socketio_manage(environ, {'': LogNamespace})
        else:
            return not_found(start_response)

def not_found(start_response):
    start_response('404 Not Found', [])
    return ['<h1>Not Found</h1>']

if __name__=="__main__":
    print 'Listening on port 8080 and on port 843 (flash policy server)'
    SocketIOServer(('127.0.0.1', 8080), Application(), namespace="socket.io", policy_server=False).serve_forever()

