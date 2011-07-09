import os, sys, stat, time, datetime
import sublime_plugin, sublime
import thread
import logging
import subprocess
import functools
import socket
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

def swank_bool(bl):
  bl.lower() == 't'

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

class ScalaOnly:
    def is_enabled(self):
        return (bool(self.window and self.window.active_view().file_name() != "" and
        self._is_scala(self.window.active_view().file_name())))

    def _is_scala(self, file_name):
        _, fname = os.path.split(file_name)
        return fname.lower().endswith(".scala")
        # return True


class EnsimeServerCommand(sublime_plugin.WindowCommand, ProcessListener, ScalaOnly):

    def ensime_project_file(self):
        prj_files = [(f + "/.ensime") for f in self.window.folders() if os.path.exists(f + "/.ensime")]
        if len(prj_files) > 0:
            return prj_files[0]
        else:
            return None

    def is_enabled(self, kill = False):
        if kill:
            return hasattr(self, 'proc') and self.proc and self.proc.poll()
        else:
            return (hasattr(self, 'proc') or self.proc or self.proc.poll()) and bool(self.ensime_project_file())

    def run(self, encoding = "utf-8", env = {}, quiet = False, kill = False):

        if not hasattr(self, 'settings'):
            self.settings = sublime.load_settings("Ensime.sublime-settings")
        
        server_dir = self.settings.get("ensime_server_path")

        if kill:
            if self.proc:
                self.proc.kill()
                self.proc = None
                self.append_data(None, "[Cancelled]")
            return

        if not hasattr(self, 'output_view'):
            self.output_view = self.window.get_output_panel("ensime_server")

        self.encoding = encoding
        self.quiet = quiet

        self.proc = None
        if not self.quiet:
            print "Starting Ensime Server."

        self.window.run_command("show_panel", {"panel": "output.ensime_server"})

        merged_env = env.copy()
        if self.window.active_view():
            user_env = self.window.active_view().settings().get('build_env')
            if user_env:
                merged_env.update(user_env)

        # Change to the working dir, rather than spawning the process with it,
        # so that emitted working dir relative path names make sense
        if len(self.window.folders()) > 0 and self.window.folders()[0] != "":
            os.chdir(self.window.folders()[0])


        err_type = OSError
        if os.name == "nt":
            err_type = WindowsError

        try:
            self.proc = AsyncProcess([server_dir + '/bin/server', self.window.folders()[0] + "/.ensime_port"], self)
        except err_type as e:
            self.append_data(None, str(e) + '\n')
        

    def append_data(self, proc, data):
        if proc != self.proc:
            # a second call to exec has been made before the first one
            # finished, ignore it instead of intermingling the output.
            if proc:
                proc.kill()
            return

        try:
            str = data
        except:
            str = '[Decode error - output not ' + self.encoding + ']'
            proc = None

        str = str.replace("\r\n", "\n").replace("\r", "\n")

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










            