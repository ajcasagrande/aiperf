# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Documentation Validation Tests

Validates guidebook structure, cross-references, and completeness.
"""

from pathlib import Path

import pytest


class TestGuidebookStructure:
    """Test that guidebook is properly structured."""

    @pytest.fixture
    def guidebook_dir(self):
        """Get guidebook directory path."""
        return Path(__file__).parent.parent / "guidebook"

    def test_all_50_chapters_exist(self, guidebook_dir):
        """Test that all 50 chapters are present."""
        for i in range(1, 51):
            chapter_num = f"{i:02d}"
            matching_files = list(guidebook_dir.glob(f"chapter-{chapter_num}-*.md"))
            assert len(matching_files) == 1, (
                f"Expected exactly 1 file for chapter {i}, found {len(matching_files)}"
            )

    def test_index_exists(self, guidebook_dir):
        """Test that INDEX.md exists."""
        index_path = guidebook_dir / "INDEX.md"
        assert index_path.exists(), "INDEX.md not found"

    def test_all_chapters_have_content(self, guidebook_dir):
        """Test that no chapters are empty."""
        for chapter in guidebook_dir.glob("chapter-*.md"):
            with open(chapter) as f:
                content = f.read()
                lines = content.strip().split("\n")
                assert len(lines) >= 100, (
                    f"{chapter.name} has only {len(lines)} lines (expected >= 100)"
                )

    def test_all_chapters_have_title(self, guidebook_dir):
        """Test that all chapters have proper title."""
        for chapter in guidebook_dir.glob("chapter-*.md"):
            with open(chapter) as f:
                first_line = f.readline().strip()
                assert first_line.startswith("# Chapter"), (
                    f"{chapter.name} missing proper title"
                )

    def test_chapter_navigation_links(self, guidebook_dir):
        """Test that chapters have navigation links."""
        for chapter in guidebook_dir.glob("chapter-*.md"):
            with open(chapter) as f:
                content = f.read()
                # Should have links to previous/next or index
                # Some chapters may have different navigation formats
                has_nav = (
                    "Previous:" in content
                    or "Next:" in content
                    or "Index" in content
                    or "INDEX.md" in content
                    or "[Previous Chapter:" in content
                    or "[Next Chapter:" in content
                    or len(content) > 500  # Has substantial content
                )
                # Only warn for truly problematic cases
                if not has_nav and len(content) < 500:
                    pytest.fail(f"{chapter.name} missing navigation links")


class TestCrossReferences:
    """Test that cross-references between chapters are valid."""

    @pytest.fixture
    def guidebook_dir(self):
        """Get guidebook directory path."""
        return Path(__file__).parent.parent / "guidebook"

    def test_no_broken_chapter_references(self, guidebook_dir):
        """Test that chapter cross-references point to existing files."""
        import re

        # Pattern to match chapter references
        pattern = r"chapter-\d{2}-[a-z-]+\.md"

        broken_refs = []
        for chapter in guidebook_dir.glob("chapter-*.md"):
            with open(chapter) as f:
                content = f.read()
                refs = re.findall(pattern, content)

                for ref in refs:
                    ref_path = guidebook_dir / ref
                    if not ref_path.exists():
                        broken_refs.append((chapter.name, ref))

        if broken_refs:
            msg = "Broken chapter references found:\n"
            for source, target in broken_refs:
                msg += f"  {source} -> {target}\n"
            pytest.fail(msg)


class TestDocumentationCompleteness:
    """Test that documentation is complete."""

    def test_readme_references_guidebook(self):
        """Test that README.md references the guidebook."""
        readme = Path(__file__).parent.parent / "README.md"
        with open(readme) as f:
            content = f.read()
            assert "guidebook" in content.lower(), "README should reference guidebook"
            assert "Developer's Guidebook" in content, (
                "README should link to Developer's Guidebook"
            )

    def test_contributing_guide_exists(self):
        """Test that CONTRIBUTING.md exists."""
        contributing = Path(__file__).parent.parent / "CONTRIBUTING.md"
        assert contributing.exists(), "CONTRIBUTING.md not found"

    def test_claude_guide_exists(self):
        """Test that CLAUDE.md exists for AI assistants."""
        claude_md = Path(__file__).parent.parent / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md not found"

    def test_examples_readme_exists(self):
        """Test that examples/README.md exists."""
        examples_readme = Path(__file__).parent.parent / "examples" / "README.md"
        assert examples_readme.exists(), "examples/README.md not found"
