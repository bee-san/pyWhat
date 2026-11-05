//! The table of `--format pretty`, drawn with comfy-table in the look of the Python CLI's
//! rich table (`box.HEAVY_HEAD`, a line between rows, padding of one space). When the
//! table fits, it has the same columns widths as rich's; when it doesn't, comfy-table
//! wraps the cells its own way, but the cells are the same.

use super::style::{ColorSystem, Colors};
use comfy_table::{
    Attribute, Cell, Color, ContentArrangement, ContentLineStyle, LineStyle, Table, TableStyle,
};

/// rich's `box.HEAVY_HEAD`.
const HEAVY_HEAD: TableStyle = TableStyle::new()
    .top_border(LineStyle::new('┏', '━', '┳', '┓'))
    .header_lines(ContentLineStyle::new('┃', '┃', '┃'))
    .header_separator(LineStyle::new('┡', '━', '╇', '┩'))
    .content_lines(ContentLineStyle::new('│', '│', '│'))
    .row_separator(LineStyle::new('├', '─', '┼', '┤'))
    .bottom_border(LineStyle::new('└', '─', '┴', '┘'));

/// The style of the header (`header_style="bold #D7Afff"`).
fn header_cell(text: &str, colors: Colors) -> Cell {
    let cell = Cell::new(text);
    if colors.is_plain() {
        return cell;
    }
    let cell = cell.add_attribute(Attribute::Bold);
    if colors.no_color {
        return cell;
    }
    match colors.system {
        ColorSystem::TrueColor => cell.fg(Color::Rgb {
            r: 0xD7,
            g: 0xAF,
            b: 0xFF,
        }),
        ColorSystem::EightBit => cell.fg(Color::AnsiValue(183)),
        ColorSystem::Standard | ColorSystem::None => cell.fg(Color::Grey),
    }
}

/// The table, `width` columns wide at most, without a line break at the end.
pub(crate) fn render(
    header: &[&str],
    rows: &[Vec<String>],
    width: usize,
    colors: Colors,
) -> String {
    let mut table = Table::new();
    table
        .load_style(HEAVY_HEAD)
        .set_content_arrangement(ContentArrangement::Dynamic)
        .set_width(width.min(u16::MAX as usize) as u16);
    if colors.is_plain() {
        table.force_no_tty();
    } else {
        table.enforce_styling();
    }
    table.set_header(header.iter().map(|text| header_cell(text, colors)));
    for row in rows {
        table.add_row(row.iter().map(Cell::new));
    }
    table.to_string()
}
