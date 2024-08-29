#!/bin/bash
python -m flake8 dashlive tests --count --select=E9,F63,F7,F82 --show-source --statistics
python -m flake8 dashlive tests --count --ignore E302,E402,C901,W504 --exit-zero --max-complexity=10 --max-line-length=127 --statistics
npx jshint ./static/js/*.js ./static/js/legacy/*.js
