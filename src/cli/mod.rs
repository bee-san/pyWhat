//! The `what` and `pywhat` commands, with the options, the output and the exit codes of
//! the Python package's CLI (`pywhat/what.py`): `pywhat::cli::main` is what both binaries
//! run, and what the Python package's commands call.
//!
//! ```no_run
//! // src/bin/what.rs
//! std::process::exit(pywhat::cli::main(std::env::args_os()))
//! ```
//!
//! What it does differently from the Python CLI: it prints the matched text and the file
//! names as they are, where the Python CLI takes them for rich markup (`thm{[bold]x[/bold]}`
//! or `:smile:`); `--interactive` needs the Python package; and a file that can't be read
//! is reported and skipped.

mod args;
mod help;
mod markup;
mod output;
mod progress;
mod python;
mod style;
mod table;
pub mod verify;

use crate::files::{Found, Identified, InputOptions};
use crate::filter::{split_tags, Filter};
use crate::processors::{default_processors, OpenStreetMap, Processor};
use crate::ranking::{Key, Top};
use crate::Identifier;
use args::Param;
use output::Printer;
use std::collections::HashMap;
use std::ffi::OsString;
use std::io::{self, IsTerminal, Read, Write};
use style::{Colors, Text, LABEL, VERSION};

/// Runs the command line `args`, the program name first (as `std::env::args_os()` gives
/// it), and returns the exit code: 0, 1 for errors (as in Python), 2 for usage errors.
/// The name of the program, without its directory, is the name that `--help` shows.
pub fn main<I, T>(args: I) -> i32
where
    I: IntoIterator<Item = T>,
    T: Into<OsString>,
{
    let mut args = args.into_iter().map(|arg| {
        arg.into()
            .into_string()
            .unwrap_or_else(|arg| arg.to_string_lossy().into_owned())
    });
    let prog = args
        .next()
        .map_or_else(|| "what".to_string(), |arg0| program_name(&arg0));
    let args: Vec<String> = args.collect();
    let env = Environment::detect();
    let mut stdin = io::stdin();
    let mut stdout = io::BufWriter::with_capacity(1 << 16, io::stdout());
    let mut stderr = io::stderr();
    let mut streams = Streams {
        stdin: &mut stdin,
        stdout: &mut stdout,
        stderr: &mut stderr,
    };
    run(&prog, &args, &env, &mut streams, &GoogleVerifier::default())
}

/// The name of the program in `--help`: the file name of `arg0` (without `.exe` on
/// Windows), like click's `_detect_program_name()`.
fn program_name(arg0: &str) -> String {
    let separators: &[char] = if cfg!(windows) { &['/', '\\'] } else { &['/'] };
    let name = arg0.rsplit(separators).next().unwrap_or(arg0);
    if cfg!(windows) && name.to_ascii_lowercase().ends_with(".exe") {
        return name[..name.len() - 4].to_string();
    }
    name.to_string()
}

/// A stream of the process: whether it is a terminal or a regular file, and its width.
#[derive(Debug, Clone, Copy, Default)]
struct StreamInfo {
    terminal: bool,
    regular_file: bool,
    columns: Option<usize>,
}

/// What the command needs to know about where it runs.
#[derive(Debug, Clone, Default)]
struct Environment {
    vars: HashMap<&'static str, String>,
    stdin: StreamInfo,
    stdout: StreamInfo,
    stderr: StreamInfo,
}

/// The environment variables that the Python CLI (click and rich) reads.
const VARIABLES: [&str; 5] = ["COLUMNS", "LINES", "TERM", "COLORTERM", "NO_COLOR"];

#[cfg(unix)]
fn stream_info<S: IsTerminal + std::os::fd::AsFd>(stream: S) -> StreamInfo {
    let regular_file = stream
        .as_fd()
        .try_clone_to_owned()
        .map(std::fs::File::from)
        .and_then(|file| file.metadata())
        .is_ok_and(|metadata| metadata.is_file());
    StreamInfo {
        terminal: stream.is_terminal(),
        regular_file,
        columns: terminal_size::terminal_size_of(stream).map(|(width, _)| width.0 as usize),
    }
}

#[cfg(windows)]
fn stream_info<S: IsTerminal + std::os::windows::io::AsHandle>(stream: S) -> StreamInfo {
    let regular_file = stream
        .as_handle()
        .try_clone_to_owned()
        .map(std::fs::File::from)
        .and_then(|file| file.metadata())
        .is_ok_and(|metadata| metadata.is_file());
    StreamInfo {
        terminal: stream.is_terminal(),
        regular_file,
        columns: terminal_size::terminal_size_of(stream).map(|(width, _)| width.0 as usize),
    }
}

#[cfg(not(any(unix, windows)))]
fn stream_info<S: IsTerminal>(stream: S) -> StreamInfo {
    StreamInfo {
        terminal: stream.is_terminal(),
        ..StreamInfo::default()
    }
}

impl Environment {
    fn detect() -> Environment {
        let vars = VARIABLES
            .iter()
            .filter_map(|&name| {
                std::env::var_os(name).map(|value| (name, value.to_string_lossy().into_owned()))
            })
            .collect();
        Environment {
            vars,
            stdin: stream_info(io::stdin()),
            stdout: stream_info(io::stdout()),
            stderr: stream_info(io::stderr()),
        }
    }

    fn var(&self, name: &str) -> Option<String> {
        self.vars.get(name).cloned()
    }

    /// The colours of a stream, as rich detects them.
    fn colors(&self, stream: &StreamInfo) -> Colors {
        Colors::detect(stream.terminal, &|name| self.var(name))
    }

    /// `shutil.get_terminal_size().columns`, which click's help uses: `COLUMNS` if it is
    /// a positive number, else the width of the terminal of stdout, else 80.
    fn click_columns(&self) -> usize {
        match self
            .var("COLUMNS")
            .and_then(|columns| python::int(&columns))
        {
            Some(columns) if columns > 0 => usize::try_from(columns).unwrap_or(usize::MAX),
            _ => self
                .stdout
                .columns
                .filter(|&columns| columns > 0)
                .unwrap_or(80),
        }
    }

    /// The width of a rich `Console` on stdout: `COLUMNS` if it is a number, else the width
    /// of the terminal of stdin or (on Windows: only) stdout, else 80. On a dumb terminal,
    /// 80 unless `COLUMNS` and `LINES` are both numbers.
    fn rich_width(&self) -> usize {
        let number = |name: &str| {
            self.var(name).filter(|value| {
                !value.is_empty() && value.chars().all(|c| python::decimal_value(c).is_some())
            })
        };
        let columns = number("COLUMNS");
        if self.stdout.terminal
            && style::is_dumb(self.var("TERM").as_deref())
            && (columns.is_none() || number("LINES").is_none())
        {
            return 80;
        }
        let width = match columns.and_then(|columns| python::int(&columns)) {
            Some(columns) => usize::try_from(columns).unwrap_or(usize::MAX),
            None if cfg!(windows) => self.stdout.columns.unwrap_or(0),
            None => self.stdin.columns.or(self.stdout.columns).unwrap_or(0),
        };
        if width == 0 {
            80
        } else {
            width
        }
    }
}

/// The streams of the process.
struct Streams<'a> {
    stdin: &'a mut dyn Read,
    stdout: &'a mut dyn Write,
    stderr: &'a mut dyn Write,
}

/// Makes the `--verify` verifier; tests give it a fake Google.
#[derive(Default)]
struct GoogleVerifier {
    make: Option<Box<dyn Fn() -> verify::GoogleApiKeyVerifier>>,
}

impl GoogleVerifier {
    fn verifier(&self) -> verify::GoogleApiKeyVerifier {
        match &self.make {
            Some(make) => make(),
            None => verify::GoogleApiKeyVerifier::new(),
        }
    }
}

/// Runs the command, returns its exit code. A closed output (`what ... | head`) ends it
/// with 1, as click does.
fn run(
    prog: &str,
    args: &[String],
    env: &Environment,
    streams: &mut Streams<'_>,
    verifier: &GoogleVerifier,
) -> i32 {
    let code = match execute(prog, args, env, streams, verifier) {
        Ok(code) => streams.stdout.flush().map_or(1, |_| code),
        Err(error) if error.kind() == io::ErrorKind::BrokenPipe => 1,
        Err(error) => {
            let _ = writeln!(streams.stderr, "Error: {error}");
            1
        }
    };
    let _ = streams.stdout.flush();
    code
}

/// An error of click's parser (an option without its value, or a flag with one): click shows
/// only `Error: <message>`, as these errors have no context, and exits with 2.
fn parse_error(message: &str, streams: &mut Streams<'_>) -> io::Result<i32> {
    streams.stdout.flush()?;
    writeln!(streams.stderr, "Error: {message}")?;
    Ok(2)
}

/// An invalid value of an option (`--map`), as click shows it: the usage line, a hint and
/// the error, exit code 2.
fn usage_error(
    prog: &str,
    message: &str,
    env: &Environment,
    streams: &mut Streams<'_>,
) -> io::Result<i32> {
    streams.stdout.flush()?;
    let width = help::help_width(env.click_columns());
    let usage = help::usage(prog, width);
    write!(
        streams.stderr,
        "{usage}\nTry '{prog} --help' for help.\n\nError: {message}\n"
    )?;
    Ok(2)
}

/// Prints `message` and a line break on stdout, with `print()`.
fn print_line(streams: &mut Streams<'_>, message: &str) -> io::Result<()> {
    writeln!(streams.stdout, "{message}")
}

/// `sys.exit(message)`: the message on stderr, exit code 1.
fn exit_with(streams: &mut Streams<'_>, message: &str) -> io::Result<i32> {
    streams.stdout.flush()?;
    writeln!(streams.stderr, "{message}")?;
    Ok(1)
}

/// `print_tags()`: every tag, sorted.
fn print_tags(streams: &mut Streams<'_>, colors: Colors) -> io::Result<()> {
    let mut text = Text::new();
    for (index, tag) in crate::tags().iter().enumerate() {
        if index > 0 {
            text.plain("\n");
        }
        text.styled(tag, LABEL);
    }
    let mut printer = Printer {
        out: streams.stdout,
        colors,
    };
    printer.print(&text)
}

/// `print_names()`: the name of every regex, sorted, with its alternative names.
fn print_names(streams: &mut Streams<'_>, colors: Colors) -> io::Result<()> {
    let mut regexes: Vec<_> = crate::regexes().iter().collect();
    regexes.sort_by_cached_key(|regex| regex.name.to_lowercase());
    let mut text = Text::new();
    for (index, regex) in regexes.iter().enumerate() {
        if index > 0 {
            text.plain("\n");
        }
        text.styled(&regex.name, LABEL);
        if !regex.alternative_names.is_empty() {
            text.plain(": ").plain(&regex.alternative_names.join(", "));
        }
    }
    let mut printer = Printer {
        out: streams.stdout,
        colors,
    };
    printer.print(&text)
}

/// `print_version()`.
fn print_version(streams: &mut Streams<'_>, colors: Colors) -> io::Result<()> {
    let mut text = Text::new();
    text.plain("PyWhat version ")
        .styled(env!("CARGO_PKG_VERSION"), VERSION);
    let mut printer = Printer {
        out: streams.stdout,
        colors,
    };
    printer.print(&text)
}

/// `create_filter()`: the filter of `--rarity`, `--include` and `--exclude` (or of their
/// boundaryless versions), or the message that Python prints before it exits with 1.
fn create_filter(
    rarity: Option<&str>,
    include: Option<&str>,
    exclude: Option<&str>,
) -> Result<Filter, &'static str> {
    let (mut min_rarity, mut max_rarity) = (0.1, 1.0);
    if let Some(rarity) = rarity {
        let rarities: Vec<&str> = rarity.split(':').collect();
        if rarities.len() != 2 {
            return Err("Invalid rarity range format ('min:max' expected)");
        }
        for (rarity, value) in rarities.iter().zip([&mut min_rarity, &mut max_rarity]) {
            if !python::is_all_space(rarity) && !rarity.is_empty() {
                *value = python::float(rarity).ok_or("Invalid rarity argument (float expected)")?;
            }
        }
    }
    let tags = |list: &str| -> Vec<String> {
        split_tags(list)
            .iter()
            .map(|tag| python::strip(tag).to_string())
            .collect()
    };
    let include = include.map(tags);
    let exclude = exclude.map(tags).unwrap_or_default();
    Filter::new(include.as_deref(), &exclude, min_rarity, max_rarity).map_err(|_| {
        "Passed tags are not valid.\n\
         You can check available tags by using: 'pywhat --tags'\n\
         and the names of the regexes, which work like tags, by using: 'pywhat --names'"
    })
}

/// `parse_top()`, with Python's whitespace: `str.strip()` and the `\s` of `N %` take
/// U+001C to U+001F too.
fn parse_top(text: &str) -> Result<Top, String> {
    let text = python::strip(text);
    match Top::parse(text) {
        Ok(top) => Ok(top),
        Err(error) => {
            if let Some(number) = text.strip_suffix('%') {
                let number = python::rstrip(number);
                if let Ok(top) = Top::parse(&format!("{number}%")) {
                    return Ok(top);
                }
            }
            Err(error)
        }
    }
}

/// `read_stdin()`: stdin read like a file (UTF-8, or UTF-16 or UTF-32 with a BOM, and the
/// UTF-16 strings in it), as one text.
fn read_stdin(stdin: &mut dyn Read) -> io::Result<String> {
    let mut data = Vec::new();
    stdin.read_to_end(&mut data)?;
    Ok(python::strip(&crate::unicode::texts(&data).join("\n")).to_string())
}

/// `Identified._collect()` of one thing found.
fn collect(identified: &mut Identified, found: Found) {
    match found {
        Found::FileSignature {
            location,
            signature,
        } => match identified
            .signatures
            .iter_mut()
            .find(|(existing, _)| *existing == location)
        {
            Some(existing) => existing.1 = signature,
            None => identified.signatures.push((location, signature)),
        },
        Found::Match { location, found } => match identified
            .regexes
            .iter_mut()
            .find(|(existing, _)| *existing == location)
        {
            Some((_, matches)) => matches.push(found),
            None => identified.regexes.push((location, vec![found])),
        },
    }
}

/// `progress_bars()`: bars on the terminal of stdout or, if stdout is a regular file
/// (`what ... > out.txt`), on the terminal of stderr. Not into a pipe, as the program that
/// reads it may be writing to the terminal too.
fn progress_bars(env: &Environment, enabled: bool) -> Option<(progress::Bars, progress::Target)> {
    let (target, stream) = bars_target(env, enabled)?;
    // rich's width (COLUMNS), else the width of the terminal that the bars are on
    let width = match env.var("COLUMNS").and_then(|columns| python::int(&columns)) {
        Some(columns) if columns > 0 => env.rich_width(),
        _ => stream.columns.filter(|&columns| columns > 0).unwrap_or(80),
    };
    let bars = progress::Bars::start(target, width, env.colors(stream));
    Some((bars, target))
}

/// Where the progress bars go, if anywhere, and the stream that is there.
fn bars_target(env: &Environment, enabled: bool) -> Option<(progress::Target, &StreamInfo)> {
    if !enabled {
        return None;
    }
    let (target, stream) = if env.stdout.regular_file {
        (progress::Target::Stderr, &env.stderr)
    } else {
        (progress::Target::Stdout, &env.stdout)
    };
    if !stream.terminal || style::is_dumb(env.var("TERM").as_deref()) {
        return None;
    }
    Some((target, stream))
}

/// The end of a search: the files that couldn't be read, on stderr (exit code 1, which
/// Python exits with when it can't read a file).
fn finish(streams: &mut Streams<'_>, unreadable: &[String]) -> io::Result<i32> {
    if unreadable.is_empty() {
        return Ok(0);
    }
    streams.stdout.flush()?;
    for message in unreadable {
        writeln!(streams.stderr, "{message}")?;
    }
    Ok(1)
}

/// The options of the main part of the command.
struct Command<'a> {
    parsed: &'a args::Parsed,
    inputs: Vec<String>,
    map: &'static str,
}

impl Command<'_> {
    fn flag(&self, param: Param) -> bool {
        self.parsed.flag(param)
    }

    fn value(&self, param: Param) -> Option<&str> {
        self.parsed.value(param)
    }
}

fn execute(
    prog: &str,
    args: &[String],
    env: &Environment,
    streams: &mut Streams<'_>,
    verifier: &GoogleVerifier,
) -> io::Result<i32> {
    let parsed = match args::parse(args) {
        Ok(parsed) => parsed,
        Err(args::UsageError(message)) => return parse_error(&message, streams),
    };
    // --help is eager: it comes first
    if parsed.flag(Param::Help) {
        let width = help::help_width(env.click_columns());
        streams
            .stdout
            .write_all(help::help(prog, width).as_bytes())?;
        return Ok(0);
    }
    // The callbacks of the options, in the order in which they were given
    let colors = env.colors(&env.stdout);
    let mut map = "google";
    for &param in parsed.invoked() {
        match param {
            Param::Tags => {
                print_tags(streams, colors)?;
                return Ok(0);
            }
            Param::Names => {
                print_names(streams, colors)?;
                return Ok(0);
            }
            Param::Version => {
                print_version(streams, colors)?;
                return Ok(0);
            }
            Param::Map => match args::map_choice(parsed.value(Param::Map).unwrap_or("")) {
                Ok(choice) => map = choice,
                Err(args::UsageError(message)) => return usage_error(prog, &message, env, streams),
            },
            _ => {}
        }
    }
    // get_text(): stdin is the input if there is none, or only empty ones (`not
    // any(value)`), unless it is a terminal
    let mut inputs = parsed.inputs.clone();
    if inputs.iter().all(String::is_empty)
        && !parsed.flag(Param::Interactive)
        && !env.stdin.terminal
    {
        inputs = vec![read_stdin(streams.stdin)?];
    }
    let command = Command {
        parsed: &parsed,
        inputs,
        map,
    };
    main_command(&command, env, streams, verifier, colors)
}

/// `main()` of `what.py`, after the options have been parsed.
fn main_command(
    command: &Command<'_>,
    env: &Environment,
    streams: &mut Streams<'_>,
    verifier: &GoogleVerifier,
    colors: Colors,
) -> io::Result<i32> {
    let interactive = command.flag(Param::Interactive);
    if command.inputs.is_empty() && !interactive {
        return exit_with(streams, "Text input expected. Run 'pywhat --help' for help");
    }
    let dist = match create_filter(
        Some(command.value(Param::Rarity).unwrap_or("0.1:1")),
        command.value(Param::Include),
        command.value(Param::Exclude),
    ) {
        Ok(filter) => filter,
        Err(message) => {
            print_line(streams, message)?;
            return Ok(1);
        }
    };
    let boundaryless = if command.flag(Param::DisableBoundaryless) {
        Filter::none()
    } else {
        match create_filter(
            Some(command.value(Param::BoundarylessRarity).unwrap_or("0.1:1")),
            command.value(Param::BoundarylessInclude),
            command.value(Param::BoundarylessExclude),
        ) {
            Ok(filter) => filter,
            Err(message) => {
                print_line(streams, message)?;
                return Ok(1);
            }
        }
    };
    // The default processors (unless -dp), and the ones that options ask for
    let mut processors: Vec<Box<dyn Processor>> = if command.flag(Param::DisableProcessing) {
        Vec::new()
    } else {
        default_processors()
    };
    if command.flag(Param::Verify) {
        processors.push(Box::new(verifier.verifier()));
    }
    if command.map == "osm" {
        processors.push(Box::new(OpenStreetMap));
    }
    let key = match command.value(Param::Key) {
        None => Key::None,
        Some(key) => match key.parse::<Key>() {
            Ok(key) => key,
            Err(()) => {
                print_line(streams, "Invalid key")?;
                return Ok(1);
            }
        },
    };
    let top = match command.value(Param::Top) {
        None => None,
        Some(top) => match parse_top(top) {
            Ok(top) => Some(top),
            Err(message) => {
                print_line(streams, &message)?;
                return Ok(1);
            }
        },
    };
    // str(kwargs["format"]).strip()
    let format = command.value(Param::Format);
    let format_name = python::strip(format.unwrap_or("None"));
    let json_output = command.flag(Param::Json) || format_name == "json";
    let stream = command.flag(Param::Stream);
    if stream {
        if key != Key::None {
            return exit_with(
                streams,
                "--stream cannot sort the matches, so it cannot be used with --key",
            );
        }
        if !json_output && format_name == "pretty" {
            return exit_with(
                streams,
                "--stream cannot print a table, so it cannot be used with --format pretty",
            );
        }
        if top.is_some() {
            return exit_with(
                streams,
                "--stream cannot pick the most likely matches, so it cannot be used with --top",
            );
        }
        if interactive {
            return exit_with(streams, "--stream cannot be used with --interactive");
        }
    }
    if interactive {
        streams.stdout.flush()?;
        writeln!(
            streams.stderr,
            "Error: --interactive is only in the Python package of pyWhat: pip install pywhat"
        )?;
        return Ok(2);
    }

    let search = SearchRun {
        identifier: Identifier::new(dist, boundaryless, processors),
        inputs: &command.inputs,
        options: InputOptions {
            only_text: command.flag(Param::OnlyText),
            include_filenames: command.flag(Param::IncludeFilenames),
        },
        print_tags: command.flag(Param::PrintTags),
        bars: progress_bars(env, !command.flag(Param::NoProgress)),
        colors,
    };
    if stream {
        // The matches are printed as soon as they are found (issue #189)
        let format = if json_output { None } else { format };
        return stream_search(search, json_output, format, streams);
    }
    let output = OutputOptions {
        json: json_output,
        pretty: format_name == "pretty",
        format,
        key,
        reverse: command.flag(Param::Reverse),
        top,
        width: env.rich_width(),
    };
    complete_search(search, &output, streams)
}

/// A search of the inputs, with its progress bars.
struct SearchRun<'a> {
    identifier: Identifier,
    inputs: &'a [String],
    options: InputOptions,
    print_tags: bool,
    bars: Option<(progress::Bars, progress::Target)>,
    colors: Colors,
}

impl SearchRun<'_> {
    /// Searches the inputs, calling `found` for everything found (it returns `false` to
    /// stop), and returns the messages for the files that couldn't be read.
    fn run(&self, found: &mut dyn FnMut(Found) -> bool) -> Vec<String> {
        let mut unreadable = Vec::new();
        self.identifier.iter_identify_with_progress(
            self.inputs,
            self.options,
            found,
            &mut |location, error| unreadable.push(format!("Could not read {location}: {error}")),
            &|progress| {
                if let Some((bars, _)) = &self.bars {
                    bars.update(progress);
                }
            },
        );
        unreadable
    }

    /// Removes the progress bars.
    fn finish_bars(&mut self) {
        if let Some((bars, _)) = self.bars.take() {
            bars.finish();
        }
    }
}

/// `print_stream()`: prints everything as soon as it is found.
struct StreamPrinter<'a, 'b> {
    printer: Printer<'a>,
    inputs: &'b [String],
    json: bool,
    format: Option<&'b str>,
    print_tags: bool,
    show_files: bool,
    /// Whether what was printed last was a file signature, and its location
    previous: Option<(bool, String)>,
    found_matches: bool,
}

impl StreamPrinter<'_, '_> {
    fn print(&mut self, found: Found) -> io::Result<()> {
        if self.json {
            self.printer.stream_json(&found)?;
        } else {
            match found {
                Found::FileSignature {
                    location,
                    signature,
                } => self.signature(location, signature)?,
                Found::Match { location, found } => self.found(location, found)?,
            }
        }
        self.printer.out.flush()
    }

    /// A file signature, printed like raw output prints it (not with a format).
    fn signature(
        &mut self,
        location: String,
        signature: &serde_json::Map<String, serde_json::Value>,
    ) -> io::Result<()> {
        if self.format.is_none() {
            let mut text = output::raw_signature(&location, signature);
            text.rstrip();
            self.printer.print(&text)?;
            self.previous = Some((true, location));
        }
        Ok(())
    }

    /// A match, printed like raw output or the format prints it.
    fn found(&mut self, location: String, found: crate::Match) -> io::Result<()> {
        self.found_matches = true;
        let one = Identified {
            signatures: Vec::new(),
            regexes: vec![(location.clone(), vec![found])],
        };
        match self.format {
            Some(format) => self.printer.format_print(&one, format)?,
            None => {
                // An empty line between the matches, but not between a file signature and
                // the matches in its file
                let after_its_signature = self.previous.as_ref() == Some(&(true, location.clone()));
                if self.previous.is_some() && !after_its_signature {
                    self.printer.print_plain("")?;
                }
                self.printer.print_raw(
                    &one,
                    self.inputs,
                    self.print_tags,
                    Some(self.show_files),
                )?;
            }
        }
        self.previous = Some((false, location));
        Ok(())
    }
}

/// `--stream`: everything printed as soon as it is found, the progress bars hidden while
/// it is printed on their terminal.
fn stream_search(
    mut search: SearchRun<'_>,
    json: bool,
    format: Option<&str>,
    streams: &mut Streams<'_>,
) -> io::Result<i32> {
    let bars_on_stdout = matches!(&search.bars, Some((_, progress::Target::Stdout)));
    let mut printer = StreamPrinter {
        printer: Printer {
            out: &mut *streams.stdout,
            colors: search.colors,
        },
        inputs: search.inputs,
        json,
        format,
        print_tags: search.print_tags,
        show_files: output::show_files_of_inputs(search.inputs),
        previous: None,
        found_matches: false,
    };
    let mut failure: Option<io::Error> = None;
    let unreadable = search.run(&mut |found| {
        let printed = match &search.bars {
            Some((bars, _)) if bars_on_stdout => bars.suspend(|| printer.print(found)),
            _ => printer.print(found),
        };
        printed.map_err(|error| failure = Some(error)).is_ok()
    });
    let found_matches = printer.found_matches;
    search.finish_bars();
    if let Some(error) = failure {
        return Err(error);
    }
    if !json && !found_matches && format.is_none() {
        Printer {
            out: streams.stdout,
            colors: search.colors,
        }
        .print_plain("Nothing found!")?;
    }
    finish(streams, &unreadable)
}

/// How the matches of a complete search are printed.
struct OutputOptions<'a> {
    json: bool,
    pretty: bool,
    format: Option<&'a str>,
    key: Key,
    reverse: bool,
    top: Option<Top>,
    /// The width of the terminal, for the table
    width: usize,
}

/// The number of matches found.
fn count(identified: &Identified) -> usize {
    identified
        .regexes
        .iter()
        .map(|(_, matches)| matches.len())
        .sum()
}

/// A search, printed once it is complete: sorted, the most likely matches with `--top`
/// (and a note on stderr about the others), in the output format.
fn complete_search(
    mut search: SearchRun<'_>,
    output: &OutputOptions<'_>,
    streams: &mut Streams<'_>,
) -> io::Result<i32> {
    let mut identified = Identified::default();
    let unreadable = search.run(&mut |found| {
        collect(&mut identified, found);
        true
    });
    search.finish_bars();
    // top_matches() sorts the top ones itself
    let key = if output.top.is_none() {
        output.key
    } else {
        Key::None
    };
    identified.sort(key, output.reverse);
    let total = count(&identified);
    if let Some(top) = &output.top {
        identified = identified.top(top, output.key, output.reverse);
    }
    let mut printer = Printer {
        out: streams.stdout,
        colors: search.colors,
    };
    if output.json {
        printer.print_json(&identified)?;
    } else if output.pretty {
        printer.pretty_print(&identified, search.inputs, search.print_tags, output.width)?;
    } else if let Some(format) = output.format {
        printer.format_print(&identified, format)?;
    } else {
        printer.print_raw(&identified, search.inputs, search.print_tags, None)?;
    }
    let shown = count(&identified);
    if shown < total {
        // On stderr, so that the output (e.g. JSON) is the same as without --top
        streams.stdout.flush()?;
        writeln!(
            streams.stderr,
            "\nShowing the {shown} most likely of {total} matches. Use --top to show more \
             of them, or --interactive to search through all of them."
        )?;
    }
    finish(streams, &unreadable)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn terminal(columns: usize) -> StreamInfo {
        StreamInfo {
            terminal: true,
            regular_file: false,
            columns: Some(columns),
        }
    }

    fn file() -> StreamInfo {
        StreamInfo {
            terminal: false,
            regular_file: true,
            columns: None,
        }
    }

    fn pipe() -> StreamInfo {
        StreamInfo::default()
    }

    fn env(stdout: StreamInfo, stderr: StreamInfo) -> Environment {
        Environment {
            vars: HashMap::new(),
            stdin: pipe(),
            stdout,
            stderr,
        }
    }

    #[test]
    fn where_the_bars_go() {
        use progress::Target;
        let target = |env: &Environment| bars_target(env, true).map(|(target, _)| target);
        // On the terminal of the output
        assert_eq!(
            target(&env(terminal(80), terminal(80))),
            Some(Target::Stdout)
        );
        // On stderr if the output is redirected to a file
        assert_eq!(target(&env(file(), terminal(80))), Some(Target::Stderr));
        assert_eq!(target(&env(file(), file())), None);
        // Never into a pipe, even if stderr is a terminal (what --json ... | jq)
        assert_eq!(target(&env(pipe(), terminal(80))), None);
        // --no-progress, and dumb terminals
        assert_eq!(
            bars_target(&env(terminal(80), terminal(80)), false).map(|t| t.0),
            None
        );
        let mut dumb = env(terminal(80), terminal(80));
        dumb.vars.insert("TERM", "dumb".into());
        assert_eq!(target(&dumb), None);
    }

    #[test]
    fn widths_like_click_and_rich() {
        let mut env = env(terminal(120), pipe());
        assert_eq!(env.click_columns(), 120);
        assert_eq!(env.rich_width(), 120);
        env.vars.insert("COLUMNS", "abc".into());
        assert_eq!((env.click_columns(), env.rich_width()), (120, 120));
        env.vars.insert("COLUMNS", "0".into());
        assert_eq!((env.click_columns(), env.rich_width()), (120, 80));
        env.vars.insert("COLUMNS", " 40".into());
        assert_eq!((env.click_columns(), env.rich_width()), (40, 120));
        env.vars.insert("COLUMNS", "200".into());
        assert_eq!((env.click_columns(), env.rich_width()), (200, 200));
        // A dumb terminal is 80 columns wide for rich, unless COLUMNS and LINES are set
        env.vars.insert("TERM", "dumb".into());
        assert_eq!(env.rich_width(), 80);
        env.vars.insert("LINES", "50".into());
        assert_eq!(env.rich_width(), 200);
        assert_eq!(program_name("/usr/local/bin/what"), "what");
    }

    /// Runs the command with `stdin` and returns (exit code, stdout, stderr).
    fn run_with(args: &[&str], stdin: &[u8], verifier: &GoogleVerifier) -> (i32, String, String) {
        let args: Vec<String> = args.iter().map(|arg| arg.to_string()).collect();
        let env = env(pipe(), pipe());
        let (mut stdin, mut stdout, mut stderr) = (stdin, Vec::new(), Vec::new());
        let mut streams = Streams {
            stdin: &mut stdin,
            stdout: &mut stdout,
            stderr: &mut stderr,
        };
        let code = run("what", &args, &env, &mut streams, verifier);
        (
            code,
            String::from_utf8(stdout).unwrap(),
            String::from_utf8(stderr).unwrap(),
        )
    }

    fn what(args: &[&str]) -> (i32, String, String) {
        run_with(args, b"", &GoogleVerifier::default())
    }

    #[test]
    fn exit_codes_and_messages() {
        assert_eq!(what(&["-db", "THM{x}"]).0, 0);
        assert_eq!(
            what(&["--rarity", "a:", "x"]),
            (
                1,
                "Invalid rarity argument (float expected)\n".into(),
                String::new()
            )
        );
        assert_eq!(what(&["--key", "x", "y"]).1, "Invalid key\n");
        let (code, _, stderr) = what(&["--stream", "--key", "name", "x"]);
        assert_eq!(code, 1);
        assert_eq!(
            stderr,
            "--stream cannot sort the matches, so it cannot be used with --key\n"
        );
        let (code, stdout, stderr) = what(&["--interactive", "x"]);
        assert_eq!((code, stdout.as_str()), (2, ""));
        assert!(stderr.contains("pip install pywhat"), "{stderr}");
        let (code, _, stderr) = what(&["--map", "bing", "x"]);
        assert_eq!(code, 2);
        assert!(stderr.ends_with(
            "Error: Invalid value for '--map': 'bing' is not one of 'google', 'osm'.\n"
        ));
    }

    #[test]
    fn stdin_is_the_input_without_inputs() {
        let (code, stdout, _) = run_with(&["-db"], b"THM{hello}\n", &GoogleVerifier::default());
        assert_eq!(code, 0);
        assert!(stdout.starts_with("Matched on: THM{hello}\n"), "{stdout}");
        let (_, stdout, _) = run_with(&["-db"], b"", &GoogleVerifier::default());
        assert_eq!(stdout, "Nothing found!\n");
    }

    #[test]
    fn verify_with_a_fake_google() {
        use std::sync::atomic::{AtomicUsize, Ordering};
        use std::sync::Arc;
        let requests = Arc::new(AtomicUsize::new(0));
        let counter = requests.clone();
        let verifier = GoogleVerifier {
            make: Some(Box::new(move || {
                let counter = counter.clone();
                verify::GoogleApiKeyVerifier::with_http(Box::new(move |_| {
                    counter.fetch_add(1, Ordering::SeqCst);
                    Ok((
                        400,
                        br#"{"error": {"details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}]}}"#.to_vec(),
                    ))
                }))
            })),
        };
        let key = format!("AIzaSy{}", "A00000000000000000000000000000000");
        let text = format!("{key} {key}");
        let (code, stdout, _) =
            run_with(&["--verify", "--format", "%n: %d", &text], b"", &verifier);
        assert_eq!(code, 0);
        assert_eq!(
            stdout
                .lines()
                .filter(|line| line.starts_with("Google API Key"))
                .count(),
            2,
            "{stdout}"
        );
        assert!(stdout.contains("Verification: invalid, Google rejected the key (API_KEY_INVALID)"));
        // Once per key, however many times it is found
        assert_eq!(requests.load(Ordering::SeqCst), 1);
        // Without --verify, nothing is sent
        let (_, stdout, _) = run_with(&["--format", "%d", &key], b"", &verifier);
        assert!(!stdout.contains("Verification"));
        assert_eq!(requests.load(Ordering::SeqCst), 1);
    }
}
