import { describe, expect, test } from "vitest";

import { ValidatorSettings } from "../types/ValidatorSettings";
import { checkValidatorSettings } from "./checkValidatorSettings";
import { decorateAllStreams } from "../../hooks/useAllStreams";

import allStreamsFixture from "../../test/fixtures/streams.json";

describe("checkValidatorSettings", () => {
    const allStreams = decorateAllStreams(allStreamsFixture.streams);
    const goodSettings: ValidatorSettings = {
        duration: 20,
        manifest: 'http://unit.test.local/manifest.mpd',
        encrypted: false,
        media: false,
        prefix: "",
        pretty: false,
        save: false,
        title: "",
        verbose: false,
    };

    test('invalid duration', () => {
        const settings = {
            ...goodSettings,
            duration: 0,
        };
        expect(checkValidatorSettings(settings, allStreams)).toEqual({
            duration: "duration must be >= 1 second and <= 3600 seconds",
        });
    });

    test('no manifest', () => {
        const settings = {
            ...goodSettings,
            manifest: "",
        };
        expect(checkValidatorSettings(settings, allStreams)).toEqual({
            manifest: "manifest URL is required",
        });
    });

    test('valid, not saving stream', () => {
        expect(checkValidatorSettings(goodSettings, allStreams)).toEqual({});
    });

    test('save with missing directory and title', () => {
        const settings = {
            ...goodSettings,
            save: true,
        };
        expect(checkValidatorSettings(settings, allStreams)).toEqual({
            prefix: "a directory name is required",
            title: "a title is required",
        });
    });

    test('duplicate directory name', () => {
        const settings = {
            ...goodSettings,
            save: true,
            title: 'a new title',
            prefix: allStreams[0].directory,
        };

        expect(checkValidatorSettings(settings, allStreams)).toEqual({
            prefix: `a stream already exists with name ${settings.prefix}`
        });
    });

    test('valid, saving stream', () => {
        const settings = {
            ...goodSettings,
            save: true,
            title: 'a new title',
            prefix: 'new.prefix',
        };
        expect(checkValidatorSettings(settings, allStreams)).toEqual({});
    });
});
