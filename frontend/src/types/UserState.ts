export interface InitialUserState {
    pk?: number;
    username?: string;
    email?: string;
    last_login?: string;
    groups: string[];
}

export interface UserState extends InitialUserState {
    isAuthenticated: boolean;
    permissions: {
        admin: boolean,
        media: boolean,
        user: boolean,
    }
}