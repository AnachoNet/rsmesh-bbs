from rsmesh_bbs import admin_ui


def test_wrap_message_text_short_line():
    assert admin_ui.wrap_message_text("Hello", 40) == ["Hello"]


def test_wrap_message_text_word_wrap():
    text = "Exported configuration to /opt/rsmesh-bbs/config.yml (42 known settings)."
    lines = admin_ui.wrap_message_text(text, 40)
    assert len(lines) > 1
    assert all(len(line) <= 40 for line in lines)
    assert " ".join(lines) == text


def test_message_lines_for_display_respects_screen_width():
    text = "A" * 100
    lines = admin_ui.message_lines_for_display(text)
    assert len(lines) > 1
    assert all(len(line) <= admin_ui.DISPLAY_COLUMNS for line in lines if line is not None)


def test_message_lines_for_display_preserves_blank_lines():
    lines = admin_ui.message_lines_for_display("Line one\n\nLine two")
    assert lines[0].endswith("Line one")
    assert lines[1] is None
    assert lines[2].endswith("Line two")
