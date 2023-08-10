#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dashlive.server.events.factory import EventFactory

from .dash_option import DashOption
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

EventSelection = DashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO),
    short_name='evs',
    full_name='eventTypes',
    title='DASH events',
    description='A comma separated list of event formats',
    from_string=DashOption.list_without_none_from_string,
    to_string=lambda evs: ','.join(evs),
    html=EV_HTML,
    cgi_name='events',
    cgi_type='<format>,..',
    cgi_choices=(None, 'ping', 'scte35'),
    hidden=False)

event_options = [EventSelection] + EventFactory.get_dash_options()
