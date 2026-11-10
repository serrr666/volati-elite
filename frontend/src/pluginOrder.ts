import type { Plugin } from './types';

export type PluginSort = 'popular' | 'name';

// Curated priorities for common investigations, not collected usage statistics.
// Match by class name so the priority survives module moves in Volatility.
const priorities: Record<string, readonly string[]> = {
    all: ['pslist', 'pstree', 'psscan', 'cmdline', 'dlllist', 'handles', 'netscan', 'sockstat', 'netstat', 'info', 'banners', 'malfind', 'psxview', 'filescan', 'dumpfiles', 'hivelist', 'printkey', 'svcscan', 'bash', 'envars', 'vadinfo', 'modules', 'lsmod', 'timeliner'],
    process: ['pslist', 'pstree', 'psscan', 'cmdline', 'psaux', 'dlllist', 'librarylist', 'handles', 'envars', 'getsids', 'privs', 'capabilities', 'threads', 'thrdscan', 'sessions', 'memmap', 'maps', 'vadinfo', 'vadwalk', 'pidhashtable', 'joblinks', 'pscallstack', 'ptrace', 'elfs', 'getservicesids'],
    network: ['netscan', 'netstat', 'sockstat', 'sockscan', 'ifconfig', 'addr', 'link', 'socketfilters'],
    malware: ['malfind', 'psxview', 'ldrmodules', 'hollowprocesses', 'processghosting', 'pebmasquerade', 'processspoofing', 'vadyarascan', 'vmayarascan', 'yarascan', 'suspiciousthreads', 'suspendedthreads', 'checkcreds', 'checkmodules', 'hiddenmodules', 'modxview', 'checksyscall', 'checkidt', 'checkafinfo', 'netfilter', 'drivermodule', 'svcdiff', 'directsystemcalls', 'indirectsystemcalls', 'unhookedsystemcalls', 'skeletonkeycheck', 'keyboardnotifiers', 'ttycheck'],
    registry: ['hivelist', 'printkey', 'hivescan', 'userassist', 'amcache', 'shimcachemem', 'scheduledtasks', 'certificates', 'hashdump', 'lsadump', 'cachedump', 'getcellroutine'],
    files: ['filescan', 'dumpfiles', 'lsof', 'files', 'mftscan', 'ads', 'residentdata', 'listfiles', 'mountinfo', 'mount', 'inodepages', 'recoverfs', 'symlinkscan'],
    kernel: ['modules', 'driverscan', 'lsmod', 'modscan', 'callbacks', 'ssdt', 'driverirp', 'unloadedmodules', 'kmsg', 'dmesg', 'kallsyms', 'moduleextract', 'kthreads', 'threads', 'devicetree', 'kpcrs', 'iomem', 'checksyscall', 'checksysctl', 'checktraptable'],
    timeline: ['timeliner', 'bash', 'consoles', 'cmdscan', 'boottime'],
    system: ['info', 'banners', 'svcscan', 'svclist', 'verinfo', 'vmcoreinfo', 'crashinfo', 'frameworkinfo', 'isfinfo'],
    other: ['strings', 'regexscan', 'vadregexscan', 'vmaregexscan', 'pedump', 'iat', 'mutantscan', 'bigpools', 'poolscanner', 'vmscan', 'layerwriter', 'configwriter', 'statistics'],
};
const normalize = (name: string) => name.toLowerCase().replaceAll('_', '');
const osOrder: Record<string, number> = { windows: 0, linux: 1, mac: 2, generic: 3 };
const rankTables = Object.fromEntries(Object.entries(priorities).map(([category, names]) => [category, new Map(names.map((name, index) => [name, index]))]));
const isDeprecated = (p: Plugin) => p.description.toLowerCase().includes('deprecated');
const byName = (a: Plugin, b: Plugin) => normalize(a.name).localeCompare(normalize(b.name), 'en')
    || (osOrder[a.os] ?? 4) - (osOrder[b.os] ?? 4)
    || Number(!a.id.includes('.malware.')) - Number(!b.id.includes('.malware.'))
    || a.id.localeCompare(b.id, 'en');

export function orderPlugins(plugins: readonly Plugin[], sort: PluginSort = 'popular', category = 'all'): Plugin[] {
    const ranks = rankTables[category] ?? rankTables.all;
    return [...plugins].sort((a, b) => {
        if (sort === 'name') return byName(a, b);
        return Number(isDeprecated(a)) - Number(isDeprecated(b))
            || (ranks.get(normalize(a.name)) ?? 1000) - (ranks.get(normalize(b.name)) ?? 1000)
            || byName(a, b);
    });
}
