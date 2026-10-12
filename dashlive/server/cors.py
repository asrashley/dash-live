#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import logging
from netifaces import interfaces, ifaddresses, AF_INET
import socket

def create_cors_allowed_origins(server_name: str, port: str, frontend_port: str, debug: bool) -> set[str]:
    if port == '80':
        port = ''
    else:
        port = f':{port}'
    frontend_port = f':{frontend_port}'

    cors_allowed_origins: set[str] = {
        f'http://127.0.0.1{port}',
        f'http://localhost{port}'
    }

    if server_name:
        cors_allowed_origins.add(f'http://{server_name}{port}')
        cors_allowed_origins.add(f'https://{server_name}{port}')

    if not debug:
        return cors_allowed_origins

    if server_name:
        cors_allowed_origins.add(f'http://{server_name}{frontend_port}')
        cors_allowed_origins.add(f'https://{server_name}{frontend_port}')

    cors_allowed_origins.add(f"http://127.0.0.1{frontend_port}")
    cors_allowed_origins.add(f"http://localhost{frontend_port}")

    for ifaceName in interfaces():
        for i in ifaddresses(ifaceName).setdefault(AF_INET, [{'addr': ''}]):  # type: ignore
            addr = i['addr']
            if not addr or addr.startswith('127'):
                continue
            cors_allowed_origins.add(f"http://{addr}{port}")
            cors_allowed_origins.add(f"http://{addr}{frontend_port}")
            try:
                hostname: str = socket.gethostbyaddr(addr)[0]
                cors_allowed_origins.add(f"http://{hostname}{port}")
                cors_allowed_origins.add(f"http://{hostname}{frontend_port}")
            except socket.herror as err:
                logging.warning('Failed to find hostname for IP address %s: %s', addr, err)

    return cors_allowed_origins
