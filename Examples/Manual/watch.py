from railways import ajax, on, run, Component
import time

class Watch(Component):

  @on(GET="/time")
  def getTime( self, request ):
    def stream():
      while True:
        yield "<html><body><pre>%s</pre></body></html>" % (time.ctime())
        time.sleep(1)
    return request.respondMultiple(stream())

run(components=[Watch()])
