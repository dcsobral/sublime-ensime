import os, sys, stat
import sublime, sublime_plugin
from ensime_server import EnsimeOnly
import ensime_environment

ensime_env = ensime_environment.ensime_env

class LangNote:

  def __init__(self, lang, msg, fname, severity, start, end, line, col):
    self.lang = lang
    self.message = msg
    self.file_name = fname
    self.severity = severity
    self.start = start
    self.end = end
    self.line = line
    self.col = col

def lang_note(lang, data):
  return LangNote(lang, data[3], data[-1], data[1], data[5], data[7], data[9], data[11])

def erase_error_highlights(view):
  view.erase_regions("ensime-error")
  view.erase_regions("ensime-error-underline")
  
def highlight_errors(view, notes):
  if notes is None:
    print "There were no notes?"
    return
  print "higlighting errors"
  errors = [view.full_line(int(note.start)) for note in notes]
  underlines = []
  for note in notes:
    underlines += [sublime.Region(int(pos)) for pos in range(int(note.start), int(note.end))]
  view.add_regions(
    "ensime-error-underline",
    underlines,
    "invalid.illegal",
    sublime.DRAW_EMPTY_AS_OVERWRITE)
  view.add_regions(
    "ensime-error", 
    errors, 
    "invalid.illegal", 
    "cross",
    sublime.DRAW_OUTLINED)

view_notes = {}

class EnsimeNotes(sublime_plugin.TextCommand, EnsimeOnly):

  def notes_for_view(self):
    return [note for note in self.notes if note.file_name == self.view.file_name()]
    
  def run(self, edit, action = "add", lang = "scala", value=None):
    if not hasattr(self, "notes"):
      self.notes = []
    if action == "add":
      self.notes += [lang_note(lang, data) for data in value[3]]
    elif action == "clear":
      self.notes = []
      erase_error_highlights(self.view)
    elif action == "render":
      erase_error_highlights(self.view)
      highlight_errors(self.view, self.notes_for_view())
    elif action == "display":
      nn = self.notes_for_view()
      vw = self.view
      vpos = vw.line(vw.sel()[0].begin()).begin()
      if len(nn) > 0 and len([a for a in nn if self.view.line(int(a.start)).begin() == vpos]) > 0:
        msgs = [note.message for note in self.notes_for_view()]
        self.view.set_status("ensime-typer", "; ".join(msgs))
      else:
        self.view.erase_status("ensime-typer")

class BackgroundTypeChecker(sublime_plugin.EventListener):

  def on_load(self, view):
    if view.settings().get("syntax") == u'Packages/scala.tmbundle/Syntaxes/Scala.tmLanguage':
      view.run_command("ensime_type_check_file")

  def on_post_save(self, view):
    if view.settings().get("syntax") == u'Packages/scala.tmbundle/Syntaxes/Scala.tmLanguage':
      view.run_command("ensime_type_check_file")

  def on_selection_modified(self, view):
    if view.settings().get("syntax") == u'Packages/scala.tmbundle/Syntaxes/Scala.tmLanguage':
      view.run_command("ensime_notes", { "action": "display" })

