export function errorMessage(detail:unknown,status:number):string{
  if(typeof detail==='string')return detail.slice(0,1600);
  if(Array.isArray(detail)){
    const messages=detail.slice(0,5).map(item=>{
      if(!item||typeof item!=='object')return '';
      const field=Array.isArray(item.loc)?item.loc.filter((v:unknown)=>v!=='body').join('.') : '';
      return typeof item.msg==='string'?(field?field+': ':'')+item.msg:'';
    }).filter(Boolean);
    if(messages.length)return messages.join('\n').slice(0,1600);
  }
  return `HTTP ${status}`;
}

export async function api<T>(path:string, options:RequestInit={}):Promise<T> {
  const response=await fetch('/api'+path,{...options,headers:{...(options.body && !(options.body instanceof FormData)?{'Content-Type':'application/json'}:{}),...options.headers}});
  if(!response.ok){let message=`HTTP ${response.status}`;try{const data=await response.json();message=errorMessage(data.detail,response.status)}catch{/* retain HTTP status */}throw new Error(message)}
  return response.json();
}
export const post=<T>(path:string,data:unknown={})=>api<T>(path,{method:'POST',body:JSON.stringify(data)});
export const value=(v:unknown):string=>v===null||v===undefined?'—':typeof v==='object'?JSON.stringify(v):String(v);
export function bytes(n:number){if(!Number.isFinite(n)||n<=0)return '0 B';const i=Math.max(0,Math.min(4,Math.floor(Math.log(n)/Math.log(1024))));return `${(n/1024**i).toFixed(i>1?1:0)} ${['B','KiB','MiB','GiB','TiB'][i]}`} 
export function elapsed(run:{started:string|null;finished:string|null}){if(!run.started)return '—';const n=Math.max(0,Math.round(((run.finished?new Date(run.finished).getTime():Date.now())-new Date(run.started).getTime())/1000));return n<60?`${n}s`:`${Math.floor(n/60)}m ${n%60}s`}
export const time=(s:string|null)=>s?new Date(s).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit',second:'2-digit',timeZone:'UTC'})+' UTC':'—';
export const short=(s:string,n=32)=>s.length>n?s.slice(0,n)+'…':s;
