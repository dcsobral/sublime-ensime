import os, sys, stat
import sublime, sublime_plugin
from ensime_server import EnsimeOnly
import ensime_environment

ensime_env = ensime_environment.ensime_env

class EnsimeScalaNotes(sublime_plugin.WindowCommand, EnsimeOnly):

  notes = []

  def run(self, action = "add", value=""):
    if action == "add":
      notes += value
      print notes.join(", ")
    elif action == "clear":
      notes = []
