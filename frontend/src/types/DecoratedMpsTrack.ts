import { MpsTrack } from "./MpsTrack";


export type DecoratedMpsTrack = Omit<MpsTrack, 'enabled'> & {
    enabled: boolean;
    clearBitrates: number;
    encryptedBitrates: number;
};
