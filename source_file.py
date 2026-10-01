import os
import time

class source_file(object):
	def __init__(self, filename):
		self.filename = os.path.abspath(filename)
		self.modified = self.get_last_modified()
		self.last_size = os.path.getsize(filename)
		
	def get_last_modified(self):
		return time.ctime(os.path.getmtime(self.filename))
		
	def was_updated(self):
		t = self.get_last_modified()
		if t > self.modified:
			self.modified = t
			return True
		else:
			return False
		
	def get_base_name(self):
		return os.path.basename(self.filename)
		
	def get_directory(self):
		return os.path.dirname(self.filename)
		
	def get_text(self, only_new_text = False):
		text = ""
		while len(text) == 0:
			with open(self.filename, 'r') as content_file:
				if only_new_text:
					content_file.seek(self.last_size)
				text = content_file.read()
			
			# Only wait when the read came back EMPTY -- an editor that truncates then
			# rewrites is caught mid-save by the watch loop, and that is all this retry is
			# for. Sleeping after every successful read cost 0.1 s per file read, two per
			# compile (the script and its imported .cblib): ~0.2 s of a ~0.29 s one-shot
			# compile, measured with cProfile (modding-from-a-mod #1226).
			if len(text) == 0:
				time.sleep(0.1)
			
		self.last_size = os.path.getsize(self.filename)
		return text