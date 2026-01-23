#!/bin/bash

cd /home/dash/dash-live

uv sync --all-extras --locked

uv run pytest -n auto
