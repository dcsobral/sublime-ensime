import os, sys, stat, random
from ensime_environment import *
from ensime_server import EnsimeOnly
import functools, socket, threading
import sublime_plugin, sublime

def save_view(view):
  if view == None or view.file_name == None:
    return
  content = view.substr(sublime.Region(0, view.size()))
  with open(view.file_name(), 'wb') as f:
    f.write(content.encode("UTF-8"))
                
class EnsimeReformatSourceCommand(sublime_plugin.WindowCommand, EnsimeOnly):

  def run(self):
    # TODO: copy buffer to temp file, run formatting on that
    #       set the current view to read only during the formatting
    #       then move the content from the temp file into the view and
    #       allow writing again in the view.
    vw = self.window.active_view()
    save_view(vw)
    fmt_result = ensime_env.client().format_source(vw.file_name())
    sublime.status_message("Formatting done!")

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
    print "Executing random words of encouragement"
    msgidx = random.randint(0, len(self.phrases) - 1)
    msg = self.phrases[msgidx]
    print "The words are: " + msg
    sublime.status_message(msg + " This could be the start of a beautiful program.")


