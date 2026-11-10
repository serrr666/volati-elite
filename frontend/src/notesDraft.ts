import {api} from './api';

// Browser origins change with the desktop's loopback port. Keep drafts in the
// case database, and serialize/coalesce writes so old text cannot arrive last.
export class NoteDraftStore {
    private cache=new Map<string,string|null>();
    private pending=new Map<string,string|null>();
    private inFlight=new Map<string,Promise<void>>();
    constructor(private read:(id:string)=>Promise<string|null>,private write:(id:string,text:string|null)=>Promise<unknown>){}
    peek(id:string){return this.cache.get(id)}
    async load(id:string):Promise<string|null>{
        if(this.cache.has(id))return this.cache.get(id)!;
        const draft=await this.read(id);
        if(!this.cache.has(id))this.cache.set(id,draft);
        return this.cache.get(id)!;
    }
    save(id:string,text:string,saved:string){
        const value=text===saved?null:text;
        this.cache.set(id,value);this.pending.set(id,value);
        return this.flush(id);
    }
    private flush(id:string):Promise<void>{
        if(this.inFlight.has(id))return this.inFlight.get(id)!;
        let successful=false;
        const task=Promise.resolve().then(async()=>{
            while(this.pending.has(id)){
                const text=this.pending.get(id)!;
                await this.write(id,text);
                if(this.pending.get(id)===text)this.pending.delete(id);
            }
            successful=true;
        }).finally(()=>{
            if(this.inFlight.get(id)===task)this.inFlight.delete(id);
            if(successful&&this.pending.has(id))return this.flush(id);
        });
        this.inFlight.set(id,task);return task;
    }
    async flushAll(){
        while(this.pending.size)await Promise.all([...this.pending.keys()].map(id=>this.flush(id)));
    }
}

export const noteDrafts=new NoteDraftStore(
    async id=>(await api<{text:string|null}>(`/cases/${id}/draft`)).text,
    (id,text)=>api(`/cases/${id}/draft`,{method:'PUT',body:JSON.stringify({text})}),
);
export const workspaceDrafts=new NoteDraftStore(
    async()=> (await api<{draft:string|null}>('/workspace/notebook')).draft,
    (_,text)=>api('/workspace/notebook/draft',{method:'PUT',body:JSON.stringify({text})}),
);
