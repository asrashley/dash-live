# Testing

## Unit Tests

Install the required test libraries:

```sh
pip install -r dev-requirements.txt
```

The quickest way to run the unit tests is to use pytest to run
multiple tests in parallel.

```sh
pytest -n auto
```

It is also possible run all unit tests using Python's built-in test
framework. This will take quite a long time (e.g. 10 minutes) to
complete:

```sh
python -m unittest
```

It is also possible to run the set of tests for one area by providing
the name of the Python file containing the tests:

```sh
python -m tests.test_mp4
```

Will run every test in the [tests/test_mp4.py](./tests/test_mp4.py) file.

To specify one or more tests within that test file, a list of test
functions can also be added to the command line:

```sh
python -m tests.test_views TestHandlers.test_availability_start_time
```

To run the unit tests inside a Docker container:

```sh
docker build -t dashlive  .
docker run --mount type=bind,source=`pwd`/tests,destination=/home/dash/dash-live/tests \
    -it --entrypoint /home/dash/dash-live/runtests.py dashlive
```

## Code Coverage

To check test code coverage:

```sh
coverage run -m pytest
coverage html
```

This will create a `htmlcov` directory containing a `./htmlcov/index.html`
file. That `index.html` file contains information about the code coverage
of all of unit tests.
