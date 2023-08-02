#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .dash_option import DashOption

EV_HTML = '''
<p>A comma separated list of event formats:</p>
<ul>
  <li>
    <a href="#ping" class="link">ping</a> - produces a payload that alternates
    between 'ping' and 'pong'.
  </li>
  <li>
    <a href="#scte35" class="link">scte35</a> - SCTE35 events that alternate
    between placement opportunity start and end.
  </li>
</ul>
'''

EventSelection = DashOption(
    name='ev',
    title='DASH events',
    description='A comma separated list of event formats',
    html=EV_HTML,
    cgi_name='events',
    cgi_type='<format>,..',
    cgi_choices=(None, 'ping', 'scte35'),
    hidden=False)
