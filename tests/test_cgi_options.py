import unittest

from dashlive.server.options.cgi_options import get_cgi_options, get_dash_options

class DateTimeTests(unittest.TestCase):
    def test_option_names_are_unique(self) -> None:
        names: set[str] = set()
        for opt in get_dash_options():
            self.assertNotIn(opt.name, names)
            names.add(opt.name)

    def test_cgi_option_names_are_unique(self) -> None:
        names: set[str] = set()
        for opt in get_dash_options():
            if isinstance(opt.cgi_name, list):
                for name in opt.cgi_name:
                    self.assertNotIn(name, names)
                    names.add(name)
            else:
                self.assertNotIn(opt.cgi_name, names)
                names.add(opt.cgi_name)

    def test_get_cgi_options(self) -> None:
        names: set[str] = set()
        for opt in get_cgi_options():
            self.assertNotIn(opt.name, names)
            names.add(opt.name)


if __name__ == "__main__":
    unittest.main()
