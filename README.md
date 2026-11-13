# volati elite

Volati Elite is a Windows desktop interface for [Volatility 3](https://github.com/volatilityfoundation/volatility3). It brings plugin execution, result analysis and investigation notes into a single workspace.

**Early test version.** Stability, performance and everyday usability are still being improved. This is an independent project, not an official Volatility Foundation product.

## Download

[Windows x64 portable test build](https://github.com/serrr666/volati-elite/releases/tag/v0.4.11-test.1)

Download `VolatiElite.exe` from the pre-release assets and run it.

For optional Volatility 2 support, extract `legacy-volatility2.zip` next to the EXE. The extracted `legacy-volatility2` folder must sit directly beside `VolatiElite.exe`. After a supported failure in Volatility 3, `Consoles` and `CmdScan` can be retried through Volatility 2 on verified Windows 7 SP0 x86 images with default options.

## Quick start

1. Drop a memory image into the window, or choose it through the file dialog.
2. Let the app finish the source checks and review the detected system. Linux and macOS analysis may require matching kernel data.
3. Start with processes, network connections or command lines. Select several plugins to queue them together.
4. Filter the results, bookmark useful rows and write down your findings in the investigation notebook.
5. Export the relevant results as CSV or JSON, or save your notes as TXT.

The original image is read from its existing location. Case data, results, caches and notes are stored locally. The profile folder remains `%LOCALAPPDATA%\Vol3Studio` for compatibility with earlier test builds.

## What is included

- A searchable plugin library with categories, practical descriptions and batch selection.
- Structured result tables with adjustable columns, full-result search and filters by unique values.
- Case notes, workspace notes and bookmarks linked to their source rows.
- Pipelines for processing plugin output and searching strings in an image.
- A run history, extracted-file access and case export.
- English, Russian, Simplified Chinese, Spanish, German and French interfaces.
- Light and dark themes.

Windows is the desktop target. Analysis support for Windows, Linux and macOS images depends on the bundled Volatility plugins, image format and available kernel data.

## Screenshots

### Home

![Volati Elite home screen](docs/images/home.png)

### Plugins

![Volati Elite plugin library](docs/images/plugins.png)

## Testing and feedback

This is a test project, not a validated forensic suite. Image compatibility, plugins and resource usage need further testing. Cross-check important findings with the underlying engine; an empty result does not prove an artifact is absent.

Bug reports are welcome in [Issues](https://github.com/serrr666/volati-elite/issues), or in Telegram direct @serpf. Include the app version, plugin, image format and steps to reproduce. Please do not attach private memory images, credentials or unreviewed case data. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License and author

[Volatility Software License 1.0](LICENSE). Third-party notices and bundled font licenses are included in the repository. Volatility 3 is developed by the Volatility Foundation.

Project: [serrr666](https://github.com/serrr666).
