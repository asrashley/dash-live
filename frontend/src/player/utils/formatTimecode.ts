export interface TimeObject {
    hours: number;
    minutes: number;
    seconds: number;
}

function pad(num: number): string {
    return `00${num}`.slice(-2);
}

export function createTimeObject(secs: number): TimeObject {
    const hours = Math.floor(secs / 3600);
    const minutes = Math.floor(secs / 60) % 60;
    const seconds = Math.floor(secs) % 60;
    return { hours, minutes, seconds };
}

export function timeObjectToString({ hours, minutes, seconds }: TimeObject): string {
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}