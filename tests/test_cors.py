from typing import ClassVar, NamedTuple
import unittest
from unittest.mock import patch

from ifaddr import IP

from dashlive.server.cors import create_cors_allowed_origins

class IPv6Address(NamedTuple):
    address: str
    prefix_length: int
    scope_id: int

class CreateCorsAllowedOriginsTests(unittest.TestCase):
    IPV4_EXAMPLE: ClassVar[str] = '192.168.1.25'
    IPV4_EXAMPLE_2: ClassVar[str] = '192.168.1.87'
    IPV6_EXAMPLE: ClassVar[IPv6Address] = IPv6Address('284c:d849:ffac:2f10:feff:37e8:389e:829d', 48, 0x30)
    IPV6_EXAMPLE_2: ClassVar[IPv6Address] = IPv6Address('c789:f12f:a78f:781a:b52e:eebc:fe8b:1e51', 48, 0x32)
    IPV6_EXAMPLE_3: ClassVar[IPv6Address] = IPv6Address('fe80::e817:18ff:fe03:4547', 64, 0x20)
    HOSTNAMES: ClassVar[dict[str, tuple[str, list[str]]]] = {
        IPV4_EXAMPLE: ('host.local', []),
        IPV4_EXAMPLE_2: ('host2.local', ['alias.local']),
        IPV6_EXAMPLE.address: ('host6.local', []),
        IPV6_EXAMPLE_2.address: ('host2-6.local', []),
    }

    @classmethod
    def get_host_by_addr(cls, addr: str) -> tuple[str, list[str], list[str]]:
        try:
            hostname, aliases = cls.HOSTNAMES[addr]
            return (hostname, aliases, [],)
        except KeyError:
            pass
        return ('', [], [])

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_include_server_and_port(self, gethostbyaddr, get_adapters) -> None:
        get_adapters.return_value = []
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        origins = create_cors_allowed_origins('dash.example', 8080, None, enable_ipv6=False)

        expected = {
            'http://127.0.0.1:8080',
            'http://localhost:8080',
            'http://dash.example:8080',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_discards_ipv6_addresses(self, gethostbyaddr, get_adapters) -> None:
        get_adapters.return_value = [
            type('Adapter', (), {
                'ips': [
                    IP('127.0.0.1', 1, 'lo'),
                    IP('::1', 1, 'lo'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP(CreateCorsAllowedOriginsTests.IPV4_EXAMPLE, 2, 'eth0'),
                    IP(CreateCorsAllowedOriginsTests.IPV6_EXAMPLE, 2, 'eth0'),
                ]}),
        ]

        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        origins = create_cors_allowed_origins('dash.example', 8080, None, enable_ipv6=False)

        expected = {
            'http://127.0.0.1:8080',
            'http://localhost:8080',
            'http://dash.example:8080',
            f'http://{self.IPV4_EXAMPLE}:8080',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}:8080',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_includes_aliases(self, gethostbyaddr, get_adapters) -> None:
        get_adapters.return_value = [
            type('Adapter', (), {
                'ips': [
                    IP('127.0.0.1', 1, 'lo'),
                    IP('::1', 1, 'lo'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP(CreateCorsAllowedOriginsTests.IPV4_EXAMPLE_2, 2, 'eth0'),
                    IP(CreateCorsAllowedOriginsTests.IPV6_EXAMPLE_2, 2, 'eth0'),
                ]}),
        ]
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        origins = create_cors_allowed_origins('dash.example', 8080, None, enable_ipv6=False)

        expected = {
            'http://127.0.0.1:8080',
            'http://localhost:8080',
            'http://dash.example:8080',
            f'http://{self.IPV4_EXAMPLE_2}:8080',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE_2][0]}:8080',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE_2][1][0]}:8080',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_port_80_omits_port(self, gethostbyaddr, get_adapters) -> None:
        get_adapters.return_value = []
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        origins = create_cors_allowed_origins('dash.example', 80, None, enable_ipv6=False)
        expected = {
            'http://127.0.0.1',
            'http://localhost',
            'http://dash.example',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_port_80_omits_port_ipv6(self, gethostbyaddr, get_adapters) -> None:
        get_adapters.return_value = []
        gethostbyaddr.return_value = ('', [], [])
        origins = create_cors_allowed_origins('dash.example', 80, None, enable_ipv6=True)
        expected = {
            'http://127.0.0.1',
            'http://[::1]',
            'http://localhost',
            'http://dash.example',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_port_80_omits_port_with_frontend_port(self, gethostbyaddr, get_adapters) -> None:
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        get_adapters.return_value = [
            type('Adapter', (), {
                'ips': [
                    IP('127.0.0.1', 1, 'lo'),
                    IP('::1', 1, 'lo'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP(CreateCorsAllowedOriginsTests.IPV4_EXAMPLE, 2, 'eth0'),
                    IP(CreateCorsAllowedOriginsTests.IPV6_EXAMPLE, 2, 'eth0'),
                ]}),
        ]
        origins = create_cors_allowed_origins('dash.example', 80, 3000, enable_ipv6=False)
        expected = {
            'http://127.0.0.1',
            'http://127.0.0.1:3000',
            'http://localhost',
            'http://localhost:3000',
            'http://dash.example',
            'http://dash.example:3000',
            f'http://{self.IPV4_EXAMPLE}',
            f'http://{self.IPV4_EXAMPLE}:3000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}:3000',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_port_80_omits_port_with_frontend_port_ipv6(self, gethostbyaddr, get_adapters) -> None:
        get_adapters.return_value = []
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        origins = create_cors_allowed_origins('dash.example', 80, 3000, enable_ipv6=True)
        expected = {
            'http://127.0.0.1',
            'http://[::1]',
            'http://localhost',
            'http://dash.example',
            'https://dash.example',
            'http://127.0.0.1:3000',
            'http://[::1]:3000',
            'http://localhost:3000',
            'http://dash.example:3000',
            'https://dash.example:3000',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_origins_include_frontend_and_network_hosts(self, gethostbyaddr, get_adapters):
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        get_adapters.return_value = [
            type('Adapter', (), {
                'ips': [
                    IP('127.0.0.1', 1, 'lo'),
                    IP('::1', 1, 'lo'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP(self.IPV4_EXAMPLE, 2, 'eth0'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP(self.IPV4_EXAMPLE_2, 3, 'eth1'),
                ]})
        ]

        origins = create_cors_allowed_origins('dash.example', 8000, 3000, enable_ipv6=False)

        expected = {
            'http://127.0.0.1:8000',
            'http://127.0.0.1:3000',
            'http://localhost:8000',
            'http://localhost:3000',
            'http://dash.example:8000',
            'http://dash.example:3000',
            f'http://{self.IPV4_EXAMPLE}:8000',
            f'http://{self.IPV4_EXAMPLE}:3000',
            f'http://{self.IPV4_EXAMPLE_2}:8000',
            f'http://{self.IPV4_EXAMPLE_2}:3000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}:8000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}:3000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE_2][0]}:8000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE_2][0]}:3000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE_2][1][0]}:8000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE_2][1][0]}:3000',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_debug_origins_include_frontend_and_network_hosts_ipv6(self, gethostbyaddr, get_adapters):
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        get_adapters.return_value = [
            type('Adapter', (), {
                'ips': [
                    IP('127.0.0.1', 1, 'lo'),
                    IP('::1', 1, 'lo'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP(CreateCorsAllowedOriginsTests.IPV4_EXAMPLE, 2, 'eth0'),
                    IP(CreateCorsAllowedOriginsTests.IPV6_EXAMPLE, 2, 'eth0'),
                ]}),
        ]

        origins = create_cors_allowed_origins('dash.example', 8000, 3000, enable_ipv6=True)

        expected = {
            'http://127.0.0.1:8000',
            'http://127.0.0.1:3000',
            'http://localhost:8000',
            'http://localhost:3000',
            'http://[::1]:8000',
            'http://[::1]:3000',
            'http://dash.example:8000',
            'http://dash.example:3000',
            f'http://{self.IPV4_EXAMPLE}:8000',
            f'http://{self.IPV4_EXAMPLE}:3000',
            f'http://[{self.IPV6_EXAMPLE.address}]:8000',
            f'http://[{self.IPV6_EXAMPLE.address}]:3000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}:8000',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}:3000',
            f'http://{self.HOSTNAMES[self.IPV6_EXAMPLE.address][0]}:8000',
            f'http://{self.HOSTNAMES[self.IPV6_EXAMPLE.address][0]}:3000',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

    @patch('dashlive.server.cors.ifaddr.get_adapters')
    @patch('dashlive.server.cors.socket.gethostbyaddr')
    def test_doesnt_resolve_link_local_addresses(self, gethostbyaddr, get_adapters) -> None:
        get_adapters.return_value = [
            type('Adapter', (), {
                'ips': [
                    IP(self.IPV4_EXAMPLE, 10, 'eth0'),
                    IP(self.IPV6_EXAMPLE, 10, 'eth0'),
                    IP(self.IPV6_EXAMPLE_3, 10, 'eth0'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP('127.0.0.1', 1, 'lo'),
                ]}),
            type('Adapter', (), {
                'ips': [
                    IP('169.254.90.81', 1, 'eth1'),
                ]}),
        ]
        gethostbyaddr.side_effect = CreateCorsAllowedOriginsTests.get_host_by_addr
        origins = create_cors_allowed_origins('dash.example', 8080, None, enable_ipv6=True)
        expected: set[str] = {
            'http://127.0.0.1:8080',
            'http://[::1]:8080',
            'http://localhost:8080',
            'http://dash.example:8080',
            'http://169.254.90.81:8080',
            f'http://{self.IPV4_EXAMPLE}:8080',
            f'http://[{self.IPV6_EXAMPLE.address}]:8080',
            f'http://[{self.IPV6_EXAMPLE_3.address}]:8080',
            f'http://{self.HOSTNAMES[self.IPV4_EXAMPLE][0]}:8080',
            f'http://{self.HOSTNAMES[self.IPV6_EXAMPLE.address][0]}:8080',
        }
        for url in list(expected):
            expected.add(url.replace('http://', 'https://'))
        self.assertEqual(origins, expected)

        called_addresses: list[str] = [call.args[0] for call in gethostbyaddr.call_args_list]
        self.assertNotIn('169.254.90.81', called_addresses)
        self.assertNotIn(self.IPV6_EXAMPLE_3.address, called_addresses)


if __name__ == '__main__':
    unittest.main()
