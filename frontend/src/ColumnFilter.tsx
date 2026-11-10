import {useEffect,useState} from 'react';
import {Loader2,Search} from 'lucide-react';
import {Dialog} from './Dialog';
import {api} from './api';
import {tr} from './i18n';
export type ColumnRule={exclude:boolean;values:string[]};
export type ColumnFilters=Record<string,ColumnRule>;
export function filterArgument(filters:ColumnFilters){
    const encoded=Object.keys(filters).length?encodeURIComponent(JSON.stringify(filters)):'';
    if(encoded.length>10000)throw new Error('Слишком много выбранных значений. Вместо этого исключите ненужные.');
    return encoded;
}
type Item={token:string;type:string|null;value:unknown;count:number};
export function ColumnFilter({runId,column,query,filters,apply,close}:{runId:string;column:string;query:string;filters:ColumnFilters;apply:(rule:ColumnRule|null)=>void;close:()=>void}){
    const [rule,setRule]=useState<ColumnRule>(()=>filters[column]??{exclude:true,values:[]});
    const [search,setSearch]=useState(''),[term,setTerm]=useState(''),[offset,setOffset]=useState(0),[items,setItems]=useState<Item[]>([]),[more,setMore]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState('');
    const encoded=filterArgument(filters);
    useEffect(()=>{const timer=setTimeout(()=>{setTerm(search);setOffset(0)},250);return()=>clearTimeout(timer)},[search]);
    useEffect(()=>{const abort=new AbortController();setLoading(true);setError('');
        api<{values:Item[];has_more:boolean}>(`/runs/${runId}/values?column=${encodeURIComponent(column)}&q=${encodeURIComponent(query)}&filters=${encoded}&search=${encodeURIComponent(term)}&offset=${offset}`,{signal:abort.signal}).then(result=>{
            if(abort.signal.aborted)return;setItems(old=>offset?[...old,...result.values]:result.values);setMore(result.has_more);
        }).catch(e=>{if(!abort.signal.aborted)setError(e.message)}).finally(()=>{if(!abort.signal.aborted)setLoading(false)});
        return()=>abort.abort();
    },[runId,column,query,encoded,term,offset]);
    const all=rule.exclude&&!rule.values.length,none=!rule.exclude&&!rule.values.length;
    function toggle(token:string){setRule(old=>({...old,values:old.values.includes(token)?old.values.filter(v=>v!==token):[...old.values,token]}))}
    function submit(){try{filterArgument({...filters,[column]:rule});apply(all?null:rule);close()}catch(e){setError((e as Error).message)}}
    const label=(item:Item)=>item.type===null?tr('(Поле отсутствует)'):item.type==='null'?tr('(Пусто)'):item.type==='text'&&item.value===''?tr('(Пустая строка)'):item.type==='true'?'true':item.type==='false'?'false':String(item.value);
    return <Dialog title={tr('Фильтр значений: {0}',column)} close={close}><div className="value-filter-body">
        <label className="search-input"><Search size={15}/><input autoFocus aria-label={tr('Поиск значений')} placeholder={tr('Поиск значений')} value={search} onChange={e=>setSearch(e.target.value)}/></label>
        <div className="value-filter-controls"><button className="text-button" onClick={()=>setRule({exclude:true,values:[]})}>{tr('Выбрать всё')}</button><button className="text-button" onClick={()=>setRule({exclude:false,values:[]})}>{tr('Снять выделение')}</button><span>{all?tr('Все значения'):none?tr('Ничего не выбрано'):tr(rule.exclude?'Исключено: {0}':'Выбрано: {0}',rule.values.length)}</span></div>
        <div className="value-filter-list" aria-busy={loading}>{items.map(item=><label key={item.token} title={label(item)}><input type="checkbox" checked={rule.exclude?!rule.values.includes(item.token):rule.values.includes(item.token)} onChange={()=>toggle(item.token)}/><span>{label(item)}</span><small>{item.count.toLocaleString()}</small></label>)}{loading&&<div className="muted"><Loader2 size={15} className="spin"/> {tr('Загрузка…')}</div>}{!loading&&!items.length&&!error&&<p className="muted">{tr('Нет совпадений')}</p>}{more&&<button className="text-button" disabled={loading} onClick={()=>setOffset(offset+100)}>{tr('Загрузить ещё')}</button>}</div>
        {error&&<p role="alert" className="error-text">{tr(error)}</p>}</div><div className="studio-dialog-footer"><button className="button secondary" onClick={()=>{apply(null);close()}}>{tr('Сбросить фильтр')}</button><button className="button primary" onClick={submit}>{tr('Применить')}</button></div></Dialog>;
}
