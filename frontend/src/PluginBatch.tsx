import {useState} from 'react';
import {Loader2,Play} from 'lucide-react';
import {Dialog} from './Dialog';
import {tr} from './i18n';
import type {Plugin} from './types';
export type BatchRequest={plugin:string;params:Record<string,unknown>};
export function PluginArgument({argument:a,params,setParams}:{argument:Plugin['args'][number];params:Record<string,unknown>;setParams:(v:Record<string,unknown>)=>void}){
    return <label className={'argument '+(a.type==='boolean'?'boolean':'')}><span><code>--{a.name}</code>{!a.optional&&<em>{tr('Обязательно')}</em>}</span>{a.type==='boolean'?<input type="checkbox" checked={Boolean(params[a.name]??a.default??false)} onChange={e=>setParams({...params,[a.name]:e.target.checked})}/>:a.type==='choice'?<select value={String(params[a.name]??'')} onChange={e=>setParams({...params,[a.name]:e.target.value})}><option value="">{tr('По умолчанию')}</option>{a.choices.map(c=><option key={c}>{c}</option>)}</select>:<input value={String(params[a.name]??'')} placeholder={a.default!=null?String(a.default):a.type.startsWith('list')?tr('Значения через пробел'):tr('Введите значение')} onChange={e=>setParams({...params,[a.name]:e.target.value})}/>}<small>{a.description}</small></label>;
}
export function PluginBatch({plugins,queue,close}:{plugins:Plugin[];queue:(requests:BatchRequest[])=>Promise<boolean>;close:()=>void}){
    const [params,setParams]=useState<Record<string,Record<string,unknown>>>({}),[sending,setSending]=useState(false);
    const missing=plugins.some(p=>p.args.some(a=>!a.optional&&a.default==null&&(params[p.id]?.[a.name]==null||params[p.id]?.[a.name]==='')));
    async function submit(){setSending(true);try{if(await queue(plugins.map(p=>({plugin:p.id,params:params[p.id]??{}}))))close()}finally{setSending(false)}}
    return <Dialog title={tr('Параметры выбранных плагинов')} close={()=>!sending&&close()}><div className="batch-dialog-body"><p className="muted">{tr('Запуски выполнятся по очереди. Все результаты сохранятся отдельно.')}</p>{plugins.map(p=><details key={p.id} open={p.args.some(a=>!a.optional&&a.default==null)||undefined}><summary>{p.name}<small>{p.os}</small></summary>{p.args.map(a=><PluginArgument key={a.name} argument={a} params={params[p.id]??{}} setParams={values=>setParams(old=>({...old,[p.id]:values}))}/>)}{!p.args.length&&<p className="muted">{tr('Дополнительные параметры не требуются.')}</p>}</details>)}</div><div className="studio-dialog-footer"><button className="button secondary" onClick={close} disabled={sending}>{tr('Отмена')}</button><button className="button primary" disabled={sending||missing} onClick={submit}>{sending?<Loader2 size={15} className="spin"/>:<Play size={15}/>} {tr('Запустить выбранные ({0})',plugins.length)}</button></div></Dialog>;
}
