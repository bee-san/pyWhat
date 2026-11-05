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
/// codes, which the data doesn't have).
pub(crate) fn render(markup: &str) -> Vec<(String, Style)> {
    if !markup.contains('[') {
        return vec![(markup.to_string(), Style::default())];
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
            let closing = closing.trim().to_lowercase();
            if closing.is_empty() {
                open.pop();
            } else if let Some(index) = open.iter().rposition(|tag| tag.name == closing) {
                open.remove(index);
            }
            // rich raises an error for a closing tag that closes nothing; the data has none
        } else {
            let definition = match parameters {
                Some(parameters) => format!("{name} {parameters}"),
                None => name.to_string(),
            };
            open.push(Open {
                name: name.trim().to_lowercase(),
                style: parse_style(&definition),
            });
        }
    }
    push(&mut spans, &markup[position..], &open);
    spans
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
