/* Bridge: the one link between the page and the Python back end.
   - Real mode: ws://127.0.0.1:<port>/ws?code=<code>, used when the page URL has ?port=&code= (the server checks
     the access code and the Origin)
   - Demo mode: no ?port / &code -> the scripted fake back end in src/demo runs in the page (?speed=N = N times faster)
   Server events go to dispatch() (the store); UI messages go out through send(). */
import type { UiMessage } from './contract';
import { actions, dispatch } from './store';
import { setTransport } from './store/core';
import { Demo } from './demo/Demo';

let ws: WebSocket | null = null;
let demo: Demo | null = null;

const params = (): URLSearchParams => new URLSearchParams(typeof location !== 'undefined' ? location.search : '');

/** Send one message. Returns false (and toasts "Not connected") when it could not go out. */
export function send(msg: UiMessage): boolean {
  if (demo) { demo.receive(msg); return true; }
  if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify(msg)); return true; }
  queueMicrotask(() => actions.toast('Not connected'));
  return false;
}
setTransport(send);


/** Connect once at start-up: the websocket when the URL has port + code, else the in-page demo. */
export function connect(): void {
  const q = params(), port = q.get('port'), code = q.get('code');
  if (!port || !code) {
    actions.setDemo(true);
    actions.setConn('Demo mode', 'var(--green)');
    demo = new Demo(dispatch, Math.max(0.1, +(q.get('speed') || 1) || 1), !!q.get('vistest'));
    demo.start();
    return;
  }
  actions.setDemo(false);
  actions.setConn('Connecting…', 'var(--lilac)');
  ws = new WebSocket(`ws://127.0.0.1:${encodeURIComponent(port)}/ws?code=${encodeURIComponent(code)}`);
  ws.onopen = () => { actions.setConn('Connected', 'var(--green)'); send({ type: 'get_settings' }); };
  ws.onclose = () => actions.setConn('Disconnected', 'var(--coral)');
  ws.onmessage = e => { try { dispatch(JSON.parse(e.data)); } catch (err) { console.error(err); } };
}
