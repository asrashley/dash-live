#!/bin/sh

# Updates the third party JavaScript libraries used by this app

if [ -d node_modules/wouter-preact/esm ]; then
    rm -rf static/js/prod/wouter-preact
    mkdir static/js/prod/wouter-preact
    cp -v node_modules/wouter-preact/esm/*.js static/js/prod/wouter-preact/
fi

if [ -d node_modules/preact ]; then
    rm -rf static/js/prod/preact
    mkdir -p static/js/prod/preact/hooks
    cp -v node_modules/preact/dist/preact.module.js static/js/prod/preact/
    cp -v node_modules/preact/hooks/dist/hooks.module.js static/js/prod/preact/hooks/
fi

if [ -d node_modules/@preact/signals ]; then
    rm -rf static/js/prod/preact/signals
    mkdir -p static/js/prod/preact/signals
    cp -v node_modules/@preact/signals/dist/signals.module.js static/js/prod/preact/signals/
fi

if [ -d node_modules/@preact/signals-core ]; then
    if [ ! -d static/js/prod/preact/signals ]; then
        mkdir -p static/js/prod/preact/signals
    fi
    cp -v node_modules/@preact/signals-core/dist/signals-core.module.js static/js/prod/preact/signals/
fi

if [ -d node_modules/htm/dist ]; then
    rm -rf static/js/prod/htm
    mkdir -p static/js/prod/htm/preact
    cp -v node_modules/htm/dist/htm.module.js static/js/prod/htm/
    cp -v node_modules/htm/preact/index.mjs static/js/prod/htm/preact/
fi

if [ -d node_modules/regexparam/dist ]; then
    rm -rf static/js/prod/regexparam
    mkdir static/js/prod/regexparam
    cp -fv node_modules/regexparam/dist/index.mjs static/js/prod/regexparam/
fi

if [ -d node_modules/linkstate/dist ]; then
    cp -vf node_modules/linkstate/dist/linkstate.module.js static/js/prod/
fi

if [ -d node_modules/temporal-polyfill ]; then
    rm -rf static/js/prod/temporal-polyfill
    mkdir -p static/js/prod/temporal-polyfill/chunks
    cp -v node_modules/temporal-polyfill/index.js static/js/prod/temporal-polyfill/
    cp -v node_modules/temporal-polyfill/chunks/*.js static/js/prod/temporal-polyfill/chunks/
fi
