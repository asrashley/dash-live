export interface MediaFile {
    bitrate: number;
    codec_fourcc: string;
    content_type: string;
    encrypted: boolean;
    name: string;
    pk: number;
    stream: number;
    track_id: number;
}
