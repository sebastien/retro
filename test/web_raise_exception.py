from retro import *

class RaiseException(Component):

	@on(GET="{path:rest}")
	def raiseException( self, request, path ):
		return Exception("RaiseException: {0}".format(path))

if __name__ == "__main__":
	run(components=[RaiseException()])
