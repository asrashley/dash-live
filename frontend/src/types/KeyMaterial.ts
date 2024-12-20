export interface KeyMaterial {
    alg: "AESCTR";
    computed: boolean;
    key: string;
    kid: string;
}
