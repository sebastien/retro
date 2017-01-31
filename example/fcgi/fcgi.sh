#!/bin/sh
# This simple script runs Lighttpd with 'fcgi.js' as FastCGI script

cd $(dirname $0)
rwdir=$PWD
echo "

Once it starts up, load
  http://localhost:8888/applications/fcgi/index.js
in your web browser for enjoyment of fcgi javascripts!

"

sed "s|ROOT|$rwdir|g" < $PWD/fcgi.conf > /tmp/rw-fcgi.conf && \
    lighttpd -D -f "/tmp/rw-fcgi.conf"
#EOF
