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

  completions = {}
  def default_completions(self, prefix):
    return [(prefix + "\tloading...", prefix)]

  def handle_reply(self, data, view):
    friend = sexp.sexp_to_key_map(data[1][1])
    comps = friend[":completions"] if ":completions" in friend else []
    comp_list = [ensime_completion(sexp.sexp_to_key_map(p)) for p in friend[":completions"]]
    real_list = [(p.name + "\t" + p.signature, p.name) for p in comp_list]
    prefix = view.substr(view.word(view.sel()[0].begin()))
    self.completions[view.id()] = { friend[":prefix"] : real_list }
    print repr(self.completions)

  def get(self, view, prefix): 
    vw_cached = self.completions.get(view.id(), {})
    cached = vw_cached.get(str(prefix[:-1]), self.default_completions(prefix))
    return cached 
 
  def on_query_completions(self, view, prefix, locations):
    if not view.match_selector(locations[0], "source.scala") and not view.match_selector(locations[0], "source.java"):
      return []
    print "Querying completions for prefix " + prefix + ", locations[0]" + repr(locations)
    data = ensime_environment.ensime_env.client().complete_member(view.file_name(), locations[0])
    print "DATA received: " + repr(data)
    friend = sexp.sexp_to_key_map(data[1][1])
    print "Friend received: " + repr(friend)
    comps = friend[":completions"] if ":completions" in friend else []
    print "comps"
    print repr(comps)
    comp_list = [ensime_completion(sexp.sexp_to_key_map(p)) for p in friend[":completions"]]
    
    return ([(p.name + "\t" + p.signature, p.name) for p in comp_list], sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)

  # def on_selection_modified(self, view):
  #   if len(view.sel()) > 0:
  #     loc = view.sel()[0].begin()
  #     prefix = view.substr(view.word(loc))
  #     if view.match_selector(loc, "source.scala") or view.match_selector(loc, "source.java"):
  #       print "Getting completions for position: " + str(loc) + " with prefix: " + prefix
  #       cl = ensime_environment.ensime_env.client()
  #       if not cl is None and not len(self.get(view, prefix)) == 0:
  #         cl.complete_member(view.file_name(), loc, lambda d: self.handle_reply(d, view))

