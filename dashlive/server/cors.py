#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import logging
from typing import cast
import ifaddr
import socket

def is_localhost(address: str) -> bool:
    local_name: set[str] = {
        'localhost', '::1', 'ip6-localhost', 'ip6-loopback'
    }
    return address.startswith('127.') or address in local_name

def is_link_local(address: str) -> bool:
    if ':' in address:
        return address.startswith('fe80:')
    return address.startswith('169.254.')

def create_cors_allowed_origins(server_name: str, port: int, frontend_port: int | None, enable_ipv6: bool) -> set[str]:
    origins: set[str] = {
        '127.0.0.1',
        'localhost'
    }
    if enable_ipv6:
        origins.add('::1')

    if server_name:
        origins.add(server_name)

    adapters = ifaddr.get_adapters()
    for adapter in adapters:
        for addr in adapter.ips:
            if addr.is_IPv6 and not enable_ipv6:
                continue
            addr_str: str
            if addr.is_IPv4:
                addr_str = cast(str, addr.ip)
            else:
                addr_str = addr.ip[0]
            if is_localhost(addr_str):
                continue
            origins.add(addr_str)
            if is_link_local(addr_str):
                continue
            try:
                hostname, aliaslist, _ = socket.gethostbyaddr(addr_str)
                if hostname:
                    origins.add(hostname)
                for alias in aliaslist:
                    origins.add(alias)
            except socket.herror as err:
                logging.warning('Failed to find hostname for IP address %s: %s', addr, err)

    port_str: str = f':{port}'
    if port == 80:
        port_str = ''
    frontend_port_str: str = ''
    if frontend_port is not None:
        frontend_port_str = f':{frontend_port}'

    cors_allowed_origins: set[str] = set()
    for origin in origins:
        origin_str: str = origin
        if ':' in origin:
            origin_str = f'[{origin}]'
        cors_allowed_origins.add(f'http://{origin_str}{port_str}')
        cors_allowed_origins.add(f'https://{origin_str}{port_str}')
        if frontend_port is not None:
            cors_allowed_origins.add(f'http://{origin_str}{frontend_port_str}')
            cors_allowed_origins.add(f'https://{origin_str}{frontend_port_str}')

    return cors_allowed_origins
