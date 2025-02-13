declare const _SERVER_PORT_: number | null;

export interface WssUrlProps {
  protocol: URL["protocol"];
  hostname: URL["hostname"];
  port: URL["port"];
}
export function wssUrl({ protocol, hostname, port }: WssUrlProps): string {
  const wsProto = protocol === 'http:' ? 'ws://' : 'wss://';
  return `${wsProto}${hostname}:${_SERVER_PORT_ ?? port}/`;
}
