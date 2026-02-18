#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dashlive.server.events.factory import EventFactory

from .dash_option import StringListDashOption
from .types import OptionUsage

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

EventSelection = StringListDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='evs',
    full_name='eventTypes',
    title='DASH events',
    description='A comma separated list of event formats',
    html=EV_HTML,
    cgi_name='events',
    cgi_type='<format>,..',
    cgi_choices=(None, 'ping', 'scte35'),
    input_type='multipleSelect',
    featured=True)

event_options = [EventSelection] + EventFactory.get_dash_options()
