import time
import socket
from urllib.parse import urlparse

def wait_for_service( service_url ):
    
    url = urlparse( service_url )
    host = url.hostname
    port = url.port

    while True:
        try:
            with socket.create_connection( (host, port) ):
                break
        except:
            time.sleep(1)