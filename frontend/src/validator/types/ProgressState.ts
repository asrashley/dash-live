export interface ProgressState {
    currentValue?: number;
    minValue: number;
    maxValue: number;
    text: string;
    finished?: boolean;
    error?: boolean;
 }
