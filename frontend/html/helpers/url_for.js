export default function urlFor(name, ...args) {
    switch (name) {
        case 'es5-home':
            return '/es5/';
        case 'static':
            return `/static/${args[0]}`;
        default:
            throw new Error(`unsupported URL ${name}`);
    }
}