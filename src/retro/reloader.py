#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 10-Nov-2010
# Last mod  : 10-Nov-2010
# -----------------------------------------------------------------------------

import builtins

# FROM: http://www.indelible.org/ink/python-reloading/

class ModuleDependencyTracker:

	BASEIMPORT   = builtins._Import__
	DEPENDENCIES = dict()
	OLD_IMPORT   = None
	PARENT       = None

	@classmethod
	def Install( self ):
		if self.OLD_IMPORT is None:
			self.OLD_IMPORT     = builtins.__import__
			builtins.__import__ = self.Import
		
	@classmethod
	def GetDependencies(self, m):
		"""Get the dependency list for the given imported module."""
		return ModuleDependencyTracker.DEPENDENCIES.get(m.__name__, None)

	@classmethod
	def Import(self, name, globals=None, locals=None, fromlist=None, level=-1):
		# Track our current parent module.  This is used to find our current
		# place in the dependency graph.
		parent  = ModuleDependencyTracker.PARENT
		PARENT = name
		# Perform the actual import using the base import function.
		m       = ModuleDependencyTracker.BASEIMPORT(name, globals, locals, fromlist, level)
		# If we have a parent (i.e. this is a nested import) and this is a
		# reloadable (source-based) module, we append ourself to our parent's
		# dependency list.
		if parent is not None and hasattr(m, '__file__'):
			l = ModuleDependencyTracker.DEPENDENCIES.setdefault(parent, [])
			l.append(m)
		# Lastly, we always restore our global PARENT pointer.
		ModuleDependencyTracker.PARENT = parent
		return m

ModuleDependencyTracker.Install()

# FROM: http://www.indelible.org/ink/python-reloading/
