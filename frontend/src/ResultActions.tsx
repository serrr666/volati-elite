import {useEffect, useRef, useState} from 'react';
import {ArrowUpRight, Copy, Download, FileText} from 'lucide-react';
import {api, bytes} from './api';
import {tr} from './i18n';
import {PageNavigation} from './PageNavigation';

export type ExtractedFile = {name: string; size: number};
type Digests = {md5: string; sha256: string};
type HashState = Digests | 'failed';

export function RunArtifacts({runId, files, notify, failure}: {
    runId: string;
    files: ExtractedFile[];
    notify: (message: string) => void;
    failure: (error: unknown) => void;
}) {
    const [requestedPage, setPage] = useState(0);
    const [attempt, setAttempt] = useState(0);
    const [results, setResults] = useState(new Map<string, HashState>());
    const pageSize = 30;
    const pages = Math.ceil(files.length / pageSize);
    const page = Math.min(requestedPage, Math.max(0, pages - 1));
    const visible = files.slice(page * pageSize, (page + 1) * pageSize);

    useEffect(() => {
        const controller = new AbortController();
        setResults(new Map());

        async function calculate() {
            for (const file of files.slice(page * pageSize, (page + 1) * pageSize)) {
                if (controller.signal.aborted) break;
                let result: HashState;
                try {
                    result = await api<Digests>(`/runs/${runId}/artifact-hashes?name=${encodeURIComponent(file.name)}`, {signal: controller.signal});
                } catch {
                    result = 'failed';
                }
                if (controller.signal.aborted) break;
                const saved = result;
                setResults(previous => new Map(previous).set(file.name, saved));
            }
        }

        void calculate();
        return () => controller.abort();
    }, [runId, files, page, attempt]);

    return <div className="artifacts-view">
        {visible.map(file => {
            const digest = results.get(file.name);
            return <article className="extracted-artifact" key={file.name}>
                <a href={`/api/runs/${runId}/artifact?name=${encodeURIComponent(file.name)}`}>
                    <span className="file-icon"><FileText size={20}/></span>
                    <span><strong>{file.name}</strong><small>{bytes(file.size)}</small></span>
                    <Download size={16}/>
                </a>
                <div className="artifact-digests">
                    {digest === 'failed' ? <><span>{tr('Не удалось вычислить хеши')}</span><button className="text-button" onClick={() => setAttempt(value => value + 1)}>{tr('Повторить')}</button></> : digest ?
                        (['md5', 'sha256'] as const).map(key => <div key={key}>
                            <span>{key === 'md5' ? 'MD5' : 'SHA-256'}</span>
                            <code>{digest[key]}</code>
                            <button className="icon-button" aria-label={tr('Скопировать хеш {0}', key.toUpperCase())} title={tr('Скопировать хеш {0}', key.toUpperCase())}
                                onClick={() => navigator.clipboard.writeText(digest[key]).then(() => notify(tr('Скопировано'))).catch(failure)}><Copy size={14}/></button>
                        </div>) : <span>{tr('Вычисляем MD5 и SHA-256…')}</span>}
                </div>
            </article>;
        })}
        {pages > 1 && <div className="table-pagination"><span>{page * pageSize + 1}–{Math.min(files.length, (page + 1) * pageSize)} / {files.length}</span>
            <PageNavigation page={page} pages={pages} ready change={setPage}/></div>}
    </div>;
}

type AddressKind = 'physaddr' | 'virtaddr';
type DumpTarget = {address: string; parameter: AddressKind | null};

export function FileScanPivot({runId, rowIndex, open, failure}: {
    runId: string;
    rowIndex: number;
    open: (parameter: AddressKind, address: string) => void;
    failure: (error: unknown) => void;
}) {
    const [target, setTarget] = useState<DumpTarget | null>(null);
    const [loading, setLoading] = useState(false);
    const pending = useRef<AbortController | null>(null);
    useEffect(() => () => pending.current?.abort(), []);

    async function inspect() {
        if (pending.current) return;
        const controller = new AbortController();
        pending.current = controller;
        setLoading(true);
        try {
            const result = await api<DumpTarget>(`/runs/${runId}/rows/${rowIndex}/dumpfiles`, {signal: controller.signal});
            if (controller.signal.aborted) return;
            if (result.parameter) open(result.parameter, result.address);
            else setTarget(result);
        } catch (error) {
            if (!controller.signal.aborted) failure(error);
        } finally {
            pending.current = null;
            if (!controller.signal.aborted) setLoading(false);
        }
    }

    return <div className="filescan-pivot">
        {target ? <><p>{tr('Тип адреса {0} не определён. Проверьте Info или выберите тип вручную.', target.address)}</p>
            <div className="pid-actions">
                <button onClick={() => open('physaddr', target.address)}>{tr('Физический адрес')}</button>
                <button onClick={() => open('virtaddr', target.address)}>{tr('Виртуальный адрес')}</button>
            </div></> : <button className="button secondary" disabled={loading} onClick={inspect}>
            <ArrowUpRight size={15}/>{tr('Открыть файл в DumpFiles')}
        </button>}
    </div>;
}
