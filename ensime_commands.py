import os, sys, stat, random, getpass
import ensime_environment
from ensime_server import EnsimeOnly
import functools, socket, threading
import sublime_plugin, sublime


def save_view(view):
  if view == None or view.file_name == None:
    return
  content = view.substr(sublime.Region(0, view.size()))
  with open(view.file_name(), 'wb') as f:
    f.write(content.encode("UTF-8"))
                
class EnsimeReformatSourceCommand(sublime_plugin.TextCommand, EnsimeOnly):

  def handle_reply(self, data):
    self.view.run_command('revert')
    self.view.set_status("ensime", "Formatting done!")

  def run(self, edit):
    #ensure_ensime_environment.ensime_env()
    vw = self.view
    if vw.is_dirty():
      vw.run_command("save")
    fmt_result = ensime_environment.ensime_env.client().format_source(vw.file_name(), self.handle_reply)
    

class RandomWordsOfEncouragementCommand(sublime_plugin.WindowCommand, EnsimeOnly):

  def run(self):
    if not hasattr(self, "phrases"):
      self.phrases = [
        "Let the hacking commence!",
        "Hacks and glory await!",
        "Hack and be merry!",
        "May the source be with you!",
        "Death to null!",
        "Find closure!",
        "May the _ be with you.",
        "CanBuildFrom[List[Dream], Reality, List[Reality]]"
      ]  
    msgidx = random.randint(0, len(self.phrases) - 1)
    msg = self.phrases[msgidx]
    sublime.status_message(msg + " This could be the start of a beautiful program, " + 
      getpass.getuser().capitalize()  + ".")

class EnsimeTypeCheckAllCommand(sublime_plugin.WindowCommand, EnsimeOnly):

  def handle_reply(self, data):
    print "got type check result"
    print data

  def run(self):
    ensime_environment.ensime_env.client().type_check_all(self.handle_reply)

class EnsimeTypeCheckFileCommand(sublime_plugin.WindowCommand, EnsimeOnly):

  def run(self):
    pass

class EnsimeOrganizeImportsCommand(sublime_plugin.TextCommand, EnsimeOnly):

  def handle_reply(self, edit, data):
    print "reply for organize imports"
    print data

  def run(self, edit):
    #ensure_ensime_environment.ensime_env()
    fname = self.view.file_name()
    ensime_environment.ensime_env.client().organize_imports(fname, lambda data: self.handle_reply(edit, data))
