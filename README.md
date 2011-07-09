# Sublime Ensime

This project provides an integration with ensime and Sublime Text Editor 2.
Sublime as an outstanding API so it should be possible to get all of ensime's features in Sublime Text Editor 2.

## What's working?
At this moment the plugin is able to read a multi project file and initialize the server for the top-level project. The messaging pipeline needs to be refactored and then it will be the commands.

## How to install?

In your sublime text Packages dir.  

```
git clone git://github.com/casualjim/sublime-ensime.git Ensime
cd Ensime
./install-ensime-server
```

and (re)start sublime text editor.  
Once you're in a project that has a .ensime file in the root folder, you can start a server from the file context menu. Or run:

```python
window.run_command("ensime_server", { "start": True})
```

## What's planned?
To implement all the features of ensime.

## Wishlist?
I'd like to use the information we get back from ensime to provide semantic highlighting.
