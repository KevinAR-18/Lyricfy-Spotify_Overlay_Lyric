from lyric_overlay.lyrics import (
    LyricsRepository,
    artist_parts,
    normalize_match_text,
    parse_lrc,
    sanitize_filename,
)


class TestSanitizeFilename:
    def test_removes_invalid_windows_characters(self):
        assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"

    def test_trims_surrounding_whitespace(self):
        assert sanitize_filename("  Coldplay - Yellow  ") == "Coldplay - Yellow"

    def test_keeps_valid_characters(self):
        assert sanitize_filename("Beyoncé - Déjà Vu") == "Beyoncé - Déjà Vu"


class TestNormalizeMatchText:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_match_text("Hello, World!") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_match_text("  multiple   spaces  ") == "multiple spaces"

    def test_casefold_unicode(self):
        assert normalize_match_text("STRASSE") == "strasse"


class TestArtistParts:
    def test_splits_on_common_separators(self):
        assert artist_parts("A & B, C") == {"a", "b", "c"}

    def test_splits_feat_and_with(self):
        assert artist_parts("Artist feat. Guest with Other") == {
            "artist",
            "guest",
            "other",
        }

    def test_single_artist(self):
        assert artist_parts("Coldplay") == {"coldplay"}


class TestParseLrc:
    def test_parses_basic_lines_sorted(self):
        text = "[00:13.50]second\n[00:10.00]first"
        lyrics = parse_lrc(text, source="test")
        assert lyrics.source == "test"
        assert [line.text for line in lyrics.lines] == ["first", "second"]
        assert [line.timestamp_ms for line in lyrics.lines] == [10000, 13500]

    def test_two_digit_fraction_padded_to_ms(self):
        lyrics = parse_lrc("[00:10.05]x", source="t")
        assert lyrics.lines[0].timestamp_ms == 10050

    def test_three_digit_fraction(self):
        lyrics = parse_lrc("[01:02.345]x", source="t")
        assert lyrics.lines[0].timestamp_ms == 62345

    def test_multiple_timestamps_same_line(self):
        lyrics = parse_lrc("[00:01.00][00:02.00]repeat", source="t")
        assert [line.timestamp_ms for line in lyrics.lines] == [1000, 2000]
        assert all(line.text == "repeat" for line in lyrics.lines)

    def test_skips_lines_without_timestamp(self):
        lyrics = parse_lrc("no timestamp here\n[00:01.00]kept", source="t")
        assert len(lyrics.lines) == 1
        assert lyrics.lines[0].text == "kept"

    def test_skips_empty_lyric_text(self):
        lyrics = parse_lrc("[00:01.00]   ", source="t")
        assert lyrics.is_empty


class TestLocalLrcMatchScore:
    def _score(self, requested_artist, requested_title, file_artist, file_title):
        return LyricsRepository._local_lrc_match_score(
            requested_artist=normalize_match_text(requested_artist),
            requested_artist_parts=artist_parts(requested_artist),
            requested_title=normalize_match_text(requested_title),
            file_artist=normalize_match_text(file_artist),
            file_artist_parts=artist_parts(file_artist),
            file_title=normalize_match_text(file_title),
        )

    def test_title_mismatch_scores_zero(self):
        assert self._score("Coldplay", "Yellow", "Coldplay", "Fix You") == 0

    def test_exact_artist_match_scores_100(self):
        assert self._score("Coldplay", "Yellow", "Coldplay", "Yellow") == 100

    def test_substring_artist_match_scores_90(self):
        assert self._score("Coldplay", "Yellow", "Coldplay Live", "Yellow") == 90

    def test_shared_artist_part_scores_80(self):
        score = self._score("A & B", "Song", "B & C", "Song")
        assert score == 80

    def test_unrelated_artist_scores_zero(self):
        assert self._score("Coldplay", "Yellow", "Radiohead", "Yellow") == 0
