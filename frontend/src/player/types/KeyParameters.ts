export type KeyParameters = {
    alg: string;
    kid: string; // hex encoded
    key: string; // hex encoded
    guidKid: string;
    b64Key: string; // base64 encoded
    computed: boolean;
};
