import os, sys, stat, time, datetime, re
import functools, socket, threading
import sublime_plugin, sublime
import thread
import logging
import subprocess
import functools
import socket
import threading
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class EnsimeEnvironment:

    def __init__(self):
        self.settings = sublime.load_settings("Ensime.sublime-settings")
        self._clientLock = threading.RLock()
        self._client = None

    def set_client(self, client):
        self._clientLock.acquire()
        try:
            self._client = client
            return self._client
        finally:
            self._clientLock.release()

    def client(self):
        return self._client


ensime_env = EnsimeEnvironment()

class ProcessListener(object):
    def on_data(self, proc, data):
        pass

    def on_finished(self, proc):
        pass

class AsyncProcess(object):
    def __init__(self, arg_list, listener, cwd = None):
        self.listener = listener
        self.killed = False

        # Hide the console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc_env = os.environ.copy()

        self.proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, cwd = cwd)

        if self.proc.stdout:
            thread.start_new_thread(self.read_stdout, ())

        if self.proc.stderr:
            thread.start_new_thread(self.read_stderr, ())

    def kill(self):
        if not self.killed:
            self.killed = True
            self.proc.kill()
            self.listener = None

    def poll(self):
        return self.proc.poll() == None

    def read_stdout(self):
        while True:
            data = os.read(self.proc.stdout.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stdout.close()
                if self.listener:
                    self.listener.on_finished(self)
                break

    def read_stderr(self):
        while True:
            data = os.read(self.proc.stderr.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stderr.close()
                break


class ScalaOnly:
    def is_enabled(self):
        return (bool(self.window and self.window.active_view().file_name() != "" and
        self._is_scala(self.window.active_view().file_name())))

    def _is_scala(self, file_name):
        _, fname = os.path.split(file_name)
        return fname.lower().endswith(".scala")
        # return True

class EnsimeOnly:
    def ensime_project_file(self):
        prj_files = [(f + "/core/.ensime") for f in self.window.folders() if os.path.exists(f + "/core/.ensime")]
        if len(prj_files) > 0:
            return prj_files[0]
        else:
            return None

    def is_enabled(self, kill = False):
        return bool(ensime_env.client()) and ensime_env.client.ready() and bool(self.ensime_project_file())

class EnsimeServerCommand(sublime_plugin.WindowCommand, ProcessListener, ScalaOnly, EnsimeOnly):

    def ensime_project_root(self):
        prj_dirs = [f for f in self.window.folders() if os.path.exists(f + "/core/.ensime")]
        if len(prj_dirs) > 0:
            return prj_dirs[0] + "/core"
        else:
            return None

    def is_started(self):
        return hasattr(self, 'proc') and self.proc and self.proc.poll()

    def is_enabled(self, **kwargs):
        start, kill, show_output = kwargs.get("start", False), kwargs.get("kill", False), kwargs.get("show_output", False)
        return ((kill or show_output) and self.is_started()) or (start and bool(self.ensime_project_file()))
                    
    def show_output_window(self, show_output = False):
        if show_output:
            self.window.run_command("show_panel", {"panel": "output.ensime_server"})
        

    def run(self, encoding = "utf-8", env = {}, start = False, quiet = False, kill = False, show_output = False):
        print "running: " + self.__class__.__name__
        self.show_output = False

        if not hasattr(self, 'settings'):
            self.settings = sublime.load_settings("Ensime.sublime-settings")

        server_dir = self.settings.get("ensime_server_path")

        if kill:
            ensime_env.client().disconnect()
            if self.proc:
                self.proc.kill()
                self.proc = None
                self.append_data(None, "[Cancelled]")
            return
        else:
            if self.is_started():
                self.show_output_window(show_output)
                if start and not self.quiet:
                    print "Ensime server is already running!"
                return

        if not hasattr(self, 'output_view'):
            self.output_view = self.window.get_output_panel("ensime_server")

        self.quiet = quiet

        self.proc = None
        if not self.quiet:
            print "Starting Ensime Server."
        
        if show_output:
            self.show_output_window(show_output)

        # Change to the working dir, rather than spawning the process with it,
        # so that emitted working dir relative path names make sense
        if self.ensime_project_root() and self.ensime_project_root() != "":
            os.chdir(self.ensime_project_root())


        err_type = OSError
        if os.name == "nt":
            err_type = WindowsError

        try:
            self.show_output = show_output
            if start:
                ensime_env.set_client(EnsimeClient(ensime_env.settings, self.window, self.ensime_project_root()))
                self.proc = AsyncProcess(['bin/server', self.ensime_project_root() + "/.ensime_port"], self, server_dir)
        except err_type as e:
            self.append_data(None, str(e) + '\n')

    def perform_handshake(self):
        self.window.run_command("ensime_handshake")
        

    def append_data(self, proc, data):
        if proc != self.proc:
            # a second call to exec has been made before the first one
            # finished, ignore it instead of intermingling the output.
            if proc:
                proc.kill()
            return

        str = data.replace("\r\n", "\n").replace("\r", "\n")

        if not ensime_env.client().ready() and re.search("Wrote port", str):
            ensime_env.client().set_ready()
            self.perform_handshake()

        selection_was_at_end = (len(self.output_view.sel()) == 1
            and self.output_view.sel()[0]
                == sublime.Region(self.output_view.size()))
        self.output_view.set_read_only(False)
        edit = self.output_view.begin_edit()
        self.output_view.insert(edit, self.output_view.size(), str)
        if selection_was_at_end:
            self.output_view.show(self.output_view.size())
        self.output_view.end_edit(edit)
        self.output_view.set_read_only(True)

    def finish(self, proc):
        if proc != self.proc:
            return

        # Set the selection to the start, so that next_result will work as expected
        edit = self.output_view.begin_edit()
        self.output_view.sel().clear()
        self.output_view.sel().add(sublime.Region(0))
        self.output_view.end_edit(edit)

    def on_data(self, proc, data):
        sublime.set_timeout(functools.partial(self.append_data, proc, data), 0)

    def on_finished(self, proc):
        sublime.set_timeout(functools.partial(self.finish, proc), 0)


class EnsimeUpdateMessagesView(sublime_plugin.WindowCommand, EnsimeOnly):
    def run(self, msg):
        print "running: " + self.__class__.__name__
        if msg != None:
            ov = ensime_env.client().output_view
            msg = msg.replace("\r\n", "\n").replace("\r", "\n")

            selection_was_at_end = (len(ov.sel()) == 1
                and ov.sel()[0]
                    == sublime.Region(ov.size()))
            ov.set_read_only(False)
            edit = ov.begin_edit()
            ov.insert(edit, ov.size(), msg + "\n")
            if selection_was_at_end:
                ov.show(ov.size())
            ov.end_edit(edit)
            ov.set_read_only(True)

class CreateEnsimeClientCommand(sublime_plugin.WindowCommand, EnsimeOnly):

    def run(self):
        print "running: " + self.__class__.__name__
        cl = EnsimeClient(self.window, u"/Users/ivan/projects/mojolly/backchat-library/core")
        cl.set_ready()
        self.window.run_command("ensime_handshake")

class EnsimeShowMessageViewCommand(sublime_plugin.WindowCommand, EnsimeOnly):

    def run(self):
        print "running: " + self.__class__.__name__
        self.window.run_command("show_panel", {"panel": "output.ensime_messages"})

class EnsimeHandshakeCommand(sublime_plugin.WindowCommand, EnsimeOnly):

    def handle_init_reply(self, init_info):
        sublime.status_message("Ensime ready!")

    def handle_reply(self, server_info):
        if server_info[1][0] == ":ok" and server_info[2] == 1:
            msg = "Initializing " + server_info[1][1][3][1] + " v." + server_info[1][1][9]
            sublime.status_message(msg)
            ensime_env.client().initialize_project(self.handle_init_reply)
        else:
            sublime.error_message("There was problem initializing ensime, msgno: " + str(server_info[2]) + ".")

    def run(self):
        print "running: " + self.__class__.__name__
        if (ensime_env.client().ready()):
            ensime_env.client().handshake(self.handle_reply)
            

def save_view(view):
    if view == None or view.file_name == None:
      return
    content = view.substr(sublime.Region(0, view.size()))
    with open(view.file_name(), 'wb') as f:
      f.write(content.encode("UTF-8"))
                
class EnsimeReformatSourceCommand(sublime_plugin.WindowCommand, EnsimeOnly):

    def run(self):
        print "running: " + self.__class__.__name__
        vw = self.window.active_view()
        print("reformatting: " + vw.file_name())
        save_view(vw)
        fmt_result = ensime_env.client().format_source(vw.file_name())
        print fmt_result
        sublime.status_message("Formatting done!")

class EnsimeMessageHandler:

    def on_data(self, data):
        pass

    def on_disconnect(self, reason):
        pass

class EnsimeServerClient:

    def __init__(self, project_root, handler):
        self.project_root = project_root
        self.connected = False
        self.handler = handler
        self._lock = threading.RLock()
        self._connect_lock = threading.RLock()
        self._receiver = None

    def port(self):
        return int(open(self.project_root + "/.ensime_port").read()) 

    def receive_loop(self):
        print "starting receive loop, we're connected: " + str(self.connected)
        from sexp_parser import sexp
        # try:
        #     sexp.parseString("""(:return (:ok (:pid nil :server-implementation (:name "ENSIMEserver") :machine nil :features nil :version "0.0.1")) 1)""")
        # except:
        #     pass    

        while 1:
            # try:
            res = self.client.recv(4096)
            print "RECV: " + res
            if res:
                if res == "" or res == None or not self.connected:
                    print "mmmm disconnected?"
                    self.handler.on_disconnect("server")
                    self.set_connected(False)
                else:
                    print "about to parse: " + res[6:]
                    dd = sexp.parseString(res[6:])[0]
                    print "calling handler with: " + str(dd)
                    sublime.set_timeout(functools.partial(self.handler.on_data, dd), 0)
            # except Exception as e:
            #     raise e
            #     self.handler.on_disconnect("server")
            #     self.set_connected(False)

    def set_connected(self, val):
        self._lock.acquire()
        try:
            self.connected = val
        finally:
            self._lock.release()

    def start_receiving(self):
        t = threading.Thread(name = "ensime-client-" + str(self.port()), target = self.receive_loop)
        t.setDaemon(True)
        t.start()
        self._receiver = t

    def connect(self):
        self._connect_lock.acquire()
        try:
            s = socket.socket()
            s.connect(("127.0.0.1", self.port()))
            self.client = s
            self.set_connected(True)
            self.start_receiving()
            return s
        except socket.error as e:
            # set sublime error status
            self.set_connected(False)
            sublime.error_message("Can't connect to ensime server:  " + e.args[1])
        finally:
            self._connect_lock.release()

    def send(self, request):
        if not self.connected:
            self.connect()
        self.client.send(request)        

    def close(self):
        self._connect_lock.acquire()
        try:
            if self.client:
                self.client.close()
            self.connected = False
        finally:
            self._connect_lock.release()    
    

class EnsimeClient(EnsimeMessageHandler):

    def __init__(self, settings, window, project_root):
        self.settings = settings
        self.project_root = project_root
        self._ready = False
        self._readyLock = threading.RLock()
        self.window = window
        self.output_view = self.window.get_output_panel("ensime_messages")
        self.message_handlers = dict()
        self._counter = 0
        self._counterLock = threading.RLock()
        self.client = EnsimeServerClient(project_root, self)
        
    def ready(self):
        return self._ready

    def set_ready(self):
        self._readyLock.acquire()
        try:
            self._ready = True
            return self.ready()
        finally:
            self._readyLock.release()

    def set_not_ready(self):
        self._readyLock.acquire()
        try:
            self._ready = False
            return self.ready()
        finally:
            self._readyLock.release()

    def on_data(self, data):
        self.feedback(data)
        # match a message with a registered response handler.
        # if the message has no registered handler check if it's a 
        # background message.
        if data[0] == ":return":
            th = {
                ":ok": lambda d: self.message_handlers[d[-1]](d),
                ":abort": lambda d: sublime.status_message(d[-1]),
                ":error": lambda d: sublime.error_message(d[-1])
            }

            if self.message_handlers.has_key(data[-1]):
                print "got a callback for the data"
                th[data[1][0]](data)
            else:
                print "Unhandled message: " + str(data)
        else:
            self.handle_server_message(data)
        #except BaseException as e:
         #   sublime.error_message("There was an exception: " + str(e))

    def handle_server_message(self, data):
        print "Received a message from the server:"
        print str(data)

    def next_message_id(self):
        self._counterLock.acquire()
        try:
            self._counter += 1
            return self._counter
        finally:
            self._counterLock.release()

    def feedback(self, msg):
        sublime.set_timeout(self.window.run_command("ensime_update_messages_view", { 'msg': msg }), 0)

    def on_disconnect(self, reason = "client"):
        if reason == "server":
            sublime.error_message("The ensime server was disconnected, you might want to restart it.")

    def project_file(self): 
        if self.ready:
            return self.project_root + "/.ensime"
        else:
            return ""

    def project_config(self):
        return open(self.project_file()).read()
    
    def prepend_length(self, data): 
        return "%06x" % len(data) + data

    def format(self, data, count):
        return str(self.prepend_length("(:swank-rpc " + str(data) + " " + str(count) + ")"))
    
    def req(self, to_send, on_complete): 
        if self.ready() and not self.client.connected:
            self.client.connect()
        msgcnt = self.next_message_id()
        self.message_handlers[msgcnt] = on_complete
        msg = self.format(to_send, msgcnt)
        self.feedback(msg)
        self.client.send(msg)

    def disconnect(self):
        print "disconnecting"
        self.client.close()

    def handshake(self, on_complete): 
        print "handshaking"
        return self.req("(swank:connection-info)", on_complete)

    def initialize_project(self, on_complete):
        print "initializing project"
        return self.req("(swank:init-project " + self.project_config() + " )", on_complete)

    def format_source(self, file_path, on_complete):
        print "formatting source: " + file_path
        return self.req('(swank:format-source ("'+file_path+'"))', on_complete)
        
