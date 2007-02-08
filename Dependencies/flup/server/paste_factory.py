def helper(wsgiServerClass, global_conf, host, port, **local_conf):
    # I think I can't write a tuple for bindAddress in .ini file
    host = host or global_conf.get('host', 'localhost')
    port = port or global_conf.get('port', 4000)

    local_conf['bindAddress'] = (host, int(port))
    
    def server(application):
        server = wsgiServerClass(application, **local_conf)
        server.run()

    return server
