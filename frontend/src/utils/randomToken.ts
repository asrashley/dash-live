const chars = 'abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ_=+#.,&!-';

export function randomToken(length: number): string {
    const array = new Uint8Array(length);
    crypto.getRandomValues(array);
    const token: string[] = [...array].map((value: number) => chars.charAt(value % chars.length));
    return token.join('');
}

