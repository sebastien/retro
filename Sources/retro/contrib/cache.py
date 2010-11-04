#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Nov-2007
# Last mod  : 04-Nov-2010
# -----------------------------------------------------------------------------

import os, stat, hashlib, threading

# ------------------------------------------------------------------------------
#
# CACHE OBJECT
#
# ------------------------------------------------------------------------------

class MemoryCache:
	"""A simple cache system using a weighted LRU style dictionary."""

	def __init__( self, limit=100 ):
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

	def clear( self, key ):
		self.remove(key)

	def remove( self, key ):
		if self.has(key):
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

class TimeoutCache:

	def __init__( self, cache, timeout=10 ):
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
	
	def has( self, key )
		if self.cache.has(key):
			value, insert_time = self.cache.get(key)
			if (time.time() - insert_time)  < self.timeout:
				return True
			else:
				return False
		else:
			return False

	def set( self, key, value ):
		self.cache.set(key, (value, time.time())
		return value
	
	def clear( self, key ):
		self.cache.clear(key)

	def remove( self, key ):
		self.cache.remove(key)

class FileCache:
	"""A simplistic filesystem-based cache"""

	def __init__( self, path ):
		self.path = path
		self.enabled = True
		assert os.path.exists(path)
		assert os.path.isdir(path)

	def get( self, key ):
		if self.has(key):
			f = file(key + ".cache", 'r')
			c = f.read()
			f.close()
			return c
		else:
			return None

	def set( self, key, data ):
		f = file(key + ".cache", 'w')
		f.write(data)
		f.close()
		return data

	def clear( self, key ):
		self.remove(key)
		
	def remove( self, key):
		if self.has(key):
			os.unlink(key + ".cache")

	def has( self, key ):
		return os.path.exists(key + ".cache")

class SignatureCache:
	"""A specific type of cache that takes a signature."""

	def __init__( self, backend=None ):
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

	def has( self, key, sig=0 ):
		"""Tells if this cache has the value for the given key and signature."""
		return self._cachedSig.has_key(key) and (self._cachedSig.get(key) == sig)
	
	def get( self, key, sig=0 ):
		"""Returns a couple (updaToDate, data) for the given key and
		signature. If the signature is different, then (False, None) is returned
		and the previous data is cleared from the cache."""
		if self._cachedSig.get(key) != sig:
			self._backend.clear(key)
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
