#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

class ValidationException(Exception):
    def __init__(self, args):
        super().__init__(args)


class MissingSegmentException(ValidationException):
    def __init__(self, url, response):
        msg = 'Failed to get segment: {:d} {} {}'.format(
            response.status_code, response.status, url)
        super().__init__(
            (msg, url, response.status))
        self.url = url
        self.status = response.status_code
        self.reason = response.status
