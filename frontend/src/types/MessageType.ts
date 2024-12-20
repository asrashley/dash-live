export type MessageLevel = 'success' | 'danger' | 'warning' | 'info';

export interface MessageType {
    id: number;
    text: string;
    footer?: string;
    level: MessageLevel;
}
