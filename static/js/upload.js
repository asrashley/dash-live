import { enableTooltips } from './tooltips.js';

function enableCopyToClipboard() {
    const btn = document.getElementById("copy-to-clipboard");
    if (!btn) {
        return;
    }
    if (navigator.clipboard) {
        btn.addEventListener('click', (ev) => {
            ev.preventDefault();
            const cmd = document.getElementById("upload-command");
            if (cmd) {
                navigator.clipboard.writeText(cmd.innerText ?? cmd.innerHTML);
            }
        });
        btn.classList.remove("visually-hidden");
    }
}

enableTooltips();
enableCopyToClipboard();