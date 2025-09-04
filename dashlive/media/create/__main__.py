#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import sys

from dashlive.media.create.create import DashMediaCreator

sys.exit(DashMediaCreator.main(sys.argv[1:]))
