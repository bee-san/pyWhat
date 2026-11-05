//! The command line, parsed the way click 8.1 parses `pywhat/what.py`'s options: long
//! options with `=` or the next argument as their value, multi-letter "short" options
//! such as `-br` (click treats them as long options), clusters of one-letter options
//! (`-ok name`), `--` before inputs that start with `-`, and unknown options taken as
//! inputs (`ignore_unknown_options`: `what -1606586780` searches the text
//! `-1606586780`).

use super::python::repr;
use std::collections::HashMap;

/// An option of `what.py`, in the order in which they are declared there.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub(crate) enum Param {
    Tags,
    Names,
    Rarity,
    Include,
    Exclude,
    OnlyText,
    Key,
    Reverse,
    Top,
    BoundarylessRarity,
    BoundarylessInclude,
    BoundarylessExclude,
    DisableBoundaryless,
    DisableProcessing,
    Verify,
    Map,
    Json,
    Interactive,
    Version,
    IncludeFilenames,
    Format,
    PrintTags,
    Stream,
    NoProgress,
    Help,
}

/// How an option is written and explained in `--help`.
pub(crate) struct OptionSpec {
    pub(crate) param: Param,
    /// The option strings, e.g. `-t` and `--tags`.
    pub(crate) opts: &'static [&'static str],
    pub(crate) takes_value: bool,
    /// What `--help` shows after the option strings of an option that takes a value.
    pub(crate) metavar: &'static str,
    pub(crate) help: &'static str,
}

const fn flag(param: Param, opts: &'static [&'static str], help: &'static str) -> OptionSpec {
    OptionSpec {
        param,
        opts,
        takes_value: false,
        metavar: "",
        help,
    }
}

const fn value(
    param: Param,
    opts: &'static [&'static str],
    metavar: &'static str,
    help: &'static str,
) -> OptionSpec {
    OptionSpec {
        param,
        opts,
        takes_value: true,
        metavar,
        help,
    }
}

/// The options, in the order of `what.py` (and of `--help`), with click's `--help` last.
pub(crate) const OPTIONS: &[OptionSpec] = &[
    flag(
        Param::Tags,
        &["-t", "--tags"],
        "Show available tags and exit.",
    ),
    flag(
        Param::Names,
        &["--names"],
        "Show the names of the regexes, with their alternative names, and exit.",
    ),
    value(
        Param::Rarity,
        &["-r", "--rarity"],
        "TEXT",
        "Filter by rarity. Rarity is how unlikely something is to be a false-positive. The \
         higher the number, the more unlikely. This is in the range of 0:1. To filter only \
         items past 0.5, use 0.5: with the colon on the end. Default 0.1:1",
    ),
    value(
        Param::Include,
        &["-i", "--include"],
        "TEXT",
        "Only show matches with these tags or names.",
    ),
    value(
        Param::Exclude,
        &["-e", "--exclude"],
        "TEXT",
        "Exclude matches with these tags or names.",
    ),
    flag(
        Param::OnlyText,
        &["-o", "--only-text"],
        "Do not scan files or folders.",
    ),
    value(
        Param::Key,
        &["-k", "--key"],
        "TEXT",
        "Sort by the specified key.",
    ),
    flag(Param::Reverse, &["--reverse"], "Sort in reverse order."),
    value(
        Param::Top,
        &["--top"],
        "N",
        "Only show the N most likely matches, or N% of them, e.g. --top 10 or --top 5%.",
    ),
    value(
        Param::BoundarylessRarity,
        &["-br", "--boundaryless-rarity"],
        "TEXT",
        "Same as --rarity but for boundaryless mode (toggles what regexes will not have \
         boundaries).",
    ),
    value(
        Param::BoundarylessInclude,
        &["-bi", "--boundaryless-include"],
        "TEXT",
        "Same as --include but for boundaryless mode.",
    ),
    value(
        Param::BoundarylessExclude,
        &["-be", "--boundaryless-exclude"],
        "TEXT",
        "Same as --exclude but for boundaryless mode.",
    ),
    flag(
        Param::DisableBoundaryless,
        &["-db", "--disable-boundaryless"],
        "Disable boundaryless mode.",
    ),
    flag(
        Param::DisableProcessing,
        &["-dp", "--disable-processing"],
        "Disable the processing of matches, e.g. adding dates to Unix timestamps or \
         checking the checksums of Bitcoin addresses.",
    ),
    flag(
        Param::Verify,
        &["--verify"],
        "Ask the services if the keys found are valid, e.g. Google API keys. This sends \
         the keys to the services.",
    ),
    value(
        Param::Map,
        &["--map"],
        "[google|osm]",
        "The map that coordinates link to: Google Maps or OpenStreetMap (osm).  [default: \
         google]",
    ),
    flag(Param::Json, &["--json"], "Return results in json format."),
    flag(
        Param::Interactive,
        &["--interactive"],
        "Load the input into memory and search through the matches interactively.",
    ),
    flag(
        Param::Version,
        &["-v", "--version"],
        "Display the version of pywhat.",
    ),
    flag(
        Param::IncludeFilenames,
        &["-if", "--include-filenames"],
        "Search filenames for possible matches.",
    ),
    value(
        Param::Format,
        &["--format"],
        "TEXT",
        "Format output according to specified rules.",
    ),
    flag(
        Param::PrintTags,
        &["-pt", "--print-tags"],
        "Add flags to output",
    ),
    flag(
        Param::Stream,
        &["--stream"],
        "Print every match as soon as it is found, not once the search is complete.",
    ),
    flag(
        Param::NoProgress,
        &["--no-progress"],
        "Do not show progress bars while searching.",
    ),
    flag(Param::Help, &["--help"], "Show this message and exit."),
];

/// The choices of `--map` (`click.Choice(["google", "osm"], case_sensitive=False)`).
pub(crate) const MAP_CHOICES: &[&str] = &["google", "osm"];

/// An error of the parser: click prints `Error: <message>` and exits with 2.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct UsageError(pub(crate) String);

/// What the command line holds.
#[derive(Debug, Default, Clone)]
pub(crate) struct Parsed {
    /// The value of every option that was given (the last one if it was given several
    /// times); flags have an empty value.
    values: HashMap<Param, String>,
    /// The options in the order they were first given, for the order of the callbacks.
    order: Vec<Param>,
    /// The inputs: files, directories or text.
    pub(crate) inputs: Vec<String>,
}

impl Parsed {
    pub(crate) fn flag(&self, param: Param) -> bool {
        self.values.contains_key(&param)
    }

    pub(crate) fn value(&self, param: Param) -> Option<&str> {
        self.values.get(&param).map(String::as_str)
    }

    /// The options that were given, in the order of their first appearance.
    pub(crate) fn invoked(&self) -> &[Param] {
        &self.order
    }

    fn set(&mut self, param: Param, value: String) {
        self.values.insert(param, value);
        if !self.order.contains(&param) {
            self.order.push(param);
        }
    }
}

fn spec(opt: &str) -> Option<&'static OptionSpec> {
    OPTIONS.iter().find(|spec| spec.opts.contains(&opt))
}

/// click's split: an option string with one letter after one `-` is a short option, any
/// other is a long one (`-br`, `--rarity`).
fn is_short(opt: &str) -> bool {
    let mut chars = opt.chars();
    chars.next() == Some('-') && chars.next().is_some_and(|c| c != '-') && chars.next().is_none()
}

fn long_option(opt: &str) -> Option<&'static OptionSpec> {
    spec(opt).filter(|_| !is_short(opt))
}

fn short_option(opt: &str) -> Option<&'static OptionSpec> {
    spec(opt).filter(|_| is_short(opt))
}

/// Parses the arguments after the program name, like click's `OptionParser.parse_args`.
pub(crate) fn parse(args: &[String]) -> Result<Parsed, UsageError> {
    let mut parsed = Parsed::default();
    // rargs: the arguments still to read, largs: the inputs found so far
    let mut rargs: std::collections::VecDeque<String> = args.iter().cloned().collect();
    let mut largs: Vec<String> = Vec::new();
    while let Some(arg) = rargs.pop_front() {
        if arg == "--" {
            break;
        }
        if arg.starts_with('-') && arg.chars().count() > 1 {
            process_opts(&arg, &mut rargs, &mut largs, &mut parsed)?;
        } else {
            largs.push(arg);
        }
    }
    largs.extend(rargs);
    parsed.inputs = largs;
    Ok(parsed)
}

/// The value of an option that takes one: the next argument, whatever it is.
fn take_value(
    opt: &str,
    rargs: &mut std::collections::VecDeque<String>,
) -> Result<String, UsageError> {
    rargs
        .pop_front()
        .ok_or_else(|| UsageError(format!("Option {} requires an argument.", repr(opt))))
}

/// `_process_opts()`: a long option (possibly with `=value`), else a cluster of short
/// options, else (it starts with `--`) an input.
fn process_opts(
    arg: &str,
    rargs: &mut std::collections::VecDeque<String>,
    largs: &mut Vec<String>,
    parsed: &mut Parsed,
) -> Result<(), UsageError> {
    let (long_opt, explicit_value) = match arg.split_once('=') {
        Some((opt, value)) => (opt, Some(value)),
        None => (arg, None),
    };
    if let Some(spec) = long_option(long_opt) {
        let value = if spec.takes_value {
            if let Some(value) = explicit_value {
                rargs.push_front(value.to_string());
            }
            take_value(long_opt, rargs)?
        } else if explicit_value.is_some() {
            return Err(UsageError(format!(
                "Option {} does not take a value.",
                repr(long_opt)
            )));
        } else {
            String::new()
        };
        parsed.set(spec.param, value);
        return Ok(());
    }
    if arg.starts_with("--") {
        // An unknown long option is an input
        largs.push(arg.to_string());
        return Ok(());
    }
    match_short_opt(arg, rargs, largs, parsed)
}

/// `_match_short_opt()`: every letter is a short option, and the rest of the argument is
/// the value of the first one that takes a value. Unknown letters are put together into
/// an input, with the `-`.
fn match_short_opt(
    arg: &str,
    rargs: &mut std::collections::VecDeque<String>,
    largs: &mut Vec<String>,
    parsed: &mut Parsed,
) -> Result<(), UsageError> {
    let mut unknown = String::new();
    for (index, letter) in arg.char_indices().skip(1) {
        let opt = format!("-{letter}");
        let Some(spec) = short_option(&opt) else {
            unknown.push(letter);
            continue;
        };
        if spec.takes_value {
            let rest = &arg[index + letter.len_utf8()..];
            if !rest.is_empty() {
                rargs.push_front(rest.to_string());
            }
            let value = take_value(&opt, rargs)?;
            parsed.set(spec.param, value);
            break;
        }
        parsed.set(spec.param, String::new());
    }
    if !unknown.is_empty() {
        largs.push(format!("-{unknown}"));
    }
    Ok(())
}

/// The value of `--map`, like click's `Choice.convert()` without case sensitivity: the
/// choice as it is declared, or the error message.
pub(crate) fn map_choice(value: &str) -> Result<&'static str, UsageError> {
    let folded = super::python::casefold_ascii(value);
    MAP_CHOICES
        .iter()
        .find(|choice| folded.as_deref() == Some(**choice))
        .copied()
        .ok_or_else(|| {
            let choices: Vec<String> = MAP_CHOICES.iter().map(|c| repr(c)).collect();
            UsageError(format!(
                "Invalid value for '--map': {} is not one of {}.",
                repr(value),
                choices.join(", ")
            ))
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_args(args: &[&str]) -> Result<Parsed, UsageError> {
        parse(&args.iter().map(|a| a.to_string()).collect::<Vec<_>>())
    }

    #[test]
    fn long_short_and_clusters() {
        let parsed = parse_args(&["-db", "--rarity", "0:", "-ok", "name", "x"]).unwrap();
        assert!(parsed.flag(Param::DisableBoundaryless));
        assert!(parsed.flag(Param::OnlyText));
        assert_eq!(parsed.value(Param::Rarity), Some("0:"));
        assert_eq!(parsed.value(Param::Key), Some("name"));
        assert_eq!(parsed.inputs, ["x"]);
        assert_eq!(
            parsed.invoked(),
            [
                Param::DisableBoundaryless,
                Param::Rarity,
                Param::OnlyText,
                Param::Key
            ]
        );
    }

    #[test]
    fn attached_values() {
        let parsed = parse_args(&["-kname", "--top=5%", "-br=0.5:", "-r=0.5:"]).unwrap();
        assert_eq!(parsed.value(Param::Key), Some("name"));
        assert_eq!(parsed.value(Param::Top), Some("5%"));
        assert_eq!(parsed.value(Param::BoundarylessRarity), Some("0.5:"));
        // -r is a short option: the rest of the argument is its value, with the "="
        assert_eq!(parsed.value(Param::Rarity), Some("=0.5:"));
    }

    #[test]
    fn unknown_options_are_inputs() {
        let parsed = parse_args(&["-1606586780", "--nope", "-h", "-o=1", "-tx", "-"]).unwrap();
        assert_eq!(
            parsed.inputs,
            ["-1606586780", "--nope", "-h", "-=1", "-x", "-"]
        );
        assert!(parsed.flag(Param::OnlyText));
        assert!(parsed.flag(Param::Tags));
    }

    #[test]
    fn explicit_values() {
        // The value is everything after the first "=", and may be empty
        let parsed = parse_args(&["--format=%m=%n", "--rarity=", "x"]).unwrap();
        assert_eq!(parsed.value(Param::Format), Some("%m=%n"));
        assert_eq!(parsed.value(Param::Rarity), Some(""));
        assert_eq!(parsed.inputs, ["x"]);
        // An unknown long option is an input, with its "=value"
        let parsed = parse_args(&["--nope=1", "--nope=a=b"]).unwrap();
        assert_eq!(parsed.inputs, ["--nope=1", "--nope=a=b"]);
    }

    #[test]
    fn callbacks_in_the_order_of_first_appearance() {
        // click's iter_params_for_processing(): the index of the first appearance
        let parsed = parse_args(&["--tags", "--names", "--tags"]).unwrap();
        assert_eq!(parsed.invoked(), [Param::Tags, Param::Names]);
        let parsed = parse_args(&["--names", "-t", "--names", "-v"]).unwrap();
        assert_eq!(
            parsed.invoked(),
            [Param::Names, Param::Tags, Param::Version]
        );
        // The last value counts
        let parsed = parse_args(&["-k", "name", "-k", "rarity"]).unwrap();
        assert_eq!(parsed.value(Param::Key), Some("rarity"));
    }

    #[test]
    fn double_dash() {
        let parsed = parse_args(&["-db", "--", "-db", "--", "x"]).unwrap();
        assert_eq!(parsed.inputs, ["-db", "--", "x"]);
        // A value can be anything, "--" too
        let parsed = parse_args(&["-r", "--", "x"]).unwrap();
        assert_eq!(parsed.value(Param::Rarity), Some("--"));
        assert_eq!(parsed.inputs, ["x"]);
    }

    #[test]
    fn errors() {
        assert_eq!(
            parse_args(&["--rarity"]).unwrap_err().0,
            "Option '--rarity' requires an argument."
        );
        assert_eq!(
            parse_args(&["-k"]).unwrap_err().0,
            "Option '-k' requires an argument."
        );
        assert_eq!(
            parse_args(&["--json=1"]).unwrap_err().0,
            "Option '--json' does not take a value."
        );
        assert_eq!(
            parse_args(&["-pt="]).unwrap_err().0,
            "Option '-pt' does not take a value."
        );
    }

    #[test]
    fn map_choices() {
        assert_eq!(map_choice("OSM"), Ok("osm"));
        assert_eq!(map_choice("oſm"), Ok("osm"));
        assert_eq!(
            map_choice("bing").unwrap_err().0,
            "Invalid value for '--map': 'bing' is not one of 'google', 'osm'."
        );
    }
}
