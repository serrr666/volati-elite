import {useEffect,useState} from 'react';
import {ChevronLeft,ChevronRight,ChevronsLeft,ChevronsRight} from 'lucide-react';
import {tr} from './i18n';
import {pageFromInput} from './pageInput';
export function PageNavigation({page,pages,ready,change}:{page:number;pages:number;ready:boolean;change:(page:number)=>void}){
    const [input,setInput]=useState(String(page+1)),[error,setError]=useState(false);
    useEffect(()=>{setInput(String(page+1));setError(false)},[page,pages]);
    function commit(){const next=pageFromInput(input,pages);if(next===null){setError(true);return}setError(false);setInput(String(next+1));if(next!==page)change(next)}
    const button=(label:string,disabled:boolean,action:()=>void,icon:React.ReactNode)=><button className="icon-button" title={label} aria-label={label} disabled={!ready||disabled} onClick={action}>{icon}</button>;
    return <div className="page-navigation">
        {pages>5&&button(tr('Первая страница'),page===0,()=>change(0),<ChevronsLeft size={16}/>)}
        {button(tr('Предыдущая страница'),page===0,()=>change(page-1),<ChevronLeft size={16}/>)}
        <form onSubmit={event=>{event.preventDefault();commit()}} className="page-number-form">
            <input aria-label={tr('Перейти на страницу')} title={tr('Введите номер страницы и нажмите Enter')} aria-invalid={error||undefined} disabled={!ready||pages<2} inputMode="numeric" value={ready?input:'—'} onFocus={event=>event.currentTarget.select()} onChange={event=>{setInput(event.target.value);setError(false)}} onBlur={()=>{setInput(String(page+1));setError(false)}} style={{width:Math.max(3,String(pages).length+1)+'ch'}}/>
            <span>/ {ready?pages:'—'}</span>
        </form>
        {button(tr('Следующая страница'),page+1>=pages,()=>change(page+1),<ChevronRight size={16}/>)}
        {pages>5&&button(tr('Последняя страница'),page+1>=pages,()=>change(pages-1),<ChevronsRight size={16}/>)}
        {error&&<span className="page-input-error" role="alert">{tr('Введите страницу от 1 до {0}',pages)}</span>}
    </div>;
}
