from retro import ajax, on, run, Component

class Telephone(Component):

  def __init__( self ):
    Component.__init__(self)
    self.tube = []

  @ajax(GET="/listen")
  def listen( self ):
    if self.tube:
      m = self.tube[0] ; del self.tube[0]
      return m

  @ajax(GET="/say/{something:rest}")
  def say( self, something ):
    self.tube.append(something)

run(components=[Telephone()])
