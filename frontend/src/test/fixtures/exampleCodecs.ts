import { CodecInformation } from "../../validator/types/CodecInformation";

export const exampleCodecs: CodecInformation[] = [
    {
        codec: "avc3.640028",
        details: [
            {
                label: "AVC/H.264",
                details: [
                    "profile_idc=100 constraint_set=0 level_idc=40",
                    "profile=High (64)",
                    "constraints=------",
                    "level=4 (28)",
                ],
            },
        ],
    },
    {
        codec: "mp4a.40.2",
        details: [
            {
                label: "AAC",
                details: ["MPEG-4 AAC (40)", "Low-Complexity AAC (2)"],
            },
        ],
    },
];
