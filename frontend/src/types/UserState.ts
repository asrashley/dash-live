export interface InitialUserState {
    isAuthenticated: boolean,
    groups: string[],
}

export interface UserState extends InitialUserState {
    permissions: {
        admin: boolean,
        media: boolean,
        user: boolean,
    }
}