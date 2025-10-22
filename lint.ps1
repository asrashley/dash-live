uv run -m flake8 dashlive tests --count --select=E9,F63,F7,F82 --show-source --statistics
uv run -m flake8 dashlive tests --count --ignore E302,E402,C901,W504 --exit-zero --max-complexity=10 --max-line-length=127 --statistics
npm run lint
npm run lint:compat
