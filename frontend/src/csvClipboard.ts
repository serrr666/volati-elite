import {tr} from './i18n';

const MAX_CLIPBOARD_BYTES = 32 * 1024 * 1024;

async function readCsv(url: string, signal: AbortSignal) {
    const response = await fetch(url, {signal});
    if (!response.ok || !response.body) throw new Error(tr('Не удалось подготовить CSV для копирования.'));

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const chunks: string[] = [];
    let size = 0;
    try {
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            size += value.byteLength;
            if (size > MAX_CLIPBOARD_BYTES) {
                await reader.cancel();
                throw new Error(tr('CSV больше 32 МиБ. Скачайте файл или отфильтруйте строки.'));
            }
            chunks.push(decoder.decode(value, {stream: true}));
        }
    } finally {
        reader.releaseLock();
    }
    return chunks.join('') + decoder.decode();
}

export async function copyCsv(url: string, signal: AbortSignal) {
    const clipboard = navigator.clipboard;
    if (!clipboard) throw new Error(tr('Не удалось записать CSV в буфер обмена.'));
    const content = readCsv(url, signal);
    try {
        if (typeof ClipboardItem !== 'undefined' && clipboard.write) {
            // Start the clipboard operation during the click, before fetching the rows.
            const item = new ClipboardItem({'text/plain': content.then(text => new Blob([text], {type: 'text/plain'}))});
            await clipboard.write([item]);
            return;
        }
    } catch {
        // Some embedded browsers support writeText but reject ClipboardItem.
    }
    const text = await content;
    signal.throwIfAborted();
    try {
        await clipboard.writeText(text);
    } catch {
        throw new Error(tr('Не удалось записать CSV в буфер обмена.'));
    }
}
