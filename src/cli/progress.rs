//! Progress bars for searches that take a while, like `pywhat/progress.py`: a bar for the
//! files (if there are several) with the file that is searched, and a bar for the regexes
//! of the file with the regex that is searched for. They appear once the search has taken
//! half a second, only on a terminal, and are removed when the search is complete.
//! indicatif draws them, in the look of rich's progress bars.

use super::style::{write_styled, ColorSystem, Colors, Style, LABEL};
use crate::files::Progress;
use indicatif::{MultiProgress, ProgressBar, ProgressDrawTarget, ProgressStyle};
use std::sync::{Arc, Condvar, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

/// How long a search runs before the bars appear, so that they don't flicker for searches
/// that are over in a moment.
pub(crate) const DELAY: Duration = Duration::from_millis(500);
/// How often the bars are drawn.
const REFRESH: Duration = Duration::from_millis(100);
const BAR_WIDTH: usize = 30;

/// rich's `bar.complete` and `bar.finished` styles.
const COMPLETE: (u8, u8, u8) = (249, 38, 114);
const FINISHED: (u8, u8, u8) = (114, 156, 31);

/// Where the bars are drawn.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Target {
    Stdout,
    Stderr,
}

/// The latest progress.
#[derive(Debug, Default, Clone)]
struct State {
    seen: bool,
    location: String,
    files_done: usize,
    files: usize,
    regexes_done: usize,
    regexes: usize,
    regex: Option<&'static str>,
}

/// Running progress bars, the progress callback of the search.
pub(crate) struct Bars {
    state: Arc<Mutex<State>>,
    multi: MultiProgress,
    done: Arc<(Mutex<bool>, Condvar)>,
    ticker: Option<JoinHandle<()>>,
}

/// Control characters (e.g. in file names) would mess up the terminal.
fn printable(text: &str) -> String {
    text.chars()
        .filter(|&c| !matches!(c, '\u{0}'..='\u{1f}' | '\u{7f}'..='\u{9f}'))
        .collect()
}

/// `str(timedelta(seconds=...))`: H:MM:SS.
fn elapsed(seconds: u64) -> String {
    format!(
        "{}:{:02}:{:02}",
        seconds / 3600,
        seconds / 60 % 60,
        seconds % 60
    )
}

fn styled(text: &str, style: &Style, colors: Colors) -> String {
    let mut out = String::new();
    write_styled(&mut out, text, style, colors);
    out
}

/// `rich.progress_bar.ProgressBar` of `completed` of `total`, `width` characters wide.
fn bar(completed: usize, total: usize, width: usize, colors: Colors) -> String {
    let completed = completed.min(total);
    let halves = (width * 2 * completed)
        .checked_div(total)
        .unwrap_or(width * 2);
    let (bars, half) = (halves / 2, halves % 2);
    let color = if completed < total {
        COMPLETE
    } else {
        FINISHED
    };
    let complete = Style {
        color: Some(color),
        ..Style::default()
    };
    let mut out = styled(&"━".repeat(bars), &complete, colors);
    if half > 0 {
        out.push_str(&styled("╸", &complete, colors));
    }
    let mut remaining = width - bars - half;
    if colors.no_color || colors.is_plain() {
        // rich only draws the rest of the bar in colour
        out.push_str(&" ".repeat(remaining));
        return out;
    }
    let mut back = String::new();
    if half == 0 && bars > 0 && remaining > 0 {
        back.push('╺');
        remaining -= 1;
    }
    back.push_str(&"━".repeat(remaining));
    if back.is_empty() {
        return out;
    }
    // grey23, an 8-bit colour
    let code = match colors.system {
        ColorSystem::Standard => "90".to_string(),
        _ => "38;5;237".to_string(),
    };
    out.push_str(&format!("\x1b[{code}m{back}\x1b[0m"));
    out
}

/// `text` cut to `width` characters with an ellipsis, like rich's `overflow="ellipsis"`.
fn ellipsis(text: &str, width: usize) -> String {
    if text.chars().count() <= width {
        return text.to_string();
    }
    if width == 0 {
        return String::new();
    }
    let mut cut: String = text.chars().take(width - 1).collect();
    cut.push('…');
    cut
}

/// The lines of the bars (`ProgressBars.render()`): a grid of the label, the bar, how far
/// it is, the time since the search started and the file or the regex, one space between
/// the columns, and only the last column cut if the lines are wider than the terminal.
fn lines(state: &State, seconds: u64, width: usize, colors: Colors) -> Vec<String> {
    if !state.seen {
        return vec![styled("Searching...", &LABEL, colors)];
    }
    // Narrower bars on a narrow terminal, to leave room for the names
    let bar_width = (width / 4).clamp(10, BAR_WIDTH);
    let time = elapsed(seconds);
    // One regex is 1% if there are 100 regexes to search for in the file
    let total = state.regexes.max(1);
    let done = if state.regexes > 0 {
        state.regexes_done
    } else {
        1
    };
    let mut rows: Vec<(&str, usize, usize, String, String, String)> = Vec::new();
    if state.files > 1 {
        rows.push((
            "Files",
            state.files_done,
            state.files,
            format!("{}/{}", state.files_done, state.files),
            time.clone(),
            printable(&state.location),
        ));
    }
    rows.push((
        "Regexes",
        done,
        total,
        format!("{}%", 100 * done / total),
        if state.files > 1 { String::new() } else { time },
        printable(state.regex.unwrap_or("")),
    ));
    let label_width = rows.iter().map(|row| row.0.len()).max().unwrap_or(0);
    let count_width = rows.iter().map(|row| row.3.len()).max().unwrap_or(0);
    let time_width = rows.iter().map(|row| row.4.len()).max().unwrap_or(0);
    let used = label_width + bar_width + count_width + time_width + 4;
    let name_width = width.saturating_sub(used + 1).max(1);
    rows.into_iter()
        .map(|(label, completed, total, count, time, name)| {
            let mut line = styled(&format!("{label:<label_width$}"), &LABEL, colors);
            line.push(' ');
            line.push_str(&bar(completed, total, bar_width, colors));
            line.push_str(&format!(" {count:>count_width$} {time:<time_width$} "));
            line.push_str(&ellipsis(&name, name_width));
            line
        })
        .collect()
}

impl Bars {
    /// Bars on `target`, for a terminal `width` columns wide, shown after [`DELAY`].
    pub(crate) fn start(target: Target, width: usize, colors: Colors) -> Bars {
        let draw_target = move || match target {
            Target::Stdout => ProgressDrawTarget::stdout(),
            Target::Stderr => ProgressDrawTarget::stderr(),
        };
        Bars::start_on(draw_target, width, colors)
    }

    /// Bars drawn on the target that `draw_target` makes once they appear.
    fn start_on(
        draw_target: impl FnOnce() -> ProgressDrawTarget + Send + 'static,
        width: usize,
        colors: Colors,
    ) -> Bars {
        let state = Arc::new(Mutex::new(State::default()));
        let done = Arc::new((Mutex::new(false), Condvar::new()));
        let multi = MultiProgress::with_draw_target(ProgressDrawTarget::hidden());
        let ticker = {
            let (state, done, multi) = (state.clone(), done.clone(), multi.clone());
            std::thread::spawn(move || {
                let (lock, condvar) = &*done;
                let wait = |timeout| {
                    let finished = lock.lock().unwrap_or_else(|e| e.into_inner());
                    let (finished, _) = condvar
                        .wait_timeout_while(finished, timeout, |finished| !*finished)
                        .unwrap_or_else(|e| e.into_inner());
                    *finished
                };
                let started = Instant::now();
                if wait(DELAY) {
                    return;
                }
                multi.set_draw_target(draw_target());
                let style = ProgressStyle::with_template("{msg}").expect("valid template");
                let mut shown: Vec<ProgressBar> = Vec::new();
                loop {
                    let latest = state.lock().unwrap_or_else(|e| e.into_inner()).clone();
                    let lines = lines(&latest, started.elapsed().as_secs(), width, colors);
                    while shown.len() < lines.len() {
                        // A files bar appears above the regexes bar
                        let bar = ProgressBar::new(1).with_style(style.clone());
                        shown.insert(
                            0,
                            match shown.first() {
                                Some(first) => multi.insert_before(first, bar),
                                None => multi.add(bar),
                            },
                        );
                    }
                    let offset = shown.len() - lines.len();
                    for (bar, line) in shown[offset..].iter().zip(lines) {
                        bar.set_message(line);
                    }
                    if wait(REFRESH) {
                        break;
                    }
                }
                for bar in &shown {
                    bar.finish_and_clear();
                }
                let _ = multi.clear();
            })
        };
        Bars {
            state,
            multi,
            done,
            ticker: Some(ticker),
        }
    }

    /// The progress callback: keeps the latest progress, which is drawn 10 times a second.
    pub(crate) fn update(&self, progress: Progress<'_>) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        state.seen = true;
        if state.location != progress.location {
            state.location = progress.location.to_string();
        }
        state.files_done = progress.files_done;
        state.files = progress.files;
        state.regexes_done = progress.regexes_done;
        state.regexes = progress.regexes;
        state.regex = progress.regex;
    }

    /// Runs `print` with the bars hidden, so that its output goes above them.
    pub(crate) fn suspend<R>(&self, print: impl FnOnce() -> R) -> R {
        self.multi.suspend(print)
    }

    /// Removes the bars.
    pub(crate) fn finish(mut self) {
        self.stop();
    }

    fn stop(&mut self) {
        let (lock, condvar) = &*self.done;
        *lock.lock().unwrap_or_else(|e| e.into_inner()) = true;
        condvar.notify_all();
        if let Some(ticker) = self.ticker.take() {
            let _ = ticker.join();
        }
    }
}

impl Drop for Bars {
    fn drop(&mut self) {
        self.stop();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(files: usize, regexes_done: usize, regex: &'static str) -> State {
        State {
            seen: true,
            location: "fixtures/test/file".into(),
            files_done: 1,
            files,
            regexes_done,
            regexes: 150,
            regex: Some(regex),
        }
    }

    #[test]
    fn lines_like_rich() {
        let plain = Colors::PLAIN;
        assert_eq!(lines(&State::default(), 0, 80, plain), ["Searching..."]);
        // One file: the regexes bar with the time; 80 columns give 20-character bars
        assert_eq!(
            lines(
                &state(1, 75, "Uniform Resource Locator (URL)"),
                3,
                80,
                plain
            ),
            [format!(
                "Regexes {}{} 50% 0:00:03 Uniform Resource Locator (URL)",
                "━".repeat(10),
                " ".repeat(10)
            )]
        );
        // Several files: the files bar first, with the time, and the regexes bar
        let two = lines(&state(2, 150, "URL"), 61, 80, plain);
        assert_eq!(
            two,
            [
                format!(
                    "Files   {}{}  1/2 0:01:01 fixtures/test/file",
                    "━".repeat(10),
                    " ".repeat(10)
                ),
                format!("Regexes {} 100%         URL", "━".repeat(20)),
            ]
        );
        // A name that doesn't fit is cut with an ellipsis, one column short of the width
        let narrow = lines(&state(1, 0, "Uniform Resource Locator (URL)"), 0, 50, plain);
        assert_eq!(narrow[0].chars().count(), 49);
        assert!(narrow[0].ends_with(" Uniform Resource…"), "{narrow:?}");
    }

    #[test]
    fn rich_bar() {
        let colors = Colors {
            system: ColorSystem::TrueColor,
            no_color: false,
        };
        assert_eq!(
            bar(1, 4, 4, colors),
            "\x1b[38;2;249;38;114m━\x1b[0m\x1b[38;5;237m╺━━\x1b[0m"
        );
        assert_eq!(bar(3, 8, 4, colors).matches('╸').count(), 1);
        assert_eq!(bar(4, 4, 4, colors), "\x1b[38;2;114;156;31m━━━━\x1b[0m");
    }

    /// A terminal that records what is written on it.
    #[derive(Debug, Clone, Default)]
    struct Recorder(Arc<Mutex<String>>);

    impl indicatif::TermLike for Recorder {
        fn width(&self) -> u16 {
            80
        }
        fn move_cursor_up(&self, _: usize) -> std::io::Result<()> {
            Ok(())
        }
        fn move_cursor_down(&self, _: usize) -> std::io::Result<()> {
            Ok(())
        }
        fn move_cursor_right(&self, _: usize) -> std::io::Result<()> {
            Ok(())
        }
        fn move_cursor_left(&self, _: usize) -> std::io::Result<()> {
            Ok(())
        }
        fn write_line(&self, line: &str) -> std::io::Result<()> {
            self.0.lock().unwrap().push_str(&format!("{line}\n"));
            Ok(())
        }
        fn write_str(&self, text: &str) -> std::io::Result<()> {
            self.0.lock().unwrap().push_str(text);
            Ok(())
        }
        fn clear_line(&self) -> std::io::Result<()> {
            Ok(())
        }
        fn flush(&self) -> std::io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn bars_appear_after_half_a_second() {
        let terminal = Recorder::default();
        let target = terminal.clone();
        let started = Instant::now();
        let bars = Bars::start_on(
            move || ProgressDrawTarget::term_like(Box::new(target)),
            80,
            Colors::PLAIN,
        );
        bars.update(Progress {
            location: "big.log",
            files_done: 0,
            files: 1,
            regexes_done: 3,
            regexes: 10,
            regex: Some("Uniform Resource Locator (URL)"),
        });
        std::thread::sleep(Duration::from_millis(300));
        assert_eq!(*terminal.0.lock().unwrap(), "", "nothing before {DELAY:?}");
        while started.elapsed() < DELAY + Duration::from_millis(400) {
            std::thread::sleep(Duration::from_millis(50));
        }
        let drawn = terminal.0.lock().unwrap().clone();
        assert!(drawn.contains("Regexes"), "{drawn:?}");
        assert!(
            drawn.contains("30% 0:00:00 Uniform Resource Locator (URL)"),
            "{drawn:?}"
        );
        bars.finish();
    }

    #[test]
    fn bars_finish_before_the_delay() {
        // Nothing is drawn, and finishing doesn't wait for the delay
        let started = Instant::now();
        let bars = Bars::start(Target::Stderr, 80, Colors::PLAIN);
        bars.update(Progress {
            location: "text",
            files_done: 0,
            files: 1,
            regexes_done: 0,
            regexes: 10,
            regex: Some("URL"),
        });
        bars.finish();
        assert!(started.elapsed() < DELAY);
        assert_eq!(printable("a\x1b[1mb\u{85}"), "a[1mb");
    }
}
