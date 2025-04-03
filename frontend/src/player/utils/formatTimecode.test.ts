import { describe, expect, test } from "vitest";
import { createTimeObject, TimeObject, timeObjectToString } from "./formatTimecode";

describe('time formatting functions', () => {
    test.each<[number, TimeObject]>([
        [0, { hours: 0, minutes: 0, seconds: 0 }],
        [23, { hours: 0, minutes: 0, seconds: 23 }],
        [83, { hours: 0, minutes: 1, seconds: 23 }],
        [7283, { hours: 2, minutes: 1, seconds: 23 }],
    ])('creates time object from %d seconds to %j', (secs: number, expected: TimeObject) => {
        expect(createTimeObject(secs)).toEqual(expected);
    });
    test.each<[TimeObject, string]>([
        [{ hours: 0, minutes: 0, seconds: 0 }, '00:00:00'],
        [{ hours: 0, minutes: 0, seconds: 23 }, '00:00:23'],
        [{ hours: 0, minutes: 1, seconds: 23 }, '00:01:23'],
        [{ hours: 2, minutes: 1, seconds: 23 }, '02:01:23'],
    ])('formats time object %j to string %s', (timeObj: TimeObject, expected: string) => {
        expect(timeObjectToString(timeObj)).toEqual(expected);
    });
});