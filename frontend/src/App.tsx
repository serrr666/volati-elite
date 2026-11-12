import {NotebookEditor,QuickNotebook,ObservationNote,investigationNotes} from './NotebookEditor';
import {FileScanPivot, RunArtifacts, type ExtractedFile} from './ResultActions';
import {ColumnFilter,filterArgument,type ColumnFilters} from './ColumnFilter';
import {PluginBatch,PluginArgument,type BatchRequest} from './PluginBatch';
import {matchesRunHistory} from './runHistory';
import {useResource} from './useResource';
import {useDialogFocus} from './useDialogFocus';
import {PageNavigation} from './PageNavigation';
import './qa.css';
import {HelpDialog} from './HelpDialog';
import type {Language} from './languages';
import {reusableRun} from './overviewRun';
import {SettingsPage,type SettingsSection} from './SettingsPage';
import {ResultContextMenu,type ContextTarget} from './ResultContextMenu';
import {Popover} from './Popover';
import {visibleSnapshot,pageSummary} from './resultSnapshot';
import type {TableSnapshot} from './resultSnapshot';
import {tr, translated, getLanguage, setLanguage} from './i18n';
import {orderPlugins} from './pluginOrder';
import type {PluginSort} from './pluginOrder';
import {PipelineWorkbench} from './PipelineWorkbench';
import {RequestScope} from './requestScope';
import {noteDrafts,workspaceDrafts} from './notesDraft';
import {restoreWorkspace,openWorkspaceCase,closeWorkspaceCase,LatestWriter,parseWindowsBanner,measuredProgress} from './workspaceState';
import type {WorkspaceState} from './workspaceState';
import {WorkspaceNotebook,WorkspaceHistory,SavedCases} from './WorkspaceViews';
import type {WorkspaceActivity} from './WorkspaceViews';
import {TableScroller} from './TableScroller';
import {ResizableTable} from './ResizableTable';
import {columnWidths} from './columnWidths';
import {CaseSwitcher} from './CaseSwitcher';
import {automaticCaseName} from './caseIdentity';
import {flushSync} from 'react-dom';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Activity, ArrowRight, ArrowUpRight, BookMarked, Check, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, Clock3, Command, Copy, Cpu, Download, FileSearch, FileText, Filter, FolderOpen, Globe, HardDrive, Hash, HelpCircle, Layers, LayoutDashboard, LayoutGrid, List, Loader2, Network, Play, Plus, PlugZap, RefreshCw, Search, Settings as SettingsIcon, ShieldCheck, SlidersHorizontal, Sparkles, Square, Star, Terminal, Trash2, X } from 'lucide-react';
import { api, post, bytes, elapsed, short, time, value } from './api';
import { categories, explain, pick, steps } from './guides';
import type { Bookmark, Case, Health, OS, Plugin, ResultRow, Run, Settings, View } from './types';
const navigation = [{ id: 'overview', label: 'Обзор кейса', icon: LayoutDashboard }, { id: 'plugins', label: 'Каталог плагинов', icon: PlugZap }, { id: 'pipeline', label: 'Конвейеры', icon: Filter }, { id: 'results', label: 'Результаты', icon: Layers }, { id: 'bookmarks', label: 'Закладки и заметки', icon: BookMarked }, { id: 'timeline', label: 'Временная шкала', icon: Clock3 }] as const;
const statuses: Record<string, string> = translated({ queued: 'В очереди', running: 'Выполняется', indexing: 'Обработка', completed: 'Завершён', failed: 'Ошибка', cancelled: 'Отменён', interrupted: 'Прерван' });
const osLabel: Record<string, string> = translated({ windows: 'Windows', linux: 'Linux', mac: 'macOS', unknown: 'ОС не выбрана', generic: 'Общие' });
const busy = (r: Run) => ['queued', 'running', 'indexing'].includes(r.status);
const noRuns: Run[] = [], noBookmarks: Bookmark[] = [];
const iconFor = (group: string) => group === 'network' ? Network : group === 'malware' ? FileSearch : group === 'process' ? Cpu : group === 'files' ? FolderOpen : group === 'timeline' ? Clock3 : group === 'kernel' ? Layers : FileSearch;
declare global {
    interface Window {
        volstudioNative?: {
            pickFile: () => Promise<string>;
            pickDirectory: () => Promise<string>;
            openDataDirectory: () => void;
        };
        __volstudioFlushDrafts?:()=>Promise<void>;
        __volstudioPendingDrop?: {
            path: string;
            name: string;
        };
    }
}

function Logo() {
 return <div className="brand"><div className="brand-word">volati<span>elite</span></div></div>;
}
function IconButton({ title, onClick, children, disabled = false }: {
    title: string;
    onClick?: () => void;
    children: ReactNode;
    disabled?: boolean;
}) { return <button className="icon-button" title={title} aria-label={title} onClick={onClick} disabled={disabled}>{children}</button>; }
function Status({ status }: {
    status: string;
}) { return <span className={'status ' + status}>{['running', 'indexing'].includes(status) ? <Loader2 size={12} className="spin"/> : status === 'completed' ? <CheckCircle2 size={12}/> : <i />}{statuses[status] || status}</span>; }
function Modal({ title, subtitle, children, onClose, wide = false }: {
    title: string;
    subtitle?: string;
    children: ReactNode;
    onClose: () => void;
    wide?: boolean;
}) { const dialogRef=useRef<HTMLElement>(null);useDialogFocus(dialogRef,onClose);return <div className="modal-backdrop" onClick={onClose}><section ref={dialogRef} role="dialog" aria-modal="true" aria-label={title} className={'modal ' + (wide ? 'wide' : '')} onClick={e => e.stopPropagation()}><div className="modal-title"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><IconButton title={tr("Закрыть")} onClick={onClose}><X size={20}/></IconButton></div>{children}</section></div>; }
function Empty({ icon: Icon = Layers, title, text, children }: {
    icon?: typeof Layers;
    title: string;
    text: string;
    children?: ReactNode;
}) { return <div className="empty"><div className="empty-icon"><Icon size={28}/></div><h3>{title}</h3><p>{text}</p>{children}</div>; }
export default function App() {
    const [health, setHealth] = useState<Health | null>(null), [plugins, setPlugins] = useState<Plugin[]>([]), [cases, setCases] = useState<Case[]>([]), [workspace,setWorkspace]=useState<WorkspaceState>({activeId:'',openIds:[]});
    const caseId=workspace.activeId;
    const preferenceWriter=useRef(new LatestWriter<Record<string,unknown>>(value=>api('/preferences',{method:'PUT',body:JSON.stringify(value)})));
    window.__volstudioFlushDrafts=()=>Promise.all([investigationNotes.flushAll(),noteDrafts.flushAll(),workspaceDrafts.flushAll(),preferenceWriter.current.flush()]).then(()=>{});
    const pendingCase=useRef<{id:string;view:View;runId?:string}|null>(null);
    function setCaseId(id:string){setWorkspace(state=>openWorkspaceCase(state,id))}
    const [activity,setActivity]=useState<WorkspaceActivity|null>(null),[activityError,setActivityError]=useState('');
    const runHistoryScroll=useRef(new Map<string,number>()),runHistoryFilters=useRef(new Map<string,string>());
    const workspaceSequence=useRef(0);
    const reloadWorkspace=useCallback(async()=>{const seq=++workspaceSequence.current;try{const data=await api<WorkspaceActivity>('/workspace/activity');if(seq===workspaceSequence.current){setActivity(old=>JSON.stringify(old)===JSON.stringify(data)?old:data);setActivityError('')}}catch(e){if(seq===workspaceSequence.current)setActivityError(e instanceof Error?e.message:String(e))}},[]);
    const [view, setView] = useState<View>('overview'), [caseData, setCaseData] = useState<{id:string;runs:Run[];bookmarks:Bookmark[]}>({id:'',runs:[],bookmarks:[]}), [selectedRun, setSelectedRun] = useState('');
    useLayoutEffect(()=>{window.scrollTo(0,0)},[view,caseId]);
    const runs=caseData.id===caseId?caseData.runs:noRuns, bookmarks=caseData.id===caseId?caseData.bookmarks:noBookmarks;
    const caseReads=useRef(new RequestScope()), caseListSequence=useRef({requested:0,applied:0});
    caseReads.current.select(caseId);
    const [plugin, setPlugin] = useState<Plugin | null>(null), [params, setParams] = useState<Record<string, unknown>>({}), [creating, setCreating] = useState(false), [palette, setPalette] = useState(false), [help, setHelp] = useState(false);
    const [toast, setToast] = useState<{id:number;text:string}|null>(null), [theme, setTheme] = useState(() => document.documentElement.dataset.theme || localStorage.getItem('vol3.theme') || 'dark'), [caseMenu, setCaseMenu] = useState(false), [queueOpen, setQueueOpen] = useState(false);
    const [language,setUILanguage]=useState(getLanguage);
    const [notebookOpen,setNotebookOpen]=useState(false);
    const [hiddenRecent, setHiddenRecent] = useState<string[]>([]);
    const [favorites, setFavorites] = useState<string[]>([]);
    function toggleRecent(id: string) {
        setHiddenRecent(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);
    }
    function toggleFavorite(id: string) {
        setFavorites(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);
    }
    const [settingsSection,setSettingsSection]=useState<SettingsSection>('general');
    function openAnalysisSettings(){setSettingsSection('analysis');setView('settings')}
    const [prefsReady,setPrefsReady]=useState(false);
    function changeLanguage(next:Language){setLanguage(next);setUILanguage(next)}
    const [pipelineDraft,setPipelineDraft]=useState<Run|null>(null);
    const [pipelineEdit,setPipelineEdit]=useState(false);
    const [focusRow,setFocusRow]=useState<{runId:string;index:number}|null>(null);
    const [hideTip,setHideTip]=useState(document.documentElement.dataset.hideTip==='true'),[tipVisible,setTipVisible]=useState(document.documentElement.dataset.hideTip!=='true'),[tipPrompt,setTipPrompt]=useState(false);
    const themeTransition=useRef<{skipTransition:()=>void}|null>(null);
    function switchTheme(){
        const next=theme==='dark'?'light':'dark';
        const update=()=>{document.documentElement.dataset.theme=next;flushSync(()=>setTheme(next))};
        themeTransition.current?.skipTransition();
        if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){update();return}
        if(document.startViewTransition){
            const transition=document.startViewTransition(()=>{document.documentElement.classList.add('theme-snapshot');update()});
            themeTransition.current=transition;
            transition.ready.catch(()=>{});
            transition.finished.catch(()=>{}).finally(()=>{if(themeTransition.current===transition){themeTransition.current=null;document.documentElement.classList.remove('theme-snapshot')}});
        }else{
            document.documentElement.classList.add('theme-changing');update();
            setTimeout(()=>document.documentElement.classList.remove('theme-changing'),320);
        }
    }
    const nativeOpener = useRef<(path?: string) => void>(() => { });
    const active = cases.find(c => c.id === caseId), current = runs.find(r => r.id === selectedRun), timers = useRef<ReturnType<typeof setTimeout> | null>(null);
    const notify = useCallback((message: string) => { setToast(old=>({id:(old?.id??0)+1,text:tr(message)})); if (timers.current)
        clearTimeout(timers.current); timers.current = setTimeout(() => setToast(null), 3500); }, []);
    const failure = useCallback((e: unknown) => notify(e instanceof Error ? e.message : String(e)), [notify]);
    const reloadCases = useCallback(async () => {const sequence=++caseListSequence.current.requested;const list=await api<Case[]>('/cases');if(sequence>caseListSequence.current.applied){caseListSequence.current.applied=sequence;setCases(old=>JSON.stringify(old)===JSON.stringify(list)?old:list)}return list},[]);
    const reloadRuns = useCallback(() => !caseId?Promise.resolve():caseReads.current.load(caseId,
        signal=>Promise.all([api<Run[]>(`/cases/${caseId}/runs`,{signal}),api<Bookmark[]>(`/cases/${caseId}/bookmarks`,{signal})]),
        ([jobs,marks])=>{setCaseData(old=>old.id===caseId&&JSON.stringify(old.runs)===JSON.stringify(jobs)&&JSON.stringify(old.bookmarks)===JSON.stringify(marks)?old:{id:caseId,runs:jobs,bookmarks:marks});setSelectedRun(id=>id||jobs[0]?.id||'')},failure),[caseId,failure]);
    useEffect(()=>{const next=pendingCase.current?.id===caseId?pendingCase.current:null;pendingCase.current=null;setSelectedRun(next?.runId??'');setView(next?.view??'overview');setPlugin(null);setParams({});setPipelineDraft(null);setFocusRow(null);setQueueOpen(false)},[caseId]);
    function openSavedCase(id:string,nextView:View='overview',runId?:string){if(id===caseId){setView(nextView);setSelectedRun(runId??'')}else{pendingCase.current={id,view:nextView,runId};setCaseId(id)}setCaseMenu(false)}
    async function closeCase(id:string){try{await investigationNotes.flushAll();await noteDrafts.flushAll();await workspaceDrafts.flushAll();setWorkspace(state=>closeWorkspaceCase(state,id));}catch(e){failure(e)}}
    async function closeAllCases(){try{await investigationNotes.flushAll();await noteDrafts.flushAll();await workspaceDrafts.flushAll();pendingCase.current=null;setWorkspace({activeId:'',openIds:[]});setCaseMenu(false);setView('overview')}catch(e){failure(e)}}
    const startup=useResource(async()=>{
        const [h,p,list,pref]=await Promise.all([api<Health>('/health'),api<{plugins:Plugin[]}>('/plugins'),api<Case[]>('/cases'),api<{language:Language;theme:string;last_case:string;hide_tip:boolean;open_cases:string[];hidden_recent_cases?:string[];favorite_plugins?:string[]}>('/preferences')]);
        return {h,p,list,pref};
    });
    useEffect(()=>{if(startup.state.status!=='ready')return;const {h,p,list,pref}=startup.state.value;setHealth(h);setPlugins(p.plugins);setCases(list);setLanguage(pref.language);setUILanguage(pref.language);setTheme(pref.theme);setHiddenRecent(pref.hidden_recent_cases??[]);setFavorites(pref.favorite_plugins??[]);setHideTip(pref.hide_tip??false);setTipVisible(!pref.hide_tip);setWorkspace(restoreWorkspace(list.map(c=>c.id),pref));setPrefsReady(true)},[startup.state]);
    useEffect(()=>{if(prefsReady)preferenceWriter.current.submit({language,theme,last_case:caseId,open_cases:workspace.openIds,hide_tip:hideTip,hidden_recent_cases:hiddenRecent,favorite_plugins:favorites}).catch(failure)},[language,theme,caseId,workspace.openIds,prefsReady,hideTip,hiddenRecent,favorites,failure]);
    useEffect(()=>{
        let alive=true,running=false,revision:number|undefined,timer:ReturnType<typeof setTimeout>;
        async function tick(){
            if(!alive||running)return;running=true;let delay=10000;
            try{if(!document.hidden){const pulse=await api<{revision:number;busy:boolean}>('/workspace/pulse');if(!alive)return;delay=pulse.busy?2000:10000;
                if(pulse.revision!==revision){await Promise.all([reloadRuns(),reloadCases(),reloadWorkspace()]);revision=pulse.revision}}}
            catch{/* A later pulse retries; explicit view loads retain their error states. */}
            finally{running=false;if(alive)timer=setTimeout(tick,delay)}
        }
        function visible(){if(!document.hidden){clearTimeout(timer);void tick()}}
        void tick();document.addEventListener('visibilitychange',visible);
        return()=>{alive=false;clearTimeout(timer);document.removeEventListener('visibilitychange',visible)};
    },[reloadRuns,reloadCases,reloadWorkspace]);
    useEffect(() => { localStorage.setItem('vol3.case', caseId); }, [caseId]);
    useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('vol3.theme', theme); }, [theme]);
    useEffect(() => { function key(e: KeyboardEvent) { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCaseMenu(false);setPalette(v => !v);
    } if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        nativeOpener.current();
    } if (e.key === 'Escape') {
        setPlugin(null);
        setCreating(false);
        setPalette(false);
        setHelp(false);
        setCaseMenu(false);
    } } function dropped(e: Event) { const path = (e as CustomEvent<{
        path: string;
    }>).detail.path; window.__volstudioPendingDrop = undefined; nativeOpener.current(path); } window.addEventListener('keydown', key); window.addEventListener('volstudio:drop', dropped); if (window.__volstudioPendingDrop) {
        const path = window.__volstudioPendingDrop.path;
        window.__volstudioPendingDrop = undefined;
        nativeOpener.current(path);
    } return () => { window.removeEventListener('keydown', key); window.removeEventListener('volstudio:drop', dropped); }; }, []);
    async function openEvidence(providedPath?: string) { try {
        if (!providedPath && !window.volstudioNative) {
            setCreating(true);
            return;
        }
        const path = providedPath || await window.volstudioNative!.pickFile();
        if (!path)
            return;
        const c = await post<Case>('/cases', { path, name: automaticCaseName(path), os: 'unknown', reuse_existing: true });
        await reloadCases();
        setCaseId(c.id);
        setCreating(false);
        setView('overview');
        notify(c.reused?tr('Открыт существующий кейс'):tr('Источник подключён. Статус проверки — в обзоре.'));
    }
    catch (e) {
        failure(e);
    } }
    nativeOpener.current = openEvidence;
    function openPlugin(p: Plugin, values: Record<string, unknown> = {}) { setPlugin(p); setParams(values); setPalette(false); }
    async function launch(p: Plugin, values: Record<string, unknown> = {}, close = true) { if (!active) {
        setCreating(true);
        return;
    } try {
        const r = await post<Run>(`/cases/${active.id}/runs`, { plugin: p.id, params: values });
        if(caseReads.current.matches(active.id)){
            setSelectedRun(r.id);
            setView('results');
            if (close) setPlugin(null);
        }
        await reloadRuns();
        notify(tr("{0} добавлен в очередь", p.name));
    }
    catch (e) {
        failure(e);
    } }
    async function queueBatch(requests:BatchRequest[]){
        if(!active)return false;
        try{const jobs=await post<Run[]>(`/cases/${active.id}/runs/batch`,{runs:requests});
            if(caseReads.current.matches(active.id)){setSelectedRun(jobs[0].id);setView('results')}
            await reloadRuns();notify(tr('Плагины добавлены в очередь: {0}',jobs.length));return true;
        }catch(e){failure(e);return false}
    }
    async function loadDemo() { try {
        const c = await post<Case>('/demo');
        await reloadCases();
        setCaseId(c.id);
        setView('overview');
        notify(tr("Открыт синтетический учебный кейс"));
    }
    catch (e) {
        failure(e);
    } }
    async function cancel(r: Run) { try {
        await post(`/runs/${r.id}/cancel`);
        await reloadRuns();
    }
    catch (e) {
        failure(e);
    } }
    async function retry(r: Run) { try {
        const n = await post<Run>(`/runs/${r.id}/retry`);
        if(caseReads.current.matches(r.case_id))setSelectedRun(n.id);
        await reloadRuns();
        notify(tr("Создан новый запуск"));
    }
    catch (e) {
        failure(e);
    } }
    function openResult(id: string,index?:number) { setFocusRow(index===undefined?null:{runId:id,index});setSelectedRun(id); setView('results'); }
    const inProgress = activity?.active??runs.filter(busy);
    const viewLabel=(id:View)=>!active&&id==='overview'?'Начало':!active&&id==='bookmarks'?'Общие заметки':!active&&id==='timeline'?'История работы':navigation.find(n=>n.id===id)?.label??'';
    const navigate = (v: View) => { if(v==='pipeline')setPipelineDraft(null);setView(v); setCaseMenu(false); };
    if(!prefsReady)return <div className="startup-screen"><div><Logo/><ResourceFeedback title={tr(startup.state.status==='error'?'Не удалось открыть рабочее пространство':'Загружаем рабочее пространство…')} error={startup.state.error} retry={startup.reload}/></div></div>;
    return <div className="app-shell" onContextMenu={e=>{if(!(e.target as HTMLElement).closest('input,textarea,[contenteditable="true"]'))e.preventDefault()}}>
    <aside className="sidebar"><Logo /><div className="case-select-wrap"><button className="case-select" aria-haspopup="dialog" aria-expanded={caseMenu} aria-controls={caseMenu?"case-switcher":undefined} onClick={() => setCaseMenu(!caseMenu)}><span className="case-avatar"><FolderOpen size={18}/></span><span><small>{tr("ТЕКУЩИЙ ОБРАЗ")}</small><strong>{active ? short(active.name, 22) : tr("Выберите образ памяти")}</strong></span><ChevronDown size={15}/></button>{caseMenu && <CaseSwitcher dismiss={()=>setCaseMenu(false)} cases={cases} activeId={caseId} openIds={workspace.openIds} select={openSavedCase} close={closeCase} create={()=>{setCaseMenu(false);openEvidence()}}/>}</div>
      <div className="nav-label">{tr("РАБОЧЕЕ ПРОСТРАНСТВО")}</div><nav>{navigation.map(n => <button key={n.id} className={view === n.id ? 'active' : ''} onClick={() => navigate(n.id)}><n.icon size={18}/><span>{tr(viewLabel(n.id))}</span>{n.id === 'plugins' ? <em>{plugins.length || '…'}</em> : n.id === 'bookmarks' && bookmarks.length > 0 ? <em>{bookmarks.length}</em> : null}</button>)}</nav>
      <div className="sidebar-spacer"/>{tipVisible&&<div className="sidebar-tip"><button className="tip-dismiss" aria-label={tr("Закрыть подсказку")} title={tr("Закрыть подсказку")} onClick={()=>{setTipVisible(false);setTipPrompt(true)}}><X size={14}/></button><div className="tip-orbit"><Sparkles size={19}/></div><span>{tr("Сначала вопрос.")}<br /><strong>{tr("Потом правильный плагин.")}</strong></span><p>{tr("Рекомендации помогут выбрать следующий шаг исследования.")}</p><button onClick={() => setHelp(true)}>{tr("Как это работает")}<ArrowUpRight size={14}/></button></div>}
      <div className="sidebar-bottom"><button className={view === 'settings' ? 'selected' : ''} onClick={() => navigate('settings')}><SettingsIcon size={18}/>{tr("Настройки")}</button></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="top-actions"><button className="global-search" onClick={() => setPalette(true)}><Search size={15}/><span>{tr("Найти плагин…")}</span><kbd aria-hidden="true">Ctrl + K</kbd></button><button className={"icon-button notebook-toggle"+(notebookOpen?" active":"")} title={tr("Блокнот расследования")} aria-label={tr("Блокнот расследования")} aria-expanded={notebookOpen} onClick={()=>setNotebookOpen(v=>!v)}><FileText size={18}/></button><IconButton title={tr("Помощь и сочетания клавиш")} onClick={() => setHelp(true)}><HelpCircle size={18}/></IconButton></div></header>
    {workspace.openIds.length>0&&<div className="case-tabs" aria-label={tr('Открытые кейсы')}>{workspace.openIds.map(id=>{const c=cases.find(c=>c.id===id);return c&&<div className={'case-tab '+(caseId===id?'active':'')} key={id}><button aria-pressed={caseId===id} title={c.name} onClick={()=>openSavedCase(id)}>{c.name}</button><button aria-label={tr('Закрыть кейс {0}',c.name)} title={tr('Закрыть кейс')} onClick={()=>closeCase(id)}><X size={13}/></button></div>})}{workspace.openIds.length>1&&<button className="text-button" onClick={closeAllCases}>{tr('Закрыть все')}</button>}<IconButton title={tr('Открыть образ памяти')} onClick={()=>openEvidence()}><Plus size={15}/></IconButton></div>}
    {active?.kind === 'demo' && <div className="demo-strip"><span><Sparkles size={13}/>{tr("Учебный кейс \u00B7 синтетические данные")}</span><span>{tr("Реальный дамп ещё не анализировался")}<button onClick={() => setCreating(true)}>{tr("Открыть свой образ")}<ArrowRight size={13}/></button></span></div>}
    <main className="main-content">
      {view === 'settings' ? <SettingsPage health={health} language={language} theme={theme} changeLanguage={changeLanguage} switchTheme={switchTheme} section={settingsSection} onSection={setSettingsSection}><SettingsView health={health} onSaved={h => { setPlugins(h.plugins); api<Health>('/health').then(setHealth); }} notify={notify} failure={failure}/></SettingsPage> :
            view === 'plugins' ? <PluginCatalog plugins={plugins} active={active} openPlugin={openPlugin} queue={queueBatch} favorites={favorites} toggleFavorite={toggleFavorite}/> :
                !active ? view==='bookmarks'?<WorkspaceNotebook cases={cases} openCase={openSavedCase} failure={failure} notify={notify}/>:view==='results'||view==='timeline'||view==='pipeline'?<WorkspaceHistory mode={view} activity={activity} error={activityError} retry={reloadWorkspace} cases={cases} openCase={openSavedCase} openImage={()=>openEvidence()}/>:<><Welcome count={plugins.length} open={() => openEvidence()}/><SavedCases cases={cases} openCase={openSavedCase} hidden={hiddenRecent} toggleHidden={toggleRecent}/></> :
                    view === 'overview' ? <><div className="page-heading"><div><h1>{tr('Обзор источника')}<span>.</span></h1><p>{tr('Проверьте источник и выберите следующий шаг анализа.')}</p></div><button className="button secondary" onClick={() => openEvidence()}><Plus size={16}/>{tr("Новый кейс")}</button></div>
       <CaseCard active={active} notify={notify}/>
       {active.kind !== 'demo' && <DetectionCard openSettings={openAnalysisSettings} active={active} changed={reloadCases} failure={failure} openResult={() => { const r = runs.find(r => r.plugin === 'banners.Banners'); if (r)
                        openResult(r.id); }}/>}
       <div className="section-heading"><div><h2>{tr("С чего начнём?")}</h2><p>{tr("Выберите вопрос \u2014 мы подскажем подходящие инструменты.")}</p></div><button className="text-button" onClick={() => setView('plugins')}>{tr("Все плагины")}<ArrowUpRight size={15}/></button></div>
       <div className="guide-grid">{steps(plugins,active.os).map((step,index)=>{const p=step.plugins[0],existing=p&&reusableRun(runs,p.id);return <button className="guide-simple" key={step.id} disabled={!p} onClick={()=>existing?openResult(existing.id):p&&openPlugin(p)}><span className="guide-simple-icon">{index===0?<Cpu size={21}/>:index===1?<Network size={21}/>:<Terminal size={21}/>}</span><span><strong>{step.title}</strong><small>{step.text}</small>{p&&<small>{p.name} · {existing?busy(existing)?tr('Открыть выполняющийся анализ'):tr('Открыть результат · {0} строк',existing.row_count):tr('Настроить запуск')}</small>}</span><ArrowRight size={16}/></button>})}</div>
       <div className="overview-lower"><section className="panel recent-panel"><div className="panel-heading"><h2><Activity size={17}/>{tr("Последние запуски")}</h2><button className="text-button" onClick={() => setView('results')}>{tr("Все результаты")}<ArrowRight size={14}/></button></div>{runs.length ? <><div className="mini-table-head"><span>{tr("ПЛАГИН")}</span><span>{tr("СТАТУС")}</span><span>{tr("СТРОКИ")}</span></div>{runs.slice(0, 5).map(r => <button className="run-row" onClick={() => openResult(r.id)} key={r.id}><span className="run-plugin"><span className="run-icon"><Terminal size={14}/></span><span><strong>{r.plugin.split('.').at(-1)}</strong><small>{short(r.plugin, 38)}</small></span></span><Status status={r.status}/><span className="row-count">{r.status === 'completed' ? r.row_count : '—'}<ChevronRight size={14}/></span></button>)}</> : <Empty title={tr("Запуски появятся здесь")} text={tr("Выберите процессы, соединения, командные строки или другой плагин.")}/>}</section></div>
</> :
                        view === 'pipeline' ? <PipelineWorkbench key={active.id+(pipelineDraft?.id??'')+String(pipelineEdit)} initial={pipelineDraft} edit={pipelineEdit} active={active} runs={runs} failure={failure} queued={r=>{reloadRuns().catch(failure);openResult(r.id)}}/> :
                        view === 'results' ? <Results openSettings={openAnalysisSettings} historyScroll={runHistoryScroll.current} historyFilters={runHistoryFilters.current} choosePlugin={()=>setView('plugins')} key={active.id+":"+(current?.id??"none")} focusRow={focusRow} pipelineFor={(r,edit=false)=>{setPipelineDraft(r);setPipelineEdit(edit);setView('pipeline')}} active={active} runs={runs} current={current} plugins={plugins} bookmarks={bookmarks} select={setSelectedRun} openPlugin={openPlugin} cancel={cancel} retry={retry} refreshBookmarks={reloadRuns} notify={notify} failure={failure}/> :
                            view === 'bookmarks' ? <BookmarksView key={active.id} active={active} bookmarks={bookmarks} openResult={openResult} reload={reloadRuns} notify={notify} failure={failure} reloadCases={reloadCases}/> :
                                <TimelineView key={active.id} active={active} runs={runs} openResult={openResult} failure={failure}/>}
    </main><footer className="statusbar"><span><span className="live-dot"/>{tr('ЛОКАЛЬНОЕ ПРОСТРАНСТВО')}<span className="status-sep">/</span>{active ? osLabel[active.os] : tr("Нет открытого кейса")}</span><span>{inProgress.length > 0 ? <button onClick={() => setQueueOpen(!queueOpen)}><Loader2 size={12} className="spin"/>{tr("Активных запусков: {0}",inProgress.length)}</button> : view==='results'&&current?.status==='failed' ? <span className="footer-run-error">{tr("Запуск не завершён")}</span> : <><Check size={12}/>{tr("Готово")}</>}</span></footer>
    </div>
    {queueOpen && <section className="queue-popover"><div className="panel-heading"><h3>{tr("Очередь анализа")}</h3><IconButton title={tr("Скрыть очередь")} onClick={() => setQueueOpen(false)}><X size={16}/></IconButton></div>{inProgress.length ? inProgress.map(r => <div className="queue-item" key={r.id}><div><button onClick={() => { openSavedCase(r.case_id,'results',r.id); setQueueOpen(false); }}>{r.plugin.split('.').at(-1)}</button><IconButton title={tr("Отменить запуск")} onClick={() => cancel(r)}><Square size={12}/></IconButton></div><Status status={r.status}/><div className={'progress-track '+(measuredProgress(r)===null?'indeterminate':'')}><i style={{width:(measuredProgress(r)??35)+'%'}}/></div></div>) : <p className="muted">{tr("Очередь пуста")}</p>}</section>}
    {creating && <ImportDialog close={() => setCreating(false)} imported={async (c) => { await reloadCases(); setCaseId(c.id); setView('overview'); setCreating(false); notify(tr("Образ подключён. SHA-256 рассчитывается в фоне.")); }} failure={failure}/>}
    {plugin && <PluginSheet key={plugin.id} plugin={plugin} params={params} setParams={setParams} active={active} close={() => setPlugin(null)} launch={() => launch(plugin, params)}/>}
    {palette && <CommandPalette plugins={plugins} close={() => setPalette(false)} select={openPlugin}/>}
    {notebookOpen&&<QuickNotebook active={active} close={()=>setNotebookOpen(false)}/>}
    {help&&<HelpDialog engine={health?.engine_version??'—'} close={()=>setHelp(false)} settings={()=>{setHelp(false);openAnalysisSettings()}} demo={()=>{setHelp(false);loadDemo()}} showTip={!tipVisible?()=>{setHideTip(false);setTipVisible(true);setTipPrompt(false);setHelp(false)}:undefined}/>}
    {tipPrompt&&<div className="tip-prompt" role="status"><div><CheckCircle2 size={17}/><span>{tr('Подсказка скрыта')}<small className="tip-help-note">{tr('Она всегда доступна в справке — значок ? справа сверху.')}</small></span><IconButton title={tr('Закрыть')} onClick={()=>setTipPrompt(false)}><X size={14}/></IconButton></div><div><button onClick={()=>{setHideTip(true);setTipPrompt(false)}}>{tr('Не показывать при запуске')}</button><button onClick={()=>{setTipVisible(true);setTipPrompt(false)}}>{tr('Вернуть')}</button></div></div>}{toast && <div role="status" aria-live="polite" key={toast.id} className="toast"><InfoMark /><span>{toast.text}</span><button onClick={() => setToast(null)} aria-label={tr("Закрыть уведомление")}><X size={15}/></button></div>}
  </div>;
}
function ResourceFeedback({title,error,retry}:{title:string;error:string;retry:()=>Promise<void>}){return <section className="resource-feedback" aria-live="polite">{error?<FileSearch size={26}/>:<Loader2 size={26} className="spin"/>}<h2>{title}</h2>{error&&<><p role="alert">{error}</p><p>{tr('Сохранённые кейсы и настройки не изменены.')}</p><button className="button secondary" onClick={()=>void retry()}><RefreshCw size={15}/>{tr('Повторить загрузку')}</button></>}</section>}
function InfoMark() { return <div className="toast-icon"><Activity size={17}/></div>; }
function DirectoryPicker({paths,onChange,description,failure}:{paths:string[];onChange:(p:string[])=>void;description:string;failure:(e:unknown)=>void}){const [manual,setManual]=useState(false),[input,setInput]=useState(''),[busy,setBusy]=useState(false);function add(p:string){if(p.trim()&&!paths.some(x=>x.toLowerCase()===p.trim().toLowerCase()))onChange([...paths,p.trim()]);setInput('');setManual(false)}async function choose(){if(!window.volstudioNative){setManual(true);return}setBusy(true);try{const p=await window.volstudioNative.pickDirectory();if(p)add(p)}catch(e){failure(e)}finally{setBusy(false)}}return <div className="directory-picker"><div className="directory-list">{paths.length?paths.map((p,i)=><div className="directory-row" key={p}><span className="directory-icon"><FolderOpen size={19}/></span><div><strong>{p.split(/[\\/]/).filter(Boolean).at(-1)||p}</strong><small title={p}>{p}</small></div><IconButton title={tr('Удалить папку из списка')} onClick={()=>onChange(paths.filter((_,idx)=>idx!==i))}><X size={15}/></IconButton></div>):<div className="directory-empty"><FolderOpen size={21} strokeWidth={1.5}/><div><strong>{tr('Папки не добавлены')}</strong><p>{description}</p></div></div>}</div><div className="directory-actions"><button className="button secondary compact" onClick={choose} disabled={busy}>{busy?<Loader2 size={14} className="spin"/>:<Plus size={14}/>} {tr('Добавить папку')}</button><button className="text-button" onClick={()=>setManual(!manual)}>{tr('Указать путь вручную')}</button></div>{manual&&<div className="directory-manual"><input autoFocus value={input} onChange={e=>setInput(e.target.value)} placeholder={tr('Полный путь к папке')} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();add(input)}}}/><button className="button secondary compact" onClick={()=>add(input)} disabled={!input.trim()}>{tr('Добавить')}</button></div>}</div>}
function ResourceSettings({config,setConfig}:{config:Settings;setConfig:(s:Settings)=>void}) {
 const presets=[1,2,4,8,16,32,64],mb=config.memory_limit_mb??0;
 const [custom,setCustom]=useState(mb>0&&!presets.includes(mb/1024));
 const [amount,setAmount]=useState(String(mb>0?mb/1024:12));
 useEffect(()=>{if(mb>0&&!presets.includes(mb/1024)){setCustom(true);setAmount(String(mb/1024))}},[mb]);
 return <div className="settings-section"><h2><Cpu size={19}/>{tr('Память процесса анализа')}</h2><p>{tr('Плагины выполняются по одному в отдельных процессах. При превышении лимита приложение останавливает анализ, сохраняя доступ к интерфейсу.')}</p>
 <div className="memory-tabs" role="group" aria-label={tr('Режим лимита памяти')}><button className={!custom?'selected':''} onClick={()=>{setCustom(false);if(mb<0)setConfig({...config,memory_limit_mb:0})}}>{tr('Готовые значения')}</button><button className={custom?'selected':''} onClick={()=>{setCustom(true);const n=Number(amount.replace(',','.'));if(n>=0.25&&n<=1024)setConfig({...config,memory_limit_mb:Math.round(n*1024)})}}>{tr('Свой лимит')}</button></div>
 {custom?<label className="custom-memory"><span>{tr('Лимит памяти')}</span><div><input type="text" inputMode="decimal" value={amount} aria-label={tr('Свой лимит памяти в ГБ')} onChange={e=>{setAmount(e.target.value);const n=Number(e.target.value.replace(',','.'));setConfig({...config,memory_limit_mb:n>=0.25&&n<=1024?Math.round(n*1024):-1})}}/><strong>{tr('ГБ')}</strong></div><small>{tr('От 0,25 до 1024 ГБ. Это верхний лимит, память заранее не выделяется.')}</small></label>:<select className="resource-select" aria-label={tr('Лимит ОЗУ')} value={mb} onChange={e=>setConfig({...config,memory_limit_mb:Number(e.target.value)})}><option value="0">{tr('Автоматически (по доступной ОЗУ)')}</option>{presets.map(n=><option value={n*1024} key={n}>{n} {tr('ГБ')}</option>)}{mb>0&&!presets.includes(mb/1024)&&<option value={mb}>{mb/1024} {tr('ГБ')}</option>}</select>}
 </div>;
}
function DetectionCard({ openSettings, active, changed, failure, openResult }: {
    openSettings:()=>void;
    active: Case;
    changed: () => Promise<unknown>;
    failure: (e: unknown) => void;
    openResult: () => void;
}) { const detecting = ['banners', 'windows'].includes(active.detect_status || ''); return <section className={'detection-card ' + (detecting ? 'detecting' : '')}><div className="detection-icon">{detecting ? <Loader2 size={20} className="spin"/> : active.detect_status === 'complete' ? <CheckCircle2 size={20}/> : <FileSearch size={20}/>}</div><div className="detection-text"><strong>{detecting ? tr("Определяем образ автоматически") : active.detect_status === 'complete' ? tr("{0} \u00B7 определено автоматически", osLabel[active.os]) : tr("Параметры образа")}</strong><p>{tr(active.detect_message) || tr("Вы можете выбрать операционную систему вручную.")}{active.image_format && <span> · {tr(active.image_format)}</span>}</p>{active.detected_banner && <details className="kernel-identity"><summary>{tr('Идентификатор ядра')}</summary><code>{active.detected_banner}</code></details>}{active.os==='linux'&&active.source_kind==='memory'&&!detecting&&<div className="linux-analysis-help"><p>{tr("Баннер Linux найден. Для разбора процессов и других структур нужен ISF JSON с точным соответствием полному баннеру; одного номера версии ядра недостаточно.")}</p><button className="text-button" onClick={openSettings}>{tr('Настроить данные ОС')}<ArrowUpRight size={14}/></button></div>}</div>{detecting ? <span className="detection-phase">{active.detect_status === 'banners' ? 'BANNERS' : 'WINDOWS INFO'}</span> : <select disabled={active.source_kind==='auxiliary'||active.source_kind==='unsupported'} aria-label={tr("Изменить ОС кейса")} value={active.os} onChange={e => api(`/cases/${active.id}`, { method: 'PATCH', body: JSON.stringify({ os: e.target.value }) }).then(changed).catch(failure)}><option value="unknown">{tr("ОС неизвестна")}</option><option value="windows">Windows</option><option value="linux">Linux</option><option value="mac">macOS</option></select>}<button className="icon-button" disabled={detecting||active.hash_status==='pending'} title={tr('Повторно определить формат и ОС')} aria-label={tr('Повторно определить формат и ОС')} onClick={()=>post(`/cases/${active.id}/detect`,{}).then(changed).catch(failure)}><RefreshCw size={16}/></button><IconButton title={tr("Посмотреть результат Banners")} disabled={active.source_kind!=='memory'} onClick={openResult}><ArrowUpRight size={16}/></IconButton></section>; }
function CaseCard({ active, notify }: {
    active: Case;
    notify: (s: string) => void;
}) { return <section className="case-card"><div className="case-card-main"><div className="evidence-icon"><HardDrive size={27}/><span className="evidence-led"/></div><div className="case-title"><div><h2>{active.name}</h2><span className={'os-tag ' + active.os}>{active.source_kind==='auxiliary'?tr('Вспомогательный файл'):active.source_kind==='unsupported'?tr('Неподдерживаемый формат'):osLabel[active.os]}</span>{active.kind === 'demo' && <span className="demo-tag">DEMO</span>}</div><p title={active.path}>{active.path}</p><div className="case-facts"><span title={String(active.size)+' B'}><HardDrive size={12}/>{bytes(active.size)}</span><i /><span><Hash size={12}/>{active.hash_status === 'pending' ? <><Loader2 size={11} className="spin"/>{tr("SHA-256 рассчитывается")} · {Math.round(active.hash_progress??0)}%</> : active.hash_status === 'demo' ? tr("Синтетический набор") : active.sha256 ? `SHA-256 ${active.sha256.slice(0, 12)}…` : tr("Ошибка проверки")}{active.sha256 && <IconButton title={tr("Скопировать SHA-256")} onClick={() => navigator.clipboard.writeText(active.sha256!).then(() => notify(tr("SHA-256 скопирован")))}><Copy size={11}/></IconButton>}</span><i /><span>{tr("Кейс")} {active.id.slice(0, 8).toUpperCase()}</span></div></div></div></section>; }
function Welcome({count,open}:{count:number;open:()=>void}){
 return <section className="start-screen"><div className="start-heading"><h1>{tr('Новый анализ памяти')}</h1><p>{tr('Откройте дамп, чтобы начать исследование.')}</p></div>
 <div className="start-dropzone" role="button" tabIndex={0} aria-label={tr('Открыть образ памяти')} onClick={open} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}}}>
 <div className="start-file-icon"><FolderOpen size={32} strokeWidth={1.5}/></div><h2>{tr('Перетащите образ памяти сюда')}</h2><p>{tr('или выберите файл на компьютере')}</p><button className="button primary large" onClick={e=>{e.stopPropagation();open()}}><FolderOpen size={17}/>{tr('Открыть образ памяти')}<ArrowRight size={16}/></button><code>RAW · MEM · VMEM · DMP · LiME · ELF</code></div>
 <div className="start-information"><div><FileSearch size={17}/><span>{tr('Система определяется автоматически через Banners и Info.')}</span></div><div><HardDrive size={17}/><span>{tr('Файл читается по локальному пути без копирования.')}</span></div></div>
 <div className="start-capabilities"><span><PlugZap size={15}/>{count} {tr('установленных плагинов')}</span><span>Windows · Linux · macOS</span></div></section>
}

function PluginCatalog({plugins, active, openPlugin, queue, favorites, toggleFavorite}: {
    favorites: string[];
    toggleFavorite: (id: string) => void;
    queue:(requests:BatchRequest[])=>Promise<boolean>;
    plugins: Plugin[];
    active?: Case;
    openPlugin: (p: Plugin) => void;
}) {
    const [search, setSearch] = useState(''), [os, setOS] = useState<string>(() => active?.os && active.os !== 'unknown' ? active.os : 'all'), [category, setCategory] = useState('all'), [grid, setGrid] = useState(false), [deprecated, setDeprecated] = useState(false), [pluginSort,setPluginSort] = useState<PluginSort>('popular');
    const [selected,setSelected]=useState<string[]>([]),[batchOpen,setBatchOpen]=useState(false),[batchSending,setBatchSending]=useState(false);
    const chosen=plugins.filter(p=>selected.includes(p.id));
    const favoriteIds = new Set(favorites);
    const matchesCategory = (plugin: Plugin, id: string) => id === 'all' ||
        (id === 'favorites' ? favoriteIds.has(plugin.id) : plugin.category === id);
    const sections = Object.entries(categories);
    sections.splice(1, 0, ['favorites', tr('Избранные плагины')]);
    const compatible=(p:Plugin)=>!active||(((active.source_kind??'memory')==='memory'||p.os==='generic')&&(active.os==='unknown'||p.os==='generic'||p.os===active.os));
    async function submit(){if(chosen.some(p=>p.args.some(a=>!a.optional&&a.default==null))){setBatchOpen(true);return}
        setBatchSending(true);try{if(await queue(chosen.map(p=>({plugin:p.id,params:{}}))))setSelected([])}finally{setBatchSending(false)}}
    const filtered = orderPlugins(plugins.filter(p => (os === 'all' || p.os === os || p.os === 'generic') && matchesCategory(p, category) && (deprecated || !p.description.toLowerCase().includes('deprecated')) && [p.id, p.description, ...explain(p)].join(' ').toLowerCase().includes(search.toLowerCase())), pluginSort, category);
    return <><div className="page-heading"><div><h1>{tr("Плагины Volatility 3")}<span>.</span></h1><p>{tr("Каталог установленного движка. Найдите плагин по названию или вопросу.")}</p></div><span className="count-pill"><PlugZap size={15}/>{plugins.length} {tr("плагинов")}</span></div><div className="catalog-layout"><aside className="category-nav"><small>{tr("КАТЕГОРИИ")}</small>{sections.map(([id, label]) => { const Icon = id === 'favorites' ? Star : id === 'all' ? LayoutGrid : iconFor(id); return <button className={category === id ? 'selected' : ''} onClick={() => setCategory(id)} key={id}><Icon size={16}/><span>{label}</span><em>{plugins.filter(p => matchesCategory(p, id) && (os === 'all' || p.os === os || p.os === 'generic')).length}</em></button>; })}<label className="mini-checkbox"><input type="checkbox" checked={deprecated} onChange={e => setDeprecated(e.target.checked)}/>{tr("Показывать устаревшие")}</label></aside><section className="catalog-main"><div className="catalog-toolbar"><label className="search-input"><Search size={17}/><input placeholder={tr("Название, задача или описание\u2026")} value={search} onChange={e => setSearch(e.target.value)}/>{search && <button onClick={() => setSearch('')} aria-label={tr("Очистить поиск")}><X size={14}/></button>}</label><select aria-label={tr("Операционная система")} value={os} onChange={e => setOS(e.target.value as OS)}><option value="all">{tr("Все ОС")}</option><option value="windows">Windows</option><option value="linux">Linux</option><option value="mac">macOS</option></select><select className="plugin-sort" aria-label={tr('Сортировка плагинов')} title={tr('Основные инструменты для типовых расследований — первыми.')} value={pluginSort} onChange={e=>setPluginSort(e.target.value as PluginSort)}><option value="popular">{tr('По популярности')}</option><option value="name">{tr('По названию')}</option></select><div className="view-toggle"><button aria-label={tr("Список")} className={!grid ? 'selected' : ''} onClick={() => setGrid(false)}><List size={17}/></button><button aria-label={tr("Карточки")} className={grid ? 'selected' : ''} onClick={() => setGrid(true)}><LayoutGrid size={16}/></button></div></div><div className="catalog-count">{filtered.length} {tr("инструментов")}<span>{tr("Нажмите на плагин, чтобы настроить запуск")}</span></div><div className="catalog-batch-toolbar"><span>{tr('Выбрано: {0}',selected.length)}</span><button className="text-button" title={tr('Не более 50 плагинов за один запуск')} disabled={batchSending||new Set([...selected,...filtered.filter(compatible).map(p=>p.id)]).size>50} onClick={()=>setSelected(old=>[...new Set([...old,...filtered.filter(compatible).map(p=>p.id)])])}>{tr('Выбрать видимые')}</button><button className="text-button" disabled={!selected.length||batchSending} onClick={()=>setSelected([])}>{tr('Снять выделение')}</button><button className="icon-button" title={tr('Параметры выбранных плагинов')} disabled={!selected.length||!active||batchSending} onClick={()=>setBatchOpen(true)}><SlidersHorizontal size={16}/></button><button className="button primary compact" disabled={!selected.length||!active||batchSending} title={!active?tr('Сначала откройте образ памяти'):undefined} onClick={submit}>{batchSending?<Loader2 size={15} className="spin"/>:<Play size={15}/>} {tr('Запустить выбранные ({0})',selected.length)}</button></div><div className={grid ? 'plugin-grid' : 'plugin-list'}>{filtered.map(p => { const Icon = iconFor(p.category); return <div key={p.id} className={'plugin-choice'+(selected.includes(p.id)?' is-selected':'')}><input type="checkbox" aria-label={tr('Выбрать плагин {0}',p.name)} checked={selected.includes(p.id)} disabled={batchSending||!compatible(p)||(!selected.includes(p.id)&&selected.length>=50)} onChange={e=>setSelected(old=>e.target.checked?[...old,p.id]:old.filter(id=>id!==p.id))}/><button className="plugin-card" onClick={() => openPlugin(p)}><span className={'plugin-icon ' + p.category}><Icon size={20}/></span><div className="plugin-card-content"><div><h3>{p.name}</h3><span className={'os-tag ' + p.os}>{osLabel[p.os]}</span></div><p>{explain(p)[1]}</p><code>{p.id}</code></div><ArrowUpRight size={17} className="plugin-arrow"/></button>
        <button className={'icon-button plugin-favorite'+(favoriteIds.has(p.id)?' selected':'')} aria-pressed={favoriteIds.has(p.id)}
            title={tr(favoriteIds.has(p.id)?'Убрать {0} из избранного':'Добавить {0} в избранное',p.name)}
            aria-label={tr(favoriteIds.has(p.id)?'Убрать {0} из избранного':'Добавить {0} в избранное',p.name)}
            onClick={()=>toggleFavorite(p.id)}><Star size={17} fill={favoriteIds.has(p.id)?'currentColor':'none'}/></button></div>; })}</div>{!filtered.length && <Empty icon={Search} title={tr("Плагинов не найдено")} text={tr(category==='favorites'&&!favorites.length?'Нажмите звёздочку рядом с нужным плагином.':'Попробуйте другой запрос, категорию или операционную систему.')}/>}</section></div>{batchOpen&&<PluginBatch plugins={chosen} close={()=>setBatchOpen(false)} queue={async values=>{const ok=await queue(values);if(ok)setSelected([]);return ok}}/>}</>;
}
function PluginSheet({ plugin: p, params, setParams, active, close, launch }: {
    plugin: Plugin;
    params: Record<string, unknown>;
    setParams: (v: Record<string, unknown>) => void;
    active?: Case;
    close: () => void;
    launch: () => void;
}) {
    const dialogRef=useRef<HTMLElement>(null);useDialogFocus(dialogRef,close);
    const [advanced, setAdvanced] = useState(false);
    const [question, description] = explain(p);
    const Icon = iconFor(p.category);
    const recommended = p.args.filter(a => !a.optional || ['pid', 'key', 'offset', 'virtaddr', 'physaddr', 'yara-rules', 'yara-file'].includes(a.name));
    const rest = p.args.filter(a => !recommended.includes(a));
    const renderArg=(a:Plugin['args'][number])=><PluginArgument key={a.name} argument={a} params={params} setParams={setParams}/>;
    const quote=(v:unknown)=>"'"+String(v).replaceAll("'","''")+"'";
    const preview=Object.entries(params).filter(([,v])=>v!==''&&v!==false).flatMap(([key,v])=>v===true?['--'+key]:Array.isArray(v)?['--'+key,...v]:['--'+key,String(v)]).map(quote).join(' ');

    return <div className="sheet-backdrop" onClick={close}><section ref={dialogRef} className="plugin-sheet" role="dialog" aria-label={tr("Настройка {0}", p.name)} aria-modal="true" onClick={e => e.stopPropagation()}><div className="sheet-top"><span>{tr("НАСТРОЙКА ПЛАГИНА")}</span><IconButton title={tr("Закрыть настройки плагина")} onClick={close}><X size={20}/></IconButton></div><div className="sheet-content"><div className={'sheet-icon ' + p.category}><Icon size={27}/></div><div className="sheet-plugin-title"><h2>{p.name}</h2><span className={'os-tag ' + p.os}>{osLabel[p.os]}</span></div><code className="plugin-id">{p.id}</code><h3 className="plugin-question">{question}</h3><p className="plugin-explanation">{description}</p>{description !== p.description && <details className="original-description"><summary>{tr("Описание разработчика")}</summary><p>{p.description}</p></details>}<div className="sheet-divider"/><div className="section-heading tight"><h3>{tr("Параметры запуска")}</h3><span className="subtle">v{p.version}</span></div>{!p.args.length ? <p className="muted">{tr("Дополнительные параметры не требуются.")}</p> : <>{recommended.map(renderArg)}{rest.length > 0 && <><button className="advanced-toggle" onClick={() => setAdvanced(!advanced)}><SlidersHorizontal size={15}/>{advanced ? tr("Скрыть") : tr("Дополнительные параметры")}<span>{rest.length}</span><ChevronDown size={14} className={advanced ? 'rotate' : ''}/></button>{advanced && rest.map(renderArg)}</>}</>}
    <div className="command-preview"><span><Terminal size={13}/>{tr("ПРИМЕР ПАРАМЕТРОВ CLI")} · PowerShell</span><code>&amp; 'vol' '-f' {quote(active?.path||'memory.raw')} '-r' 'json' {quote(p.id)} {preview}</code><small>{tr("Фактический запуск Studio и его параметры доступны в журнале результата.")}</small></div></div><div className="sheet-bottom"><div><span className="live-dot"/>{active ? short(active.name, 36) : tr("Сначала откройте образ памяти")}</div><button className="button primary" onClick={launch}><Play size={16} fill="currentColor"/>{active ? tr("Добавить в очередь") : tr("Открыть образ памяти")}</button></div></section></div>;
}
function ImportDialog({close,imported,failure}:{close:()=>void;imported:(c:Case)=>void;failure:(e:unknown)=>void}){
 const [path,setPath]=useState(''),[name,setName]=useState(''),[os,setOS]=useState<OS>('unknown'),[loading,setLoading]=useState(false),[picking,setPicking]=useState(false);
 async function browse(){setPicking(true);try{const result=window.volstudioNative?{path:await window.volstudioNative.pickFile()}:await post<{path:string}>('/pick-file');if(result.path){setPath(result.path);setName(automaticCaseName(result.path))}}catch(e){failure(e)}finally{setPicking(false)}}
 async function submit(){setLoading(true);try{imported(await post<Case>('/cases',{path,name:name||automaticCaseName(path),os,reuse_existing:true}))}catch(e){failure(e)}finally{setLoading(false)}}
 return <Modal title={tr('Открыть образ памяти')} onClose={close}><div className="import-body"><label className="field-label">{tr('Исходный образ')}<div className="path-picker"><input autoFocus value={path} placeholder={tr('Выберите файл или вставьте полный путь')} onChange={e=>setPath(e.target.value)}/><button className="button secondary" onClick={browse} disabled={picking}>{picking?<Loader2 size={16} className="spin"/>:<FolderOpen size={16}/>} {tr('Обзор…')}</button></div></label><div className="form-two"><label className="field-label">{tr('Название кейса')}<input value={name} maxLength={160} onChange={e=>setName(e.target.value)}/></label><label className="field-label">{tr('Операционная система')}<select value={os} onChange={e=>setOS(e.target.value as OS)}><option value="unknown">{tr('Определить автоматически')}</option><option value="windows">Windows</option><option value="linux">Linux</option><option value="mac">macOS</option></select></label></div></div><div className="modal-footer"><button className="button secondary" onClick={close}>{tr('Отмена')}</button><button className="button primary" onClick={submit} disabled={loading||!path.trim()}>{loading?<Loader2 size={16} className="spin"/>:<ArrowRight size={16}/>} {tr('Открыть')}</button></div></Modal>;
}
function CommandPalette({ plugins, close, select }: {
    plugins: Plugin[];
    close: () => void;
    select: (p: Plugin) => void;
}) { const dialogRef=useRef<HTMLElement>(null);useDialogFocus(dialogRef,close);const [q, setQ] = useState(''); const matches = orderPlugins(plugins).filter(p => !p.description.includes('deprecated') && [p.id, ...explain(p)].join(' ').toLowerCase().includes(q.toLowerCase())).slice(0, 12); return <div className="modal-backdrop palette-backdrop" onClick={close}><section ref={dialogRef} className="command-palette" role="dialog" aria-modal="true" aria-label={tr("Поиск плагинов")} onClick={e => e.stopPropagation()}><div className="palette-input"><Search size={20}/><input autoFocus placeholder={tr("Что вы хотите исследовать?")} value={q} onChange={e => setQ(e.target.value)}/><button type="button" className="palette-dismiss" aria-label={tr("Закрыть")} onClick={close}><X size={16}/></button></div><div className="palette-caption">{q ? tr("РЕЗУЛЬТАТЫ ПОИСКА") : tr("ИНСТРУМЕНТЫ VOLATILITY 3")}</div><div className="palette-results">{matches.map(p => <button key={p.id} onClick={() => select(p)}><span className="run-icon"><Terminal size={16}/></span><span><strong>{p.name}<small>{osLabel[p.os]}</small></strong><p>{explain(p)[0]}</p></span><ArrowUpRight size={15}/></button>)}{!matches.length && <p className="muted">{tr("Ничего не найдено")}</p>}</div><div className="palette-footer"><Command size={12}/>{tr("Поиск по названию, описанию и вопросу исследования")}</div></section></div>; }
type SharedProps = {
    active: Case;
    runs: Run[];
    failure: (e: unknown) => void;
};
function Results({ openSettings, historyScroll,historyFilters, choosePlugin, focusRow,pipelineFor, active, runs, current, plugins, bookmarks, select, openPlugin, cancel, retry, refreshBookmarks, notify, failure }: SharedProps & {
    openSettings:()=>void;
    historyScroll:Map<string,number>;
    historyFilters:Map<string,string>;
    choosePlugin:()=>void;
    pipelineFor:(r:Run,edit?:boolean)=>void;
    focusRow:{runId:string;index:number}|null;
    current?: Run;
    plugins: Plugin[];
    bookmarks: Bookmark[];
    select: (id: string) => void;
    openPlugin: (p: Plugin, v?: Record<string, unknown>) => void;
    cancel: (r: Run) => void;
    retry: (r: Run) => void;
    refreshBookmarks: () => Promise<void>;
    notify: (s: string) => void;
}) {
    const [query, setQuery] = useState(''), [page, setPage] = useState(0), [sort, setSort] = useState(''), [direction, setDirection] = useState('asc'), [tab, setTab] = useState('table'), [logs, setLogs] = useState({ text: '', error: '', command: '', worker_command: '' }), [artifacts, setArtifacts] = useState<{
        name: string;
        size: number;
    }[]>([]), [row, setRow] = useState<ResultRow | null>(null), [hidden, setHidden] = useState<string[]>([]), [columnMenu, setColumnMenu] = useState(false), [note, setNote] = useState(''), [exportMenu, setExportMenu] = useState(false);
    const [searchInput,setSearchInput]=useState(''),[valueColumn,setValueColumn]=useState<string|null>(null),[columnFilters,setColumnFilters]=useState<ColumnFilters>({});
    const filterArgs=filterArgument(columnFilters);
    useEffect(()=>{const timer=setTimeout(()=>{setQuery(searchInput);setPage(0)},250);return()=>clearTimeout(timer)},[searchInput]);
    const [savedRows,setSavedRows]=useState<Set<number>>(()=>new Set()),[savingRows,setSavingRows]=useState<Set<number>>(()=>new Set());
    const pendingSaves=useRef(new Set<number>());
    const markedRows=useMemo(()=>new Set([...savedRows,...bookmarks.filter(b=>b.run_id===current?.id).map(b=>b.row_idx)]),[savedRows,bookmarks,current?.id]);
    const historyNode=useRef<HTMLElement|null>(null);
    const [historyQuery,setHistoryQuery]=useState(()=>historyFilters.get(active.id)??'');
    const visibleRuns=runs.filter(run=>matchesRunHistory(run,historyQuery,statuses[run.status]??run.status));
    function filterHistory(query:string){setHistoryQuery(query);historyFilters.set(active.id,query);if(historyFilters.size>100)historyFilters.delete(historyFilters.keys().next().value!);historyScroll.set(active.id,0);if(historyNode.current)historyNode.current.scrollTop=0}
    useLayoutEffect(()=>{if(historyNode.current)historyNode.current.scrollTop=historyScroll.get(active.id)??0},[active.id,historyScroll]);
    const [widthRevision,setWidthRevision]=useState(0);
    const [context,setContext]=useState<ContextTarget|null>(null);
    useEffect(()=>setContext(null),[current?.id,page,query,sort,direction,filterArgs]);
    function contextFor(e:React.MouseEvent<HTMLElement>,r:ResultRow,text:string){e.preventDefault();e.stopPropagation();const selection=window.getSelection();const selected=selection?.anchorNode&&e.currentTarget.contains(selection.anchorNode)?selection.toString():'';setContext({x:e.clientX,y:e.clientY,value:text,selection:selected,rowText:columns.map(c=>{const v=value(r.data[c]);return /[\t\r\n"]/.test(v)?'"'+v.replaceAll('"','""')+'"':v}).join('\t'),restore:e.currentTarget.closest('tr') as HTMLElement})}
    function copyResult(text:string){navigator.clipboard.writeText(text).then(()=>notify(tr('Скопировано'))).catch(failure)}
    const [table,setTable]=useState<TableSnapshot<ResultRow>|null>(null),[tableError,setTableError]=useState<{key:string;message:string}|null>(null),[tableAttempt,setTableAttempt]=useState(0);
    const requestKey=JSON.stringify([current?.id,current?.status,current?.row_count,page,query,sort,direction,filterArgs,tableAttempt]);
    const error=tableError?.key===requestKey?tableError.message:'';
    const {ready,rows,columns,total}=visibleSnapshot(requestKey,table,error?requestKey:'');
    const fetching=!!current&&!ready&&!error,summary=pageSummary(total,page,ready);
    const inspectorRef=useRef<HTMLElement|null>(null);
    const observationText=useRef('');
    useEffect(()=>{
        if(!row||!inspectorRef.current)return;
        const previous=document.activeElement as HTMLElement|null,dialog=inspectorRef.current;
        const controls=()=>Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(el=>el.getClientRects().length>0);
        controls()[0]?.focus();
        const trap=(event:KeyboardEvent)=>{if(event.key!=='Tab')return;const items=controls(),first=items[0],last=items.at(-1);if(!first||!last)return;
            if(!dialog.contains(document.activeElement)){event.preventDefault();first.focus()}
            else if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
            else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}};
        dialog.addEventListener('keydown',trap);
        return()=>{dialog.removeEventListener('keydown',trap);if(previous?.isConnected)previous.focus()};
    },[!!row]);
    useEffect(() => { setPage(0); setQuery(''); setSearchInput('');setColumnFilters({});setValueColumn(null); setSort(''); setHidden([]); setRow(null); setTab('table'); }, [current?.id]);
    useEffect(()=>{if(!row)return;const close=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();setRow(null)}};window.addEventListener('keydown',close,true);return()=>window.removeEventListener('keydown',close,true)},[row]);
    useEffect(() => { setPage(0); }, [query, sort, direction,filterArgs]);
    useEffect(()=>{
        if(!current)return;
        const controller=new AbortController();
        api<{rows:ResultRow[];columns:string[];total:number}>(`/runs/${current.id}/rows?offset=${page*100}&q=${encodeURIComponent(query)}&sort=${encodeURIComponent(sort)}&direction=${direction}&filters=${filterArgs}`,{signal:controller.signal}).then(data=>{
            if(controller.signal.aborted)return;
            if(page>0&&page*100>=data.total){setPage(Math.max(0,Math.ceil(data.total/100)-1));return}
            setTable({key:requestKey,...data});setTableError(null);
        }).catch(e=>{if(!controller.signal.aborted){setTableError({key:requestKey,message:e instanceof Error?e.message:String(e)});failure(e)}});
        return()=>controller.abort();
    },[requestKey,failure]);
    useEffect(() => {
        if (!current || tab !== 'log') return;
        const controller = new AbortController();
        api<{text: string; error: string; command: string; worker_command: string}>(`/runs/${current.id}/logs`, {signal: controller.signal})
            .then(data => { if (!controller.signal.aborted) setLogs(data); })
            .catch(error => { if (!controller.signal.aborted) failure(error); });
        return () => controller.abort();
    }, [current?.id, current?.status, tab === 'log' ? current?.progress : 0, tab, failure]);
    useEffect(() => {
        if (!current || tab !== 'artifacts' || current.status !== 'completed') return;
        const controller = new AbortController();
        api<ExtractedFile[]>(`/runs/${current.id}/artifacts`, {signal: controller.signal})
            .then(data => { if (!controller.signal.aborted) setArtifacts(data); })
            .catch(error => { if (!controller.signal.aborted) failure(error); });
        return () => controller.abort();
    }, [current?.id, current?.status, tab, failure]);
    useEffect(()=>{let alive=true;if(!focusRow||focusRow.runId!==current?.id)return;setQuery('');setSearchInput('');setColumnFilters({});setSort('');setPage(Math.floor(focusRow.index/100));api<ResultRow>(`/runs/${focusRow.runId}/rows/${focusRow.index}`).then(r=>{if(alive){setRow(r);setNote(observationText.current=bookmarks.find(b=>b.run_id===focusRow.runId&&b.row_idx===r.index)?.note||'')}}).catch(failure);return()=>{alive=false}},[focusRow,current?.id,failure]);
    function inspect(r: ResultRow) { setRow(r); setNote(observationText.current=bookmarks.find(b => b.run_id === current?.id && b.row_idx === r.index)?.note || ''); }
    async function saveRow(r:ResultRow,text?:string){
        if(!current||pendingSaves.current.has(r.index))return;
        pendingSaves.current.add(r.index);setSavingRows(new Set(pendingSaves.current));
        try{await post(`/cases/${active.id}/bookmarks`,{run_id:current.id,row_idx:r.index,note:text});
            setSavedRows(old=>new Set([...old,r.index]));notify(tr('Строка {0} сохранена в закладки',r.index+1));
            await refreshBookmarks();
        }catch(e){failure(e)}finally{pendingSaves.current.delete(r.index);setSavingRows(new Set(pendingSaves.current))}
    }
    const visible = columns.filter(c => !hidden.includes(c)), treeColumn=['ImageFileName','Process','Name'].find(c=>visible.includes(c))??visible[0], pid = row?.data.PID ?? row?.data.Pid ?? row?.data.pid;
    const consoleBuild = current?.unsupported_console_build;
    const cmdline = consoleBuild ? plugins.find(plugin => plugin.id === 'windows.cmdline.CmdLine') : undefined;
    const dumpFiles = current?.plugin === 'windows.filescan.FileScan' && current.status === 'completed'
        ? plugins.find(plugin => plugin.id === 'windows.dumpfiles.DumpFiles') : undefined;
    return <>{current&&valueColumn&&<ColumnFilter key={current.id+valueColumn} runId={current.id} column={valueColumn} query={query} filters={columnFilters} close={()=>setValueColumn(null)} apply={rule=>{setColumnFilters(old=>{const next={...old};if(rule)next[valueColumn]=rule;else delete next[valueColumn];return next});setPage(0)}}/>}<div className="page-heading"><div><h1>{tr("Результаты анализа")}<span>.</span></h1><p>{tr("Фильтруйте результаты, исследуйте контекст и сохраняйте наблюдения.")}</p></div><button className="button secondary" onClick={choosePlugin}><Plus size={16}/>{tr("Новый запуск")}</button></div>
    <div className="results-layout"><aside className="runs-sidebar" ref={historyNode} onScroll={e=>historyScroll.set(active.id,e.currentTarget.scrollTop)}><div className="runs-sidebar-heading"><strong>{tr("Запуски")}</strong><span>{historyQuery?visibleRuns.length+' / '+runs.length:runs.length}</span></div><label className="history-search"><Search size={13}/><input aria-label={tr('Плагин или статус…')} placeholder={tr('Плагин или статус…')} value={historyQuery} onChange={event=>filterHistory(event.target.value)}/>{historyQuery&&<button aria-label={tr('Очистить поиск')} onClick={()=>filterHistory('')}><X size={12}/></button>}</label>{visibleRuns.map(r => <button key={r.id} className={'run-tab ' + (r.id === current?.id ? 'selected' : '')} onClick={() => select(r.id)}><div><Terminal size={15}/><strong>{r.plugin.split('.').at(-1)}</strong>{r.status === 'completed' ? <CheckCircle2 size={13}/> : busy(r) ? <Loader2 size={13} className="spin"/> : <span className="error-dot"/>}</div><small>{time(r.created)}</small><span>{r.status === 'completed' ? tr("{0} строк \u00B7 {1}", r.row_count.toLocaleString(), elapsed(r)) : statuses[r.status]}</span></button>)}{runs.length>0&&!visibleRuns.length&&<p className="muted no-runs">{tr("Ничего не найдено")}</p>}{!runs.length && <p className="muted no-runs">{tr("Выберите плагин, чтобы начать анализ.")}</p>}</aside><section className="result-panel">{!current ? <Empty title={tr("Готовы к исследованию")} text={tr("Запустите плагин из каталога или рекомендаций на странице обзора.")}/> : <><div className="result-heading"><div><div className="result-title"><h2>{current.plugin.split('.').at(-1)}</h2><Status status={current.status}/></div><code>{current.plugin}</code></div><div className="result-actions">{busy(current) && <IconButton title={tr("Отменить запуск")} onClick={() => cancel(current)}><Square size={15}/></IconButton>}<IconButton title={tr("Повторить запуск")} onClick={() => retry(current)}><RefreshCw size={16}/></IconButton><button className="button secondary compact" disabled={current.status!=='completed'} onClick={()=>pipelineFor(current)}><Filter size={14}/>{tr('Фильтровать результат')}</button>{current.purpose==='pipeline'&&<IconButton title={tr('Редактировать рецепт')} onClick={()=>pipelineFor(current,true)}><SlidersHorizontal size={15}/></IconButton>}<div className="dropdown-wrap"><button className="button secondary compact" disabled={current.status !== 'completed'} aria-haspopup="dialog" aria-expanded={exportMenu} onClick={() => {setColumnMenu(false);setExportMenu(!exportMenu)}}><Download size={14}/>{tr("Экспорт")}<ChevronDown size={12}/></button>{exportMenu && <Popover className="dropdown-menu" label={tr("Экспорт")} dismiss={()=>setExportMenu(false)}><a href={`/api/runs/${current.id}/export?format=csv&q=${encodeURIComponent(query)}&filters=${filterArgs}`} onClick={() => setExportMenu(false)}>{tr(query||filterArgs?'CSV · текущая выборка':'CSV \u00B7 все строки')}</a><a href={`/api/runs/${current.id}/export?format=json&q=${encodeURIComponent(query)}&filters=${filterArgs}`} onClick={() => setExportMenu(false)}>{tr("JSON · структурированные строки")}</a></Popover>}</div></div></div>
    {current.plugin==='banners.Banners'&&ready&&rows.some(r=>parseWindowsBanner(r.data.Banner))&&<div className="banner-explanation"><strong>{tr('Идентификаторы ядра Windows')}</strong><br/>{tr('PDB — файл отладочных данных; GUID и ревизия подбирают данные для анализа. Найденные сигнатуры не означают несколько установленных ОС. Версию системы смотрите в Info.')}</div>}
    {busy(current) && <div className="running-banner"><div><Loader2 size={16} className="spin"/><span>{current.status === 'queued' ? (active.hash_status === 'pending' ? tr("Ожидание SHA-256 образа\u2026") : tr("Ожидание свободного движка\u2026")) : tr(current.message==='PDB scanning finished'?'Поиск данных ядра завершён. Анализ продолжается.':current.message)}</span>{measuredProgress(current)!==null&&<strong>{measuredProgress(current)!.toFixed(0)}%</strong>}</div><div className={'progress-track '+(measuredProgress(current)===null?'indeterminate':'')}><i style={{width:(measuredProgress(current)??35)+'%'}}/></div></div>}
    {current.status === 'failed' && <div className="error-banner"><ShieldCheck size={18}/><div><strong>{tr("Запуск не завершён")}</strong><p>{consoleBuild ? tr('В Volatility {0} плагин {1} не поддерживает структуры conhost для Windows {2}.', current.engine_version, current.plugin.split('.').at(-1), consoleBuild) : tr(current.error?.split('\n')[0])}</p>
        {consoleBuild && <p>{tr('Для истории консоли нужен анализатор с поддержкой этой сборки. CmdLine показывает аргументы запуска процессов.')}</p>}
        {cmdline && <button onClick={() => {const existing = reusableRun(runs, cmdline.id); if (existing) select(existing.id); else openPlugin(cmdline);}}>{tr('Открыть CmdLine')}<ArrowRight size={13}/></button>}<button onClick={() => setTab('log')}>{tr("Посмотреть полный журнал")}<ArrowRight size={13}/></button>{!consoleBuild&&(active.os==='linux'||/symbol_table_name|OfflineException/i.test(current.error??''))&&<button onClick={openSettings}>{tr("Настроить данные ОС")}<ArrowRight size={13}/></button>}</div></div>}
    {current.purpose==='pipeline'&&current.status==='completed'&&<div className="pipeline-result-summary"><Filter size={17}/><div><strong>{current.pipeline_summary?.limit_reached?tr('Достигнут лимит строк — обработана часть источника'):tr('Конвейер завершён')}</strong><small>{tr('Просмотрено записей')}: {current.pipeline_summary?.scanned_records?.toLocaleString()} · {tr('Получено строк')}: {current.row_count.toLocaleString()}</small></div></div>}
    {['cancelled', 'interrupted'].includes(current.status) && <div className="inline-notice"><Square size={16}/>{tr("Запуск")}{current.status === 'cancelled' ? tr("отменён аналитиком") : tr("прерван при закрытии приложения")}{tr(". Вы можете запустить плагин повторно.")}</div>}
    <div className="result-tabs"><div>{[['table', tr("Таблица")], ['log', tr("Журнал и команда")], ['artifacts', tr("Извлечённые файлы{0}", artifacts.length ? ' · ' + artifacts.length : '')]].map(([id, label]) => <button key={id} className={tab === id ? 'selected' : ''} onClick={() => setTab(id)}>{label}{id === 'table' && <span>{current.row_count}</span>}</button>)}</div><span>{elapsed(current)}</span></div>
    {tab === 'table' ? <><div className="table-toolbar"><label className="search-input"><Search size={15}/><input placeholder={tr("Поиск по всем строкам\u2026")} value={searchInput} onChange={e => setSearchInput(e.target.value)}/>{searchInput && <button onClick={() => setSearchInput('')} aria-label={tr("Сбросить фильтр")}><X size={13}/></button>}</label><span className="table-count">{fetching ? <Loader2 size={13} className="spin"/> : <Filter size={13}/>} {ready?total.toLocaleString('ru-RU'):'—'} {tr("строк")}</span><div className="dropdown-wrap"><IconButton title={tr("Настроить колонки")} onClick={() => {setExportMenu(false);setColumnMenu(!columnMenu)}}><SlidersHorizontal size={16}/></IconButton>{columnMenu && <Popover className="dropdown-menu columns-menu" label={tr("Настроить колонки")} dismiss={()=>setColumnMenu(false)}>{columns.map(c => <label key={c}><input type="checkbox" checked={!hidden.includes(c)} onChange={() => setHidden(hidden.includes(c) ? hidden.filter(v => v !== c) : [...hidden, c])}/>{c}</label>)}<button className="reset-column-widths" onClick={()=>{columnWidths.reset(current.plugin);setWidthRevision(v=>v+1);setColumnMenu(false)}}>{tr('Сбросить ширину столбцов')}</button></Popover>}</div></div>{Object.keys(columnFilters).length>0&&<div className="active-value-filters">{Object.keys(columnFilters).map(c=><button key={c} onClick={()=>setValueColumn(c)}><Filter size={11}/> {c}</button>)}<button onClick={()=>setColumnFilters({})}>{tr('Сбросить фильтры')}</button></div>}<TableScroller>{error?<div className="timeline-feedback"><p role="alert">{tr('Не удалось загрузить результаты')}: {error}</p><button className="button secondary" onClick={()=>setTableAttempt(n=>n+1)}>{tr('Повторить')}</button></div>:columns.length ? <ResizableTable pageKey={requestKey} rowNumberDigits={String(Math.max(1,...rows.map(r=>r.index+1))).length} key={JSON.stringify([current.plugin,visible,widthRevision])} scope={current.plugin} columns={visible} filterColumns={Object.keys(columnFilters)} onFilter={setValueColumn} sort={sort} direction={direction} onSort={c=>{setSort(c);setDirection(sort===c&&direction==='asc'?'desc':'asc')}}>{rows.map(r => <tr key={r.index} tabIndex={0} aria-label={tr('Открыть строку {0}',r.index+1)} onKeyDown={e=>{if(e.target===e.currentTarget&&(e.key==='Enter'||e.key===' ')){e.preventDefault();inspect(r)}}} onClick={() => {if(!window.getSelection()?.toString())inspect(r)}} className={row?.index === r.index ? 'selected' : ''}><td className="bookmark-cell"><button aria-label={tr("Сохранить строку")} title={tr("Сохранить строку")} aria-pressed={markedRows.has(r.index)} disabled={savingRows.has(r.index)} className={markedRows.has(r.index)?'bookmarked':''} onClick={e => { e.stopPropagation(); saveRow(r); }}>{savingRows.has(r.index)?<Loader2 size={13} className="spin"/>:markedRows.has(r.index)?<Check size={13}/>:<BookMarked size={13}/>}</button></td><td className="index-cell">{r.index + 1}</td>{visible.map(c => <td key={c} onContextMenu={e=>contextFor(e,r,value(r.data[c]))} title={value(r.data[c])} className={/pid|port|size|thread/i.test(c)?'numeric-cell':/offset|base|addr/i.test(c)?'mono-cell':''} style={c === treeColumn&&r.depth>0 ? {paddingLeft:14+r.depth*18}:undefined}>{current.plugin==='banners.Banners'&&c==='Banner'?<BannerValue raw={r.data[c]}/>:c === 'State' ? <span className={'connection-state ' + (r.data[c] === 'ESTABLISHED' ? 'established' : '')}>{value(r.data[c])}</span> : value(r.data[c])}</td>)}</tr>)}</ResizableTable> : <Empty icon={FileSearch} title={fetching ? tr("Загружаем результаты…") : busy(current) ? tr("Движок работает") : tr("Данных для отображения нет")} text={fetching ? tr("Подготавливаем таблицу.") : busy(current) ? tr("После завершения здесь появится структурированный результат. Прогресс и сообщения доступны в журнале.") : tr("Пустой результат не доказывает отсутствие артефактов. Проверьте статус и журнал запуска.")}/>}</TableScroller>{columns.length > 0 && !rows.length && !fetching && !error && <Empty icon={Search} title={tr("Нет совпадений")} text={tr("Измените фильтр поиска.")}/>}<div className="table-pagination"><span>{!ready?tr(error?'Данные недоступны':'Загружаем результаты…'):total?tr("{0}\u2013{1} из {2}",summary.start,summary.end,total.toLocaleString('ru-RU')):tr("0 строк")}<i>·</i>{tr("100 строк на странице")}</span><PageNavigation page={page} pages={summary.pages} ready={ready} change={setPage}/></div></> :
                tab === 'log' ? <div className="log-view"><div className="log-label"><Terminal size={14}/>{tr(current.purpose==='pipeline'?'ПАРАМЕТРЫ КОНВЕЙЕРА':"АРГУМЕНТЫ VOLATILITY")}<IconButton title={tr("Скопировать команду")} onClick={() => navigator.clipboard.writeText(logs.command).then(() => notify(tr("Команда скопирована")))}><Copy size={13}/></IconButton></div><pre>{logs.command || tr("Команда появится при начале запуска.")}</pre>{logs.worker_command&&<details className="worker-command"><summary>{tr("Фактический запуск Studio")}</summary><div className="log-label"><span>PowerShell</span><IconButton title={tr("Скопировать команду")} onClick={()=>navigator.clipboard.writeText(logs.worker_command).then(()=>notify(tr("Команда скопирована")))}><Copy size={13}/></IconButton></div><pre>{logs.worker_command}</pre></details>}<div className="provenance-grid"><span>{tr("Версия Studio")}<strong>{current.studio_version||tr("Не записано")}</strong></span><span>Studio EXE SHA-256<strong title={current.studio_sha256}>{current.studio_sha256?short(current.studio_sha256,22):tr("Не записано")}</strong></span><span>{tr("Версия движка")}<strong>{current.engine_version}</strong></span><span>{tr("Режим символов")}<strong>{current.offline ? tr("Офлайн") : tr("Загрузка разрешена")}</strong></span><span>{tr("Начало (UTC)")}<strong>{time(current.started)}</strong></span><span>{tr("Источник")}<strong>{active.kind === 'demo' ? tr("Синтетические данные") : short(current.input_sha256 || tr("SHA-256 рассчитывается"), 22)}</strong></span></div><div className="log-label">{tr(current.purpose==='pipeline'?'ЖУРНАЛ КОНВЕЙЕРА':"ЖУРНАЛ VOLATILITY")}<small>{tr("последние 50 KB")}</small></div><pre className="engine-log">{logs.text || logs.error || tr("Сообщений пока нет.")}</pre></div> : <div>{artifacts.length ? <RunArtifacts runId={current.id} files={artifacts} notify={notify} failure={failure}/> : <Empty icon={FolderOpen} title={tr("Извлечённых файлов нет")} text={current.status!=="completed" ? tr("Файлы доступны после успешного завершения запуска. Проверьте статус и журнал.") : tr("Плагины с опциями извлечения сохраняют файлы в отдельный каталог запуска. Здесь будут доступны ссылки на них.")}/>}</div>}</>}</section></div>
    {context&&<ResultContextMenu target={context} close={()=>setContext(null)} copy={copyResult}/>}
    {row && current && <div className="sheet-backdrop" onClick={() => setRow(null)}><section ref={inspectorRef} className="plugin-sheet row-sheet" role="dialog" aria-modal="true" aria-label={tr("Подробности строки")} onClick={e => e.stopPropagation()}><div className="sheet-top"><span>{tr("ИНСПЕКТОР АРТЕФАКТА")}</span><IconButton title={tr("Закрыть инспектор")} onClick={() => setRow(null)}><X size={20}/></IconButton></div><div className="sheet-content"><div className="eyebrow">{current.plugin.split('.').at(-1)} / ROW {row.index + 1}</div><h2>{String(row.data.ImageFileName || row.data.Process || row.data.Owner || row.data.Variable || row.data.Name || tr("Подробности строки"))}</h2>{pid !== undefined && <span className="pid-pill">PID {String(pid)}</span>}<p className="address-note">{tr(current.purpose==='pipeline'&&current.params.source==='image'?'Offset — смещение байтов в исходном файле.':'Адреса и смещения заданы плагином. Они могут относиться к виртуальной или физической памяти и не равны смещению в файле.')}</p>{dumpFiles && <FileScanPivot key={current.id+':'+row.index} runId={current.id} rowIndex={row.index} failure={failure}
            open={(parameter,address)=>{setRow(null);openPlugin(dumpFiles,{[parameter]:[address]});}}/>}<dl className="row-details">{Object.entries(row.data).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{value(v)}</dd></div>)}</dl>{pid !== undefined && <><h3 className="small-heading">{tr("Продолжить исследование PID")} {String(pid)}</h3><div className="pid-actions">{pick(plugins, active.os, ['cmdline', 'dlllist', 'malfind', 'handles']).filter(p => p.args.some(a => a.name === 'pid')).map(p => <button key={p.id} onClick={() => { setRow(null); openPlugin(p, { pid: [Number(pid)] }); }}><Terminal size={14}/>{p.name}<ArrowUpRight size={13}/></button>)}</div></>}<h3 className="small-heading">{tr("Заметка аналитика")}</h3><ObservationNote key={current.id+":"+row.index} initial={note} change={text=>{observationText.current=text}}/><div className="row-source"><Hash size={13}/><span>{tr("Запуск")} {current.id} {tr("\u00B7 строка")} {row.index + 1}<small>{tr("Источник и параметры сохраняются вместе с наблюдением.")}</small></span></div></div><div className="sheet-bottom"><button className="button secondary" onClick={() => navigator.clipboard.writeText(JSON.stringify(row.data, null, 2)).then(() => notify(tr("JSON строки скопирован")))}><Copy size={15}/>JSON</button><button className="button primary" onClick={() => saveRow(row, observationText.current)}><BookMarked size={15}/>{tr("Сохранить наблюдение")}</button></div></section></div>}
  </>;
}
function BookmarksView({ active, bookmarks, openResult, reload, failure }: {
    active: Case;
    bookmarks: Bookmark[];
    openResult: (id: string,index?:number) => void;
    reload: () => Promise<void>;
    notify: (s: string) => void;
    failure: (e: unknown) => void;
    reloadCases: () => Promise<unknown>;
}) {
    const grouped = new Map<string, Bookmark[]>();
    for (const bookmark of bookmarks) {
        const group = grouped.get(bookmark.plugin) ?? [];
        group.push(bookmark);
        grouped.set(bookmark.plugin, group);
    }
    return <><div className="page-heading"><div><div className="eyebrow">{tr('Блокнот аналитика')}</div><h1>{tr("Наблюдения и заметки")}<span>.</span></h1><p>{tr("Сохранённые наблюдения, доказательства и ваши выводы в одном месте.")}</p></div><a className="button secondary" href={`/api/cases/${active.id}/report`}><Download size={16}/>{tr("Отчёт HTML")}</a></div><div className="notebook-layout"><section><div className="section-heading"><h2>{tr("Наблюдения")}<span className="count-pill">{bookmarks.length}</span></h2></div>{bookmarks.length ? Array.from(grouped, ([plugin, group]) => <details open className="bookmark-group" key={plugin}>
        <summary><strong>{plugin.split('.').at(-1)}</strong><span className="count-pill">{group.length}</span></summary>
        <div className="bookmark-group-items">{group.map(b => <article className="bookmark-card" key={b.id}><div className="bookmark-heading"><span className="bookmark-icon"><BookMarked size={17}/></span><div><h3>{String(b.data.ImageFileName || b.data.Process || b.data.Owner || b.data.Variable || b.data.Name || b.plugin.split('.').at(-1))}</h3><span>{b.plugin} {tr("\u00B7 строка")} {b.row_idx + 1}</span></div><IconButton title={tr("Удалить закладку")} onClick={() => api(`/bookmarks/${b.id}`, { method: 'DELETE' }).then(reload).catch(failure)}><Trash2 size={15}/></IconButton></div><div className="bookmark-values">{Object.entries(b.data).slice(0, 5).map(([k, v]) => <span key={k}><small>{k}</small><strong>{short(value(v), 50)}</strong></span>)}</div>{b.note && <p className="bookmark-note">{b.note}</p>}<button className="text-button" onClick={() => openResult(b.run_id,b.row_idx)}>{tr("Открыть исходный результат")}<ArrowRight size={14}/></button></article>)}</div></details>) : <section className="panel"><Empty icon={BookMarked} title={tr("Сохраните первое наблюдение")} text={tr("В результатах нажмите на строку или значок закладки. Сохранится ссылка на конкретный запуск и исходные данные.")}/></section>}</section><aside className="panel case-notes"><NotebookEditor scope={active.id} title={tr("Заметки кейса")}/></aside></div></>;
}
type TimelineEvent = {
    time: string;
    field: string;
    original: string;
    plugin: string;
    run_created: string;
    run_id: string;
    row_idx: number;
    data: Record<string, unknown>;
};
function TimelineView({ active, runs, openResult, failure }: SharedProps & {
    openResult: (id: string,index?:number) => void;
}) {
    type Page={events:TimelineEvent[];total:number;offset:number;limit:number};
    const [response,setResponse]=useState<{key:string;data:Page}|null>(null);
    const [loadError,setLoadError]=useState<{key:string;message:string}|null>(null);
    const [mode,setMode]=useState('artifacts'),[q,setQ]=useState(''),[search,setSearch]=useState(''),[runFilter,setRunFilter]=useState('latest');
    const [eventPage,setEventPage]=useState(0),[attempt,setAttempt]=useState(0);
    const complete=runs.filter(r=>r.status==='completed').length;
    const key=JSON.stringify([active.id,complete,search,eventPage,attempt,runFilter]);
    useEffect(()=>{const timer=setTimeout(()=>{setSearch(q);setEventPage(0)},250);return()=>clearTimeout(timer)},[q]);
    useEffect(()=>{setEventPage(0)},[active.id,complete]);
    useEffect(()=>{
        if(mode!=='artifacts')return;
        const controller=new AbortController();
        const params=new URLSearchParams({offset:String(eventPage*100),limit:'100',q:search,scope:runFilter==='latest'?'latest':'all'});if(!['latest','all'].includes(runFilter))params.set('run_id',runFilter);
        api<Page>(`/cases/${active.id}/timeline?${params}`,{signal:controller.signal}).then(data=>{
            if(controller.signal.aborted)return;
            if(eventPage>0&&eventPage*100>=data.total){setEventPage(Math.max(0,Math.ceil(data.total/100)-1));return}
            setResponse({key,data});setLoadError(null);
        }).catch(error=>{if(!controller.signal.aborted){setLoadError({key,message:String(error instanceof Error?error.message:error)});failure(error)}});
        return()=>controller.abort();
    },[key,mode,failure]);
    const ready=response?.key===key&&q===search,events=ready?response.data.events:[],total=ready?response.data.total:0;
    const error=loadError?.key===key?loadError.message:'';
    const runEvents=runs.slice().reverse().filter(r=>[r.plugin,r.status,r.created].some(v=>v.toLowerCase().includes(q.toLowerCase())));
    const pages=Math.max(1,Math.ceil(total/100));
    return <>
        <div className="page-heading"><div><h1>{tr('Временная шкала')}<span>.</span></h1><p>{tr('Сопоставляйте временные поля артефактов с их источниками.')}</p></div><span className="count-pill"><Clock3 size={15}/>{mode==='runs'?runEvents.length:ready?total:'…'} {tr('событий')}</span></div>
        <div className="timeline-toolbar"><div className="segmented"><button className={mode==='artifacts'?'selected':''} onClick={()=>setMode('artifacts')}>{tr('Артефакты памяти')}</button><button className={mode==='runs'?'selected':''} onClick={()=>setMode('runs')}>{tr('Ход исследования')}</button></div><label className="search-input"><Search size={15}/><input maxLength={512} placeholder={tr('Фильтр событий…')} value={q} onChange={e=>setQ(e.target.value)}/>{q&&<button title={tr('Сбросить фильтр')} aria-label={tr('Сбросить фильтр')} onClick={()=>setQ('')}><X size={15}/></button>}</label></div>
        {mode==='artifacts'&&<label className="timeline-run-filter">{tr('Источники событий')}<select aria-label={tr('Источники событий')} value={runFilter} onChange={e=>{setRunFilter(e.target.value);setEventPage(0)}}><option value="latest">{tr('Последний завершённый запуск каждого плагина')}</option><option value="all">{tr('Все завершённые запуски')}</option>{runs.filter(r=>r.status==='completed').map(r=><option key={r.id} value={r.id}>{r.plugin.split('.').at(-1)} · {r.created.slice(0,10)} {time(r.created)} · #{r.id.slice(0,8)}</option>)}</select></label>}
        <section className="panel timeline-panel" aria-busy={mode==='artifacts'&&!ready&&!error}>
        {mode==='artifacts'? error?<div className="timeline-feedback"><p role="alert">{tr('Не удалось загрузить временную шкалу')}: {error}</p><button className="button secondary" onClick={()=>setAttempt(n=>n+1)}>{tr('Повторить')}</button></div>:!ready?<div className="timeline-feedback" role="status"><Loader2 size={20} className="spin"/><p>{tr('Загрузка временной шкалы…')}</p><small>{tr('При первом открытии индексируются временные поля сохранённых результатов.')}</small></div>:events.length?<>
            <div className="timeline-note"><Clock3 size={14}/>{tr('Время приведено к UTC. Подпись события соответствует исходному полю плагина.')}</div>
            <div className="timeline-event-list">{events.map(e=><button className="timeline-row" key={JSON.stringify([e.run_id,e.row_idx,e.field])} title={`${e.original} → ${e.time}`} onClick={()=>openResult(e.run_id,e.row_idx)}><span className="timeline-time"><strong>{e.time.slice(11,23)}</strong><small>{e.time.slice(0,10)} UTC</small></span><span className="timeline-node"><i/></span><span className="timeline-detail"><strong>{String(e.data.ImageFileName||e.data.Process||e.data.Owner||e.data.Variable||e.plugin.split('.').at(-1))}<span>{e.data.PID!==undefined?`PID ${e.data.PID}`:''}</span></strong><small>{e.field} · {e.plugin}{tr('· строка')} {e.row_idx+1} · #{e.run_id.slice(0,8)} · {time(e.run_created)}</small></span><ArrowUpRight size={15}/></button>)}</div>
            <div className="table-pagination"><span>{tr('{0}–{1} из {2}',eventPage*100+1,eventPage*100+events.length,total)}</span><div><button className="text-button" disabled={!eventPage} onClick={()=>setEventPage(0)}>{tr('В начало')}</button><IconButton title={tr('Предыдущая страница')} disabled={!eventPage} onClick={()=>setEventPage(n=>n-1)}><ChevronLeft size={16}/></IconButton><span>{eventPage+1} / {pages}</span><IconButton title={tr('Следующая страница')} disabled={eventPage+1>=pages} onClick={()=>setEventPage(n=>n+1)}><ChevronRight size={16}/></IconButton><button className="text-button" disabled={eventPage+1>=pages} onClick={()=>setEventPage(pages-1)}>{tr('В конец')}</button></div></div>
        </>:search?<Empty icon={Search} title={tr('Совпадений нет')} text={tr('Измените запрос или сбросьте фильтр. Поиск охватывает всю временную шкалу.')}/>:<Empty icon={Clock3} title={tr('Временных событий пока нет')} text={tr('Запустите плагины с временными полями, например PsList, NetScan или DllList. События без часового пояса сюда не включаются.')}/>:runEvents.length?runEvents.map(r=><button className="timeline-row" key={r.id} onClick={()=>openResult(r.id)}><span className="timeline-time"><strong>{time(r.created).replace(' UTC','')}</strong><small>{r.created.slice(0,10)} UTC</small></span><span className="timeline-node"><i/></span><span className="timeline-detail"><strong>{r.plugin.split('.').at(-1)}</strong><small>{r.plugin} · {r.row_count} {tr('строк')}</small></span><Status status={r.status}/></button>):<Empty icon={Clock3} title={tr(q?'Совпадений нет':'История начинается с первого запуска')} text={tr(q?'Измените запрос или сбросьте фильтр.':'Здесь появятся события выполнения плагинов.')}/>}
        </section>
    </>;
}
function SettingsView({ onSaved, notify, failure }: {
    health: Health | null;
    onSaved: (v: {
        plugins: Plugin[];
    }) => void;
    notify: (s: string) => void;
    failure: (e: unknown) => void;
}) { const resource=useResource(()=>api<Settings>('/settings'));const [config, setConfig] = useState<Settings|null>(null), [symbolText, setSymbolText] = useState(''), [pluginText, setPluginText] = useState(''), [saving, setSaving] = useState(false); useEffect(()=>{if(resource.state.status!=='ready')return;const c=resource.state.value;setConfig(c);setSymbolText(c.symbol_dirs.join('\n'));setPluginText(c.plugin_dirs.join('\n'))},[resource.state]);async function save() {if(!config||resource.state.status!=='ready'||saving)return;if(!Number.isInteger(config.memory_limit_mb??0)||(config.memory_limit_mb??0)<0){failure(new Error(tr('Введите лимит от 0,25 до 1024 ГБ')));return} setSaving(true); try {
    const r = await api<{
        catalog: {
            plugins: Plugin[];
        };
    }>('/settings', { method: 'PUT', body: JSON.stringify({ ...config, symbol_dirs: symbolText.split('\n').map(s => s.trim()).filter(Boolean), plugin_dirs: pluginText.split('\n').map(s => s.trim()).filter(Boolean) }) });
    onSaved(r.catalog);
    notify(tr("Настройки сохранены. Каталог плагинов обновлён."));
}
catch (e) {
    failure(e);
}
finally {
    setSaving(false);
} } if(!config||resource.state.status!=='ready')return <ResourceFeedback title={tr(resource.state.status==='error'?'Не удалось загрузить настройки':'Загружаем настройки…')} error={resource.state.error} retry={resource.reload}/>;return <><div className="page-heading engine-settings-heading"><div><h1>{tr("Настройки приложения")}<span>.</span></h1><p>{tr("Символы, дополнительные плагины и доступ к сети.")}</p></div></div><div className="settings-layout"><section className="panel settings-panel"><div className="settings-section"><h2><Globe size={19}/>{tr("Символы и сеть")}</h2><label className="switch-row"><span><strong>{tr("Офлайн-режим")}</strong><small>{tr("Запретить Volatility загружать символы из сети. Для Windows, Linux и macOS могут потребоваться локальные символы.")}</small></span><input type="checkbox" role="switch" checked={config.offline} onChange={e => setConfig({ ...config, offline: e.target.checked })}/></label><DirectoryPicker paths={symbolText.split('\n').filter(Boolean)} onChange={paths=>setSymbolText(paths.join('\n'))} description={tr('Выберите папку с данными ОС, если она нужна для вашего образа.')} failure={failure}/></div><ResourceSettings config={config} setConfig={setConfig}/><div className="settings-section"><h2><PlugZap size={19}/>{tr("Дополнительные плагины")}</h2><p>{tr("Только доверенные Python-плагины: их код выполняется на вашем компьютере.")}</p><DirectoryPicker paths={pluginText.split('\n').filter(Boolean)} onChange={paths=>setPluginText(paths.join('\n'))} description={tr('Выберите папку с дополнительными плагинами.')} failure={failure}/></div><div className="settings-save"><span>{tr("Новые настройки применяются к новым запускам.")}</span><button className="button primary" onClick={save} disabled={saving}>{saving ? <Loader2 size={16} className="spin"/> : <Check size={16}/>}{tr("Сохранить и обновить")}</button></div></section></div></>; }

function BannerValue({raw}:{raw:unknown}){const parsed=parseWindowsBanner(raw);return parsed?<span className="banner-value"><strong>{parsed.pdb}</strong><small><span>GUID {parsed.guid}</span><span>{tr("Ревизия")} {parsed.age}</span></small></span>:<>{value(raw)}</>}
