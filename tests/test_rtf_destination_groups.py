"""The dependency-free RTF fallback must drop non-content destination groups.

`strip_rtf_fallback` deleted control *words* and then removed all braces, so
everything inside `\\fonttbl`, `\\colortbl`, `\\stylesheet`, `\\*\\generator` and
`\\info` survived as literal text: font names, style names, the generator
string, and the document title and author all landed in the extracted book text.

That junk pollutes the Step 8 glossary, shifts `words` / `estimated_tokens` in
metadata.json, and leaks `\\info` metadata into a file the user may publish as a
skill. Only the fallback is affected — `striprtf` handles this correctly — so it
was also a divergence between the two RTF paths.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.rtf import strip_rtf_fallback

# A realistic header: font table, colour table, stylesheet, generator, \info.
FULL_HEADER_RTF = (
    r"{\rtf1\ansi\ansicpg1252\deff0"
    "\n" r"{\fonttbl{\f0\fnil\fcharset0 Calibri;}{\f1\fswiss Helvetica Neue;}}"
    "\n" r"{\colortbl;\red255\green0\blue0;\red0\green0\blue255;}"
    "\n" r"{\stylesheet{\s0\snext0 Normal;}{\s1\sbasedon0 heading 1;}}"
    "\n" r"{\*\generator Riched20 10.0.19041;}"
    "\n" r"{\info{\title Secret Draft}{\author Jane Roe}}"
    "\n" r"\pard\f0\fs24 Chapter 1\par"
    "\n" r"Real body text here.\par}"
)

LEAK_PROBES = [
    "Calibri",
    "Helvetica Neue",
    "Normal",
    "heading 1",
    "Riched20",
    "Secret Draft",
    "Jane Roe",
]


class TestDestinationGroupsDropped:
    @pytest.mark.parametrize("probe", LEAK_PROBES)
    def test_probe_does_not_leak(self, probe):
        assert probe not in strip_rtf_fallback(FULL_HEADER_RTF)

    def test_body_text_survives(self):
        out = strip_rtf_fallback(FULL_HEADER_RTF)
        assert "Chapter 1" in out
        assert "Real body text here." in out

    def test_chapter_heading_is_on_its_own_line(self):
        lines = [ln for ln in strip_rtf_fallback(FULL_HEADER_RTF).splitlines()
                 if ln.strip()]
        assert lines[0].strip() == "Chapter 1"

    def test_info_metadata_not_exposed(self):
        """\\info carries title/author (and can carry comments and revisions)."""
        rtf = r"{\rtf1{\info{\title Confidential}{\author A. Person}}Body.\par}"
        out = strip_rtf_fallback(rtf)
        assert out.strip() == "Body."

    def test_pict_binary_payload_dropped(self):
        rtf = (r"{\rtf1{\pict\wmetafile8 0102030405060708090a0b0c}"
               r"Caption here.\par}")
        out = strip_rtf_fallback(rtf)
        assert "0102030405" not in out
        assert "Caption here." in out

    def test_nested_group_inside_skipped_group(self):
        rtf = (r"{\rtf1 {\stylesheet{\s1\sbasedon0{\*\ud junk}heading 1;}}"
               r"Body.\par}")
        out = strip_rtf_fallback(rtf)
        assert "heading 1" not in out
        assert "junk" not in out
        assert "Body." in out

    def test_content_group_after_skipped_group_is_kept(self):
        rtf = r"{\rtf1{\fonttbl{\f0 Arial;}}{\b Bold text}\par tail\par}"
        out = strip_rtf_fallback(rtf)
        assert "Arial" not in out
        assert "Bold text" in out
        assert "tail" in out


class TestIgnorableDestinations:
    """Per the RTF spec an unknown "\\*" destination must be skipped whole."""

    def test_unknown_star_destination_skipped(self):
        rtf = r"{\rtf1{\*\somevendorext payload text}Body.\par}"
        out = strip_rtf_fallback(rtf)
        assert "payload text" not in out
        assert "Body." in out

    def test_field_keeps_result_drops_instruction(self):
        rtf = (r"{\rtf1 See {\field{\*\fldinst HYPERLINK bm1}"
               r"{\fldrslt chapter 4}} now.\par}")
        out = strip_rtf_fallback(rtf)
        assert "HYPERLINK" not in out
        assert "See chapter 4 now." in out.replace("\n", " ")


class TestEscapedLiteralsSurvive:
    """"\\{", "\\}" and "\\\\" are text, not delimiters or control symbols."""

    def test_escaped_braces_become_literal_braces(self):
        out = strip_rtf_fallback(r"{\rtf1 A set \{a, b\} of items.\par}")
        assert "{a, b}" in out

    def test_escaped_backslash_preserved(self):
        out = strip_rtf_fallback(r"{\rtf1 Path C:\\temp\\out\par}")
        assert r"C:\temp\out" in out


class TestExistingBehaviourPreserved:
    """Regression net for the \\uN decoding added in #52."""

    _BS = "\\"

    def test_unicode_escapes_still_decode(self):
        text = (r"{\rtf1{\fonttbl{\f0 Arial;}}"
                + self._BS + "u8220" + self._BS + "'93Hi"
                + self._BS + "u8221" + self._BS + "'94" + r"\par}")
        out = strip_rtf_fallback(text)
        assert "\u201cHi\u201d" in out
        assert "Arial" not in out

    def test_par_and_tab_still_convert(self):
        out = strip_rtf_fallback(r"{\rtf1 a\par b\tab c}")
        assert "\n" in out
        assert "\t" in out


class TestMalformedInputIsNotTruncated:
    def test_unterminated_skipped_group_falls_back(self):
        """Losing the whole body would be worse than leaking table residue."""
        rtf = r"{\rtf1{\fonttbl{\f0 Arial; Body text never closed"
        out = strip_rtf_fallback(rtf)
        assert "Body text never closed" in out
