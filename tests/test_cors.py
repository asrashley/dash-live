import unittest
from unittest.mock import patch

from dashlive.server.cors import AF_INET, create_cors_allowed_origins


class CreateCorsAllowedOriginsTests(unittest.TestCase):
    def test_non_debug_origins_include_server_and_port(self):
        with patch('dashlive.server.cors.interfaces') as interfaces:
            origins = create_cors_allowed_origins('dash.example', '8080', '3000', False)

        self.assertEqual(origins, {
            'http://127.0.0.1:8080',
            'http://localhost:8080',
            'http://dash.example:8080',
            'https://dash.example:8080',
        })
        interfaces.assert_not_called()

    def test_port_80_omits_port(self):
        origins = create_cors_allowed_origins('dash.example', '80', '3000', False)

        self.assertEqual(origins, {
            'http://127.0.0.1',
            'http://localhost',
            'http://dash.example',
            'https://dash.example',
        })

    @patch('dashlive.server.cors.socket.gethostbyaddr', return_value=('media.example', [], []))
    @patch('dashlive.server.cors.ifaddresses')
    @patch('dashlive.server.cors.interfaces', return_value=['eth0'])
    def test_debug_origins_include_frontend_and_network_hosts(self, interfaces, ifaddresses, gethostbyaddr):
        ifaddresses.return_value = {
            AF_INET: [
                {'addr': '192.168.1.25'},
                {'addr': '127.0.0.1'},
                {'addr': ''},
            ]
        }

        origins = create_cors_allowed_origins('dash.example', '8000', '3000', True)

        self.assertEqual(origins, {
            'http://127.0.0.1:8000',
            'http://localhost:8000',
            'http://dash.example:8000',
            'https://dash.example:8000',
            'http://dash.example:3000',
            'https://dash.example:3000',
            'http://127.0.0.1:3000',
            'http://localhost:3000',
            'http://192.168.1.25:8000',
            'http://192.168.1.25:3000',
            'http://media.example:8000',
            'http://media.example:3000',
        })
        interfaces.assert_called_once_with()
        ifaddresses.assert_called_once_with('eth0')
        gethostbyaddr.assert_called_once_with('192.168.1.25')


if __name__ == '__main__':
    unittest.main()
