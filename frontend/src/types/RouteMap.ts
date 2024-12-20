export type RouteEntry = {
    title: string;
    re: RegExp;
    route: string,
    url: (props?: object) => string;
};

export type RouteMap = {
    [name: string]: RouteEntry;
};
