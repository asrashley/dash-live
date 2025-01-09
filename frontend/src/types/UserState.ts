export interface InitialUserState {
    pk?: number;
    username?: string;
    email?: string;
    last_login?: string;
    isAuthenticated: boolean;
    groups: string[];
}

export interface UserState extends InitialUserState {
    permissions: {
        admin: boolean,
        media: boolean,
        user: boolean,
    }
}