export type MpsTrack = {
    codec_fourcc: string;
    content_type: string;
    encrypted: boolean;
    lang: string | null;
    pk: number;
    role: string;
    track_id: number;
    enabled?: boolean;
}
