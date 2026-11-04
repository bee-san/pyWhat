//! Styled text and how it is written: plain text when the output isn't a terminal, and
//! the escape sequences of rich's colour systems on a terminal. Like rich, everything that
//! is printed loses its backspaces, vertical tabs, form feeds and carriage returns, and
//! its tabs become spaces (tab stops every 8 characters).

use std::fmt::Write;

/// A style: bold, a colour and a link.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct Style {
    pub(crate) bold: bool,
    pub(crate) color: Option<(u8, u8, u8)>,
    pub(crate) link: Option<String>,
}

/// `bold #D7Afff`, the style of pyWhat's labels ("Matched on: ").
pub(crate) const LABEL: Style = Style {
    bold: true,
    color: Some((0xD7, 0xAF, 0xFF)),
    link: None,
};

/// `bold`.
pub(crate) const BOLD: Style = Style {
    bold: true,
    color: None,
    link: None,
};

/// `bold #49C3CE`, the style of the version number.
pub(crate) const VERSION: Style = Style {
    bold: true,
    color: Some((0x49, 0xC3, 0xCE)),
    link: None,
};

/// The colours that a terminal shows, as rich detects them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ColorSystem {
    /// Not a terminal: no escape sequences at all.
    None,
    Standard,
    EightBit,
    TrueColor,
}

/// How to write styles.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct Colors {
    pub(crate) system: ColorSystem,
    /// `NO_COLOR`: bold and links, but no colours.
    pub(crate) no_color: bool,
}

impl Colors {
    pub(crate) const PLAIN: Colors = Colors {
        system: ColorSystem::None,
        no_color: false,
    };

    /// rich's `Console._detect_color_system()` for a stream that is a terminal (or not).
    pub(crate) fn detect(is_terminal: bool, env: &dyn Fn(&str) -> Option<String>) -> Colors {
        let term = env("TERM").unwrap_or_default().trim().to_lowercase();
        if !is_terminal || term == "dumb" || term == "unknown" {
            return Colors::PLAIN;
        }
        let system = if cfg!(windows) {
            // Windows 10 and later understand the escape sequences of 24-bit colours once
            // they are enabled; older consoles get none
            #[cfg(windows)]
            let enabled = anstyle_query::windows::enable_ansi_colors().unwrap_or(false);
            #[cfg(not(windows))]
            let enabled = true;
            if enabled {
                ColorSystem::TrueColor
            } else {
                ColorSystem::None
            }
        } else {
            let color_term = env("COLORTERM").unwrap_or_default().trim().to_lowercase();
            if color_term == "truecolor" || color_term == "24bit" {
                ColorSystem::TrueColor
            } else {
                match term.rsplit_once('-').map_or("", |(_, colors)| colors) {
                    "256color" => ColorSystem::EightBit,
                    _ => ColorSystem::Standard,
                }
            }
        };
        Colors {
            system,
            no_color: env("NO_COLOR").is_some(),
        }
    }

    pub(crate) fn is_plain(self) -> bool {
        self.system == ColorSystem::None
    }
}

/// rich's `rgb_to_hls()` saturation and lightness (`colorsys`).
fn lightness_saturation(r: f64, g: f64, b: f64) -> (f64, f64) {
    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    let lightness = (max + min) / 2.0;
    if max == min {
        return (lightness, 0.0);
    }
    let saturation = if lightness <= 0.5 {
        (max - min) / (max + min)
    } else {
        (max - min) / (2.0 - max - min)
    };
    (lightness, saturation)
}

/// rich's `Color.downgrade(EIGHT_BIT)` of a 24-bit colour.
fn eight_bit((r, g, b): (u8, u8, u8)) -> u8 {
    let (r, g, b) = (r as f64 / 255.0, g as f64 / 255.0, b as f64 / 255.0);
    let (lightness, saturation) = lightness_saturation(r, g, b);
    if saturation < 0.1 {
        let gray = (lightness * 25.0).round_ties_even() as u8;
        return match gray {
            0 => 16,
            25 => 231,
            gray => 231 + gray,
        };
    }
    let level = |value: f64| (value * 5.0).round_ties_even() as u8;
    16 + 36 * level(r) + 6 * level(g) + level(b)
}

/// rich's `STANDARD_PALETTE.match()`: the closest of the 16 standard colours.
fn standard((r, g, b): (u8, u8, u8)) -> u8 {
    const PALETTE: [(i64, i64, i64); 16] = [
        (0, 0, 0),
        (170, 0, 0),
        (0, 170, 0),
        (170, 85, 0),
        (0, 0, 170),
        (170, 0, 170),
        (0, 170, 170),
        (170, 170, 170),
        (85, 85, 85),
        (255, 85, 85),
        (85, 255, 85),
        (255, 255, 85),
        (85, 85, 255),
        (255, 85, 255),
        (85, 255, 255),
        (255, 255, 255),
    ];
    let (r, g, b) = (i64::from(r), i64::from(g), i64::from(b));
    let distance = |&(r2, g2, b2): &(i64, i64, i64)| {
        let red_mean = (r + r2) / 2;
        let (red, green, blue) = (r - r2, g - g2, b - b2);
        let squared = (((512 + red_mean) * red * red) >> 8)
            + 4 * green * green
            + (((767 - red_mean) * blue * blue) >> 8);
        (squared as f64).sqrt()
    };
    let mut best = 0;
    for (index, color) in PALETTE.iter().enumerate() {
        if distance(color) < distance(&PALETTE[best]) {
            best = index;
        }
    }
    best as u8
}

/// Writes `text` in `style`, like rich's `Style.render()`.
pub(crate) fn write_styled(out: &mut String, text: &str, style: &Style, colors: Colors) {
    if text.is_empty() || colors.is_plain() || *style == Style::default() {
        out.push_str(text);
        return;
    }
    let mut codes = String::new();
    if style.bold {
        codes.push('1');
    }
    if let (Some(rgb), false) = (style.color, colors.no_color) {
        if !codes.is_empty() {
            codes.push(';');
        }
        let _ = match colors.system {
            ColorSystem::TrueColor => write!(codes, "38;2;{};{};{}", rgb.0, rgb.1, rgb.2),
            ColorSystem::EightBit => write!(codes, "38;5;{}", eight_bit(rgb)),
            ColorSystem::Standard | ColorSystem::None => {
                let number = standard(rgb);
                if number < 8 {
                    write!(codes, "{}", 30 + number)
                } else {
                    write!(codes, "{}", 82 + number)
                }
            }
        };
    }
    let styled = if codes.is_empty() {
        text.to_string()
    } else {
        format!("\x1b[{codes}m{text}\x1b[0m")
    };
    match &style.link {
        Some(link) => {
            let _ = write!(out, "\x1b]8;;{link}\x1b\\{styled}\x1b]8;;\x1b\\");
        }
        None => out.push_str(&styled),
    }
}

/// A piece of text to print: text as it is, or markup of the data files.
#[derive(Debug, Clone)]
enum Piece {
    Plain(String, Style),
    Markup(String),
}

/// Text to print, built from pieces. Like the strings that the Python CLI gives rich,
/// except that only the data is markup.
#[derive(Debug, Clone, Default)]
pub(crate) struct Text {
    pieces: Vec<Piece>,
}

impl Text {
    pub(crate) fn new() -> Text {
        Text::default()
    }

    /// Text as it is.
    pub(crate) fn plain(&mut self, text: &str) -> &mut Self {
        self.styled(text, Style::default())
    }

    /// Text in a style.
    pub(crate) fn styled(&mut self, text: &str, style: Style) -> &mut Self {
        if !text.is_empty() {
            self.pieces.push(Piece::Plain(text.to_string(), style));
        }
        self
    }

    /// A label, such as "Matched on: ".
    pub(crate) fn label(&mut self, text: &str) -> &mut Self {
        self.styled(text, LABEL)
    }

    /// A string of the data files, which may contain rich markup.
    pub(crate) fn markup(&mut self, markup: &str) -> &mut Self {
        if !markup.is_empty() {
            self.pieces.push(Piece::Markup(markup.to_string()));
        }
        self
    }

    pub(crate) fn append(&mut self, other: Text) -> &mut Self {
        self.pieces.extend(other.pieces);
        self
    }

    /// The text as the Python CLI writes it before rich renders it, with markup.
    pub(crate) fn source(&self) -> String {
        self.pieces
            .iter()
            .map(|piece| match piece {
                Piece::Plain(text, _) | Piece::Markup(text) => text.as_str(),
            })
            .collect()
    }

    /// `str.rstrip()` of the text before rendering (Python strips the markup).
    pub(crate) fn rstrip(&mut self) -> &mut Self {
        while let Some(last) = self.pieces.last_mut() {
            let text = match last {
                Piece::Plain(text, _) | Piece::Markup(text) => text,
            };
            let kept = super::python::rstrip(text).len();
            text.truncate(kept);
            if !text.is_empty() {
                break;
            }
            self.pieces.pop();
        }
        self
    }

    /// `str.lstrip()` of the text before rendering.
    pub(crate) fn lstrip(&mut self) -> &mut Self {
        while let Some(first) = self.pieces.first_mut() {
            let text = match first {
                Piece::Plain(text, _) | Piece::Markup(text) => text,
            };
            let removed = text.len() - super::python::lstrip(text).len();
            text.drain(..removed);
            if !text.is_empty() {
                break;
            }
            self.pieces.remove(0);
        }
        self
    }

    /// `str.strip()` of the text before rendering.
    pub(crate) fn strip(&mut self) -> &mut Self {
        self.lstrip().rstrip()
    }

    /// The text with its styles, with the markup rendered.
    fn spans(&self) -> Vec<(String, Style)> {
        let mut spans = Vec::new();
        for piece in &self.pieces {
            match piece {
                Piece::Plain(text, style) => spans.push((text.clone(), style.clone())),
                Piece::Markup(markup) => spans.extend(super::markup::render(markup)),
            }
        }
        spans
    }

    /// The plain text, as rich prints it to a file or a pipe.
    pub(crate) fn to_plain(&self) -> String {
        self.render(Colors::PLAIN)
    }

    /// The text as rich prints it: control codes removed, tabs expanded, and styles
    /// written for `colors`.
    pub(crate) fn render(&self, colors: Colors) -> String {
        let mut out = String::new();
        let mut column = 0;
        for (text, style) in self.spans() {
            let text = sanitize(&text, &mut column);
            // A style per line, the line breaks outside of it
            for (index, line) in text.split('\n').enumerate() {
                if index > 0 {
                    out.push('\n');
                }
                write_styled(&mut out, line, &style, colors);
            }
        }
        out
    }
}

/// What rich does to text it prints: backspaces, vertical tabs, form feeds and carriage
/// returns removed (`strip_control_codes`), tabs expanded to the next multiple of 8
/// characters on the line (`Text.expand_tabs`). `column` is the number of characters on
/// the line so far.
pub(crate) fn sanitize(text: &str, column: &mut usize) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '\x08' | '\x0b' | '\x0c' | '\r' => {}
            '\n' => {
                out.push(c);
                *column = 0;
            }
            '\t' => {
                let spaces = 8 - *column % 8;
                out.extend(std::iter::repeat_n(' ', spaces));
                *column += spaces;
            }
            _ => {
                out.push(c);
                *column += 1;
            }
        }
    }
    out
}

/// `sanitize()` for a text on its own.
pub(crate) fn sanitized(text: &str) -> String {
    sanitize(text, &mut 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rich_downgrades() {
        // Color.parse("#D7AFFF").downgrade(...) in rich 12.2.0
        assert_eq!(eight_bit((0xD7, 0xAF, 0xFF)), 183);
        assert_eq!(eight_bit((0x49, 0xC3, 0xCE)), 80);
        assert_eq!(standard((0xD7, 0xAF, 0xFF)), 7);
        assert_eq!(standard((0x49, 0xC3, 0xCE)), 6);
        assert_eq!(eight_bit((0x80, 0x80, 0x80)), 244);
    }

    #[test]
    fn styles() {
        let true_color = Colors {
            system: ColorSystem::TrueColor,
            no_color: false,
        };
        let mut out = String::new();
        write_styled(&mut out, "x", &LABEL, true_color);
        assert_eq!(out, "\x1b[1;38;2;215;175;255mx\x1b[0m");
        let mut out = String::new();
        write_styled(
            &mut out,
            "x",
            &LABEL,
            Colors {
                no_color: true,
                ..true_color
            },
        );
        assert_eq!(out, "\x1b[1mx\x1b[0m");
        let mut text = Text::new();
        text.label("Name: ").plain("a\tb\r\n\tc");
        assert_eq!(text.to_plain(), "Name: a b\n        c");
        assert_eq!(
            text.render(true_color),
            "\x1b[1;38;2;215;175;255mName: \x1b[0ma b\n        c"
        );
    }

    #[test]
    fn colour_systems_like_rich() {
        // Console._detect_color_system() of rich 12.2.0, on a terminal
        let detect = |vars: &[(&str, &str)], terminal: bool| {
            let vars: Vec<(String, String)> = vars
                .iter()
                .map(|(name, value)| (name.to_string(), value.to_string()))
                .collect();
            Colors::detect(terminal, &|name| {
                vars.iter().find(|(n, _)| n == name).map(|(_, v)| v.clone())
            })
        };
        let system = |vars: &[(&str, &str)]| detect(vars, true).system;
        if cfg!(windows) {
            return; // Windows terminals get 24-bit colours once they are enabled
        }
        assert_eq!(system(&[("TERM", "xterm-256color")]), ColorSystem::EightBit);
        assert_eq!(
            system(&[("TERM", "xterm-256color"), ("COLORTERM", "truecolor")]),
            ColorSystem::TrueColor
        );
        assert_eq!(
            system(&[("TERM", "xterm"), ("COLORTERM", "24bit")]),
            ColorSystem::TrueColor
        );
        assert_eq!(system(&[("TERM", "xterm")]), ColorSystem::Standard);
        assert_eq!(system(&[("TERM", "xterm-16color")]), ColorSystem::Standard);
        assert_eq!(system(&[]), ColorSystem::Standard);
        for dumb in ["dumb", "unknown", "DUMB"] {
            assert_eq!(system(&[("TERM", dumb)]), ColorSystem::None, "{dumb}");
        }
        // Not a terminal: no escape sequences
        assert_eq!(detect(&[("TERM", "xterm-256color")], false), Colors::PLAIN);
        // NO_COLOR, even empty, keeps bold and links
        let no_color = detect(&[("TERM", "xterm-256color"), ("NO_COLOR", "")], true);
        assert!(no_color.no_color);
        assert_eq!(no_color.system, ColorSystem::EightBit);
    }

    #[test]
    fn control_codes_like_rich() {
        // strip_control_codes() removes backspace, vertical tab, form feed and carriage
        // return; other control characters stay
        assert_eq!(
            sanitized("a\x08b\x0bc\x0cd\re\x07f\x1bg"),
            "abcde\x07f\x1bg"
        );
        // Tabs expand to the next multiple of 8 on the line
        assert_eq!(
            sanitized("\tx\n1234567\tx\n12345678\tx"),
            "        x\n1234567 x\n12345678        x"
        );
    }

    #[test]
    fn rstrip_strips_the_source() {
        let mut text = Text::new();
        text.plain("a").markup("b [https://x y]").plain("\n\n");
        text.rstrip();
        // rich gets "ab [https://x y]" and prints "ab "
        assert_eq!(text.to_plain(), "ab ");
        let mut text = Text::new();
        text.plain("a ").markup("  ").plain(" \n");
        text.rstrip();
        assert_eq!(text.to_plain(), "a");
    }
}
