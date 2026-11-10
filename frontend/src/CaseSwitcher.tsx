import {useLayoutEffect,useRef,useState,type KeyboardEvent} from 'react';
import {Check,Plus,Search,X} from 'lucide-react';
import {tr} from './i18n';
import {caseMatches} from './caseIdentity';
import {Popover} from './Popover';
import type {Case} from './types';
import './CaseSwitcher.css';

export function CaseSwitcher({cases,activeId,openIds,select,close,create,dismiss}:{cases:Case[];activeId:string;openIds:string[];select:(id:string)=>void;close:(id:string)=>void;create:()=>void;dismiss:()=>void}){
    const [query,setQuery]=useState('');
    const root=useRef<HTMLDivElement>(null),search=useRef<HTMLInputElement>(null),closed=useRef<string|null>(null);
    const filtered=cases.filter(c=>caseMatches(c,query));
    const groups=[true,false].map(opened=>({opened,cases:filtered.filter(c=>openIds.includes(c.id)===opened)})).filter(group=>group.cases.length);
    useLayoutEffect(()=>{
        if(!closed.current)return;
        const id=closed.current;closed.current=null;
        const target=Array.from(root.current?.querySelectorAll<HTMLButtonElement>('button[data-case-id]')??[]).find(button=>button.dataset.caseId===id);
        (target??search.current)?.focus();
    },[openIds]);
    function keys(event:KeyboardEvent<HTMLDivElement>){
        if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
        if((event.key==='Home'||event.key==='End')&&event.target===search.current)return;
        const options=Array.from(root.current?.querySelectorAll<HTMLButtonElement>('[data-case-choice]')??[]);
        if(!options.length)return;
        const index=options.indexOf(document.activeElement as HTMLButtonElement);
        const next=event.key==='Home'?0:event.key==='End'?options.length-1:event.key==='ArrowDown'?(index+1)%options.length:index<0?options.length-1:(index-1+options.length)%options.length;
        event.preventDefault();options[next].focus();
    }
    return <Popover id="case-switcher" className="case-menu case-switcher" label={tr('Выбор образа')} dismiss={dismiss} surfaceRef={root} onKeyDown={keys}>
        <label className="case-search"><Search size={15} aria-hidden="true"/><input ref={search} autoFocus value={query} onChange={e=>setQuery(e.target.value)}
            aria-label={tr('Найти образ по имени, пути, ID или SHA-256')} placeholder={tr('Имя, путь, ID или SHA-256')}/></label>
        <div className="case-options">{groups.map(group=><section className="case-group" key={String(group.opened)}>
            <h3 className="case-group-label">{tr(group.opened?'Открытые образы':'Недавние образы')}</h3>
            {group.cases.map(c=>{
                const slash=Math.max(c.path.lastIndexOf('\\'),c.path.lastIndexOf('/'));
                const directory=slash>=0?c.path.slice(0,slash+1):c.path;
                return <div className={'case-option-row'+(c.id===activeId?' is-active':'')} key={c.id}>
                    <button type="button" className="case-option" data-case-choice data-case-id={c.id}
                        aria-pressed={c.id===activeId} title={c.name+'\n'+c.path+'\n'+c.id} onClick={()=>select(c.id)}>
                        <span className="case-selection-mark" aria-hidden="true">{c.id===activeId&&<Check size={16} strokeWidth={2.25}/>}</span>
                        <span className="case-option-copy"><strong>{c.name}</strong><small>
                            {directory&&<span className="case-directory">{directory}</span>}<code>{c.id.slice(0,8).toUpperCase()}</code>
                        </small></span>
                    </button>
                    {group.opened&&<button type="button" className="case-close" aria-label={tr('Закрыть образ {0}',c.name)} title={tr('Закрыть образ')}
                        onClick={()=>{closed.current=c.id;close(c.id)}}><X size={14} strokeWidth={1.8} aria-hidden="true"/></button>}
                </div>;
            })}
        </section>)}{!filtered.length&&<p className="case-no-matches" role="status">{tr('Образы не найдены')}</p>}</div>
        <div className="case-menu-footer"><button type="button" data-case-choice className="case-create" onClick={create}><Plus size={16} strokeWidth={1.8} aria-hidden="true"/>{tr('Открыть образ памяти')}</button></div>
    </Popover>;
}
