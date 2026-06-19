# tests/test_render.py
from marginalia.render import render, ANNOTATE_TAGS


def test_returns_page_and_element_map():
    page, elements = render("# Title\n\nFirst paragraph.", title="Doc")
    assert page.startswith("<!DOCTYPE html>")
    assert "<title>Doc</title>" in page
    # one h1 + one p annotated
    assert len(elements) == 2
    assert any(v == "Title" for v in elements.values())
    assert any(v == "First paragraph." for v in elements.values())


def test_every_annotatable_block_gets_a_data_cid():
    md = "## Heading\n\n- item one\n- item two\n\n> a quote"
    page, elements = render(md)
    # h2 + 2 li + blockquote = 4 annotated elements
    assert len(elements) == 4
    for cid in elements:
        assert f'data-cid="{cid}"' in page


def test_label_is_truncated_to_140_chars():
    long = "x" * 300
    page, elements = render(long)
    (label,) = elements.values()
    assert len(label) == 140


def test_empty_blocks_are_not_annotated():
    page, elements = render("Hello\n\n\n")
    assert len(elements) == 1  # just the one paragraph


def test_theme_and_js_are_embedded():
    page, _ = render("hi")
    assert "<style>" in page and "</style>" in page
    assert "<script>" in page and "</script>" in page


def test_annotate_tags_constant_is_exported():
    assert "p" in ANNOTATE_TAGS and "blockquote" in ANNOTATE_TAGS and "td" in ANNOTATE_TAGS


def test_inner_p_of_blockquote_is_not_annotated():
    page, elements = render("> just a quote")
    # only the blockquote is annotated, not the <p> markdown nests inside it
    assert len(elements) == 1
    assert "just a quote" in next(iter(elements.values()))
