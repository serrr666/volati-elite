# Changelog

## 0.4.18

- Match CSV downloads, clipboard copies and JSON exports to the current result filters and sort order.
- Search exact large integers in saved column values and refresh extracted-file hashes after a file is rewritten.

## 0.4.17

- Keep notebook saves and run cancellation available while upgrading a large timeline. Publish a complete timeline after its index is ready.
- Keep the plugin catalog consistent with the active analysis settings while it refreshes. Retain the working catalog if a refresh fails.
- Keep the requested results page when opening a new run or navigating to a bookmarked row.

## 0.4.16

- Validate source identity as well as file size and timestamp before reusing a case or starting a new memory analysis.
- Verify previously attached evidence against its saved SHA-256 on the first new analysis after upgrade.
- Keep cancelled work cancelled and mark unfinished work as interrupted on close. Preserve the original source digest in derived results.
- Include VMware snapshot inventories in the file picker and clarify the default OS data retrieval setting.

## 0.4.15

- Include MFT update and access times in the timeline, including saved results.
- Retain extraction records when files are removed or unavailable.
- Show VMware snapshot files and a direct path to string search for supplementary sources.
- Warn before repeating a console analysis that failed on the same image and engine version.

## 0.4.14

- Make process memory extraction visible in Memmap and open the extracted files and hashes when the run finishes.
- Pass the correct PID argument shape when opening a plugin from a process row.
- Show loading and retry states when reading extracted files.
- Prevent duplicate queue submissions while a plugin launch is being saved.

## 0.4.13

- Hide the suggested plugins on Home and restore them from Appearance settings.

## 0.4.12

- Copy result rows as CSV from the Export menu, including all rows that match the current filters.
- Run all memory analysis plugins through Volatility 3.
- Recover the OS detection status on restart and match non-ASCII text in column-value search.
- Use Volati Elite branding in exported case reports.

## 0.4.11

- Search observations and find text in the investigation notebook.
- Show the completed result count in the sidebar and simplify queue notifications.
