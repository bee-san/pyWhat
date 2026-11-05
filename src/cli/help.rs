//! `--help` and the usage line of errors, formatted like click 8.1 formats them: its
//! `HelpFormatter` (`click/formatting.py`) with Python's `textwrap.TextWrapper`, so the text
//! wraps exactly where Python's does.

use super::args::OPTIONS;
use super::python;
use std::sync::OnceLock;

/// The help text of `pywhat/what.py`'s `main()`, as click cleans it (`inspect.cleandoc`).
const HELP: &str = include_str!("help.txt");

/// What `--help` shows after the program name in the usage line.
const USAGE_ARGS: &str = "[OPTIONS] [TEXT_INPUT]...";

/// The width of click's help: `max(min(columns, 80) - 2, 50)`, where `columns` is what
/// Python's `shutil.get_terminal_size()` returns.
pub(crate) fn help_width(columns: usize) -> usize {
    (columns.min(80).saturating_sub(2)).max(50)
}

/// `--help`, ending with a line break.
pub(crate) fn help(prog: &str, width: usize) -> String {
    let mut formatter = HelpFormatter::new(width);
    formatter.write_usage(prog, USAGE_ARGS);
    formatter.write_paragraph();
    formatter.indent();
    formatter.write_text(HELP);
    formatter.dedent();
    formatter.write_paragraph();
    formatter.write_heading("Options");
    formatter.indent();
    let rows: Vec<(String, String)> = OPTIONS
        .iter()
        .map(|spec| {
            // join_options(): sorted by the length of the prefix ("-" before "--")
            let mut opts: Vec<&str> = spec.opts.to_vec();
            opts.sort_by_key(|opt| if opt.starts_with("--") { 2 } else { 1 });
            let mut first = opts.join(", ");
            if spec.takes_value {
                first.push(' ');
                first.push_str(spec.metavar);
            }
            (first, spec.help.to_string())
        })
        .collect();
    formatter.write_dl(&rows);
    formatter.dedent();
    let mut text = formatter.buffer.trim_end_matches('\n').to_string();
    text.push('\n');
    text
}

/// The usage line of a usage error, without a line break.
pub(crate) fn usage(prog: &str, width: usize) -> String {
    let mut formatter = HelpFormatter::new(width);
    formatter.write_usage(prog, USAGE_ARGS);
    formatter.buffer.trim_end_matches('\n').to_string()
}

/// `len(strip_ansi(text))`: the help has no escape sequences, so the number of characters.
fn term_len(text: &str) -> usize {
    text.chars().count()
}

/// click's `HelpFormatter`.
struct HelpFormatter {
    width: usize,
    current_indent: usize,
    buffer: String,
}

impl HelpFormatter {
    fn new(width: usize) -> Self {
        HelpFormatter {
            width,
            current_indent: 0,
            buffer: String::new(),
        }
    }

    fn write(&mut self, text: &str) {
        self.buffer.push_str(text);
    }

    fn indent(&mut self) {
        self.current_indent += 2;
    }

    fn dedent(&mut self) {
        self.current_indent -= 2;
    }

    fn spaces(count: usize) -> String {
        " ".repeat(count)
    }

    fn write_usage(&mut self, prog: &str, args: &str) {
        let prefix = "Usage: ";
        let usage_prefix = format!("{prefix:>width$}{prog} ", width = self.current_indent);
        let text_width = self.width.saturating_sub(self.current_indent);
        if text_width >= term_len(&usage_prefix) + 20 {
            let indent = Self::spaces(term_len(&usage_prefix));
            let wrapped = wrap_text(args, text_width, &usage_prefix, &indent, false);
            self.write(&wrapped);
        } else {
            self.write(&usage_prefix);
            self.write("\n");
            let indent = Self::spaces(self.current_indent.max(term_len(prefix)) + 4);
            let wrapped = wrap_text(args, text_width, &indent, &indent, false);
            self.write(&wrapped);
        }
        self.write("\n");
    }

    fn write_heading(&mut self, heading: &str) {
        let indent = Self::spaces(self.current_indent);
        self.write(&format!("{indent}{heading}:\n"));
    }

    fn write_paragraph(&mut self) {
        if !self.buffer.is_empty() {
            self.write("\n");
        }
    }

    fn write_text(&mut self, text: &str) {
        let indent = Self::spaces(self.current_indent);
        let wrapped = wrap_text(text, self.width, &indent, &indent, true);
        self.write(&wrapped);
        self.write("\n");
    }

    fn write_dl(&mut self, rows: &[(String, String)]) {
        let (col_max, col_spacing) = (30, 2);
        let widest = rows
            .iter()
            .map(|(first, _)| term_len(first))
            .max()
            .unwrap_or(0);
        let first_col = widest.min(col_max) + col_spacing;
        for (first, second) in rows {
            let indent = Self::spaces(self.current_indent);
            self.write(&format!("{indent}{first}"));
            if second.is_empty() {
                self.write("\n");
                continue;
            }
            if term_len(first) <= first_col - col_spacing {
                self.write(&Self::spaces(first_col - term_len(first)));
            } else {
                self.write("\n");
                self.write(&Self::spaces(first_col + self.current_indent));
            }
            let text_width = (self.width as isize - first_col as isize - 2).max(10) as usize;
            let wrapped = wrap_text(second, text_width, "", "", true);
            let lines = splitlines(&wrapped);
            match lines.split_first() {
                Some((first_line, rest)) => {
                    self.write(&format!("{first_line}\n"));
                    for line in rest {
                        let indent = Self::spaces(first_col + self.current_indent);
                        self.write(&format!("{indent}{line}\n"));
                    }
                }
                None => self.write("\n"),
            }
        }
    }
}

/// `str.splitlines()`.
fn splitlines(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = text.char_indices().peekable();
    while let Some((index, c)) = chars.next() {
        let end = match c {
            '\r' => {
                if let Some(&(_, '\n')) = chars.peek() {
                    chars.next();
                    index + 2
                } else {
                    index + 1
                }
            }
            '\n' | '\x0b' | '\x0c' | '\x1c' | '\x1d' | '\x1e' | '\u{85}' | '\u{2028}'
            | '\u{2029}' => index + c.len_utf8(),
            _ => continue,
        };
        lines.push(&text[start..index]);
        start = end;
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

/// `str.expandtabs(8)`.
fn expand_tabs(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut column = 0;
    for c in text.chars() {
        match c {
            '\t' => {
                let spaces = 8 - column % 8;
                out.push_str(&" ".repeat(spaces));
                column += spaces;
            }
            '\n' | '\r' => {
                out.push(c);
                column = 0;
            }
            _ => {
                out.push(c);
                column += 1;
            }
        }
    }
    out
}

/// click's `wrap_text()`: wraps `text` to `width` columns, paragraph by paragraph (with
/// the indentation of their first line) if `preserve_paragraphs`.
fn wrap_text(
    text: &str,
    width: usize,
    initial_indent: &str,
    subsequent_indent: &str,
    preserve_paragraphs: bool,
) -> String {
    let text = expand_tabs(text);
    let mut wrapper = TextWrapper {
        width: width as isize,
        initial_indent: initial_indent.to_string(),
        subsequent_indent: subsequent_indent.to_string(),
    };
    if !preserve_paragraphs {
        return wrapper.fill(&text);
    }
    // (indentation, raw, text) of each paragraph
    let mut paragraphs: Vec<(usize, bool, String)> = Vec::new();
    let mut buffer: Vec<&str> = Vec::new();
    let mut indent: Option<usize> = None;
    let flush = |buffer: &mut Vec<&str>, indent: Option<usize>, paragraphs: &mut Vec<_>| {
        if buffer.is_empty() {
            return;
        }
        if python::strip(buffer[0]) == "\x08" {
            paragraphs.push((indent.unwrap_or(0), true, buffer[1..].join("\n")));
        } else {
            paragraphs.push((indent.unwrap_or(0), false, buffer.join(" ")));
        }
        buffer.clear();
    };
    for line in splitlines(&text) {
        if line.is_empty() {
            flush(&mut buffer, indent, &mut paragraphs);
            indent = None;
        } else {
            let line = if indent.is_none() {
                let stripped = python::lstrip(line);
                indent = Some(term_len(line) - term_len(stripped));
                stripped
            } else {
                line
            };
            buffer.push(line);
        }
    }
    flush(&mut buffer, indent, &mut paragraphs);
    let mut wrapped = Vec::new();
    for (indent, raw, text) in paragraphs {
        let extra = " ".repeat(indent);
        let saved = (
            wrapper.initial_indent.clone(),
            wrapper.subsequent_indent.clone(),
        );
        wrapper.initial_indent.push_str(&extra);
        wrapper.subsequent_indent.push_str(&extra);
        wrapped.push(if raw {
            wrapper.indent_only(&text)
        } else {
            wrapper.fill(&text)
        });
        (wrapper.initial_indent, wrapper.subsequent_indent) = saved;
    }
    wrapped.join("\n\n")
}

/// Python's `textwrap.TextWrapper` with click's options (`replace_whitespace=False`) and
/// click's `_handle_long_word`.
struct TextWrapper {
    width: isize,
    initial_indent: String,
    subsequent_indent: String,
}

/// `TextWrapper.wordsep_re`, with `\Z` written as fancy-regex writes it.
fn wordsep_re() -> &'static fancy_regex::Regex {
    static WORDSEP: OnceLock<fancy_regex::Regex> = OnceLock::new();
    WORDSEP.get_or_init(|| {
        let ws = r"[\t\n\x0b\x0c\r ]";
        let nws = r"[^\t\n\x0b\x0c\r ]";
        let wp = r#"[\w!"'&.,?]"#;
        let lt = r"[^\d\W]";
        let pattern = format!(
            r"({ws}+|(?<={wp})-{{2,}}(?=\w)|{nws}+?(?:-(?:(?<={lt}{{2}}-)|(?<={lt}-{lt}-))(?={lt}-?{lt})|(?={ws}|\z)|(?<={wp})(?=-{{2,}}\w)))"
        );
        fancy_regex::Regex::new(&pattern).expect("wordsep_re compiles")
    })
}

impl TextWrapper {
    /// `_split_chunks()`: words, whitespace and hyphenated parts of words.
    fn split_chunks(text: &str) -> Vec<String> {
        let text = expand_tabs(text);
        let mut chunks = Vec::new();
        let mut last = 0;
        for found in wordsep_re().find_iter(&text) {
            let Ok(found) = found else { break };
            chunks.push(text[last..found.start()].to_string());
            chunks.push(found.as_str().to_string());
            last = found.end();
        }
        chunks.push(text[last..].to_string());
        chunks.retain(|chunk| !chunk.is_empty());
        chunks
    }

    fn fill(&self, text: &str) -> String {
        self.wrap(text).join("\n")
    }

    fn indent_only(&self, text: &str) -> String {
        splitlines(text)
            .iter()
            .enumerate()
            .map(|(index, line)| {
                let indent = if index == 0 {
                    &self.initial_indent
                } else {
                    &self.subsequent_indent
                };
                format!("{indent}{line}")
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// `_wrap_chunks()`.
    fn wrap(&self, text: &str) -> Vec<String> {
        let len = |chunk: &str| chunk.chars().count() as isize;
        let is_blank = |chunk: &str| python::strip(chunk).is_empty();
        let mut chunks = Self::split_chunks(text);
        chunks.reverse();
        let mut lines: Vec<String> = Vec::new();
        while !chunks.is_empty() {
            let mut cur_line: Vec<String> = Vec::new();
            let mut cur_len: isize = 0;
            let indent = if lines.is_empty() {
                &self.initial_indent
            } else {
                &self.subsequent_indent
            };
            let width = self.width - len(indent);
            if chunks.last().is_some_and(|chunk| is_blank(chunk)) && !lines.is_empty() {
                chunks.pop();
            }
            while let Some(chunk) = chunks.last() {
                let l = len(chunk);
                if cur_len + l <= width {
                    cur_len += l;
                    cur_line.push(chunks.pop().expect("a chunk"));
                } else {
                    break;
                }
            }
            if chunks.last().is_some_and(|chunk| len(chunk) > width) {
                // click's _handle_long_word: break the word to fill the line
                let space_left = (width - cur_len).max(1) as usize;
                let last = chunks.last_mut().expect("a chunk");
                let cut_at = last
                    .char_indices()
                    .nth(space_left)
                    .map_or(last.len(), |(index, _)| index);
                let rest = last.split_off(cut_at);
                cur_line.push(std::mem::replace(last, rest));
            }
            cur_line.pop_if(|chunk| is_blank(chunk));
            if !cur_line.is_empty() {
                lines.push(format!("{indent}{}", cur_line.concat()));
            }
        }
        lines
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn chunks_like_textwrap() {
        // click's TextWrapper()._split_chunks() in Python 3.10
        assert_eq!(
            TextWrapper::split_chunks("Hello there -- you goof-ball, use the -b option!"),
            [
                "Hello", " ", "there", " ", "--", " ", "you", " ", "goof-", "ball,", " ", "use",
                " ", "the", " ", "-b", " ", "option!"
            ]
        );
        assert_eq!(
            TextWrapper::split_chunks("a--b well--done '--rarity 0:' x-1"),
            [
                "a", "--", "b", " ", "well", "--", "done", " ", "'", "--", "rarity", " ", "0:'",
                " ", "x-1"
            ]
        );
    }

    #[test]
    fn wraps_like_textwrap() {
        let wrapper = TextWrapper {
            width: 20,
            initial_indent: "* ".into(),
            subsequent_indent: "  ".into(),
        };
        // click's TextWrapper(20, initial_indent="* ", subsequent_indent="  ").fill(text)
        assert_eq!(
            wrapper.fill("The quick brown fox jumps over the lazy dog, supercalifragilistic"),
            "* The quick brown\n  fox jumps over the\n  lazy dog, supercal\n  ifragilistic"
        );
    }

    #[test]
    fn widths() {
        assert_eq!(help_width(10_000), 78);
        assert_eq!(help_width(60), 58);
        assert_eq!(help_width(10), 50);
    }

    #[test]
    fn usage_line() {
        assert_eq!(usage("what", 78), "Usage: what [OPTIONS] [TEXT_INPUT]...");
        assert!(help("what", 78).starts_with("Usage: what [OPTIONS] [TEXT_INPUT]...\n\n  pyWhat"));
    }
}
