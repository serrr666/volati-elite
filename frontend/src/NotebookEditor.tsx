import {useCallback,useEffect,useMemo,useRef,useState,useSyncExternalStore} from 'react';
import {Check,ChevronDown,ChevronUp,Copy,Download,FilePenLine,Loader2,Search,X} from 'lucide-react';
import {api} from './api';
import {tr} from './i18n';
import {NotebookStore,type NotebookValue} from './notebookStore';
import type {Case} from './types';
export const investigationNotes=new NotebookStore(
    id=>api<NotebookValue>(id==='workspace'?'/workspace/notebook':`/cases/${id}/notebook`),
    (id,text)=>api(id==='workspace'?'/workspace/notebook/commit':`/cases/${id}/notebook`,{method:'PUT',body:JSON.stringify({text})}),
);
export function NotebookEditor({scope,title,focus=false}:{scope:string;title:string;focus?:boolean}){
    const subscribe=useCallback((listener:()=>void)=>investigationNotes.subscribe(scope,listener),[scope]);
    const snapshot=useCallback(()=>investigationNotes.snapshot(scope),[scope]);
    const state=useSyncExternalStore(subscribe,snapshot),input=useRef<HTMLTextAreaElement>(null),focused=useRef(false);
    const [message,setMessage]=useState('');
    const [searchOpen,setSearchOpen]=useState(false),[query,setQuery]=useState(''),[matchIndex,setMatchIndex]=useState(-1);
    const matches=useMemo(()=>query ? Array.from(state.text.matchAll(new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'giu'))) : [],[query,state.text]);
    function stepMatch(direction:number){
        if(!matches.length)return;
        const next=matchIndex<0?(direction===1?0:matches.length-1):(matchIndex+direction+matches.length)%matches.length;
        const match=matches[next];
        setMatchIndex(next);
        input.current?.focus();
        input.current?.setSelectionRange(match.index,match.index+match[0].length);
    }
    useEffect(()=>{void investigationNotes.load(scope).catch(()=>{});return()=>{void investigationNotes.flush(scope).catch(()=>{})}},[scope]);
    useEffect(()=>{if(focus&&state.loaded&&!focused.current){input.current?.focus();focused.current=true}},[focus,state.loaded]);
    async function copy(){try{await navigator.clipboard.writeText(state.text);setMessage(tr('Скопировано'))}catch(e){setMessage(String(e))}}
    function download(){const url=URL.createObjectURL(new Blob([state.text],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=(title.replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').slice(0,110)||'investigation')+'.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
    return <section className="investigation-editor"><div className="notebook-editor-heading"><strong title={title}>{title}</strong><div><button className="icon-button" disabled={!state.loaded} title={tr('Поиск в блокноте')} aria-label={tr('Поиск в блокноте')} aria-expanded={searchOpen} onClick={()=>setSearchOpen(value=>!value)}><Search size={15}/></button><button className="icon-button" disabled={!state.loaded} title={tr('Копировать заметки')} aria-label={tr('Копировать заметки')} onClick={copy}><Copy size={15}/></button><button className="icon-button" disabled={!state.loaded} title={tr('Экспорт заметок TXT')} aria-label={tr('Экспорт заметок TXT')} onClick={download}><Download size={15}/></button></div></div>
    {searchOpen&&<div className="notebook-find"><label className="search-input"><Search size={14}/><input autoFocus value={query} maxLength={160} aria-label={tr('Поиск в блокноте')} placeholder={tr('Поиск в блокноте')} onChange={e=>{setQuery(e.target.value);setMatchIndex(-1)}} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();stepMatch(e.shiftKey?-1:1)}if(e.key==='Escape'){e.preventDefault();setSearchOpen(false)}}}/></label><small aria-live="polite">{query?(matches.length?`${Math.max(0,Math.min(matchIndex+1,matches.length))} / ${matches.length}`:tr('Ничего не найдено')):''}</small><button className="icon-button" disabled={!matches.length} title={tr('Предыдущее совпадение')} aria-label={tr('Предыдущее совпадение')} onClick={()=>stepMatch(-1)}><ChevronUp size={15}/></button><button className="icon-button" disabled={!matches.length} title={tr('Следующее совпадение')} aria-label={tr('Следующее совпадение')} onClick={()=>stepMatch(1)}><ChevronDown size={15}/></button></div>}
    <textarea ref={input} aria-label={tr('Текст расследования')} disabled={!state.loaded} maxLength={100000} spellCheck={false} value={state.text} placeholder={tr('План, гипотезы, команды, находки и выводы…')} onChange={e=>{setMessage('');investigationNotes.edit(scope,e.target.value)}} onBlur={()=>{void investigationNotes.flush(scope).catch(()=>{})}} onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();e.stopPropagation();void investigationNotes.flush(scope).catch(()=>{})}}}/>
    <div className="notebook-editor-status"><span role="status">{state.status==='loading'?tr('Загрузка…'):state.status==='error'?tr(state.loaded?'Не удалось сохранить заметки':'Не удалось загрузить заметки'):state.status==='ready'?<><Check size={13}/>{tr('Все изменения сохранены')}</>:<><Loader2 size={13} className="spin"/>{tr('Сохраняем заметки…')}</>}</span><small>{state.text.length.toLocaleString()} / 100 000</small></div>
    {state.status==='error'&&<div role="alert" className="notebook-error"><p>{state.error}</p><button className="button secondary" onClick={()=>{void (state.loaded?investigationNotes.flush(scope):investigationNotes.load(scope)).catch(()=>{})}}>{tr('Повторить')}</button></div>}{message&&<small role="status">{message}</small>}</section>;
}
export function QuickNotebook({active,close}:{active?:Case;close:()=>void}){
    const [shared,setShared]=useState(false);const general=shared||!active,scope=general?'workspace':active.id;
    const title=general?tr('Общие заметки'):active!.name;
    useEffect(()=>{function key(e:KeyboardEvent){if(e.key==='Escape'&&!e.defaultPrevented){e.preventDefault();close()}}window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[close]);
    return <aside className="quick-notebook" role="complementary" aria-label={tr('Блокнот расследования')}><div className="quick-notebook-heading"><h2><FilePenLine size={17}/>{tr('Блокнот расследования')}</h2><button className="icon-button" title={tr('Закрыть')} aria-label={tr('Закрыть блокнот')} onClick={close}><X size={18}/></button></div>{active&&<div className="notebook-scope"><button aria-pressed={!general} onClick={()=>setShared(false)}>{tr('Заметки кейса')}</button><button aria-pressed={general} onClick={()=>setShared(true)}>{tr('Общие заметки')}</button></div>}<NotebookEditor key={scope} scope={scope} title={title} focus/></aside>;
}
// Typing an observation must not render the underlying 100-row result table.
export function ObservationNote({initial,change}:{initial:string;change:(text:string)=>void}){
    const [text,setText]=useState(initial);
    return <textarea aria-label={tr('Заметка аналитика')} maxLength={20000} value={text} onChange={e=>{setText(e.target.value);change(e.target.value)}} placeholder={tr('Что стоит проверить? Почему эта строка важна?')} rows={4}/>;
}
