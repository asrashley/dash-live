export type CgiOptionChoice = [string, string];

export type OptionUsage = 'manifest' | 'video' | 'audio' | 'text' | 'time' | 'html';

export interface CgiOptionDescription {
    featured: boolean;
    description: string;
    name: string;
    options: CgiOptionChoice[];
    syntax: string;
    title: string;
    usage: OptionUsage[];
}
