import os, sys, stat, random, getpass
import ensime_environment
from ensime_server import EnsimeOnly
import functools, socket, threading
import sublime_plugin, sublime
import sexp
from sexp import key,sym

class EnsimeCompletion:

  def __init__(self, name, signature, type_id, is_callable = False, to_insert = None):
    self.name = name
    self.signature = signature
    self.is_callable = is_callable
    self.type_id = type_id
    self.to_insert = to_insert

def ensime_completion(p):
    return EnsimeCompletion(
      p[":name"], 
      p[":type-sig"], 
      p[":type-id"], 
      bool(p[":is-callable"]) if ":is-callable" in p else False,
      p[":to-insert"] if ":to-insert" in p else None)


class EnsimeCompletionsListener(sublime_plugin.EventListener): 
 
  def on_query_completions(self, view, prefix, locations):
    if not view.match_selector(locations[0], "source.scala") and not view.match_selector(locations[0], "source.java"):
      return []
 
    data = ensime_environment.ensime_env.client().complete_member(view.file_name(), locations[0])
    friend = sexp.sexp_to_key_map(data[1][1])
    comps = friend[":completions"] if ":completions" in friend else []
    comp_list = [ensime_completion(sexp.sexp_to_key_map(p)) for p in friend[":completions"]]
    
    return ([(p.name + "\t" + p.signature, p.name) for p in comp_list], sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)

