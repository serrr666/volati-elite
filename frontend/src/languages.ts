export const languages=[{code:'en',name:'English',locale:'en-GB'},{code:'ru',name:'Русский',locale:'ru-RU'},{code:'zh-CN',name:'简体中文',locale:'zh-CN'},{code:'es',name:'Español',locale:'es-ES'},{code:'de',name:'Deutsch',locale:'de-DE'},{code:'fr',name:'Français',locale:'fr-FR'}] as const;
export type Language=typeof languages[number]['code'];
export const normalizeLanguage=(value:unknown):Language=>languages.find(v=>v.code===value)?.code??'en';
export const localeFor=(value:unknown)=>languages.find(v=>v.code===value)?.locale??'en-GB';
export function buildDate(value:string|undefined,language:Language){const date=value?new Date(value):null;return date&&Number.isFinite(date.getTime())?new Intl.DateTimeFormat(localeFor(language),{timeZone:'UTC',dateStyle:'medium'}).format(date):'—'}
