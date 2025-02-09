export interface CodecDetails {
    label: string;
    error?: string;
    details: string[];
}

export interface CodecInformation {
    codec: string;
    error?: string;
    details: CodecDetails[];
}
