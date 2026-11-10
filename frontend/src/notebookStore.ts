export type NotebookValue={text:string;draft:string|null};
export type NotebookState={text:string;loaded:boolean;status:'loading'|'ready'|'dirty'|'saving'|'error';error:string};
type Entry={state:NotebookState;saved:string;dirty:boolean;listeners:Set<()=>void>;load?:Promise<void>;write?:Promise<void>;timer?:ReturnType<typeof setTimeout>};
// Shared between the page and the quick notebook. Writes are delayed and serialized.
export class NotebookStore{
    private entries=new Map<string,Entry>();
    constructor(private read:(id:string)=>Promise<NotebookValue>,private write:(id:string,text:string)=>Promise<unknown>,private delay=700){}
    private entry(id:string){let e=this.entries.get(id);if(!e){e={state:{text:'',loaded:false,status:'loading',error:''},saved:'',dirty:false,listeners:new Set()};this.entries.set(id,e)}return e}
    snapshot(id:string){return this.entry(id).state}
    subscribe(id:string,listener:()=>void){const e=this.entry(id);e.listeners.add(listener);return()=>{e.listeners.delete(listener)}}
    private update(e:Entry,patch:Partial<NotebookState>){e.state={...e.state,...patch};for(const listener of e.listeners)listener()}
    load(id:string):Promise<void>{const e=this.entry(id);if(e.state.loaded)return Promise.resolve();if(e.load)return e.load;
        this.update(e,{status:'loading',error:''});
        e.load=Promise.resolve().then(()=>this.read(id)).then(value=>{e.saved=value.text;e.dirty=(value.draft??value.text)!==value.text;this.update(e,{text:value.draft??value.text,loaded:true,status:e.dirty?'dirty':'ready'});if(e.dirty)this.schedule(id,e)}).catch(error=>{this.update(e,{status:'error',error:String(error instanceof Error?error.message:error)});throw error}).finally(()=>{e.load=undefined});return e.load;
    }
    private schedule(id:string,e:Entry){clearTimeout(e.timer);e.timer=setTimeout(()=>{e.timer=undefined;void this.flush(id).catch(()=>{})},this.delay)}
    edit(id:string,text:string){const e=this.entry(id);if(!e.state.loaded)throw new Error('Notebook has not loaded');if(text.length>100000)throw new Error('Notebook exceeds 100,000 characters');e.dirty=text!==e.saved;this.update(e,{text,status:e.dirty?'dirty':'ready',error:''});clearTimeout(e.timer);if(e.dirty)this.schedule(id,e)}
    flush(id:string):Promise<void>{const e=this.entry(id);clearTimeout(e.timer);e.timer=undefined;if(e.write)return e.write;if(!e.dirty)return Promise.resolve();
        e.write=Promise.resolve().then(async()=>{while(e.dirty){const submitted=e.state.text;this.update(e,{status:'saving',error:''});await this.write(id,submitted);e.saved=submitted;e.dirty=e.state.text!==submitted;this.update(e,{status:e.dirty?'dirty':'ready'})}}).catch(error=>{this.update(e,{status:'error',error:String(error instanceof Error?error.message:error)});throw error}).finally(()=>{e.write=undefined});return e.write;
    }
    async flushAll(){await Promise.all([...this.entries.keys()].map(id=>this.flush(id)))}
}
