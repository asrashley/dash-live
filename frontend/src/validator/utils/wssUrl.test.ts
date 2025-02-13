import { describe, expect, test } from "vitest"
import { wssUrl } from "./wssUrl";

describe('wssUrl function', () => {

    test('generates WS url without a server port', () => {
        window["_SERVER_PORT_"] = null;
        const url = new URL('http://localhost:3000/');
        expect(wssUrl(url)).toEqual('ws://localhost:3000/');
    });

    test('generates WSS url without a server port', () => {
        window["_SERVER_PORT_"] = null;
        const url = new URL('https://localhost:3000/');
        expect(wssUrl(url)).toEqual('wss://localhost:3000/');
    });

    test('generates WS url with _SERVER_PORT_', () => {
        window["_SERVER_PORT_"] = 5000;
        const url = new URL('http://localhost:3000/');
        expect(wssUrl(url)).toEqual('ws://localhost:5000/');
    });
});