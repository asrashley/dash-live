declare module "codec-string" {
    export interface DecodedValue {
        decode?: string;
        warning?: string;
        error?: string;
        title?: string;
    }

    export interface DecodedCodec {
        label: string;
        error?: string;
        parsed: DecodedValue[];
    }

    export interface DecodeResult {
        error?: string;
        decodes: DecodedCodec[];
    }

    export function decode(codecString: string): DecodeResult;
}
