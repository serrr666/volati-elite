import {FileSearch, FolderOpen, Loader2} from 'lucide-react';
import {api} from './api';
import {tr} from './i18n';
import type {Case} from './types';
import {useResource} from './useResource';

type Snapshot = {name: string; filename: string; current: boolean; path: string | null};
type Inventory = {snapshots: Snapshot[]; truncated: boolean};

export function SourceActions({active, openFile, searchStrings}: {
    active: Case;
    openFile: (path: string) => void;
    searchStrings: () => void;
}) {
    return <section className="panel source-actions">
        {active.image_format === 'VMware snapshot inventory · VMSD metadata' &&
            <SnapshotInventory caseId={active.id} openFile={openFile}/>}
        <button className="button secondary" onClick={searchStrings}>
            <FileSearch size={16}/>{tr('Поиск строк в источнике')}
        </button>
    </section>;
}

function SnapshotInventory({caseId, openFile}: {caseId: string; openFile: (path: string) => void}) {
    const {state, reload} = useResource(() => api<Inventory>(`/cases/${caseId}/snapshot-inventory`));
    return <div className="snapshot-inventory">
        <h2>{tr('Снимки VMware')}</h2>
        {state.status === 'error' ? <div className="snapshot-info">
            <span role="alert">{tr('Не удалось прочитать список снимков')}</span>
            <button className="text-button" onClick={() => void reload()}>{tr('Повторить')}</button>
        </div> : state.status !== 'ready' ? <div className="snapshot-info" role="status">
            <Loader2 size={15} className="spin"/>{tr('Загрузка…')}
        </div> : <><ul className="snapshot-list">
            {state.value.snapshots.map((item, index) => <li key={index}>
                <div>
                    <strong>{item.name || item.filename || tr('Снимок VMware')}</strong>
                    {item.current && <small>{tr('Текущий снимок')}</small>}
                    {item.filename && item.name && <code>{item.filename}</code>}
                </div>
                {item.path ? <button className="text-button" onClick={() => openFile(item.path!)}>
                    <FolderOpen size={15}/>{tr('Открыть файл состояния')}
                </button> : item.filename && <span>{tr('Файл состояния не найден рядом')}</span>}
            </li>)}
        </ul>
        {!state.value.snapshots.length && <p>{tr('В каталоге нет записей о снимках')}</p>}
        {state.value.truncated && <p>{tr('Показана часть каталога снимков')}</p>}</>}
    </div>;
}
