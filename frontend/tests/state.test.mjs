import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {fileURLToPath} from 'node:url';
const bundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/requestScope.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {RequestScope}=await import('data:text/javascript;base64,'+Buffer.from(bundle.outputFiles[0].text).toString('base64'));
const notesBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/notesDraft.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {NoteDraftStore}=await import('data:text/javascript;base64,'+Buffer.from(notesBundle.outputFiles[0].text).toString('base64'));
const apiBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/api.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {errorMessage,bytes}=await import('data:text/javascript;base64,'+Buffer.from(apiBundle.outputFiles[0].text).toString('base64'));
const caseBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/caseIdentity.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {automaticCaseName,caseMatches}=await import('data:text/javascript;base64,'+Buffer.from(caseBundle.outputFiles[0].text).toString('base64'));
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}};
const snapshotBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/resultSnapshot.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {visibleSnapshot,pageSummary}=await import('data:text/javascript;base64,'+Buffer.from(snapshotBundle.outputFiles[0].text).toString('base64'));
const workspaceBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/workspaceState.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {restoreWorkspace,openWorkspaceCase,closeWorkspaceCase,LatestWriter,parseWindowsBanner,measuredProgress}=await import('data:text/javascript;base64,'+Buffer.from(workspaceBundle.outputFiles[0].text).toString('base64'));
const widthsBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/columnWidths.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {ColumnWidthStore,clampColumnWidth}=await import('data:text/javascript;base64,'+Buffer.from(widthsBundle.outputFiles[0].text).toString('base64'));

test('long command columns retain their width by name without affecting other plugin layouts',()=>{
 const store=new ColumnWidthStore();
 store.save('windows.cmdline.CmdLine',new Map([['PID',90],['Args',25000],['Process',220]]));
 store.save('windows.pslist.PsList',new Map([['PID',72],['ImageFileName',180]]));
 assert.equal(store.read('windows.cmdline.CmdLine').get('Args'),25000);
 assert.equal(store.read('windows.cmdline.CmdLine').get('PID'),90);
 assert.equal(store.read('windows.pslist.PsList').get('PID'),72);
 const edited=store.read('windows.cmdline.CmdLine');edited.set('Args',80);
 assert.equal(store.read('windows.cmdline.CmdLine').get('Args'),25000);
 store.reset('windows.cmdline.CmdLine');assert.equal(store.read('windows.cmdline.CmdLine').size,0);
 assert.equal(store.read('windows.pslist.PsList').get('PID'),72);
});
test('column dragging cannot create a negative or nonfinite browser layout',()=>{
 for(const n of [-500,0,20])assert.equal(clampColumnWidth(n),64);
 for(const n of [NaN,Infinity,-Infinity])assert.equal(clampColumnWidth(n),160);
 assert.equal(clampColumnWidth(2e9),32768);
 assert.equal(clampColumnWidth(288000.1),32768);
});
test('opening many plugin schemas bounds the session sizing cache',()=>{
 const store=new ColumnWidthStore(2);
 for(const scope of ['a','b','c'])store.save(scope,new Map([['Text',240]]));
 assert.equal(store.read('a').size,0);assert.equal(store.read('b').get('Text'),240);assert.equal(store.read('c').get('Text'),240);
});

test('an explicitly empty workspace never reopens a saved or local-storage case',()=>{
    assert.deepEqual(restoreWorkspace(['a','b'],{last_case:'',open_cases:[]}),{activeId:'',openIds:[]});
    assert.deepEqual(restoreWorkspace(['a','b'],{last_case:'a'}),{activeId:'a',openIds:['a']});
    assert.deepEqual(restoreWorkspace(['a'],{last_case:'gone',open_cases:['gone']}),{activeId:'',openIds:[]});
});
test('two cases can be closed, then reopened without deleting saved cases',()=>{
    let state=openWorkspaceCase({activeId:'',openIds:[]},'a');state=openWorkspaceCase(state,'b');state=openWorkspaceCase(state,'a');
    assert.deepEqual(state,{activeId:'a',openIds:['a','b']});
    state=closeWorkspaceCase(state,'b');assert.equal(state.activeId,'a');
    state=closeWorkspaceCase(state,'a');assert.deepEqual(state,{activeId:'',openIds:[]});
    assert.deepEqual(openWorkspaceCase(state,'b'),{activeId:'b',openIds:['b']});
});
test('preference writes serialize rapid case switches and closing to empty',async()=>{
    const gate=deferred(),written=[];const writer=new LatestWriter(async value=>{written.push(value);if(written.length===1)await gate.promise});
    const first=writer.submit('a');await Promise.resolve();writer.submit('b');writer.submit('');gate.resolve();await first;await writer.flush();
    assert.deepEqual(written,['a','']);
});
test('failed preference writes are retained for the native close retry',async()=>{
    let fail=true;const written=[];const writer=new LatestWriter(async value=>{if(fail)throw new Error('disk');written.push(value)});
    await assert.rejects(writer.submit('empty'),/disk/);fail=false;await writer.flush();assert.deepEqual(written,['empty']);
});
test('Windows PDB identifiers are parsed only for the exact format',()=>{
    assert.deepEqual(parseWindowsBanner('ntkrnlmp.pdb|769C521E4833ECF72E21F02BF33691A5|1'),{pdb:'ntkrnlmp.pdb',guid:'769C521E4833ECF72E21F02BF33691A5',age:'1'});
    for(const raw of ['Linux version 6.1.0','ntoskrnl.pdb|not-a-guid|1',null,'x.pdb|'+ 'a'.repeat(32)+'|1\n'])assert.equal(parseWindowsBanner(raw),null);
});

test('pending page, filter or sort cannot display the preceding table response',()=>{
 const snapshot={key:'run:A/page:249/filter:old/sort:PID',rows:[{PID:25999}],columns:['PID'],total:25000};
 for(const key of ['run:A/page:0/filter:old/sort:PID','run:A/page:249/filter:new/sort:PID','run:A/page:249/filter:old/sort:Name']){
  const view=visibleSnapshot(key,snapshot);assert(!view.ready);assert.deepEqual(view.rows,[]);assert.equal(view.total,0);
 }
 assert.deepEqual(visibleSnapshot(snapshot.key,snapshot).rows,[{PID:25999}]);
});
test('failed table response hides stale data until an explicit successful retry',()=>{
 const data={key:'request-1',rows:[{Text:'private-evidence'}],columns:['Text'],total:1};
 assert(!visibleSnapshot('request-1',data,'request-1').ready);
 assert.deepEqual(visibleSnapshot('request-1',data,'request-1').rows,[]);
 assert(!visibleSnapshot('retry-2',data).ready);
 assert(visibleSnapshot('retry-2',{...data,key:'retry-2'}).ready);
});
test('loading the last page does not show a false 250/1 counter',()=>{
 assert.deepEqual(pageSummary(0,249,false),{start:0,end:0,page:0,pages:0});
 assert.deepEqual(pageSummary(25000,249,true),{start:24901,end:25000,page:250,pages:250});
});
test('zero results and a shortened result set have valid pagination',()=>{
 assert.deepEqual(pageSummary(0,0,true),{start:0,end:0,page:1,pages:1});
 assert.deepEqual(pageSummary(1,249,true),{start:1,end:1,page:1,pages:1});
});

test('automatic aliases fit title validation without breaking Unicode or changing evidence paths',()=>{
 const name='x'.repeat(159)+'🔎'+'y'.repeat(20)+'.raw',path='C:\\Evidence\\'+name;
 const alias=automaticCaseName(path);
 assert.equal(Array.from(alias).length,160);
 assert(alias.endsWith('🔎'));assert(!/[\uD800-\uDBFF]$/.test(alias));
 assert.equal(path,'C:\\Evidence\\'+name);
 assert.equal(automaticCaseName('/case/память.raw'),'память.raw');
});

test('identically named cases can be selected by path, ID or digest without regex matching',()=>{
 const a={name:'memory.raw',path:'C:\\A\\memory.raw',id:'1234abcd',sha256:'0011aabb'};
 const b={name:'memory.raw',path:'C:\\B\\memory.raw',id:'5678efab',sha256:'9922ccdd'};
 assert.deepEqual([a,b].filter(c=>caseMatches(c,'c:\\b\\')).map(c=>c.id),['5678efab']);
 assert(caseMatches(a,'ABCD'));assert(caseMatches(b,'22CC'));assert(caseMatches(a,'  memory  '));
 assert(!caseMatches(a,'.*'));assert(caseMatches(a,''));
});

test('validation errors show actionable fields without echoing raw submitted evidence',()=>{
 const detail=[{loc:['body','notes'],msg:'String should have at most 100000 characters',input:'PRIVATE-EVIDENCE'.repeat(100000),ctx:{max_length:100000}}];
 const message=errorMessage(detail,422);
 assert.equal(message,'notes: String should have at most 100000 characters');
 assert(!message.includes('PRIVATE-EVIDENCE'));
 assert.equal(errorMessage({unexpected:'object'},500),'HTTP 500');
 assert(errorMessage('x'.repeat(10000),400).length<=1600);
});

test('late previous-case results cannot appear in the new case, even if abort is ignored',async()=>{
 const scope=new RequestScope(),old=deferred(),fresh=deferred(),shown=[],errors=[];let signal;
 scope.select('A');const a=scope.load('A',s=>{signal=s;return old.promise},x=>shown.push(x),e=>errors.push(e));
 await Promise.resolve();scope.select('B');
 const b=scope.load('B',()=>fresh.promise,x=>shown.push(x),e=>errors.push(e));
 fresh.resolve('B rows');await b;old.resolve('A rows');await a;
 assert(signal.aborted);assert.deepEqual(shown,['B rows']);assert.deepEqual(errors,[]);
});

test('rapid refreshes share a slow request instead of starving its completion',async()=>{
 const scope=new RequestScope(),response=deferred(),shown=[];let reads=0;
 scope.select('A');const refresh=()=>scope.load('A',()=>{reads++;return response.promise},x=>shown.push(x),assert.fail);
 const pending=Array.from({length:30},refresh);await Promise.resolve();assert.equal(reads,1);
 response.resolve('complete');await Promise.all(pending);assert.deepEqual(shown,['complete']);
 await scope.load('A',async()=> 'next',x=>shown.push(x),assert.fail);assert.deepEqual(shown,['complete','next']);
});

test('A to B to A cannot revive the first A response',async()=>{
 const scope=new RequestScope(),old=deferred(),shown=[];
 scope.select('A');const stale=scope.load('A',()=>old.promise,x=>shown.push(x),assert.fail);
 scope.select('B');scope.select('A');await scope.load('A',async()=> 'new A',x=>shown.push(x),assert.fail);
 old.resolve('old A');await stale;assert.deepEqual(shown,['new A']);
});

test('stale errors and refresh callbacks do not affect the current case',async()=>{
 const scope=new RequestScope(),old=deferred(),errors=[];let staleReads=0;
 scope.select('A');const pending=scope.load('A',()=>old.promise,assert.fail,e=>errors.push(e));
 await Promise.resolve();scope.select('B');old.reject(new Error('old source missing'));await pending;
 await scope.load('A',()=>{staleReads++;return Promise.resolve('wrong')},assert.fail,assert.fail);
 assert.equal(staleReads,0);assert.deepEqual(errors,[]);
 await scope.load('B',async()=>{throw new Error('current failure')},assert.fail,e=>errors.push(e.message));
 assert.deepEqual(errors,['current failure']);
});

test('drafts survive a fresh frontend origin and remain isolated by case',async()=>{
 const database=new Map();const newOrigin=()=>new NoteDraftStore(async id=>database.get(id)??null,async(id,text)=>{if(text===null)database.delete(id);else database.set(id,text)});
 const first=newOrigin();await first.save('A','unsaved A','saved A');await first.save('B','unsaved B','saved B');
 const restarted=newOrigin();assert.equal(await restarted.load('A'),'unsaved A');assert.equal(await restarted.load('B'),'unsaved B');
 await restarted.save('A','unsaved A','unsaved A');assert.equal(await newOrigin().load('A'),null);assert.equal(await newOrigin().load('B'),'unsaved B');
});

test('closing waits for the latest coalesced draft, not the first in-flight write',async()=>{
 const first=deferred(),written=[];const store=new NoteDraftStore(async()=>null,async(id,text)=>{if(!written.length)await first.promise;written.push(text)});
 const a=store.save('A','first','saved');await Promise.resolve();const b=store.save('A','latest','saved');
 let closed=false;const closing=store.flushAll().then(()=>{closed=true});await Promise.resolve();assert.equal(closed,false);
 first.resolve();await Promise.all([a,b,closing]);assert.deepEqual(written,['first','latest']);assert.equal(closed,true);
});

test('a failed draft write prevents close; retry retains the latest text',async()=>{
 let failing=true;const written=[];const store=new NoteDraftStore(async()=>null,async(id,text)=>{if(failing)throw new Error('disk full');written.push(text)});
 await assert.rejects(store.save('A','evidence note','saved'),/disk full/);await assert.rejects(store.flushAll(),/disk full/);
 assert.equal(store.peek('A'),'evidence note');failing=false;await store.flushAll();assert.deepEqual(written,['evidence note']);
});

test('late draft load cannot overwrite text already edited in this session',async()=>{
 const response=deferred();const store=new NoteDraftStore(()=>response.promise,async()=>{});
 const loading=store.load('A');await store.save('A','new text','saved');response.resolve('old draft');assert.equal(await loading,'new text');
});

test('scanner completion is not presented as overall plugin completion',()=>{
    assert.equal(measuredProgress({purpose:'analysis',progress:99}),null);
    assert.equal(measuredProgress({purpose:'detection',progress:100}),null);
    assert.equal(measuredProgress({purpose:'pipeline',progress:42}),42);
    assert.equal(measuredProgress({purpose:'pipeline',progress:100}),99);
    assert.equal(measuredProgress({purpose:'pipeline',progress:NaN}),null);
});

test('binary evidence sizes use IEC units and preserve sensible bounds',()=>{
 assert.equal(bytes(5368709120),'5.0 GiB');assert.equal(bytes(1024),'1 KiB');assert.equal(bytes(1),'1 B');
 for(const value of [0,-1,NaN,Infinity])assert.equal(bytes(value),'0 B');
});

const guidesBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/overviewRun.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {reusableRun}=await import('data:text/javascript;base64,'+Buffer.from(guidesBundle.outputFiles[0].text).toString('base64'));
test('overview does not misrepresent a PID-filtered result as the full process list',()=>{
 const rows=[{id:'filtered',plugin:'pslist',params:{pid:[428]},status:'completed'},{id:'failed',plugin:'pslist',params:{},status:'failed'},{id:'all',plugin:'pslist',params:{},status:'completed'}];
 assert.equal(reusableRun(rows,'pslist').id,'all');assert.equal(reusableRun(rows.slice(0,2),'pslist'),undefined);
 assert.equal(reusableRun(rows,'cmdline'),undefined);
});
test('overview opens an existing default run rather than queueing the same work twice',()=>{
 const rows=[{id:'ready',plugin:'pslist',params:{},status:'completed'},{id:'active',plugin:'pslist',params:{pid:[]},status:'running'}];
 assert.equal(reusableRun(rows,'pslist').id,'active');
});

const resourceBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/resourceState.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {ResourceGate}=await import('data:text/javascript;base64,'+Buffer.from(resourceBundle.outputFiles[0].text).toString('base64'));
const pagesBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/pageInput.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {pageFromInput}=await import('data:text/javascript;base64,'+Buffer.from(pagesBundle.outputFiles[0].text).toString('base64'));

test('failed settings read publishes no editable defaults and retry restores exact values',async()=>{
 const gate=new ResourceGate();await gate.load(async()=>{throw new Error('read unavailable')});
 assert.deepEqual(gate.snapshot(),{status:'error',value:null,error:'read unavailable'});
 const saved={offline:false,memory_limit_mb:1536,symbol_dirs:['D:\\Case data\\内核'],plugin_dirs:[]};
 await gate.load(async()=>saved);assert.equal(gate.snapshot().status,'ready');assert.deepEqual(gate.snapshot().value,saved);
});
test('partial bootstrap failure cannot publish empty open images as loaded preferences',async()=>{
 const gate=new ResourceGate(),health=deferred(),prefs=deferred(),history=deferred();
 const loading=gate.load(()=>Promise.all([health.promise,prefs.promise,history.promise]));
 health.resolve({version:'qa'});history.resolve([{id:'retained-case'}]);prefs.reject(new Error('preferences read failed'));
 await loading;assert.equal(gate.snapshot().status,'error');assert.equal(gate.snapshot().value,null);
 const preferences={language:'fr',open_cases:['retained-case'],last_case:'retained-case'};
 await gate.load(async()=>({preferences}));assert.deepEqual(gate.snapshot().value.preferences,preferences);
});
test('late success from a superseded load cannot overwrite a successful retry',async()=>{
 const gate=new ResourceGate(),old=deferred();const first=gate.load(()=>old.promise);
 await gate.load(async()=>({memory_limit_mb:8192}));old.resolve({memory_limit_mb:0});await first;
 assert.equal(gate.snapshot().value.memory_limit_mb,8192);
});
test('late failure from a superseded load cannot hide a successful retry',async()=>{
 const gate=new ResourceGate(),old=deferred();const first=gate.load(()=>old.promise);
 await gate.load(async()=>['kept']);old.reject(new Error('stale failure'));await first;
 assert.deepEqual(gate.snapshot(),{status:'ready',value:['kept'],error:''});
});
test('unmounted resource cannot publish a delayed response',async()=>{
 const gate=new ResourceGate(),pending=deferred();let notifications=0;const unsubscribe=gate.subscribe(()=>notifications++);
 const read=gate.load(()=>pending.promise);gate.invalidate();unsubscribe();pending.resolve('late');await read;
 assert.equal(gate.snapshot().status,'loading');assert.equal(notifications,1);
});
test('page jump validates complete page numbers without rounding or exponent coercion',()=>{
 for(const value of ['', '0','-1','3.5','1e2','2 pages','Infinity','9007199254740993'])assert.equal(pageFromInput(value,250),null,value);
 assert.equal(pageFromInput(' 250 ',250),249);assert.equal(pageFromInput('1',250),0);assert.equal(pageFromInput('251',250),null);
});
test('page jump respects the actual filtered page count',()=>{
 assert.equal(pageFromInput('57',57),56);assert.equal(pageFromInput('58',57),null);
 assert.equal(pageFromInput('2',1),null);assert.equal(pageFromInput('1',1),0);assert.equal(pageFromInput('1',0),null);
});

const historyBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/runHistory.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {matchesRunHistory}=await import('data:text/javascript;base64,'+Buffer.from(historyBundle.outputFiles[0].text).toString('base64'));
test('history search finds plugin, run ID and translated status without changing rows',()=>{
 const run=Object.freeze({id:'a7b9',plugin:'windows.filescan.FileScan',status:'completed'});
 for(const query of ['filescan','WINDOWS.FILE',' A7B9 ','ЗАВЕРШЁН','completed',''])assert.equal(matchesRunHistory(run,query,'Завершён'),true,query);
 assert.equal(matchesRunHistory(run,'cmdline','Завершён'),false);
 assert.deepEqual(run,{id:'a7b9',plugin:'windows.filescan.FileScan',status:'completed'});
});

const notebookBundle=buildSync({entryPoints:[fileURLToPath(new URL('../src/notebookStore.ts',import.meta.url))],bundle:true,format:'esm',write:false});
const {NotebookStore}=await import('data:text/javascript;base64,'+Buffer.from(notebookBundle.outputFiles[0].text).toString('base64'));
test('notebook typing coalesces 1000 keystrokes into one write and shares the same text between editors',async()=>{
 const writes=[];const store=new NotebookStore(async()=>({text:'',draft:null}),async(id,text)=>{writes.push([id,text])},60000);
 await store.load('A');let first=0,second=0;const off=store.subscribe('A',()=>first++),off2=store.subscribe('A',()=>second++);
 for(let i=1;i<=1000;i++)store.edit('A','x'.repeat(i));
 assert.equal(writes.length,0);assert.equal(store.snapshot('A').text.length,1000);assert.equal(first,second);
 await store.flushAll();assert.deepEqual(writes,[['A','x'.repeat(1000)]]);assert.equal(store.snapshot('A').status,'ready');off();off2();
});
test('notebook close waits for text typed during an earlier save, with no stale write arriving last',async()=>{
 const gate=deferred(),written=[];const store=new NotebookStore(async()=>({text:'',draft:null}),async(id,text)=>{written.push(text);if(written.length===1)await gate.promise},60000);
 await store.load('A');store.edit('A','first');const first=store.flushAll();await Promise.resolve();store.edit('A','latest');let closed=false;const closing=store.flushAll().then(()=>{closed=true});await Promise.resolve();assert.equal(closed,false);
 gate.resolve();await Promise.all([first,closing]);assert.deepEqual(written,['first','latest']);assert.equal(store.snapshot('A').text,'latest');assert.equal(store.snapshot('A').status,'ready');
});
test('a failed notebook save retains text, blocks close and can be retried',async()=>{
 let failed=true;const written=[];const store=new NotebookStore(async()=>({text:'original',draft:null}),async(id,text)=>{if(failed)throw new Error('disk full');written.push(text)},60000);
 await store.load('A');store.edit('A','important findings');await assert.rejects(store.flushAll(),/disk full/);assert.equal(store.snapshot('A').status,'error');assert.equal(store.snapshot('A').text,'important findings');failed=false;await store.flushAll();assert.deepEqual(written,['important findings']);
});
test('notebooks recover legacy drafts and remain isolated between cases and a new session',async()=>{
 const database=new Map([['A',{text:'saved',draft:'recovered'}],['workspace',{text:'shared',draft:null}]]);let reads=0;
 const create=()=>new NotebookStore(async id=>{reads++;return database.get(id)??{text:'',draft:null}},async(id,text)=>{database.set(id,{text,draft:null})},60000);
 const store=create();await Promise.all([store.load('A'),store.load('A')]);assert.equal(reads,1);assert.equal(store.snapshot('A').text,'recovered');await store.load('workspace');store.edit('A','case note');await store.flushAll();assert.equal(store.snapshot('workspace').text,'shared');const fresh=create();await fresh.load('A');assert.equal(fresh.snapshot('A').text,'case note');assert.equal(fresh.snapshot('A').status,'ready');
});
test('notebook loading failures are retryable and over-limit edits cannot replace valid text',async()=>{
 let failing=true;const store=new NotebookStore(async()=>{if(failing)throw new Error('unavailable');return {text:'original',draft:null}},async()=>{},60000);
 await assert.rejects(store.load('A'),/unavailable/);assert.equal(store.snapshot('A').loaded,false);failing=false;await store.load('A');assert.throws(()=>store.edit('A','x'.repeat(100001)));assert.equal(store.snapshot('A').text,'original');await store.flushAll();
});
