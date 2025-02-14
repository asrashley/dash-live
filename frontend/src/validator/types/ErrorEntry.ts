import { AssertionLocation } from "./AssertionLocation";

export interface ErrorEntry {
    assertion: AssertionLocation;
    location: [number, number];
    clause?: string;
    msg: string;
}