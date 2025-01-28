export type InitialUserState = {
    pk?: number;
    username?: string;
    email?: string;
    lastLogin: string | null;
    mustChange: boolean;
    groups: string[];
}

export type UserState = InitialUserState & {
    isAuthenticated: boolean;
    permissions: {
        admin: boolean,
        media: boolean,
        user: boolean,
    }
}