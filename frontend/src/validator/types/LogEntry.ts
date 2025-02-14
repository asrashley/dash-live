export type LogEntry = {
    id: number;
    level: 'error' | 'info' | 'debug';
    text: string;
};
