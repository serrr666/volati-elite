import zh from './locales/zh-CN.json';
import es from './locales/es.json';
import de from './locales/de.json';
import fr from './locales/fr.json';
import {normalizeLanguage,type Language} from './languages';
const dictionaries:Partial<Record<Language,Record<string,string>>>={'zh-CN':zh,es,de,fr};
import keys from './translation-keys.json';

const english=`Case overview
Plugin library
Results
Bookmarks & notes
Timeline
Queued
Running
Indexing
Completed
Failed
Cancelled
Interrupted
OS not selected
General
Close
Existing case opened
Image attached. Banners is identifying the system automatically.
{0} added to the queue
{0} plugins queued. Results are saved automatically.
Synthetic training case opened
New run created
ACTIVE CASE
Select a memory image
Create case
WORKSPACE
Start with a question.
Find the right plugin.
Recommendations help you choose your next investigation step.
How it works
Engine settings
Engine ready
Connecting to engine…
Settings
Find a plugin…
Light theme
Dark theme
Help & keyboard shortcuts
Local workspace
Training case · synthetic data
No real memory image has been analysed
Open your image
Memory holds the answers
Explore the image. Connect artifacts. Preserve evidence.
New case
Where should we start?
Choose a question — we will suggest the right tools.
All plugins
Start investigating
Recent runs
All results
PLUGIN
STATUS
ROWS
Your runs will appear here
Start with image orientation or select a plugin from the library.
Case at a glance
Completed
plugins
Retrieved
rows
Saved
bookmarks
runs
Quick start
Orientation + processes + context
Run
Your image stays on your computer. Results and history are stored locally.
No open case
active runs
All changes saved
Analysis queue
Hide queue
Cancel run
Queue is empty
Image attached. SHA-256 is being calculated in the background.
Investigate with confidence
Vol3 Studio · an independent interface for Volatility 3
1. Open a memory image
Attach a local file. The app identifies its OS, calculates SHA-256 and preserves case provenance.
2. Ask the image a question
Use guided recommendations or the library. Parameters come from installed Volatility plugins, and every run preserves its command.
3. Preserve observations
Filter tables, inspect rows, add notes and export results. A plugin match is an observation that needs interpretation.
Find plugin
Open image
Close panel
Volatility 3 documentation
Dismiss notification
Identifying image automatically
{0} · identified automatically
Image details
You can select the operating system manually.
Change case OS
Unknown OS
View Banners results
Calculating SHA-256
Synthetic dataset
Verification failed
Copy SHA-256
SHA-256 copied
Case
Local analysis
TRAINING MODE
SOURCE IMAGE IS READ-ONLY
Now they are easier to find.
The power of Volatility 3 in a workspace
that guides every step of your investigation.
Open memory image
Try the training case
installed plugins
Your data stays with you
Drop an image into the window · Ctrl O to open · Files stay local
The right tool
Your installed engine's library. Find a plugin by name or question.
CATEGORIES
Show deprecated plugins
Name, question or description…
Clear search
Operating system
All operating systems
List view
Card view
tools
Select a plugin to configure a run
No plugins found
Try another search, category or operating system.
Required
Default
For example: 4280 4860
Space-separated values
Enter a value
Configure {0}
PLUGIN CONFIGURATION
Close plugin configuration
Developer description
Run parameters
No additional parameters required.
Hide
Advanced parameters
CLI EQUIVALENT
Plugin output is evidence to investigate. Empty output does not establish absence of artifacts.
Open a memory image first
Add to queue
Open a memory image
Create a case for a local investigation
Choose a file on your computer
{0} · will be copied into the local case directory
RAW, MEM, VMEM, DMP, LiME and other Volatility formats
Choose file
or drop a file here to copy it locally
Local path
Case name
For example: Workstation investigation
Identify automatically
Local paths are read without copying. SHA-256 is calculated in the background; analysis starts after verification.
Cancel
Plugin search
What would you like to investigate?
SEARCH RESULTS
VOLATILITY 3 TOOLS
Nothing found
Search by name, description or investigation question
Observation bookmarked
Details matter
Filter results, investigate context and preserve observations.
New run
Runs
{0} rows · {1}
Select a plugin to start analysing.
Ready to investigate
Run a plugin from the library or the case overview recommendations.
Run again
Export
CSV · all rows
JSON · original tree
Waiting for image SHA-256…
Waiting for the engine…
Run did not complete
View full log
Run
cancelled by the analyst
interrupted when the application closed
. You can run the plugin again.
Table
Log & command
Extracted files{0}
Search all rows…
Reset filter
Configure columns
Bookmark row
Engine is working
No data to display
Structured results will appear after completion. Progress and messages are available in the log.
Empty results do not establish absence of artifacts. Check the run status and log.
No matches
Try a different search filter.
{0}–{1} of {2}
0 rows
100 rows per page
Previous page
Next page
VOLATILITY COMMAND
Copy command
Command copied
The command will appear when the run starts.
Engine version
Symbol mode
Offline
Downloads allowed
Started (UTC)
Source
Synthetic data
VOLATILITY LOG
last 50 KB
No messages yet.
No extracted files
Plugins with extraction options save files into their run directory. Download links will appear here.
Row details
ARTIFACT INSPECTOR
Close inspector
Continue investigating PID
Analyst note
What should be checked? Why is this row important?
· row
Source and parameters are preserved with the observation.
Row JSON copied
Save observation
Case notes saved
Connect the dots
Saved observations, evidence and your conclusions in one place.
HTML report
Observations
Remove bookmark
Open source result
Save your first observation
Select a result row or its bookmark icon. A reference to the exact run and original data is preserved.
Case notes
Hypotheses, questions and investigation conclusions…
Save notes
Your conclusions are stored separately from plugin output and included in the case export.
Every event has a time
Connect artifact timestamps to their sources.
events
Memory artifacts
Investigation activity
Filter events…
The 10,000-event limit was reached. Full data is available in individual run exports.
Times are normalized to UTC. Event labels retain the original plugin field.
Showing the first 500 matches. Refine your filter.
No timestamped events yet
Run plugins with timestamps, such as PsList, NetScan or DllList. Timestamps without a timezone are excluded.
History starts with the first run
Plugin execution events will appear here.
Settings saved. Plugin library refreshed.
Make the workspace yours
Symbols, additional plugins and network access.
Symbols & network
Offline mode
Prevent Volatility from downloading symbols. Windows, Linux and macOS analysis may require local symbols.
Symbol directories
One existing directory per line. The engine also uses its built-in symbols and local cache.
Additional plugins
Connect a directory containing your own plugins compatible with the installed Volatility 3.
Plugin directories
Plugins execute Python code on your computer. Only connect plugins you trust.
New settings apply to new runs.
Save & refresh
The original engine.
A visual workspace.
Installed plugins
Studio version
Engine documentation
Local storage
Cases, results, notes and the symbol cache are stored on your computer.
import warnings:
Processes
Network
Anomaly hunting
Registry
Files
Kernel
Chronology
System
Other
Where to start
Identify the OS version, architecture and image details. This is the first step before analysis.
Which processes were running?
Lists active processes, their parents, creation times and identifiers.
Are there traces of other processes?
Scans memory for process structures. Discovered entries may belong to terminated processes.
Who started this process?
Reconstructs the process hierarchy. Look for unusual parent-child relationships.
Which arguments were used?
Lists command lines. Results can be restricted to selected PIDs.
Who was the host communicating with?
Finds network objects and associates connections with processes when information is available.
Lists network objects and connection information.
Are there unusual memory regions?
Finds potentially injected code. Results require review and do not independently prove compromise.
What is loaded in the process?
Lists loaded libraries, paths, addresses and load times.
Which objects is this process using?
Files, registry keys, mutexes and other open process objects.
Which services were found?
Finds Windows services: name, state, start type and executable path.
Identify the Linux kernel
Finds kernel version banners to help select matching Linux symbols.
What was entered in Bash?
Finds shell commands still present in memory. History may be incomplete.
Search with YARA
Scans memory using supplied YARA rules. Configure a rule before running.
Read a registry key
Shows the requested key in loaded registry hives.
Which files remain in memory?
Scans for file objects. An object does not guarantee all file contents are present.
Extract file data
Saves available file data from memory into the current run directory.
Build a timeline
Combines timestamped events from supported plugins. This can take considerable time.
Image orientation
Identify the system and retrieve its processes.
Process context
Connect command lines, network connections and loaded libraries.
Deeper investigation
Review memory regions and artifacts that need closer attention.`.split('\n');

if(keys.length!==english.length)throw new Error(`Translation count mismatch: ${keys.length}/${english.length}`);
export const en:Record<string,string>=Object.fromEntries(keys.map((key,i)=>[key,english[i]]));
Object.assign(en,{
 'Каталог плагинов':'Plugins',
 'Плагины Volatility 3':'Plugins',
 'Закрыть подсказку':'Dismiss tip',
 'Подсказка скрыта':'Tip dismissed',
 'Не показывать при запуске':'Do not show at startup',
 'Вернуть':'Restore',
 'Показать подсказку на боковой панели':'Show sidebar tip',
 'Папки не добавлены':'No directories added',
 'Выберите папку с данными ОС, если она нужна для вашего образа.':'Choose an OS analysis data directory if your image requires one.',
 'Выберите папку с дополнительными плагинами.':'Choose a directory containing additional plugins.',
 'Указать путь вручную':'Enter path manually',
 'Полный путь к папке':'Full directory path',
 'Добавить':'Add',
 'Удалить папку из списка':'Remove directory from list',
 'Добавить папку':'Add directory',
 'Открыть папку хранения':'Open data directory',
 'Новый анализ памяти':'New memory analysis',
 'Откройте дамп, чтобы начать исследование.':'Open a memory image to start investigating.',
 'Перетащите образ памяти сюда':'Drop a memory image here',
 'или выберите файл на компьютере':'or choose a file on your computer',
 'Система определяется автоматически через Banners и Info.':'The system is identified automatically using Banners and Info.',
 'Файл читается по локальному пути без копирования.':'The local file is read directly, without copying.',
 'Открыть учебный кейс':'Open training case',
 'Обзор образа памяти':'Memory image overview',
 'Результаты анализа':'Analysis results',
 'Наблюдения и заметки':'Observations & notes',
 'Настройки приложения':'Application settings',
 'Ищем баннер ядра через Volatility Banners':'Looking for a kernel banner with Volatility Banners',
 'ОС определена по баннеру ядра':'OS identified from a kernel banner',
 'Баннер не найден. Проверяем слой Windows через Info':'No kernel banner found. Checking the Windows layer with Info',
 'Windows определена по успешно разобранному слою памяти':'Windows identified from a successfully parsed memory layer',
 'Автоматически определить ОС не удалось. Проверьте журнал и выберите ОС вручную.':'OS identification was inconclusive. Review the log and select an OS manually.',
 'ОС выбрана аналитиком':'OS selected by the analyst',
 'Файл не найден. Укажите полный локальный путь к дампу.':'File not found. Enter the full local path to the memory image.',
 'Файл пуст':'The file is empty',
 'Не удалось построить слой памяти или найти символы. Проверьте ОС дампа и пути символов. В настройках можно разрешить загрузку символов.':'Unable to build a memory layer or find symbols. Check the image OS and symbol directories. Symbol downloads can be enabled in settings.',
 'Volatility завершил запуск с ошибкой. Полный вывод сохранён в журнале.':'Volatility failed. The full output has been saved to the log.',
 'Язык интерфейса':'Interface language',
 'Русский':'Russian',
 'Английский':'English',
 'JSON · структурированные строки':'JSON · structured rows',
 'Исходный JSONL':'Original JSONL',
 'Память процесса анализа':'Analysis memory budget',
 'Автоматически (по доступной ОЗУ)':'Automatic (available RAM)',
 'Плагины выполняются по одному в отдельных процессах. При превышении лимита приложение останавливает анализ, сохраняя доступ к интерфейсу.':'Plugins run one at a time in separate processes. If the budget is exceeded, analysis is stopped while the interface remains available.',
 'Пиковая ОЗУ':'Peak RAM',
 'Лимит ОЗУ':'RAM budget',
 'Символы могут загружаться из сети; содержимое образа не отправляется.':'Symbols may be downloaded; image contents are never uploaded.',
});
const bootLanguage=document.documentElement.hasAttribute('data-theme')?document.documentElement.lang:localStorage.getItem('vol3.lang');
let language:Language=bootLanguage?normalizeLanguage(bootLanguage):navigator.languages.some(l=>/^ru(?:-|$)/i.test(l))?'ru':'en';
const runtimeRu:Record<string,string>={'Preparing analysis':'Подготовка анализа','Analysis complete':'Анализ завершён','Analysis failed':'Ошибка анализа','Indexing results':'Обработка результатов','Cancelled by analyst':'Отменено аналитиком','Pipeline row limit reached':'Достигнут лимит строк конвейера'};
const friendlyRu:Record<string,string>={
 'Каталог плагинов':'Плагины',
 'Плагины Volatility 3':'Плагины',
 'Символы, дополнительные плагины и доступ к сети.':'Данные ОС для анализа, плагины и доступ к сети.',
 'Символы и сеть':'Данные ОС и сеть',
 'Каталоги символов':'Папки с данными ОС для анализа',
 'Режим символов':'Доступ к данным ОС',
 'Запретить Volatility загружать символы из сети. Для Windows, Linux и macOS могут потребоваться локальные символы.':'Использовать только локальные описания структур ОС. Если выключено, движок сможет загружать нужные служебные файлы. Содержимое дампа не отправляется.',
 'Один существующий каталог в строке. Движок использует также свои встроенные символы и локальный кеш.':'Одна существующая папка в строке. Добавьте сюда описания нужной сборки ОС, если автоматической загрузки недостаточно.',
 'Ищет строки версии ядра. Они помогают подобрать подходящие символы Linux.':'Ищет версию ядра. По ней можно подобрать описания структур вашей сборки Linux.',
 'Кейсы, результаты, заметки и кеш символов хранятся на вашем компьютере.':'Кейсы, результаты, заметки и служебные файлы хранятся на вашем компьютере.',
 'Не удалось построить слой памяти или найти символы. Проверьте ОС дампа и пути символов. В настройках можно разрешить загрузку символов.':'Не удалось прочитать структуры ОС. Проверьте выбранную систему и доступ к данным ОС в настройках. Подробности доступны в журнале.',
};
Object.assign(en,{'Символы, дополнительные плагины и доступ к сети.':'OS analysis data, plugins and network access.','Символы и сеть':'OS analysis data & network','Каталоги символов':'OS analysis data directories','Режим символов':'OS data access','Ищет строки версии ядра. Они помогают подобрать подходящие символы Linux.':'Finds the kernel version to help match your Linux build to its structure definitions.','Не удалось построить слой памяти или найти символы. Проверьте ОС дампа и пути символов. В настройках можно разрешить загрузку символов.':'Unable to read OS structures. Check the selected OS and access to OS analysis data in Settings. Details are available in the log.'});
export const getLanguage=()=>language;
export function setLanguage(value:Language){language=normalizeLanguage(value);localStorage.setItem('vol3.lang',language);document.documentElement.lang=language}
export function tr(key:string|undefined,...args:unknown[]):string{
 if(!key)return '';
 let canonical=sourceRuByEnglish[key]??key;
 const budget=key.match(/^Memory budget exceeded \((\d+) MB\)\./);if(budget){canonical='Превышен лимит памяти ({0} MiB). Анализ остановлен. Увеличьте лимит в настройках и повторите запуск.';args=[budget[1]]}
 const missingType=key.match(/^The kernel symbol table is missing type (.+)\. Complete symbols /)??key.match(/^В найденных данных ядра отсутствует тип (.+)\. Нужны полные данные типов /);
 if(missingType){canonical='В данных ядра отсутствует тип {0}. Нужен полный набор типов для этой сборки.';args=[missingType[1]]}
 const preparing=key.match(/^(?:Preparing OS analysis data:|Подготовка данных ОС:)\s*(.*)$/);if(preparing){canonical='Подготовка данных ОС: {0}';args=[preparing[1]]}
 const ruVM='Не удалось отобразить память VMware. Проверьте комплект VMSS/VMEM и журнал; сжатые блоки пока не поддерживаются. ';
 const enVM='VMware memory mapping is unavailable. Check the VMSS/VMEM file set and log; compressed blocks are not supported. ';
 let suffix='';if(key.startsWith(ruVM)||key.startsWith(enVM)){canonical=ruVM;suffix=key.slice(key.startsWith(ruVM)?ruVM.length:enVM.length)}
 const english=en[canonical]??canonical;
 const candidate=language==='ru'?(friendlyRu[canonical]??runtimeRu[canonical]??canonical):language==='en'?english:(dictionaries[language]?.[english]??english);
 return candidate.replace(/\{(\d+)\}/g,(_,i)=>String(args[Number(i)]??''))+suffix;
}
export function translated<T extends Record<string,string>>(data:T):T{return new Proxy(data,{get(target,key){const v=Reflect.get(target,key);return typeof v==='string'?tr(v):v}})}

Object.assign(en,{
  "По популярности": "By popularity",
  "По названию": "By name",
  "Сортировка плагинов": "Plugin order",
  "Основные инструменты для типовых расследований — первыми.": "Core tools for common investigations first. Priorities are curated.",
  "Режим лимита памяти": "Memory budget mode",
  "Готовые значения": "Presets",
  "Свой лимит": "Custom budget",
  "Лимит памяти": "Memory budget",
  "Свой лимит памяти в ГБ": "Custom memory budget in GB",
  "ГБ": "GB",
  "От 0,25 до 1024 ГБ. Это верхний лимит, память заранее не выделяется.": "0.25–1024 GB. This is an upper budget; RAM is not reserved in advance.",
  "Введите лимит от 0,25 до 1024 ГБ": "Enter a budget between 0.25 and 1024 GB",
  "Конвейеры": "Pipelines",
  "Извлекайте строки, фильтруйте данные и выбирайте поля — шаг за шагом.": "Extract strings, filter data and select fields, step by step.",
  "Запустить конвейер": "Run pipeline",
  "Добавляем в очередь…": "Adding to queue…",
  "Источник данных": "Data source",
  "Результаты плагинов": "Plugin results",
  "Файл памяти": "Memory image",
  "Исходный запуск": "Source run",
  "Выберите запуск": "Choose a run",
  "Выберите исходный запуск": "Choose a source run",
  "Сначала выполните плагин или выберите файл памяти.": "Run a plugin first, or choose the memory image.",
  "Учебный кейс не содержит файла памяти": "The training case has no memory image file",
  "Кодировка": "Encoding",
  "Минимум символов": "Minimum characters",
  "Строки длиннее 64 КиБ разбиваются на фрагменты с сохранением смещений.": "Strings longer than 64 KiB are split into fragments with their offsets preserved.",
  "Шаги обработки": "Processing steps",
  "Добавьте первый шаг": "Add your first step",
  "Каждый следующий шаг получает результат предыдущего.": "Each step receives the output of the previous one.",
  "Тип шага": "Step type",
  "Содержит": "Contains",
  "Не содержит": "Does not contain",
  "Сравнить значение": "Compare value",
  "Выбрать поля": "Select fields",
  "Разделить текст на поля": "Split text into fields",
  "Убрать повторы": "Remove duplicates",
  "Выше": "Move up",
  "Ниже": "Move down",
  "Удалить шаг": "Remove step",
  "Поле": "Field",
  "Все поля": "All fields",
  "Выберите поле": "Choose a field",
  "Условие": "Condition",
  "Разделитель": "Delimiter",
  "Пусто — пробельные символы": "Empty: whitespace",
  "Значение": "Value",
  "Поля через запятую": "Comma-separated fields",
  "Пусто — все поля": "Empty: all fields",
  "Без учёта регистра": "Ignore case",
  "Новые поля: Field1, Field2… Исходные поля сохраняются.": "New fields: Field1, Field2… Original fields are preserved.",
  "Конвейер обработки": "Processing pipeline",
  "Таблица и экспорт": "Table and export",
  "Лимит выходных строк": "Output row limit",
  "При достижении лимита обработка останавливается. Это явно отмечается в результате.": "Processing stops at the row limit. The result is clearly marked as partial.",
  "Найти URL": "Find URLs",
  "Найти PowerShell": "Find PowerShell",
  "Убрать повторяющиеся строки": "Remove duplicate rows",
  "Файл читается блоками. Длительность полного поиска зависит от размера данных и скорости диска.": "The file is read in blocks. Full-scan time depends on data size and disk speed.",
  "Проверьте длину строки и лимит результатов": "Check string length and result limit",
  "Заполните параметры всех шагов": "Complete the settings of every step",
  "В конвейер": "Create pipeline",
  "Достигнут лимит строк — обработана часть источника": "Row limit reached — source processed partially",
  "Конвейер завершён": "Pipeline complete",
  "Просмотрено записей": "Records examined",
  "Получено строк": "Output rows",
  "Pipeline row limit reached": "Pipeline row limit reached"
});

Object.assign(en,{"ПАРАМЕТРЫ КОНВЕЙЕРА": "PIPELINE SETTINGS", "ЖУРНАЛ КОНВЕЙЕРА": "PIPELINE LOG", "volati elite · независимый интерфейс для Volatility 3": "volati elite · independent interface for Volatility 3"});

Object.assign(en,{'Добавить шаг':'Add step'});

Object.assign(en,{"Исходный образ": "Source image", "Выберите файл или вставьте полный путь": "Choose a file or paste its full path", "Обзор…": "Browse…", "Открыть": "Open", "Не удалось прочитать и проверить исходный образ": "Unable to read and verify the source image", "Unknown container / possible raw memory": "Unknown container / possible raw memory"});

Object.assign(en,{'Только доверенные Python-плагины: их код выполняется на вашем компьютере.':'Trusted Python plugins only: their code runs on your computer.'});

Object.assign(en,{"Фильтровать результат": "Filter output", "Редактировать рецепт": "Edit recipe", "Повторно определить формат и ОС": "Recheck format and OS", "Offset — смещение байтов в исходном файле.": "Offset is a byte offset in the original source file.", "Адреса и смещения заданы плагином. Они могут относиться к виртуальной или физической памяти и не равны смещению в файле.": "Addresses and offsets are defined by the plugin. They may refer to virtual or physical memory and are not file offsets.", "Найден идентификатор ядра Windows. Проверяем структуры памяти через Info.": "Windows kernel identifier found. Validating memory structures with Info.", "Ядро Windows обнаружено, но структуры памяти не разобраны. Откройте журнал Info: причина может быть в неполных данных типов или формате памяти.": "Windows kernel identified, but memory structures could not be parsed. Open the Info log to check for incomplete type data or unsupported memory mapping.", "ОС выбрана аналитиком. ": "OS selected by the analyst. ", "ОС выбрана аналитиком": "OS selected by the analyst", "Этот источник не распознан как совместимый образ памяти системы. Доступны поиск строк и общие сканеры; проверьте тип файла.": "This source is not recognized as a compatible full-system memory image. String search and generic scanners are available; check the file type."});

Object.assign(en,{"Память читается непосредственно из контейнера VMware. Конвертация и копирование образа не требуются.": "Memory is read directly from the VMware container; no conversion or image copy is required.", "Это текстовое описание типов Volatility 2, а не образ памяти. Доступен поиск строк; для анализа Linux в Volatility 3 нужен RAM-образ и подходящий ISF JSON.": "This is a Volatility 2 text type description, not a memory image. String search is available; Volatility 3 Linux analysis requires a RAM image and matching ISF JSON.", "Это карта адресов ядра, а не образ памяти. Она сама по себе не содержит процессов Linux и не заменяет ISF JSON.": "This is a kernel address map, not a memory image. It does not contain Linux processes and cannot replace ISF JSON.", "Это описание снимков VMware, а не содержимое RAM. Откройте соответствующий VMSS/VMEM/VMSN; поиск строк в метаданных доступен.": "This is VMware snapshot inventory metadata, not RAM. Open the corresponding VMSS/VMEM/VMSN; metadata string search is available.", "Слой ELF в установленном Volatility 3 поддерживает ELF64. Этот ELF32 нельзя автоматически считать совместимым RAM-образом; поиск строк доступен.": "The installed Volatility 3 ELF layer supports ELF64. This ELF32 container cannot be treated as a compatible RAM image; string search is available.", "Файл начинается с PE/MZ. Это может быть программа или дамп отдельного процесса; он не подтверждён как снимок RAM всей системы. Доступны поиск строк и общие сканеры.": "The file starts with PE/MZ. It may be an executable or an individual process image, not a confirmed full-system RAM capture. String search and generic scanners are available.", "Рабочее пространство": "Workspace", "Блокнот аналитика": "Analyst notebook", "ЛОКАЛЬНОЕ ПРОСТРАНСТВО": "LOCAL WORKSPACE", "Обзор источника": "Source overview", "Проверьте источник и выберите следующий шаг анализа.": "Review the source and choose the next analysis step.", "Вспомогательный файл": "Auxiliary file", "Неподдерживаемый формат": "Unsupported format", "Не удалось построить слой памяти. Проверьте формат и полноту образа; одних данных типов недостаточно.": "A memory translation layer could not be constructed. Check the image format and completeness; symbol files alone cannot repair the memory mapping."});
Object.assign(runtimeRu,{"Preparing OS analysis data": "Подготовка данных ОС", "DWARF text · Volatility 2 profile data": "Текстовый DWARF · данные профиля Volatility 2", "Linux System.map · kernel address map": "Linux System.map · карта адресов ядра", "VMware snapshot inventory · VMSD metadata": "Описание снимков VMware · метаданные VMSD", "VMware checkpoint · embedded RAM": "Состояние VMware · встроенная RAM", "VMware checkpoint · mapping unavailable": "Состояние VMware · память не отображена", "Unknown container / possible raw memory": "Неизвестный контейнер / возможный RAW-образ", "ELF64 memory container": "Контейнер памяти ELF64", "Windows crash dump": "Аварийный дамп Windows", "PE file or process image": "PE-файл или образ отдельного процесса"});
const sourceRuByEnglish:Record<string,string>={"Memory is read directly from the VMware container; no conversion or image copy is required.": "Память читается непосредственно из контейнера VMware. Конвертация и копирование образа не требуются.", "This is a Volatility 2 text type description, not a memory image. String search is available; Volatility 3 Linux analysis requires a RAM image and matching ISF JSON.": "Это текстовое описание типов Volatility 2, а не образ памяти. Доступен поиск строк; для анализа Linux в Volatility 3 нужен RAM-образ и подходящий ISF JSON.", "This is a kernel address map, not a memory image. It does not contain Linux processes and cannot replace ISF JSON.": "Это карта адресов ядра, а не образ памяти. Она сама по себе не содержит процессов Linux и не заменяет ISF JSON.", "This is VMware snapshot inventory metadata, not RAM. Open the corresponding VMSS/VMEM/VMSN; metadata string search is available.": "Это описание снимков VMware, а не содержимое RAM. Откройте соответствующий VMSS/VMEM/VMSN; поиск строк в метаданных доступен.", "The installed Volatility 3 ELF layer supports ELF64. This ELF32 container cannot be treated as a compatible RAM image; string search is available.": "Слой ELF в установленном Volatility 3 поддерживает ELF64. Этот ELF32 нельзя автоматически считать совместимым RAM-образом; поиск строк доступен.", "The file starts with PE/MZ. It may be an executable or an individual process image, not a confirmed full-system RAM capture. String search and generic scanners are available.": "Файл начинается с PE/MZ. Это может быть программа или дамп отдельного процесса; он не подтверждён как снимок RAM всей системы. Доступны поиск строк и общие сканеры.", "Workspace": "Рабочее пространство", "Analyst notebook": "Блокнот аналитика", "LOCAL WORKSPACE": "ЛОКАЛЬНОЕ ПРОСТРАНСТВО", "Source overview": "Обзор источника", "Review the source and choose the next analysis step.": "Проверьте источник и выберите следующий шаг анализа.", "Auxiliary file": "Вспомогательный файл", "Unsupported format": "Неподдерживаемый формат", "A memory translation layer could not be constructed. Check the image format and completeness; symbol files alone cannot repair the memory mapping.": "Не удалось построить слой памяти. Проверьте формат и полноту образа; одних данных типов недостаточно."};

Object.assign(en,{'В данных ядра отсутствует тип {0}. Нужен полный набор типов для этой сборки.':'The kernel data is missing type {0}. A complete type definition set for this build is required.'});
Object.assign(en,{'Источник подключён. Статус проверки — в обзоре.':'Source attached. Check its status in the overview.'});
Object.assign(en,{
 'ПРИМЕР ПАРАМЕТРОВ CLI':'CLI ARGUMENT EXAMPLE',
 'Фактический запуск Studio и его параметры доступны в журнале результата.':'The actual Studio worker command and its parameters are in the result log.',
 'АРГУМЕНТЫ VOLATILITY':'VOLATILITY ARGUMENTS',
 'Фактический запуск Studio':'Actual Studio worker command',
 'Активных запусков: {0}':'Active runs: {0}',
 'Готово':'Ready',
 'Не удалось сохранить черновик локально. Сохраните заметки кнопкой ниже.':'The local draft could not be saved. Save your notes with the button below.',
 'Черновик сохранён локально. В отчёт он попадёт после сохранения заметок.':'Draft saved locally. Save the notes to include them in the report.',
 'Есть несохранённые изменения. Сохраните заметки кнопкой ниже.':'You have unsaved changes. Save your notes with the button below.',
 'Заметки сохранены. Локальный черновик обновить не удалось.':'Notes saved. The local draft could not be updated.',
});

Object.assign(en,{"Прокрутка столбцов влево и вправо":"Scroll columns left and right","Перетащите ползунок, чтобы увидеть остальные столбцы":"Drag the scrollbar to view more columns","Таблица результатов":"Results table","Загружаем результаты…":"Loading results…","Подготавливаем таблицу.":"Preparing the table."});

Object.assign(en,{"{0}–{1} из {2}":"{0}–{1} of {2}","Файлы доступны после успешного завершения запуска. Проверьте статус и журнал.":"Files are available after a successful run. Check the status and log."});

Object.assign(en,{"Выбор кейса":"Choose case","Найти кейс по имени, пути, ID или SHA-256":"Find a case by name, path, ID or SHA-256","Имя, путь, ID или SHA-256":"Name, path, ID or SHA-256","Кейсы не найдены":"No matching cases","UTF-16LE: поддерживаются ASCII и кириллица; другие алфавиты пока извлекаются не полностью.":"UTF-16LE supports ASCII and Cyrillic; other scripts are not fully extracted yet."});

Object.assign(en,{"Не записано":"Not recorded"});

Object.assign(en,{"Все алфавиты Unicode (больше шума)": "All Unicode scripts (more noise)", "Unicode: проверяются оба байтовых выравнивания. Возможны совпадения в двоичных данных.": "Unicode scans both byte alignments. Binary data may also produce matches.", "Обычный UTF-16LE: ASCII и кириллица. Для других алфавитов включите Unicode.": "Standard UTF-16LE: ASCII and Cyrillic. Enable Unicode for other scripts.", "Сбросить фильтр": "Clear filter", "В начало": "First", "В конец": "Last", "Не удалось загрузить временную шкалу": "Could not load the timeline", "Повторить": "Retry", "Загрузка временной шкалы…": "Loading timeline…", "При первом открытии индексируются временные поля сохранённых результатов.": "The first visit indexes time fields in saved results.", "Совпадений нет": "No matches", "Измените запрос или сбросьте фильтр. Поиск охватывает всю временную шкалу.": "Change the query or clear the filter. Search covers the entire timeline.", "Измените запрос или сбросьте фильтр.": "Change the query or clear the filter."});

Object.assign(en,{"Строки длиннее 65 536 символов разбиваются на фрагменты с сохранением смещений.":"Strings longer than 65,536 characters are split into fragments with byte offsets preserved."});

Object.assign(en,{"Не удалось построить слой памяти или найти данные типов ОС. Проверьте ОС образа и папки данных для анализа.": "Could not construct a memory layer or locate OS type information. Check the image OS and analysis data directories.", "Плагину требуется YARA. Проверьте зависимости движка.": "This plugin requires YARA. Check the engine dependencies.", "Файл или необходимая зависимость не найдены. Проверьте журнал запуска.": "A file or required dependency was not found. Check the run log.", "Volatility завершил запуск с ошибкой. Полный вывод сохранён в журнале.": "Volatility failed. The full diagnostic output is available in the run log."});
Object.assign(sourceRuByEnglish,{"Could not construct a memory layer or locate OS type information. Check the image OS and analysis data directories.": "Не удалось построить слой памяти или найти данные типов ОС. Проверьте ОС образа и папки данных для анализа.", "This plugin requires YARA. Check the engine dependencies.": "Плагину требуется YARA. Проверьте зависимости движка.", "A file or required dependency was not found. Check the run log.": "Файл или необходимая зависимость не найдены. Проверьте журнал запуска.", "Volatility failed. The full diagnostic output is available in the run log.": "Volatility завершил запуск с ошибкой. Полный вывод сохранён в журнале."});
Object.assign(sourceRuByEnglish,{"Volatility failed. The full output has been saved to the log.":"Volatility завершил запуск с ошибкой. Полный вывод сохранён в журнале."});

Object.assign(en,{"Не удалось загрузить результаты": "Could not load results", "Данные недоступны": "Data unavailable", "Открыть строку {0}": "Open row {0}", "Источники событий": "Event sources", "Последний завершённый запуск каждого плагина": "Latest completed run of each plugin", "Все завершённые запуски": "All completed runs"});

Object.assign(en,{"Открытые кейсы": "Open cases", "Сохранённые кейсы": "Saved cases", "Закрыть кейс {0}": "Close case {0}", "Закрыть кейс": "Close case", "Закрыть все": "Close all", "Наблюдения в кейсах": "Case observations", "Найти кейс": "Find a case", "Наблюдения появятся после сохранения строк результатов.": "Observations appear after saving result rows.", "Сохранённых кейсов пока нет.": "No saved cases yet.", "{0} наблюдений": "{0} observations", "{0} запусков": "{0} runs", "Общие заметки": "Workspace notes", "Планы, гипотезы и ссылки — доступны без открытого образа.": "Plans, hypotheses and links, available without an open image.", "Блокнот рабочего пространства": "Workspace notebook", "Эти заметки хранятся отдельно от кейсов и не включаются в их отчёты.": "These notes are stored separately from cases and are excluded from case reports.", "Не удалось загрузить заметки": "Could not load notes", "Запишите план исследования, вопросы или полезные ссылки…": "Write an investigation plan, questions or useful links…", "Общие заметки сохранены": "Workspace notes saved", "Все изменения сохранены": "All changes saved", "Черновик сохранён локально": "Draft saved locally", "Сохраняем черновик…": "Saving draft…", "Не удалось сохранить черновик": "Could not save the draft", "Загрузка…": "Loading…", "История работы": "Analysis history", "Результаты всех кейсов": "Results across cases", "Запуски анализов во всех сохранённых кейсах. Временные события памяти доступны внутри кейса.": "Analysis runs across saved cases. Memory timestamps are available inside each case.", "Обрабатывайте файл памяти или результаты плагинов.": "Process a memory image or plugin results.", "Откройте готовый результат, даже если его кейс сейчас закрыт.": "Open a saved result, including results from closed cases.", "Выберите источник для конвейера": "Choose a pipeline source", "Файл памяти → строки → фильтры. Результат плагина → поиск, выбор полей, сравнение и удаление повторов.": "Memory image → strings → filters. Plugin results → search, select fields, compare and deduplicate.", "Откройте сохранённый кейс ниже или подключите новый образ, затем выберите источник в редакторе.": "Open a saved case below or attach an image, then choose a source in the editor.", "Последние конвейеры": "Recent pipelines", "Сохранённые результаты": "Saved results", "Поиск по кейсу или плагину": "Search by case or plugin", "Не удалось загрузить историю": "Could not load history", "Здесь пока нет подходящих запусков.": "No matching runs yet.", "Показаны последние 100 запусков. Полная история доступна в каждом кейсе.": "Showing the latest 100 runs. Full history is available in each case.", "Идентификаторы ядра Windows": "Windows kernel identifiers", "PDB — файл отладочных данных; GUID и ревизия подбирают данные для анализа. Найденные сигнатуры не означают несколько установленных ОС. Версию системы смотрите в Info.": "PDB names a debug data file; the GUID and revision identify matching analysis data. Multiple signatures do not mean multiple installed operating systems. Use Info for system details.", "Ревизия": "Revision"});

Object.assign(en,{"Начало": "Home", "Поиск данных ядра завершён. Анализ продолжается.": "Kernel data scan finished. Analysis is still running."});

Object.assign(en,{'Ширина столбца {0}':'Width of column {0}','Перетащите границу. Двойной щелчок — ширина по содержимому страницы. Стрелки — изменить ширину, Enter — подобрать.':'Drag the edge. Double-click to fit this page. Arrow keys resize; Enter fits the contents.','Сбросить ширину столбцов':'Reset column widths'});

Object.assign(en,{"Это контейнер файлов AD1 (FTK), а не прямой образ RAM. Откройте его в FTK Imager и извлеките дамп памяти, если он есть внутри. Поиск строк читает байты контейнера без распаковки; его смещения не являются адресами памяти.": "This is an AD1 file container (FTK), not a directly readable RAM image. Open it in FTK Imager and extract a memory dump if one is included. String search reads container bytes without extraction; its offsets are not memory addresses.", "AD1 logical evidence container": "AD1 logical evidence container", "Определение образа отменено. Нажмите повторное определение, чтобы продолжить.": "Image identification was cancelled. Use identify again to continue."});

Object.assign(sourceRuByEnglish,{"This is an AD1 file container (FTK), not a directly readable RAM image. Open it in FTK Imager and extract a memory dump if one is included. String search reads container bytes without extraction; its offsets are not memory addresses.": "Это контейнер файлов AD1 (FTK), а не прямой образ RAM. Откройте его в FTK Imager и извлеките дамп памяти, если он есть внутри. Поиск строк читает байты контейнера без распаковки; его смещения не являются адресами памяти.", "Image identification was cancelled. Use identify again to continue.": "Определение образа отменено. Нажмите повторное определение, чтобы продолжить."});

Object.assign(en,{'Идентификатор ядра':'Kernel identifier'});

Object.assign(en,{'Логический контейнер AD1 (FTK)':'AD1 logical evidence container'});Object.assign(sourceRuByEnglish,{'AD1 logical evidence container':'Логический контейнер AD1 (FTK)'});

Object.assign(sourceRuByEnglish,{'Kernel identifier':'Идентификатор ядра'});

Object.assign(en,{'Превышен лимит памяти ({0} MiB). Анализ остановлен. Увеличьте лимит в настройках и повторите запуск.':'Memory budget exceeded ({0} MiB). Analysis stopped. Increase the budget in Settings and retry.'});

Object.assign(en,{
  "Это образ раздела с файловой системой ext, а не снимок RAM. Плагины процессов и сети здесь неприменимы. Используйте инструмент анализа дисков; поиск строк читает байты раздела без восстановления файлов.": "This is an ext filesystem partition image, not a RAM capture. Process and network memory plugins do not apply. Use a disk forensics tool; string search reads partition bytes without recovering files.",
  "Это ELF-файл программы или библиотеки, а не ELF core dump. Он не подтверждён как снимок RAM всей системы. Доступен поиск строк.": "This is an ELF executable or shared library, not an ELF core dump. It is not a confirmed full-system RAM capture. String search is available.",
  "Баннер Linux найден. Для разбора процессов и других структур нужен ISF JSON с точным соответствием полному баннеру; одного номера версии ядра недостаточно.": "A Linux banner was found. Process and other structure analysis requires ISF JSON matching the full banner exactly; the kernel version alone is insufficient.",
  "Не удалось прочитать структуры Linux. Сначала проверьте ISF JSON для полного баннера ядра и выбранную папку данных ОС. Недостающие данные типов также мешают построению слоя памяти; эта ошибка сама по себе не доказывает повреждение образа.": "Linux structures could not be read. First check the ISF JSON for the full kernel banner and the selected OS data directory. Missing type information can also prevent memory-layer construction; this error alone does not prove image corruption.",
  "ext filesystem partition image": "ext filesystem partition image",
  "ELF executable or shared object": "ELF executable or shared object",
  "Настроить данные ОС": "Configure OS data",
  "Какие аргументы у процессов Linux?": "What arguments did Linux processes use?",
  "Показывает доступные аргументы процессов Linux; чтение может быть неполным.": "Shows available Linux process arguments; recovery can be incomplete.",
  "Какие библиотеки загружены?": "Which libraries were loaded?",
  "Перечисляет библиотеки процессов Linux. Сопоставляйте пути и контекст процесса.": "Lists Linux process libraries. Correlate paths with process context."
});
Object.assign(runtimeRu,{"ext filesystem partition image": "Образ раздела ext", "ELF executable or shared object": "Исполняемый ELF или библиотека"});

Object.assign(sourceRuByEnglish,{
  "This is an ext filesystem partition image, not a RAM capture. Process and network memory plugins do not apply. Use a disk forensics tool; string search reads partition bytes without recovering files.": "Это образ раздела с файловой системой ext, а не снимок RAM. Плагины процессов и сети здесь неприменимы. Используйте инструмент анализа дисков; поиск строк читает байты раздела без восстановления файлов.",
  "This is an ELF executable or shared library, not an ELF core dump. It is not a confirmed full-system RAM capture. String search is available.": "Это ELF-файл программы или библиотеки, а не ELF core dump. Он не подтверждён как снимок RAM всей системы. Доступен поиск строк.",
  "A Linux banner was found. Process and other structure analysis requires ISF JSON matching the full banner exactly; the kernel version alone is insufficient.": "Баннер Linux найден. Для разбора процессов и других структур нужен ISF JSON с точным соответствием полному баннеру; одного номера версии ядра недостаточно.",
  "Linux structures could not be read. First check the ISF JSON for the full kernel banner and the selected OS data directory. Missing type information can also prevent memory-layer construction; this error alone does not prove image corruption.": "Не удалось прочитать структуры Linux. Сначала проверьте ISF JSON для полного баннера ядра и выбранную папку данных ОС. Недостающие данные типов также мешают построению слоя памяти; эта ошибка сама по себе не доказывает повреждение образа.",
  "Configure OS data": "Настроить данные ОС",
  "What arguments did Linux processes use?": "Какие аргументы у процессов Linux?",
  "Shows available Linux process arguments; recovery can be incomplete.": "Показывает доступные аргументы процессов Linux; чтение может быть неполным.",
  "Which libraries were loaded?": "Какие библиотеки загружены?",
  "Lists Linux process libraries. Correlate paths with process context.": "Перечисляет библиотеки процессов Linux. Сопоставляйте пути и контекст процесса."
});

Object.assign(en,{
  "ТЕКУЩИЙ ОБРАЗ": "CURRENT IMAGE",
  "Выбор образа": "Image switcher",
  "Открытые образы": "Open images",
  "Недавние образы": "Recent images",
  "Найти образ по имени, пути, ID или SHA-256": "Find image by name, path, ID or SHA-256",
  "Закрыть образ {0}": "Close image {0}",
  "Закрыть образ": "Close image",
  "Образы не найдены": "No images found"
});
Object.assign(sourceRuByEnglish,{
  "CURRENT IMAGE": "ТЕКУЩИЙ ОБРАЗ",
  "Image switcher": "Выбор образа",
  "Open images": "Открытые образы",
  "Recent images": "Недавние образы",
  "Find image by name, path, ID or SHA-256": "Найти образ по имени, пути, ID или SHA-256",
  "Close image {0}": "Закрыть образ {0}",
  "Close image": "Закрыть образ",
  "No images found": "Образы не найдены"
});

Object.assign(en,{
  "Разделы настроек": "Settings sections",
  "Интерфейс": "Appearance",
  "Анализ": "Analysis",
  "О программе": "About",
  "Оформление": "Theme",
  "Светлое": "Light",
  "Тёмное": "Dark",
  "Сборка (UTC)": "Built (UTC)",
  "Данные приложения": "Application data",
  "Кейсы, результаты и заметки хранятся на вашем компьютере.": "Cases, results and notes are stored on your computer.",
  "Открыть папку": "Open folder",
  "Не удалось загрузить некоторые плагины:": "Some plugins could not be loaded:",
  "Анализ образов оперативной памяти: процессы, сетевые соединения, командные строки и другие артефакты. Независимый графический интерфейс для Volatility 3.": "Memory image analysis: processes, network connections, command lines and other artifacts. An independent graphical interface for Volatility 3.",
  "Справка": "Help",
  "Активные процессы и их идентификаторы.": "Active processes and their identifiers.",
  "Сетевые соединения": "Network connections",
  "Соединения и связанные с ними процессы.": "Connections and associated processes.",
  "Командные строки": "Command lines",
  "Аргументы запуска процессов.": "Process launch arguments.",
  "Открыть выполняющийся анализ": "View running analysis",
  "Открыть результат · {0} строк": "View result · {0} rows",
  "Настроить запуск": "Configure run",
  "Копирование результата": "Copy result",
  "Скопировать значение": "Copy value",
  "Скопировать выделенный текст": "Copy selected text",
  "Скопировать строку (TSV)": "Copy row (TSV)",
  "Скопировано": "Copied"
});
Object.assign(sourceRuByEnglish,{
  "Settings sections": "Разделы настроек",
  "Appearance": "Интерфейс",
  "Analysis": "Анализ",
  "About": "О программе",
  "Theme": "Оформление",
  "Light": "Светлое",
  "Dark": "Тёмное",
  "Built (UTC)": "Сборка (UTC)",
  "Application data": "Данные приложения",
  "Cases, results and notes are stored on your computer.": "Кейсы, результаты и заметки хранятся на вашем компьютере.",
  "Open folder": "Открыть папку",
  "Some plugins could not be loaded:": "Не удалось загрузить некоторые плагины:",
  "Memory image analysis: processes, network connections, command lines and other artifacts. An independent graphical interface for Volatility 3.": "Анализ образов оперативной памяти: процессы, сетевые соединения, командные строки и другие артефакты. Независимый графический интерфейс для Volatility 3.",
  "Help": "Справка",
  "Active processes and their identifiers.": "Активные процессы и их идентификаторы.",
  "Network connections": "Сетевые соединения",
  "Connections and associated processes.": "Соединения и связанные с ними процессы.",
  "Command lines": "Командные строки",
  "Process launch arguments.": "Аргументы запуска процессов.",
  "View running analysis": "Открыть выполняющийся анализ",
  "View result · {0} rows": "Открыть результат · {0} строк",
  "Configure run": "Настроить запуск",
  "Copy result": "Копирование результата",
  "Copy value": "Скопировать значение",
  "Copy selected text": "Скопировать выделенный текст",
  "Copy row (TSV)": "Скопировать строку (TSV)",
  "Copied": "Скопировано"
});

Object.assign(en,{"Выберите процессы, соединения, командные строки или другой плагин.": "Choose processes, connections, command lines or another plugin."});
Object.assign(sourceRuByEnglish,{"Choose processes, connections, command lines or another plugin.": "Выберите процессы, соединения, командные строки или другой плагин."});

Object.assign(en,{"Volatility работает в офлайн-режиме и не нашёл данные ядра Windows. Откройте Настройки → Анализ: добавьте локальные данные ОС или разрешите их загрузку.": "Volatility is offline and Windows kernel data is unavailable. Open Settings → Analysis: add local OS data or allow downloads."});
Object.assign(sourceRuByEnglish,{"Volatility is offline and Windows kernel data is unavailable. Open Settings → Analysis: add local OS data or allow downloads.": "Volatility работает в офлайн-режиме и не нашёл данные ядра Windows. Откройте Настройки → Анализ: добавьте локальные данные ОС или разрешите их загрузку."});

Object.assign(en,{
  "Дата сборки": "Build date",
  "Папка может содержать извлечённые данные и чувствительные сведения из образов. Не отправляйте её целиком без проверки содержимого.": "This folder may contain extracted data and sensitive information from images. Review its contents before sharing it.",
  "Источник и проверка целостности": "Source and integrity verification",
  "Перетащите файл памяти в окно или выберите его через Проводник. Studio читает файл по исходному пути и рассчитывает SHA-256 в фоне. Анализ начинается после проверки; исходный файл не изменяется.": "Drop a memory image into the window or choose it with the file picker. Studio reads the original path and calculates SHA-256 in the background. Analysis starts after verification; the source file is not modified.",
  "Расширение файла не гарантирует совместимость. Для снимка VMware могут понадобиться сопутствующие VMSS/VMEM. AD1, раздел диска и дамп отдельного процесса не равнозначны снимку оперативной памяти всей системы.": "A file extension does not guarantee compatibility. VMware snapshots may require companion VMSS/VMEM files. AD1 containers, disk partitions and individual process dumps are not equivalent to full-system memory captures.",
  "Определение системы и данные ОС": "System identification and OS data",
  "Banners ищет идентификаторы ядра, Info уточняет доступные сведения Windows. Эти запуски выполняются автоматически при подключении подходящего образа; их результаты остаются в истории.": "Banners searches for kernel identifiers; Info retrieves available Windows details. These runs start automatically for suitable images, and their results remain in the history.",
  "Строки PDB и GUID в Windows — идентификаторы отладочных данных. Версию системы смотрите в Info. Для Linux нужен ISF JSON, соответствующий полному баннеру конкретного ядра.": "Windows PDB and GUID strings identify debugging data. Use Info for the OS version. Linux requires ISF JSON matching the full banner of the specific kernel.",
  "В Настройках → Анализ можно добавить локальные данные ОС и разрешить их загрузку. В офлайн-режиме используются только локальные файлы. Содержимое образа приложение не загружает в интернет.": "In Settings → Analysis, add local OS data or allow downloads. Offline mode uses local files only. The application does not upload image contents to the internet.",
  "Плагины, очередь и память": "Plugins, queue and memory",
  "На обзоре доступны процессы, соединения и командные строки. Кнопка открывает имеющийся результат без фильтра либо форму запуска. Остальные инструменты находятся в разделе Плагины и поиске Ctrl+K.": "The overview offers processes, connections and command lines. Each action opens an existing unfiltered result or the run settings. Find other tools in Plugins or with Ctrl+K.",
  "PID ограничивает анализ выбранными процессами, если плагин поддерживает этот параметр. Для необязательного PID пустое поле означает анализ без такого ограничения. Обязательные параметры отмечены в форме.": "PID restricts analysis to selected processes when supported by the plugin. Leaving an optional PID field empty removes that restriction. Required parameters are marked in the form.",
  "Плагины выполняются по одному в отдельных процессах. Лимит памяти задаётся в Настройках → Анализ. Отмена останавливает запуск; незавершённый результат не следует считать полным.": "Plugins run one at a time in separate processes. Set the memory budget in Settings → Analysis. Cancelling stops the run; an unfinished result must not be treated as complete.",
  "Таблица и длинные командные строки": "Tables and long command lines",
  "Поиск охватывает все строки результата, а не только текущую страницу. Сортировка доступна по заголовку. Верхний горизонтальный ползунок помогает читать широкие таблицы мышью.": "Search covers all result rows, including other pages. Click a column heading to sort. Use the top horizontal scrollbar to read wide tables with a mouse.",
  "Перетащите границу заголовка, чтобы изменить ширину столбца. Двойной щелчок подбирает ширину по текущей странице. Последний столбец подбирается автоматически, пока вы не настроили его вручную.": "Drag a heading boundary to resize a column. Double-click it to fit the current page. The last column is fitted automatically until you resize it manually.",
  "Щёлкните строку или нажмите Enter на ней, чтобы открыть все поля и действия для PID. ПКМ в ячейке открывает копирование значения и строки. Значок закладки появляется при наведении на свою ячейку или клавиатурном фокусе.": "Click a row or press Enter on it to see all fields and PID actions. Right-click a cell to copy its value or row. The bookmark icon appears when its cell is hovered or the button has keyboard focus.",
  "Конвейеры и поиск строк": "Pipelines and string search",
  "Источник конвейера — файл памяти или готовый результат плагина. Добавляйте поиск, сравнение значений, выбор полей, разделение текста и удаление повторов. Шаги выполняются по порядку без запуска произвольных команд оболочки.": "A pipeline takes a memory image or a completed plugin result. Add search, comparisons, field selection, text splitting and deduplication. Steps run in order without executing arbitrary shell commands.",
  "Для файла доступны ASCII и UTF-16LE. Режим всех алфавитов Unicode включается отдельно. Смещение найденной строки относится к байтам файла и не равно виртуальному адресу процесса.": "Image string search supports ASCII and UTF-16LE. Enable all Unicode scripts separately. A string offset refers to bytes in the source file, not a process virtual address.",
  "При достижении лимита строк обработка останавливается, а результат помечается как частичный. Поиск печатных строк не заменяет разбор структур ОС.": "Processing stops at the row limit, and the result is marked as partial. Searching printable strings does not replace parsing OS structures.",
  "Наблюдения, заметки и экспорт": "Observations, notes and export",
  "Сохраняйте важные строки в закладки с пояснением. Заметки относятся к текущему кейсу. Общий блокнот доступен без образа и хранится отдельно от отчётов кейсов.": "Bookmark important rows with an explanation. Case notes belong to the current case. The workspace notebook is available without an image and is separate from case reports.",
  "Черновик заметки сохраняется локально, но для включения текста в отчёт нажмите Сохранить заметки. Закрытие вкладки образа сохраняет его историю в Недавних образах.": "Note drafts are stored locally. Click Save notes to include the text in a report. Closing an image tab preserves its history in Recent images.",
  "CSV и JSON экспортируют всю выбранную выборку результата. Журнал содержит параметры, фактическую команду, версии и сведения об источнике. Перед передачей отчёта проверьте его содержимое на чувствительные данные.": "CSV and JSON export the entire selected result set. The log includes parameters, the actual command, versions and source information. Review reports for sensitive data before sharing them.",
  "Как понимать пустые результаты и ошибки": "Understanding empty results and errors",
  "Ноль строк не доказывает отсутствие артефактов. Проверьте выбранный образ, ОС, параметры и полный журнал запуска. Данные процессов и соединений могут быть неполными или относиться к завершённым объектам.": "Zero rows do not prove that artifacts are absent. Check the selected image, OS, parameters and full run log. Process and connection data may be incomplete or refer to terminated objects.",
  "Находка Malfind или сканера сама по себе не доказывает заражение. Сопоставляйте процессы, командные строки, соединения и другие источники.": "A Malfind or scanner finding alone does not prove infection. Correlate processes, command lines, connections and other sources.",
  "Если исходный файл перенесён или изменён, сохранённый кейс не становится новым доказательством автоматически. Подключите доступный файл и проверьте его хеш. Путь к результатам и журналам доступен в Настройках → О программе → Данные приложения.": "Moving or changing a source file does not automatically update a saved case. Attach the available file and verify its hash. Find the results and log location in Settings → About → Application data.",
  "Практическая справка по работе с образами памяти и результатами анализа.": "Practical guidance for working with memory images and analysis results.",
  "Быстрый старт": "Quick start",
  "Откройте образ и дождитесь проверки SHA-256.": "Open an image and wait for SHA-256 verification.",
  "Проверьте определённую ОС и доступность данных ядра.": "Check the identified OS and availability of kernel data.",
  "Начните с PsList, соединений и командных строк.": "Start with PsList, connections and command lines.",
  "Сохраните наблюдения и экспортируйте нужные результаты.": "Save observations and export the results you need.",
  "Настройки анализа": "Analysis settings",
  "Подготовка данных ОС: {0}": "Preparing OS analysis data: {0}",
  "Не удалось отобразить память VMware. Проверьте комплект VMSS/VMEM и журнал; сжатые блоки пока не поддерживаются. ": "VMware memory mapping is unavailable. Check the VMSS/VMEM file set and log; compressed blocks are not supported. "
});

Object.assign(en,{
  "Загружаем рабочее пространство…": "Loading workspace…",
  "Не удалось открыть рабочее пространство": "Could not open the workspace",
  "Сохранённые кейсы и настройки не изменены.": "Saved cases and settings have not been changed.",
  "Повторить загрузку": "Retry loading",
  "Загружаем настройки…": "Loading settings…",
  "Не удалось загрузить настройки": "Could not load settings",
  "Первая страница": "First page",
  "Последняя страница": "Last page",
  "Перейти на страницу": "Go to page",
  "Введите номер страницы и нажмите Enter": "Enter a page number and press Enter",
  "Введите страницу от 1 до {0}": "Enter a page from 1 to {0}"
});

Object.assign(en,{"Плагин или статус…":"Plugin or status…"});

Object.assign(sourceRuByEnglish,Object.fromEntries(Object.entries(en).filter(([ru,english])=>ru!==english).map(([ru,english])=>[english,ru])));

export const localizationCatalog=()=>[...new Set([...Object.values(en),...Object.keys(runtimeRu)])].sort();

// Release 0.4.6
Object.assign(en,{"Выбрано: {0}": "Selected: {0}", "Исключено: {0}": "Excluded: {0}", "Выбрать видимые": "Select visible", "Снять выделение": "Clear selection", "Выбрать плагин {0}": "Select plugin {0}", "Запустить выбранные ({0})": "Run selected ({0})", "Параметры выбранных плагинов": "Selected plugin options", "Плагины добавлены в очередь: {0}": "Plugins queued: {0}", "Запуски выполнятся по очереди. Все результаты сохранятся отдельно.": "Runs execute sequentially. Each result is saved separately.", "Фильтр значений: {0}": "Value filter: {0}", "Поиск значений": "Search values", "Все значения": "All values", "Выбрать всё": "Select all", "Ничего не выбрано": "Nothing selected", "Загрузить ещё": "Load more", "Применить": "Apply", "Сбросить фильтры": "Clear filters", "(Поле отсутствует)": "(Field missing)", "(Пусто)": "(Empty)", "(Пустая строка)": "(Empty string)", "Строка {0} сохранена в закладки": "Row {0} bookmarked", "Она всегда доступна в справке — значок ? справа сверху.": "It is always available in Help: the ? icon at the top right.", "CSV · текущая выборка": "CSV · filtered rows", "Слишком много выбранных значений. Вместо этого исключите ненужные.": "Too many selected values. Exclude unwanted values instead.", "Не более 50 плагинов за один запуск": "Up to 50 plugins per batch", "В каталоге можно выделить несколько плагинов галочками и запустить одной кнопкой. Для индивидуальных параметров используйте кнопку настройки рядом с запуском.": "Select multiple plugins with checkboxes and run them with one button. Use the adjacent options button to configure each plugin.", "Значок фильтра в заголовке столбца показывает уникальные значения и число строк. Выбор применяется ко всему результату и CSV/JSON, а не только к текущей странице.": "The filter icon in a column header shows distinct values and row counts. Selection applies to the entire result and CSV/JSON, not just the current page.", "Некоторые плагины возвращают короткое имя из структуры ОС. Studio не дописывает расширение. Полный путь и аргументы ищите в CmdLine или других источниках.": "Some plugins return a short name stored in the OS structure. Studio does not append an extension. Check CmdLine or other sources for the full path and arguments."});

Object.assign(en,{"Блокнот расследования": "Investigation notebook", "Закрыть блокнот": "Close notebook", "Текст расследования": "Investigation notes", "Копировать заметки": "Copy notes", "Экспорт заметок TXT": "Export notes as TXT", "План, гипотезы, команды, находки и выводы…": "Plan, hypotheses, commands, findings and conclusions…", "Сохраняем заметки…": "Saving notes…", "Не удалось сохранить заметки": "Could not save notes", "Блокнот справа сверху доступен на любом экране. Заметки кейса и общие заметки сохраняются автоматически; Ctrl+S сохраняет сразу. Можно копировать текст и экспортировать TXT.": "The notebook at the top right is available on every screen. Case and workspace notes save automatically; Ctrl+S saves immediately. Copy text or export TXT."});

Object.assign(en,{"Версия приложения":"App version"});

Object.assign(en, {
    "Избранные плагины": "Favorite plugins",
    "Добавить {0} в избранное": "Add {0} to favorites",
    "Убрать {0} из избранного": "Remove {0} from favorites",
    "Нажмите звёздочку рядом с нужным плагином.": "Click the star next to a plugin to save it.",
    "Скрыть убранные образы": "Hide removed images",
    "Показать убранные образы ({0})": "Show removed images ({0})",
    "Вернуть {0} в недавние": "Restore {0} to recent images",
    "Убрать {0} из недавних": "Remove {0} from recent images",
    "Нет образов в списке": "No images to show",
    "Не удалось вычислить хеши": "Could not calculate hashes",
    "Вычисляем MD5 и SHA-256…": "Calculating MD5 and SHA-256…",
    "Скопировать хеш {0}": "Copy {0} hash",
    "Тип адреса {0} не определён. Проверьте Info или выберите тип вручную.": "Could not determine the address type for {0}. Check Info or choose it manually.",
    "Физический адрес": "Physical address",
    "Виртуальный адрес": "Virtual address",
    "Открыть файл в DumpFiles": "Open file in DumpFiles",
    "В Volatility {0} плагин {1} не поддерживает структуры conhost для Windows {2}.": "In Volatility {0}, {1} does not support the conhost structures for Windows {2}.",
    "Для истории консоли нужен анализатор с поддержкой этой сборки. CmdLine показывает аргументы запуска процессов.": "Console history requires an analyzer that supports this build. CmdLine shows process launch arguments.",
    "Открыть CmdLine": "Open CmdLine"
});
