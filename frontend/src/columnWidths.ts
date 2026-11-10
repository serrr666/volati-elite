// Session-only display preferences. Evidence and exports are never changed.
export const MIN_COLUMN_WIDTH=64,MAX_COLUMN_WIDTH=32_768;
export function clampColumnWidth(width:number){
    return Number.isFinite(width)?Math.max(MIN_COLUMN_WIDTH,Math.min(MAX_COLUMN_WIDTH,Math.ceil(width))):160;
}
export class ColumnWidthStore{
    private layouts=new Map<string,Map<string,number>>();
    constructor(private limit=48){}
    read(scope:string){return new Map(this.layouts.get(scope));}
    save(scope:string,widths:Map<string,number>){
        this.layouts.delete(scope);
        this.layouts.set(scope,new Map([...widths].map(([key,width])=>[key,clampColumnWidth(width)])));
        while(this.layouts.size>this.limit)this.layouts.delete(this.layouts.keys().next().value!);
    }
    reset(scope:string){this.layouts.delete(scope);}
}
export const columnWidths=new ColumnWidthStore();
