import os, sys, stat, time, datetime, re
import functools, socket, threading
import sublime_plugin, sublime
from string import strip



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
    #TODO: possibly use a smaller buffer but allow for recomposing a message
    #      from multiple buffers in case they overflow.
    from sexpr_parser import parse
    while self.connected:
      try:
        res = self.client.recv(4096)
        print "RECV: " + res
        if res:
          msglen = int(res[:6], 16) + 6
          msg = res[6:msglen]
          nxt = strip(res[msglen:])
          while len(nxt) > 0 or len(msg) > 0:
            sublime.set_timeout(functools.partial(self.handler.on_data, parse(msg)), 0)
            if len(nxt) > 0:
              msglen = int(nxt[:6], 16) + 6
              msg = nxt[6:msglen]
              nxt = strip(nxt[msglen:])
            else: 
              msg = ""
              msglen = ""
        else:
          self.set_connected(False)
      except Exception as e:
        print "*****    ERROR     *****"
        print e
        self.handler.on_disconnect("server")
        self.set_connected(False)

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
    try:
      if not self.connected:
        self.connect()
      self.client.send(request)
    except:
      self.handler.disconnect("server")
      self.set_connected(False)

  def close(self):
    self._connect_lock.acquire()
    try:
      if self.client:
        self.client.close()
      self.connect = False
    finally:
      self._connect_lock.release()    


class EnsimeClient(EnsimeMessageHandler):

  def __init__(self, settings, window, project_root):
    def ignore(d): 
      None      

    def clear_notes(lang, data):
      if data[-1] == "t":
        self.window.run_command("ensime_java_notes", {"action": "clear"})

    def full_type_check_done(d):
      if d[-1] == "t":
        sublime.status_message("Full type check done!")
    
    
    self.settings = settings
    self.project_root = project_root
    self._ready = False
    self._readyLock = threading.RLock()
    self.window = window
    self.output_view = self.window.get_output_panel("ensime_messages")
    self.message_handlers = dict()
    self.procedure_handlers = dict()
    self._counter = 0
    self._procedure_counter = 0
    self._counterLock = threading.RLock()
    self.client = EnsimeServerClient(project_root, self)
    self._reply_handlers = {
      ":ok": lambda d: self.message_handlers[d[-1]](d),
      ":abort": lambda d: sublime.status_message(d[-1]),
      ":error": lambda d: sublime.error_message(d[-1])
    }
    self._server_message_handlers = {
      "clear-all-scala-notes": lambda d: clear_notes("scala", d),
      "clear-all-java-notes": lambda d: clear_notes("java", d),
      "compiler-ready": lambda d: self.window.run_command("random_words_of_encouragement"),
      "full-typecheck-finished": ignore,
      "indexer-ready": ignore,
      "background-message": sublime.status_message
    }
      
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

  def remove_handler(self, handler_id):
    del self.message_handlers[handler_id]

  def on_data(self, data):
    self.feedback(str(data))
    # match a message with a registered response handler.
    # if the message has no registered handler check if it's a 
    # background message.
    if data[0] == ":return":
      th = self._reply_handlers

      # if data[0][0][0][1:] == "procedure-id" and self.procedure_handlers.has_key(data[0][0][1]):
      #   self.procedure_handlers[data[0][0][1]](data)
      #   del self.proceure_handlers[data[0][0][1]]
      if self.message_handlers.has_key(data[-1]):
        th[data[1][0]](data)
      else:
        print "Unhandled message: " + str(data)
    else:
        self.handle_server_message(data)

  def handle_server_message(self, data):
    handled = self._server_message_handlers
    try:
      if handled.has_key(data[0][1:]):
        handled[data[0][1:]](data[-1])
      else:
        print "Received a message from the server:"
        print str(data)
    except Exception as e:
      print "Error when handling server message: " + str(data)
      print e.args
    

  def next_message_id(self):
    self._counterLock.acquire()
    try:
      self._counter += 1
      return self._counter
    finally:
      self._counterLock.release()

  def next_procedure_id(self):
    self._counterLock.acquire()
    try:
      self._procedure_counter += 1
      return self._procedure_counter
    finally:
      self._counterLock.release()

  def feedback(self, msg):
    self.window.run_command("ensime_update_messages_view", { 'msg': msg })

  def on_disconnect(self, reason = "client"):
    self._counterLock.acquire()
    try:
      self._counter = 0
      self._procedure_counter = 0
    finally:
      self._counterLock.release()
      
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
    return str("(:swank-rpc " + str(data) + " " + str(count) + ")")
  
  def req(self, to_send, on_complete, msg_id = None): 
    msgcnt = msg_id
    if msg_id == None:
      msgcnt = self.next_message_id()
      
    if self.ready() and not self.client.connected:
      self.client.connect()
    self.message_handlers[msgcnt] = on_complete
    msg = self.format(to_send, msgcnt)
    self.feedback(msg)
    self.client.send(self.prepend_length(msg))

  def refactor_req(self, to_send, on_complete, msg_id = None):
    msgcnt = msg_id
    if msg_id == None:
      msgcnt = self.next_procedure_id()

    if self.ready() and not self.client.connected:
      self.client.connect()
    self.procedure_handlers[msgcnt] = on_complete
    msg = self.format(to_send, 't')
    self.feedback(msg)
    self.client.send(self.prepend_length(msg))

  def disconnect(self):
    self._counterLock.acquire()
    try:
      self._counter = 0
      self._procedure_counter = 0
    finally:
      self._counterLock.release()
    self.client.close()

  def handshake(self, on_complete): 
    self.req("(swank:connection-info)", on_complete)

  def initialize_project(self, on_complete):
    self.req("(swank:init-project " + self.project_config() + " )", on_complete)

  def format_source(self, file_path, on_complete):
    self.req('(swank:format-source ("'+file_path+'"))', on_complete)

  def type_check_all(self, on_complete):
    self.req('(swank:typecheck-all)', on_complete)

  def type_check_file(self, file_path, on_complete):
    pass

  def organize_imports(self, file_path, on_complete):
    self.req('(swank:perform-refactor ' + str(self.next_procedure_id()) + ' organizeImports ' +
                '(file "'+file_path+'") t)', on_complete)
  
  def perform_organize(self, previous_id, msg_id, on_complete):
    self.req("(swank:exec-refactor " + str(int(previous_id)) + " organizeImports)", on_complete, int(msg_id))
      
