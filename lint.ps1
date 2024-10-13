python -m flake8 dashlive tests --count --select=E9,F63,F7,F82 --show-source --statistics
python -m flake8 dashlive tests --count --ignore E302,E402,C901,W504 --exit-zero --max-complexity=10 --max-line-length=127 --statistics
npx jshint ./static/js/legacy/*.js static/js/compat/*.js
npx eslint ./static/js/*.js ./static/js/spa/**/*.js
