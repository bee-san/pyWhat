//! rich's console markup, for the strings of pyWhat's data files: some descriptions in
//! `regex.json` are written for rich (`[#CAE4F1][link=https://...]CORS[/link][/#CAE4F1]`),
//! and rich takes the wiki-style links of `file_signatures.json` (`[https://... name]`) for
//! tags too, and leaves them out. The Python CLI prints all of its output as markup; this
//! one only the data, and prints the matched text and the file names as they are (#291,
//! Python bug 4).

use super::style::Style;
use std::sync::OnceLock;

/// rich's `RE_TAGS`: a tag is `[` and a letter, `#`, `/` or `@`, up to the next `]`,
/// possibly escaped with backslashes.
fn tags() -> &'static regex::Regex {
    static TAGS: OnceLock<regex::Regex> = OnceLock::new();
    TAGS.get_or_init(|| regex::Regex::new(r"(\\*)\[([a-z#/@][^\[]*?)\]").expect("valid regex"))
}

/// A style that rich can parse, as far as the data uses them: `bold`, colours as
/// `#rrggbb` and `link URL`. Anything else is no style, which is what rich makes of a
/// style it can't parse.
fn parse_style(definition: &str) -> Style {
    let mut style = Style::default();
    let mut words = definition.split_whitespace();
    while let Some(word) = words.next() {
        match word.to_lowercase().as_str() {
            "bold" | "b" => style.bold = true,
            "link" => match words.next() {
                Some(url) => style.link = Some(url.to_string()),
                None => return Style::default(),
            },
            color if color.len() == 7 && color.starts_with('#') => {
                match u32::from_str_radix(&color[1..], 16) {
                    Ok(rgb) => style.color = Some(((rgb >> 16) as u8, (rgb >> 8) as u8, rgb as u8)),
                    Err(_) => return Style::default(),
                }
            }
            _ => return Style::default(),
        }
    }
    style
}

/// An open tag: its name (to match the closing tag) and its style.
struct Open {
    name: String,
    style: Style,
}

/// rich's `STYLE_ATTRIBUTES`: the attributes of styles, with their short names.
fn attribute(word: &str) -> Option<&'static str> {
    Some(match word {
        "dim" | "d" => "dim",
        "bold" | "b" => "bold",
        "italic" | "i" => "italic",
        "underline" | "u" => "underline",
        "blink" => "blink",
        "blink2" => "blink2",
        "reverse" | "r" => "reverse",
        "conceal" | "c" => "conceal",
        "strike" | "s" => "strike",
        "underline2" | "uu" => "underline2",
        "frame" => "frame",
        "encircle" => "encircle",
        "overline" | "o" => "overline",
        _ => return None,
    })
}

/// rich's `Style.normalize()`, which matches closing tags with opening ones: the attributes
/// in rich's order (`[b]` is closed by `[/bold]`), the colour, the background colour and
/// the link. A style that rich can't parse is compared as written, in lower case; this
/// takes every other word for a colour, so it differs from rich only for unknown colours
/// written in another order.
fn normalize(definition: &str) -> String {
    const ORDER: [&str; 13] = [
        "bold",
        "dim",
        "italic",
        "underline",
        "blink",
        "blink2",
        "reverse",
        "conceal",
        "strike",
        "underline2",
        "frame",
        "encircle",
        "overline",
    ];
    let unparsed = || definition.trim().to_lowercase();
    if definition.is_empty() || definition.trim() == "none" {
        return "none".to_string();
    }
    let mut attributes: Vec<(&str, bool)> = Vec::new();
    let (mut color, mut background, mut link) = (None, None, None);
    let mut words = definition.split_whitespace();
    while let Some(original) = words.next() {
        let word = original.to_lowercase();
        match word.as_str() {
            "on" => match words.next() {
                Some(next) => background = Some(next.to_lowercase()),
                None => return unparsed(),
            },
            // The word after "not" and "link" as it is written
            "not" => match words.next().and_then(attribute) {
                Some(name) => attributes.push((name, false)),
                None => return unparsed(),
            },
            "link" => match words.next() {
                Some(next) => link = Some(next.to_string()),
                None => return unparsed(),
            },
            _ => match attribute(&word) {
                Some(name) => attributes.push((name, true)),
                None => color = Some(word),
            },
        }
    }
    let mut parts: Vec<String> = Vec::new();
    for name in ORDER {
        if let Some(&(_, on)) = attributes.iter().rev().find(|(n, _)| *n == name) {
            parts.push(if on {
                name.to_string()
            } else {
                format!("not {name}")
            });
        }
    }
    parts.extend(color);
    if let Some(background) = background {
        parts.push(format!("on {background}"));
    }
    if let Some(link) = link {
        parts.push(format!("link {link}"));
    }
    if parts.is_empty() {
        "none".to_string()
    } else {
        parts.join(" ")
    }
}

fn combined(open: &[Open]) -> Style {
    let mut style = Style::default();
    for tag in open {
        style.bold |= tag.style.bold;
        if tag.style.color.is_some() {
            style.color = tag.style.color;
        }
        if tag.style.link.is_some() {
            style.link.clone_from(&tag.style.link);
        }
    }
    style
}

/// The text of `markup` with its styles, as `rich.markup.render()` makes it (without emoji
/// codes, which the data doesn't have). A closing tag that closes nothing is left out.
pub(crate) fn render(markup: &str) -> Vec<(String, Style)> {
    match render_or_error(markup, false) {
        Ok(spans) => spans,
        Err(_) => unreachable!("only the strict rendering fails"),
    }
}

/// The `MarkupError` that rich raises for `markup`, if any: a closing tag that closes
/// nothing, such as the `[/b]` of the format string `[/b]%m`.
pub(crate) fn error(markup: &str) -> Option<String> {
    render_or_error(markup, true).err()
}

fn render_or_error(markup: &str, strict: bool) -> Result<Vec<(String, Style)>, String> {
    if !markup.contains('[') {
        return Ok(vec![(markup.to_string(), Style::default())]);
    }
    let mut spans: Vec<(String, Style)> = Vec::new();
    let mut open: Vec<Open> = Vec::new();
    let push = |spans: &mut Vec<(String, Style)>, text: &str, open: &[Open]| {
        if !text.is_empty() {
            // Escaped brackets that aren't part of a tag
            spans.push((text.replace("\\[", "["), combined(open)));
        }
    };
    let mut position = 0;
    for captures in tags().captures_iter(markup) {
        let whole = captures.get(0).expect("a match");
        let escapes = captures.get(1).map_or("", |m| m.as_str());
        let tag_text = captures.get(2).map_or("", |m| m.as_str());
        push(&mut spans, &markup[position..whole.start()], &open);
        position = whole.end();
        if !escapes.is_empty() {
            let (backslashes, escaped) = (escapes.len() / 2, escapes.len() % 2 == 1);
            if backslashes > 0 {
                spans.push(("\\".repeat(backslashes), combined(&open)));
            }
            if escaped {
                // An escaped tag is text, with its brackets
                spans.push((whole.as_str()[escapes.len()..].to_string(), combined(&open)));
                continue;
            }
        }
        let (name, parameters) = match tag_text.split_once('=') {
            Some((name, parameters)) => (name, Some(parameters)),
            None => (tag_text, None),
        };
        if let Some(closing) = name.strip_prefix('/') {
            // Where rich says the tag is: in characters, after the escaped backslashes
            let at = || markup[..whole.start()].chars().count() + escapes.len();
            let closing = closing.trim();
            let closed = if closing.is_empty() {
                open.pop().is_some()
            } else {
                let closing = normalize(closing);
                match open.iter().rposition(|tag| tag.name == closing) {
                    Some(index) => {
                        open.remove(index);
                        true
                    }
                    None => false,
                }
            };
            if !closed && strict {
                return Err(if closing.is_empty() {
                    format!(
                        "closing tag '[/]' at position {} has nothing to close",
                        at()
                    )
                } else {
                    let markup = &whole.as_str()[escapes.len()..];
                    format!(
                        "closing tag '{markup}' at position {} doesn't match any open tag",
                        at()
                    )
                });
            }
        } else {
            let definition = match parameters {
                Some(parameters) => format!("{name} {parameters}"),
                None => name.to_string(),
            };
            open.push(Open {
                name: normalize(name),
                style: parse_style(&definition),
            });
        }
    }
    push(&mut spans, &markup[position..], &open);
    Ok(spans)
}

/// The text of `markup` without its tags.
pub(crate) fn plain(markup: &str) -> String {
    render(markup).into_iter().map(|(text, _)| text).collect()
}

/// `rich.markup.escape()`: `text` as markup that prints `text` as it is.
pub(crate) fn escape(text: &str) -> String {
    static ESCAPE: OnceLock<regex::Regex> = OnceLock::new();
    let escape =
        ESCAPE.get_or_init(|| regex::Regex::new(r"(\\*)(\[[a-z#/@].*?\])").expect("valid regex"));
    escape
        .replace_all(text, |captures: &regex::Captures<'_>| {
            let backslashes = &captures[1];
            format!("{backslashes}{backslashes}\\{}", &captures[2])
        })
        .into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn data_markup() {
        // What rich 12.2.0 prints for these strings of the data files
        assert_eq!(
            plain("Used for [#CAE4F1][link=https://en.wikipedia.org/wiki/Cross-origin_resource_sharing]Cross-Origin Resource Sharing (CORS)[/link][/#CAE4F1]"),
            "Used for Cross-Origin Resource Sharing (CORS)"
        );
        assert_eq!(
            plain("Compressed file using [https://segaretro.org/Rob_Northen_compression Rob Northen compression] (version 1 and 2) algorithm"),
            "Compressed file using  (version 1 and 2) algorithm"
        );
        assert_eq!(plain("a \\[b] \\\\[bold]c"), "a [b] \\c");
        assert_eq!(plain("[1] [A] x"), "[1] [A] x");
        let spans = render("x [#CAE4F1][link=https://a.b]y[/link][/#CAE4F1] z");
        assert_eq!(spans[1].0, "y");
        assert_eq!(spans[1].1.color, Some((0xCA, 0xE4, 0xF1)));
        assert_eq!(spans[1].1.link.as_deref(), Some("https://a.b"));
        assert_eq!(spans[2], (" z".to_string(), Style::default()));
    }

    #[test]
    fn normalize_like_rich() {
        // Style.normalize() in rich 12.2.0
        for (definition, normalized) in [
            ("b", "bold"),
            ("B", "bold"),
            ("bold #D7Afff", "bold #d7afff"),
            ("#D7Afff bold", "bold #d7afff"),
            ("red bold", "bold red"),
            ("on blue red", "red on blue"),
            ("link https://A.b", "link https://A.b"),
            ("link", "link"),
            ("not bold", "not bold"),
            ("u r", "underline reverse"),
            ("i", "italic"),
            ("", "none"),
        ] {
            assert_eq!(normalize(definition), normalized, "{definition:?}");
        }
    }

    #[test]
    fn markup_errors_like_rich() {
        // The MarkupError messages of rich 12.2.0
        assert_eq!(
            error("[/b]THM{x}").as_deref(),
            Some("closing tag '[/b]' at position 0 doesn't match any open tag")
        );
        assert_eq!(
            error("[b]THM{x}[/i]").as_deref(),
            Some("closing tag '[/i]' at position 9 doesn't match any open tag")
        );
        assert_eq!(
            error("x[/]y").as_deref(),
            Some("closing tag '[/]' at position 1 has nothing to close")
        );
        assert_eq!(
            error("[b]THM{x}[/b][/b]").as_deref(),
            Some("closing tag '[/b]' at position 13 doesn't match any open tag")
        );
        assert_eq!(
            error("é[/b]").as_deref(),
            Some("closing tag '[/b]' at position 1 doesn't match any open tag")
        );
        for valid in [
            "[b]x[/bold]",
            "[bold red]x[/red bold]",
            "\\[/b]",
            "[link=https://a.b]x[/link]",
            "[b]x",
            "[/b",
            "[@click]x[/@click]",
            "a \\\\[b]x[/b]",
        ] {
            assert_eq!(error(valid), None, "{valid:?}");
        }
        // Rendering leaves the tag out
        assert_eq!(plain("x[/b]y"), "xy");
    }

    #[test]
    fn escape_like_rich() {
        // rich.markup.escape() in rich 12.2.0
        for (text, escaped) in [
            ("a\\", "a\\"),
            ("[b]x", "\\[b]x"),
            ("\\[b]", "\\\\\\[b]"),
            ("x [B] [1]", "x [B] [1]"),
            ("[/]", "\\[/]"),
            ("a[b]c\\", "a\\[b]c\\"),
        ] {
            assert_eq!(escape(text), escaped, "{text:?}");
            assert_eq!(plain(&escape(text)), text, "{text:?}");
        }
    }
}
