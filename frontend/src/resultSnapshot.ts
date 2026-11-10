export type TableSnapshot<T>={key:string;rows:T[];columns:string[];total:number};
// A response belongs to the exact run AND page/filter/sort. Never relabel rows
// from a previous response while a new request is pending or has failed.
export function visibleSnapshot<T>(key:string,snapshot:TableSnapshot<T>|null,errorKey=''){
    const ready=snapshot?.key===key && errorKey!==key;
    return {ready,rows:ready?snapshot.rows:[],columns:ready?snapshot.columns:[],total:ready?snapshot.total:0};
}
export function pageSummary(total:number,page:number,ready:boolean){
    if(!ready)return {start:0,end:0,page:0,pages:0};
    const pages=Math.max(1,Math.ceil(total/100)),safePage=Math.min(Math.max(0,page),pages-1);
    return {start:total?safePage*100+1:0,end:Math.min((safePage+1)*100,total),page:safePage+1,pages};
}
