export function pageFromInput(text:string,pages:number):number|null{
    if(!/^\d+$/.test(text.trim()))return null;
    const number=Number(text);
    return Number.isSafeInteger(number)&&number>=1&&number<=pages?number-1:null;
}
