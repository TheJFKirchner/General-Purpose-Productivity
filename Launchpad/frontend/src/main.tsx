/* Entry: global styles, connect the bridge (websocket or in-page demo), render the shell. */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './fonts.css';
import './theme.css';
import App from './App';
import { connect } from './bridge';

connect();
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
