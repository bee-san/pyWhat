//! The output formats, ports of `pywhat/printer.py`: raw output, the `--format pretty`
//! table, custom `--format` strings, `--json`, and `--stream`.

use super::python;
use super::style::{sanitized, Colors, Text, BOLD};
use crate::files::{Found, Identified};
use crate::identify::Match;
use crate::json::dumps;
use serde_json::{Map, Value};
use std::io::{self, Write};
use std::path::Path;

/// `str(value)` of a value of a file signature.
fn py_str(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(text)) => text.clone(),
        Some(Value::Null) | None => "None".to_string(),
        Some(Value::Bool(true)) => "True".to_string(),
        Some(Value::Bool(false)) => "False".to_string(),
        Some(other) => dumps(other),
    }
}

/// `str(match["Regex Pattern"]["Rarity"])`: as the regex has it (`1` or `0.5`), or the
/// float a processor gave it.
fn rarity_text(found: &Match) -> String {
    match found.regex.to_json_value().get("Rarity") {
        Some(rarity) if found.rarity == found.regex.rarity => dumps(rarity),
        _ => dumps(&Value::from(found.rarity)),
    }
}

/// Whether the regex of a match has an `"Exploit"` key, even a null one, which makes
/// `--format pretty` show the Exploit column (`_check_if_exploit_in_json`).
fn has_exploit_key(found: &Match) -> bool {
    found.regex.to_json_value().contains_key("Exploit")
}

fn non_empty(text: &Option<String>) -> Option<&str> {
    text.as_deref().filter(|text| !text.is_empty())
}

/// `_show_files()`: whether to show the file of every match: the input is a directory, or
/// there are several inputs and some of the matches are in files.
pub(crate) fn show_files(identified: &Identified, inputs: &[String]) -> bool {
    if inputs.len() == 1 {
        return Path::new(&inputs[0]).is_dir();
    }
    identified
        .regexes
        .iter()
        .any(|(location, _)| location != "text")
}

/// `_show_files_of_inputs()`: like [`show_files`] before anything is found, for
/// `--stream`: the input is a directory, or one of several inputs exists.
pub(crate) fn show_files_of_inputs(inputs: &[String]) -> bool {
    if inputs.len() == 1 {
        return Path::new(&inputs[0]).is_dir();
    }
    inputs.iter().any(|input| Path::new(input).exists())
}

/// `_raw_signature()`: a file signature as raw output shows it.
pub(crate) fn raw_signature(location: &str, signature: &Map<String, Value>) -> Text {
    let mut text = Text::new();
    text.plain("\n")
        .label("File Identified")
        .plain(": ")
        .styled(location, BOLD)
        .plain(" with Magic Numbers ")
        .markup(&py_str(signature.get("ISO 8859-1")))
        .plain(".\n")
        .label("File Description:")
        .plain(" ")
        .markup(&py_str(signature.get("Description")))
        .plain(".\n");
    text
}

/// A match as raw output shows it: "Matched on:", "Name:", "Link:", "Description:",
/// "Exploit:" and "Tags:" lines, then an empty line.
fn raw_match(found: &Match, print_tags: bool) -> Text {
    let mut output = Text::new();
    output.label("Matched on: ").plain(&found.matched);
    output.plain("\n").label("Name: ").markup(&found.regex.name);
    if let Some(link) = found.link() {
        output.plain("\n").label("Link: ").plain(" ").plain(&link);
    }
    if let Some(description) = non_empty(&found.description) {
        output
            .plain("\n")
            .label("Description: ")
            .markup(description);
    }
    if let Some(exploit) = non_empty(&found.exploit) {
        output.plain("\n").label("Exploit: ").plain(exploit);
    }
    if print_tags {
        output
            .plain("\n")
            .label("Tags: ")
            .markup(&found.tags.join(", "));
    }
    output.plain("\n\n");
    output
}

/// The Description cell of the table: the link, the description and the tags, each on
/// a line, or "None".
fn description_cell(found: &Match, print_tags: bool) -> String {
    let mut lines: Vec<Text> = Vec::new();
    if let Some(link) = found.link() {
        let mut text = Text::new();
        text.plain("Click here to analyse in the browser\n")
            .plain(&link);
        lines.push(text);
    }
    if let Some(description) = non_empty(&found.description) {
        let mut text = Text::new();
        text.markup(description);
        lines.push(text);
    }
    if print_tags {
        let mut text = Text::new();
        text.plain("Tags: ").markup(&found.tags.join(", "));
        lines.push(text);
    }
    if lines.is_empty() {
        return "None".to_string();
    }
    let mut cell = Text::new();
    for (index, line) in lines.into_iter().enumerate() {
        if index > 0 {
            cell.plain("\n");
        }
        cell.append(line);
    }
    cell.to_plain()
}

/// Where the output goes, and how its styles are written.
pub(crate) struct Printer<'a> {
    pub(crate) out: &'a mut dyn Write,
    pub(crate) colors: Colors,
}

impl Printer<'_> {
    /// `console.print(text)`: the text and a line break.
    pub(crate) fn print(&mut self, text: &Text) -> io::Result<()> {
        let mut rendered = text.render(self.colors);
        rendered.push('\n');
        self.out.write_all(rendered.as_bytes())
    }

    /// `console.print(text, markup=False)` of plain text.
    pub(crate) fn print_plain(&mut self, text: &str) -> io::Result<()> {
        let mut plain = Text::new();
        plain.plain(text);
        self.print(&plain)
    }

    /// `print_raw()`, with `show_files` given or found out.
    pub(crate) fn print_raw(
        &mut self,
        identified: &Identified,
        inputs: &[String],
        print_tags: bool,
        show_files: Option<bool>,
    ) -> io::Result<()> {
        let mut output = Text::new();
        if !identified.signatures.is_empty() && !identified.regexes.is_empty() {
            for (location, signature) in &identified.signatures {
                output.append(raw_signature(location, signature));
            }
        }
        if !identified.regexes.is_empty() {
            let show_files = show_files.unwrap_or_else(|| self::show_files(identified, inputs));
            for (location, matches) in &identified.regexes {
                for found in matches {
                    if show_files {
                        // One span, as in Python's "[bold #D7Afff]File: {key}[/bold #D7Afff]"
                        output.label(&format!("File: {location}")).plain("\n");
                    }
                    output.append(raw_match(found, print_tags));
                }
            }
        }
        let source = output.source();
        if source.is_empty() {
            self.print_plain("Nothing found!")?;
        }
        if !python::strip(&source).is_empty() {
            output.rstrip();
            self.print(&output)?;
        }
        Ok(())
    }

    /// `format_print()`: `format` for every match, with `%m`, `%n`, `%d`, `%e`, `%r`, `%l`
    /// and `%t` replaced, one after another, and `\\` and `\%` for `\` and `%`. The
    /// output is rich markup, like in Python; its `MarkupError` is an `InvalidInput` error.
    pub(crate) fn format_print(&mut self, identified: &Identified, format: &str) -> io::Result<()> {
        if identified.regexes.is_empty() {
            return Ok(());
        }
        // The format split at its "\\", which become "\" (format_list)
        let mut parts: Vec<&str> = Vec::new();
        let mut rest = format;
        while let Some(index) = rest.find("\\\\") {
            if index > 0 {
                parts.push(&rest[..index]);
            }
            parts.push("\\");
            rest = &rest[index + 2..];
        }
        parts.push(rest);
        // The output as Python gives it to rich: markup, which the format can use too. The
        // values that contain the matched text are escaped, so that they are printed as
        // they are (#291, Python bug 4); the names, descriptions and tags are data, whose
        // markup rich renders.
        let mut source = Vec::new();
        for (_, matches) in &identified.regexes {
            for found in matches {
                let values = [
                    ("%m", super::markup::escape(&found.matched)),
                    ("%n", found.regex.name.clone()),
                    ("%d", found.description.clone().unwrap_or_default()),
                    (
                        "%e",
                        super::markup::escape(found.exploit.as_deref().unwrap_or("")),
                    ),
                    ("%r", rarity_text(found)),
                    (
                        "%l",
                        super::markup::escape(&found.link().unwrap_or_default()),
                    ),
                    ("%t", found.tags.join(", ")),
                ];
                source.push(substitute(&parts, &values));
            }
        }
        let source = source.join("\n");
        if !python::strip(&source).is_empty() {
            // rich stops at a closing tag that closes nothing, before printing anything
            if let Some(error) = super::markup::error(&source) {
                return Err(io::Error::new(io::ErrorKind::InvalidInput, error));
            }
            let mut text = Text::new();
            text.markup(&source);
            self.print(&text)?;
        }
        Ok(())
    }

    /// `print_json()`: `json.dumps()` of everything found, on one line.
    pub(crate) fn print_json(&mut self, identified: &Identified) -> io::Result<()> {
        let mut json = identified.to_json();
        json.push('\n');
        self.out.write_all(json.as_bytes())
    }

    /// `print_stream()` with `json_output`: a JSON line for everything found, as soon as it
    /// is found, without the "Fragment" of the matches.
    pub(crate) fn stream_json(&mut self, found: &Found) -> io::Result<()> {
        let mut line = String::new();
        match found {
            Found::FileSignature {
                location,
                signature,
            } => {
                line.push_str("{\"File Signatures\": {");
                line.push_str(&dumps(&Value::String(location.clone())));
                line.push_str(": ");
                line.push_str(&dumps(&Value::Object((*signature).clone())));
                line.push_str("}, \"Regexes\": null}");
            }
            Found::Match { location, found } => {
                line.push_str("{\"File Signatures\": null, \"Regexes\": {");
                line.push_str(&dumps(&Value::String(location.clone())));
                line.push_str(": [");
                found.write_json(&mut line, false);
                line.push_str("]}}");
            }
        }
        self.print_plain(&line)
    }

    /// `--format pretty`: the file signatures, and a table of the matches.
    pub(crate) fn pretty_print(
        &mut self,
        identified: &Identified,
        inputs: &[String],
        print_tags: bool,
        width: usize,
    ) -> io::Result<()> {
        let mut text = Text::new();
        for (location, signature) in &identified.signatures {
            text.plain("\n")
                .label("File Identified")
                .plain(": ")
                .styled(location, BOLD)
                .plain(" with Magic Numbers ")
                .markup(&py_str(signature.get("ISO 8859-1")))
                .plain(".\n")
                .label("File Description: ")
                .plain(" ")
                .markup(&py_str(signature.get("Description")))
                .plain(".\n\n");
        }
        if identified.regexes.is_empty() {
            text.plain("\nNothing found!");
            text.lstrip();
            return self.print(&text);
        }
        text.plain("\n")
            .label("Possible Identification")
            .plain("\n");
        let show_files = show_files(identified, inputs);
        let bug_bounty = identified
            .regexes
            .iter()
            .flat_map(|(_, matches)| matches)
            .any(has_exploit_key);
        let mut header = vec!["Matched Text", "Identified as", "Description"];
        if show_files {
            header.push("File");
        }
        if bug_bounty {
            header.push("Exploit");
        }
        let mut rows: Vec<Vec<String>> = Vec::new();
        for (location, matches) in &identified.regexes {
            for found in matches {
                let mut row = vec![
                    sanitized(&found.matched),
                    sanitized(&super::markup::plain(&found.regex.name)),
                    sanitized(&description_cell(found, print_tags)),
                ];
                if show_files {
                    row.push(sanitized(location));
                }
                if bug_bounty {
                    row.push(sanitized(non_empty(&found.exploit).unwrap_or("")));
                }
                rows.push(row);
            }
        }
        text.strip();
        let mut out = text.render(self.colors);
        out.push('\n');
        out.push_str(&super::table::render(&header, &rows, width, self.colors));
        out.push('\n');
        self.out.write_all(out.as_bytes())
    }
}

/// The substitutions of `format_print()` in each part of the format: `re.sub(r"(?<!\\)"
/// + format, value, part)` for every `%x` in order, then `re.sub(r"\\%", "%", part)`.
fn substitute(parts: &[&str], values: &[(&str, String)]) -> String {
    let mut out = String::new();
    for part in parts {
        let mut text = part.to_string();
        for (format, value) in values {
            text = replace_unescaped(&text, format, value);
        }
        out.push_str(&text.replace("\\%", "%"));
    }
    out
}

/// `re.sub(r"(?<!\\)" + pattern, lambda _: value, text)`: every `pattern` that doesn't
/// follow a backslash.
fn replace_unescaped(text: &str, pattern: &str, value: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut previous: Option<char> = None;
    let mut index = 0;
    while index < text.len() {
        if text[index..].starts_with(pattern) && previous != Some('\\') {
            out.push_str(value);
            index += pattern.len();
            previous = pattern.chars().last();
            continue;
        }
        let c = text[index..].chars().next().expect("a character");
        out.push(c);
        previous = Some(c);
        index += c.len_utf8();
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn substitutions_like_re_sub() {
        assert_eq!(replace_unescaped("%m\\%m%m", "%m", "X"), "X\\%mX");
        // The value of %m is searched for the next formats, as Python does
        let values = [("%m", "thm{%n}".to_string()), ("%n", "Name".to_string())];
        assert_eq!(substitute(&["%m"], &values), "thm{Name}");
        assert_eq!(substitute(&["\\%d %m"], &values), "%d thm{Name}");
        assert_eq!(substitute(&["\\", "%m"], &values), "\\thm{Name}");
    }
}
