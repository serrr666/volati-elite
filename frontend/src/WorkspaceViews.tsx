import {useState} from 'react';
import {ArrowUpRight,FolderOpen,RotateCcw,Search,X} from 'lucide-react';
import {elapsed,time} from './api';
import {tr} from './i18n';
import {NotebookEditor} from './NotebookEditor';
import type {Case,Run,View} from './types';

export type WorkspaceRun=Run&{case_name:string};
export type WorkspaceActivity={runs:WorkspaceRun[];active:WorkspaceRun[];total_runs:number;completed_runs:number};
export type OpenSaved=(id:string,view?:View,runId?:string)=>void;
export function SavedCases({cases, openCase, observations = false, hidden = [], toggleHidden}: {
    cases: Case[];
    openCase: OpenSaved;
    observations?: boolean;
    hidden?: string[];
    toggleHidden?: (id: string) => void;
}) {
    const [query, setQuery] = useState('');
    const [showHidden, setShowHidden] = useState(false);
    const hiddenIds = new Set(hidden);
    const hiddenCount = cases.filter(item => hiddenIds.has(item.id)).length;
    const list = cases.filter(item => (!observations || !!item.bookmark_count) &&
        (!toggleHidden || showHidden || !hiddenIds.has(item.id)) &&
        [item.name, item.path, item.id].some(value => value.toLowerCase().includes(query.toLowerCase())));
    return <section className="workspace-library">
        <div className="section-heading">
            <h2>{tr(observations ? 'Наблюдения в кейсах' : 'Недавние образы')}</h2>
            {toggleHidden && hiddenCount > 0 && <button className="text-button" aria-pressed={showHidden} onClick={() => setShowHidden(value => !value)}>
                {tr(showHidden ? 'Скрыть убранные образы' : 'Показать убранные образы ({0})', hiddenCount)}
            </button>}
            <label className="search-input"><Search size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder={tr('Найти кейс')}/></label>
        </div>
        {!list.length ? <p className="workspace-muted">{tr(observations ? 'Наблюдения появятся после сохранения строк результатов.' : 'Нет образов в списке')}</p> :
            <div className="saved-case-list">{list.map(item => {
                const isHidden = hiddenIds.has(item.id);
                const label = tr(isHidden ? 'Вернуть {0} в недавние' : 'Убрать {0} из недавних', item.name);
                return <div className="saved-case" key={item.id}>
                    <button className="saved-case-open" onClick={() => openCase(item.id, observations ? 'bookmarks' : 'overview')}>
                        <FolderOpen size={18}/><span><strong>{item.name}</strong><small>{item.id.slice(0, 8).toUpperCase()} · {observations ? tr('{0} наблюдений', item.bookmark_count ?? 0) : tr('{0} запусков', item.run_count ?? 0)}</small></span><ArrowUpRight size={15}/>
                    </button>
                    {toggleHidden && <button className="icon-button recent-hide" aria-label={label} title={label} onClick={() => toggleHidden(item.id)}>
                        {isHidden ? <RotateCcw size={15}/> : <X size={15}/>}
                    </button>}
                </div>;
            })}</div>}
    </section>;
}
export function WorkspaceNotebook({cases,openCase}:{cases:Case[];openCase:OpenSaved;failure:(e:unknown)=>void;notify:(s:string)=>void}){
    return <><div className="page-heading"><div><h1>{tr('Общие заметки')}</h1><p>{tr('Планы, гипотезы и ссылки — доступны без открытого образа.')}</p></div></div><section className="panel workspace-notebook"><NotebookEditor scope="workspace" title={tr('Блокнот рабочего пространства')}/></section><SavedCases cases={cases} openCase={openCase} observations/></>;
}
export function WorkspaceHistory({mode,activity,error,cases,openCase,openImage,retry}:{mode:'results'|'timeline'|'pipeline';activity:WorkspaceActivity|null;error:string;cases:Case[];openCase:OpenSaved;openImage:()=>void;retry:()=>void}){
    const [query,setQuery]=useState('');
    const rows=(activity?.runs??[]).filter(r=>(mode!=='pipeline'||r.purpose==='pipeline')&&[r.plugin,r.case_name,r.id].some(v=>v.toLowerCase().includes(query.toLowerCase())));
    const title=mode==='pipeline'?'Конвейеры':mode==='timeline'?'История работы':'Результаты всех кейсов';
    return <><div className="page-heading"><div><h1>{tr(title)}</h1><p>{tr(mode==='timeline'?'Запуски анализов во всех сохранённых кейсах. Временные события памяти доступны внутри кейса.':mode==='pipeline'?'Обрабатывайте файл памяти или результаты плагинов.':'Откройте готовый результат, даже если его кейс сейчас закрыт.')}</p></div><button className="button secondary" onClick={openImage}><FolderOpen size={16}/>{tr('Открыть образ памяти')}</button></div>
    {mode==='pipeline'&&<section className="panel workspace-pipeline-intro"><h2>{tr('Выберите источник для конвейера')}</h2><p>{tr('Файл памяти → строки → фильтры. Результат плагина → поиск, выбор полей, сравнение и удаление повторов.')}</p><p>{tr('Откройте сохранённый кейс ниже или подключите новый образ, затем выберите источник в редакторе.')}</p></section>}
    <div className="section-heading"><h2>{tr(mode==='pipeline'?'Последние конвейеры':mode==='timeline'?'Последние запуски':'Сохранённые результаты')}</h2><label className="search-input"><Search size={14}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder={tr('Поиск по кейсу или плагину')}/></label></div>
    {error?<section className="panel workspace-feedback" role="alert"><p>{tr('Не удалось загрузить историю')}: {error}</p><button className="button secondary" onClick={retry}>{tr('Повторить')}</button></section>:!activity?<p className="workspace-muted">{tr('Загрузка…')}</p>:<section className="panel workspace-run-list">{!rows.length?<p className="workspace-feedback">{tr('Здесь пока нет подходящих запусков.')}</p>:rows.map(r=><button key={r.id} onClick={()=>openCase(r.case_id,'results',r.id)}><span className="workspace-run-main"><strong>{r.plugin.split('.').at(-1)}</strong><small>{r.case_name}</small></span><span className={'status '+r.status}>{tr(({completed:'Завершён',queued:'В очереди',running:'Выполняется',indexing:'Обработка',failed:'Ошибка',cancelled:'Отменён',interrupted:'Прерван'} as Record<string,string>)[r.status]??r.status)}</span><span className="workspace-run-meta">{r.created.slice(0,10)} · {time(r.created)}<small>{r.status==='completed'?tr('{0} строк · {1}',r.row_count,elapsed(r)):r.id.slice(0,8)}</small></span><ArrowUpRight size={15}/></button>)}</section>}
    {activity&&<p className="workspace-muted">{tr('Показаны последние 100 запусков. Полная история доступна в каждом кейсе.')}</p>}
    {mode==='pipeline'&&<SavedCases cases={cases} openCase={(id)=>openCase(id,'pipeline')}/>}</>;
}
