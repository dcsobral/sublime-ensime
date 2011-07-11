import os, sys, stat
import sublime, sublime_plugin
import ensime_server
from ensime_server import EnsimeOnly
from ensime_environment import ensime_env

global ensime_env

class EnsimeScalaNotes(sublime_plugin.WindowCommand, EnsimeOnly):

  notes = []

  def run(self, action = "add", value=""):
    if action == "add":
      notes += value
      print notes.join(", ")
    elif action == "clear":
      notes = []
