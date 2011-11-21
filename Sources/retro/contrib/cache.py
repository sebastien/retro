#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Nov-2007
# Last mod  : 14-Nov-2011
# -----------------------------------------------------------------------------

import os, stat, hashlib, threading, urllib, pickle

class CacheError(Exception):
	pass

class CacheMiss(Exception):
	pass

# ------------------------------------------------------------------------------
#
# CACHE OBJECT
#
# ------------------------------------------------------------------------------

class Cache:

	def __init__( self ):
		self.enabled = True

	def get( self, key ):
		raise NotImplementedError
	
	def has( self, key ):
		raise NotImplementedError

	def set( self, key, value ):
		raise NotImplementedError
	
	def clear( self, key ):
		raise NotImplementedError

	def remove( self, key ):
		raise NotImplementedError

class NoCache(Cache):

	def __init__( self ):
		Cache.__init__(self)

	def get( self, key ):
		return False
	
	def has( self, key ):
		return False

	def set( self, key, value ):
		return False
	
	def clear( self, key ):
		return False

	def remove( self, key ):
		return False

class MemoryCache(Cache):
	"""A simple cache system using a weighted LRU style dictionary."""

	def __init__( self, limit=100 ):
		Cache.__init__(self)
		self.data   = {}
		self.weight = 0
		self.limit  = 100
		self.lock   = threading.Lock()
		self.enabled = True

	def enable( self ):
		self.enabled = True

	def disable( self ):
		self.enabled = False

	def get( self, key ):
		d = self.data.get(key)
		if d:
			# We increase the hit count
			d[1] += 1
			return d[2]
		else:
			return None

	def has( self, key ):
		res = self.data.get(key)
		return res and True

	def set( self, key, data, weight=1 ):
		self.lock.acquire()
		if self.data.has_key(key):
			# We update the data if it's already there
			previous       = self.data[key]
			self.weight   -= previous[0]
			previous[0]    = weight
			previous[2]    = data
			self.data[key] = previous
		else:
			self.data[key] = [weight, 0, data]
			self.weight   += weight
		self.lock.release()
		if self.weight > self.limit:
			self.cleanup()
		return data

	def clear( self ):
		self.data = {}

	def remove( self, key ):
		if self.data.has_key(key):
			del self.data[key]

	def cleanup( self ):
		self.lock.acquire()
		items = self.data.items()
		# FIXME: This is slooooow
		# We compare the hits
		items.sort(lambda a,b:cmp(a[1][1], b[1][1]))
		i = 0
		while self.weight > self.limit and i < len(items):
			del self.data[items[i][0]]
			self.weight -= items[i][1][0]
			i += 1
		self.lock.release()

class TimeoutCache(Cache):

	def __init__( self, cache, timeout=10 ):
		Cache.__init__(self)
		self.cache   = cache
		self.timeout = timeout
	
	def get( self, key ):
		if self.cache.has(key):
			value, insert_time = self.cache.get(key)
			if (time.time() - insert_time)  < self.timeout:
				return value
			else:
				return None
		else:
			return None
	
	def has( self, key ):
		if self.cache.has(key):
			value, insert_time = self.cache.get(key)
			if (time.time() - insert_time)  < self.timeout:
				return True
			else:
				return False
		else:
			return False

	def set( self, key, value ):
		self.cache.set(key, (value, time.time()))
		return value
	
	def clear( self ):
		self.cache.clear()

	def remove( self, key ):
		self.cache.remove(key)

class FileCache(Cache):
	"""A simplistic filesystem-based cache"""

	def __init__( self, path=None ):
		Cache.__init__(self)
		self.setPath(path)
		self.enabled = True
	
	def setPath( self, path ):
		path = path or "."
		assert os.path.exists(path)
		assert os.path.isdir(path)
		self.path = path

	def get( self, key ):
		if self.has(key):
			with file(self.path + "/" + self._normKey(key) + ".cache", 'r') as f:
				return self._load(f)
		else:
			return None

	def set( self, key, data ):
		with file(self.path + "/" + self._normKey(key) + ".cache", 'w') as f:
			self._save(data, f)
		return data

	def clear( self ):
		assert False, "Not implemented"
		
	def remove( self, key):
		if self.has(key):
			os.unlink(self.path + "/" + self._normKey(key) + ".cache")

	def has( self, key ):
		return os.path.exists(self.path + "/" + self._normKey(key) + ".cache")
	
	def _normKey( self, key ):
		key = urllib.urlencode(dict(_=key))
		return key[2:]
	
	def _save( self, data, fd ):
		try:
			return pickle.dump(data, fd)
		except Exception, e:
			print ("[!] FileCache._save:%s" % (e))
			return None

	def _load( self, fd ):
		try:
			return pickle.load(fd)
		except Exception, e:
			print ("[!] FileCache._load:%s" % (e))
			return None

class SignatureCache(Cache):
	"""A specific type of cache that takes a signature."""

	def __init__( self, backend=None ):
		Cache.__init__(self)
		# TODO: Add cache clearing functions
		self._cachedSig  = {}
		self._backend    = backend or MemoryCache()
		self.enabled     = True

	def cache( self, signatureFunction  ):
		"""A decorator that will memoize the result of the function as long as
		the 'signatureFunction' returns the same result. The signatureFunction
		takes the same arguments as the cached/decorated function."""
		def decorator(function):
			function_tag = repr(function)
			def cache_wrapper(*args):
				signature = signatureFunction(*args)
				if self._cachedSig.get(function_tag) != signatureFunction:
					result = function(*args)
					self._cachedSig [function_tag] = signature
					self._backend.set(function_tag, result)
					return result
				else:
					result = self._backend.get(function_tag)
					return result

	def clear( self ):
		self._cachedSig = {}
		self.backend.clear()

	def has( self, key, sig=0 ):
		"""Tells if this cache has the value for the given key and signature."""
		return self._cachedSig.has_key(key) and (self._cachedSig.get(key) == sig)
	
	def get( self, key, sig=0 ):
		"""Returns a couple (updaToDate, data) for the given key and
		signature. If the signature is different, then (False, None) is returned
		and the previous data is cleared from the cache."""
		if self._cachedSig.get(key) != sig:
			self._backend.remove(key)
			return False, None
		else:
			return True, self._backend.get(key)

	def set( self, key, sig, data ):
		"""Associates the given data with the give key and signature."""
		self._cachedSig[key]  = sig
		self._backend.set(key, data)
		return data

	@staticmethod
	def sha1(  path ):
		f = file(path, 'rb')
		t = f.read()
		f.close()
		return hashlib.sha1(t).hexdigest()

	@staticmethod
	def mtime( path):
		return  os.stat(path)[stat.ST_MTIME]

# EOF - vim: tw=80 ts=4 sw=4 noet
