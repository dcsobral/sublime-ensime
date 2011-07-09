import os, sys, stat, time, datetime
import sublime_plugin, sublime
import threading
import logging
import socket
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class ProcessListener(object):
    def on_data(self, proc, data):
        pass

    def on_finished(self, proc):
        pass


class AsyncProcess(object):
    def __init__(self, arg_list, listener):
        self.listener = listener
        self.killed = False

        # Hide the console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc_env = os.environ.copy()

        self.proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env)

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

class EnsimeClient:
    def __init__(self, project_root="/Users/ivan/projects/mojolly/backchat-library"):
        self.project_root = project_root
        self.client = self._connect()

    def _port(self):
        return int(open(self.project_root + "/ensime_port").read())

    def _current_message(self):
        return int(open(self.project_root + "/message.counter." + self._port()).read())
        
    def _with_length_header(self, data): 
        return "%06x" % len(data) + data

    def _make_message(self, data):
        return str(self._with_length_header("(:swank-rpc " + str(data) + " " + str(1) + ")"))

    def _connect(self):
        try:
            s = socket.socket()
            s.connect(("127.0.0.1", self._port()))
            return s
        except socket.error as e:
            # set sublime error status
            sublime.error_message("Can't connect to ensime server:  " + e.args[1])

    def close(self):
        self.client.close()

    def req(self, to_send): 
        self.client.send(self._make_message(to_send))
        resp = self.client.recv(1024)
        return resp

    def handshake(self): 
        self.req("(swank:connection-info)")

class StartEnsimeServerCommand(sublime_plugin.WindowCommand, ProcessListener):

    def run(self):
        sublime.status_message("Success!")


