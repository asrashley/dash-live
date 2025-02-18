export type InitialUserState = {
    pk?: number;
    username?: string;
    email?: string;
    lastLogin: string | null;
    mustChange: boolean;
    groups: string[];
};
