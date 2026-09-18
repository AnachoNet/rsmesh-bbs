"""Shared admin terminal UI helpers for core and module admin extensions."""

from rich.console import Console

from .config_init import get_board_name
from .version import VERSION

DISPLAY_COLUMNS = 80
DISPLAY_LINES = 24
SEPARATOR_COLUMNS = 79
HEADER_TITLE_LINE = 1
HEADER_SEPARATOR_LINE = 2
HEADER_BLANK_LINE = 3
CONTENT_START_LINE = 4
CONTENT_END_LINE = 21
MENU_SEPARATOR_LINE = 22
MENU_INPUT_LINE = 23
PAGE_HEADER_LINE_COUNT = 3
MENU_OPTION_INDENT = 5
# Confirmation/action messages: 5-column indent + 70 text + 5-column right margin.
MESSAGE_WRAP_TEXT_WIDTH = 70
CONTENT_LINES_PER_PAGE = CONTENT_END_LINE - CONTENT_START_LINE + 1

console = Console(width=DISPLAY_COLUMNS, force_terminal=True)


def clear_screen():
    console.clear()


def print_bold(message):
    console.print(message, style="bold", overflow="crop", no_wrap=True)


def print_separator():
    console.print("=" * SEPARATOR_COLUMNS, style="bold", overflow="crop", no_wrap=True)


def input_bold(prompt):
    console.print(prompt, style="bold", end="", markup=False)
    return input()


def format_header_line(
    header: str,
    version_text: str = VERSION,
    line_width: int = SEPARATOR_COLUMNS,
) -> str:
    """Format a header with version right-aligned; last character at column line_width."""
    if len(version_text) >= line_width:
        return version_text[-line_width:]
    header_part = header[: line_width - len(version_text)]
    padding = line_width - len(header_part) - len(version_text)
    return f"{header_part}{' ' * padding}{version_text}"


def print_header_line(header: str) -> None:
    console.print(
        format_header_line(header),
        style="bold",
        overflow="crop",
        no_wrap=True,
        markup=False,
    )


def print_page_header(menu_name=None):
    board_name = get_board_name()
    if menu_name:
        header = f"{board_name} SysAdmin : {menu_name}"
    else:
        header = f"{board_name} SysAdmin"

    print_header_line(header)
    print_separator()
    console.print()


def begin_data_display(page_title):
    print_page_header(page_title)


def begin_form_screen(page_title):
    clear_screen()
    begin_data_display(page_title)


def wrap_message_text(text, max_width):
    """Wrap a single line of plain text to fit within max_width (word-aware).

    Words are never broken across lines; a word longer than max_width occupies
    its own line whole.
    """
    if max_width <= 0:
        return [text or ""]
    text = text or ""
    if len(text) <= max_width:
        return [text]

    lines = []
    words = text.split()
    current = []
    current_len = 0

    def flush():
        nonlocal current, current_len
        if current:
            lines.append(" ".join(current))
            current = []
            current_len = 0

    for word in words:
        if not current:
            if len(word) <= max_width:
                current = [word]
                current_len = len(word)
            else:
                lines.append(word)
            continue
        candidate = current_len + 1 + len(word)
        if len(word) <= max_width and candidate <= max_width:
            current.append(word)
            current_len = candidate
        elif len(word) <= max_width:
            flush()
            current = [word]
            current_len = len(word)
        else:
            flush()
            lines.append(word)
    flush()
    return lines or [""]


def message_lines_for_display(
    message,
    indent=MENU_OPTION_INDENT,
    text_width=MESSAGE_WRAP_TEXT_WIDTH,
):
    """Return display lines for a message, wrapped to the admin message width."""
    prefix = " " * indent
    max_text_width = max(1, text_width)
    display_lines = []
    raw_lines = (message or "").splitlines()
    if not raw_lines:
        raw_lines = [""]
    for raw in raw_lines:
        if raw == "":
            display_lines.append(None)
            continue
        for wrapped in wrap_message_text(raw, max_text_width):
            display_lines.append(prefix + wrapped)
    return display_lines


def render_message_body(message):
    """Print a message using the standard admin indent and line wrapping."""
    for line in message_lines_for_display(message):
        if line is None:
            console.print()
        else:
            print_bold(line)


def finish_action_message(message, page_title):
    clear_screen()
    begin_data_display(page_title)
    display_lines = message_lines_for_display(message)
    render_message_body(message)
    lines_used = PAGE_HEADER_LINE_COUNT + len(display_lines)
    _pad_to_line(MENU_SEPARATOR_LINE, lines_used)
    print_separator()


def _chunk_lines(lines, page_size):
    if not lines:
        return []
    return [lines[i:i + page_size] for i in range(0, len(lines), page_size)]


def _render_display_lines(lines):
    for line in lines:
        if line == '':
            console.print()
        else:
            print_bold(line[:DISPLAY_COLUMNS])


def _print_no_data(message):
    render_message_body(message)


def _pad_to_line(target_line, lines_used):
    padding = target_line - lines_used - 1
    if padding > 0:
        console.print("\n" * padding, end="")


def paginate_display(
    page_title,
    lines,
    *,
    empty_message="No data found.",
    select_prompt=None,
    select_empty_exits=False,
    hotkeys=None,
):
    back_footer = "Enter or X=back:"
    if not lines:
        clear_screen()
        begin_data_display(page_title)
        _print_no_data(empty_message)
        lines_used = PAGE_HEADER_LINE_COUNT + 1
        _pad_to_line(MENU_SEPARATOR_LINE, lines_used)
        print_separator()
        if select_prompt:
            prompt = select_prompt if select_empty_exits else f"Enter=continue  {select_prompt}"
        else:
            prompt = back_footer
        choice = input_bold(prompt).strip()
        if select_prompt:
            if choice.upper() == 'X' or (select_empty_exits and not choice):
                clear_screen()
                return 0, 'X'
            if choice:
                clear_screen()
                return 0, choice
            clear_screen()
            return False
        if choice.upper() == 'X' or not choice:
            clear_screen()
            return False
        clear_screen()
        return False

    pages = _chunk_lines(lines, CONTENT_LINES_PER_PAGE)
    page_index = 0

    while True:
        clear_screen()
        begin_data_display(page_title)
        page_lines = pages[page_index]
        _render_display_lines(page_lines)
        lines_used = PAGE_HEADER_LINE_COUNT + len(page_lines)
        _pad_to_line(MENU_SEPARATOR_LINE, lines_used)
        print_separator()

        page_info = f"Page {page_index + 1}/{len(pages)}"
        if select_prompt:
            prompt = f"{page_info}  N=next  P=prev  {select_prompt}"
        else:
            prompt = f"{page_info}  N=next  P=prev  {back_footer}"

        choice = input_bold(prompt).strip()
        choice_key = choice.upper()

        if hotkeys and choice_key in hotkeys:
            hotkeys[choice_key]()
            continue

        if choice_key == 'N':
            if page_index < len(pages) - 1:
                page_index += 1
            continue
        if choice_key == 'P':
            if page_index > 0:
                page_index -= 1
            continue

        if select_prompt:
            if choice_key == 'X' or (select_empty_exits and not choice):
                clear_screen()
                return len(page_lines), 'X'
            if choice:
                clear_screen()
                return len(page_lines), choice
            continue

        if choice_key == 'X' or not choice:
            clear_screen()
            return False
        continue


def record_detail_lines(fields):
    lines = []
    for label, value in fields:
        text = str(value) if value is not None else ""
        if "\n" in text:
            lines.append(f"  {label} :")
            for content_line in text.splitlines():
                lines.append(f"    {content_line}")
        else:
            lines.append(f"  {label} : {text}")
    return lines


def record_detail_prompt(lines_used):
    _pad_to_line(MENU_SEPARATOR_LINE, lines_used)
    print_separator()
    input_bold("Enter or X=back: ")
    clear_screen()


def display_record_detail(page_title, detail_lines, not_found_message=None):
    clear_screen()
    begin_data_display(page_title)
    if detail_lines is None:
        _print_no_data(not_found_message or "Record not found.")
        record_detail_prompt(PAGE_HEADER_LINE_COUNT + 1)
        return
    _render_display_lines(detail_lines)
    record_detail_prompt(PAGE_HEADER_LINE_COUNT + len(detail_lines))


def list_with_record_view(page_title, list_lines_fn, empty_message, view_fn):
    result = paginate_display(
        page_title,
        list_lines_fn(),
        empty_message=empty_message,
        select_prompt="Enter ID to view or X=back:",
        select_empty_exits=True,
    )
    if result is False:
        return False
    _, choice = result
    if choice and choice.upper() != 'X':
        view_fn(choice.strip())
    return False
