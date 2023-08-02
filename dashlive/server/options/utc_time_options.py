#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import DashOption

ClockDrift = DashOption(
    name='dft',
    title='Clock drift',
    description='Number of seconds of delay to add to wall clock time',
    cgi_name='drift',
    cgi_type='<seconds>',
    cgi_choices=(None, 10),
    usage={'manifest', 'time'})

UTCMethod = DashOption(
    name='utc',
    title='UTC timing method',
    description='Select UTCTiming element method.',
    cgi_name='time',
    cgi_choices=(None, 'direct', 'head', 'http-ntp', 'iso', 'ntp', 'sntp', 'xsd'),
    hidden=False,
    usage={'manifest'})

UTCValue = DashOption(
    name='utv',
    title='UTC value',
    description='Sets the value attribute of the UTCTiming element',
    cgi_name='time_value',
    cgi_type='<string>',
    usage={'time'})

time_options = [
    ClockDrift,
    UTCMethod,
    UTCValue
]
