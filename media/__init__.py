#

import V1, V2, V3, A1, A2, V1ENC, V2ENC, V3ENC, A1ENC

import os
from segment import Representation, Segment

representations = { 'V1':V1.representation, 
                    'V2':V2.representation, 
                    'V3':V3.representation,
                    'V1ENC':V1ENC.representation,
                    'V2ENC':V2ENC.representation,
                    'V3ENC':V3ENC.representation,
                    'A1':A1.representation,
                    'A2':A2.representation,
                    'A1ENC':A1ENC.representation,
                    }
#                    'A2ENC':A2ENC.representation,
