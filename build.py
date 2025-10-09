#!/usr/bin/env python3
"""
Blog builder script
- Scans blogs/ and collections/ for .tex files
- Extracts git history for each file
- Generates HTML for all versions using pandoc
- Creates navigation for collections
- Generates index pages
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional
import re


class BlogBuilder:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.blogs_dir = base_dir / "blogs"
        self.collections_dir = base_dir / "collections"
        self.output_dir = base_dir / "docs"
        # Use UTC+8 timezone (China Standard Time)
        self.tz = timezone(timedelta(hours=8))

    def get_current_time(self):
        """Get current time in configured timezone"""
        return datetime.now(self.tz)

    def run(self):
        """Main build process"""
        print("Starting blog build...")

        # Create output directory
        self.output_dir.mkdir(exist_ok=True)

        # Create .nojekyll file for GitHub Pages
        (self.output_dir / ".nojekyll").touch()

        # Create dark mode CSS header for pandoc
        self.create_dark_mode_header()

        # Build regular blogs
        print("\n=== Building regular blogs ===")
        self.build_regular_blogs()

        # Build collections
        print("\n=== Building collections ===")
        self.build_collections()

        # Generate main index
        print("\n=== Generating main index ===")
        self.generate_main_index()

        print(f"\n✓ Build complete! Output in {self.output_dir}")

    def create_dark_mode_header(self):
        """Create dark mode CSS header file for pandoc"""
        dark_css = '''<style>
/* Code font - using web-safe fonts as fallback */
code, pre, pre code {
  font-family: 'CodeNewRoman Nerd Font', 'JetBrains Mono', 'Fira Code', Consolas, Monaco, monospace;
}

/* Light mode code blocks */
div.sourceCode {
  overflow-x: auto !important;
  max-width: 100%;
}
pre {
  background-color: #f5f5f5 !important;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 1em;
  overflow-x: auto !important;
  max-width: 100%;
  box-sizing: border-box;
}
pre.sourceCode {
  overflow-x: auto !important;
}
code {
  background-color: #f5f5f5;
  padding: 0.2em 0.4em;
  border-radius: 3px;
  white-space: pre !important;
  word-wrap: normal !important;
  overflow-wrap: normal !important;
}
pre code {
  background-color: transparent;
  padding: 0;
}
/* More specific selectors to override Pandoc defaults */
code.sourceCode {
  white-space: pre !important;
  word-wrap: normal !important;
  overflow-wrap: normal !important;
}
code.sourceCode > span {
  white-space: pre !important;
  display: inline !important;
}

/* Note/disclaimer style */
.note {
  font-size: 0.9em;
  font-style: italic;
  color: #666;
  background-color: #f9f9f9;
  border-left: 3px solid #ccc;
  padding: 0.5em 1em;
  margin: 1em 0;
}

@media (prefers-color-scheme: dark) {
  html { color: #e8e8e8; background-color: #1a1a1a; }
  body { color: #e8e8e8; background-color: #1a1a1a; }
  a { color: #58a6ff; }
  a:visited { color: #8e96f0; }
  h1, h2, h3, h4, h5, h6 { color: #e8e8e8; }
  code { background-color: #2d2d2d; color: #e8e8e8; }
  pre { background-color: #2d2d2d !important; border-color: #4a4a4a; }
  blockquote { border-left-color: #4a4a4a; color: #b0b0b0; }
  hr { background-color: #4a4a4a; border-top-color: #4a4a4a; }
  table, th, td, tbody { border-color: #4a4a4a; }
  .date, .meta { color: #a0a0a0; }
  header#title-block-header { border-bottom-color: #4a4a4a; }
  .note { color: #a0a0a0; background-color: #2a2a2a; border-left-color: #555; }
}
</style>'''

        with open(self.output_dir / ".dark-mode.html", 'w') as f:
            f.write(dark_css)

    def build_regular_blogs(self):
        """Build all regular blog posts"""
        if not self.blogs_dir.exists():
            print("No blogs directory found")
            return

        tex_files = sorted(self.blogs_dir.rglob("*.tex"))
        for tex_file in tex_files:
            print(f"Processing {tex_file.relative_to(self.base_dir)}")
            self.build_article(tex_file, is_collection=False)

    def build_collections(self):
        """Build all collections"""
        if not self.collections_dir.exists():
            print("No collections directory found")
            return

        for collection_dir in sorted(self.collections_dir.iterdir()):
            if not collection_dir.is_dir():
                continue

            collection_name = collection_dir.name
            print(f"\nProcessing collection: {collection_name}")

            # Get all tex files in collection, sorted
            tex_files = sorted(collection_dir.rglob("*.tex"))
            if not tex_files:
                continue

            # Build each article with navigation
            for i, tex_file in enumerate(tex_files):
                prev_file = tex_files[i-1] if i > 0 else None
                next_file = tex_files[i+1] if i < len(tex_files) - 1 else None

                nav_info = {
                    'collection_name': collection_name,
                    'prev': prev_file,
                    'next': next_file,
                    'index': i,
                    'total': len(tex_files)
                }

                print(f"  [{i+1}/{len(tex_files)}] {tex_file.name}")
                self.build_article(tex_file, is_collection=True, nav_info=nav_info)

            # Generate collection index
            self.generate_collection_index(collection_name, tex_files)

    def build_article(self, tex_file: Path, is_collection: bool = False, nav_info: dict = None):
        """Build a single article with all its versions from git history"""

        # Determine output directory
        if is_collection:
            rel_path = tex_file.relative_to(self.collections_dir)
            collection_name = rel_path.parts[0]  # First part is collection name
            article_name = tex_file.stem
            # Check if .tex file is in a folder with the same name
            if tex_file.parent.name == article_name:
                # collections/name/article/article.tex -> docs/collections/name/article/
                output_dir = self.output_dir / "collections" / collection_name / article_name
            else:
                # collections/name/article.tex -> docs/collections/name/article/
                output_dir = self.output_dir / "collections" / collection_name / article_name
        else:
            rel_path = tex_file.relative_to(self.blogs_dir)
            article_name = tex_file.stem
            # Check if .tex file is in a folder with the same name
            if tex_file.parent.name == article_name:
                # blogs/2025/article-name/article-name.tex -> docs/blogs/2025/article-name/
                output_dir = self.output_dir / "blogs" / rel_path.parent
            else:
                # blogs/2025/article-name.tex -> docs/blogs/2025/article-name/
                output_dir = self.output_dir / "blogs" / rel_path.parent / article_name

        output_dir.mkdir(parents=True, exist_ok=True)

        # Get git history
        versions = self.get_git_history(tex_file)

        # Pre-generate navigation files
        nav_top_file = None
        nav_bottom_file = None

        if nav_info:
            # For collections: full navigation with prev/next
            nav_top_html = self.generate_nav_html(nav_info, position='top')
            nav_top_file = output_dir / ".nav-top.html"
            with open(nav_top_file, 'w') as f:
                f.write(nav_top_html)

            nav_bottom_html = self.generate_nav_html(nav_info, position='bottom')
            nav_bottom_file = output_dir / ".nav-bottom.html"
            with open(nav_bottom_file, 'w') as f:
                f.write(nav_bottom_html)
        elif not is_collection:
            # For regular posts: simple back to home link
            nav_html = self.generate_simple_nav_html()
            nav_bottom_file = output_dir / ".nav-bottom.html"
            with open(nav_bottom_file, 'w') as f:
                f.write(nav_html)

        try:
            if not versions:
                # No git history, just use current file
                print(f"    No git history, using current version")
                self.pandoc_convert(tex_file, output_dir / "latest.html",
                                  article_name, self.get_current_time().strftime("%Y-%m-%d"),
                                  nav_top_file, nav_bottom_file)
            else:
                # Generate all historical versions
                for commit_hash, commit_date in versions:
                    # Use full timestamp for filename to avoid conflicts
                    # Format: 2025-10-04T18:28
                    version_timestamp = commit_date.replace(' ', 'T').split('+')[0].rsplit(':', 1)[0]
                    output_file = output_dir / f"{version_timestamp}.html"

                    # Get file content at this commit
                    try:
                        content = self.get_file_at_commit(tex_file, commit_hash)
                        # Display date in metadata
                        display_date = commit_date.split()[0]
                        self.pandoc_convert_content(content, output_file, article_name,
                                                   display_date, nav_top_file, nav_bottom_file)
                    except Exception as e:
                        print(f"    Warning: Failed to get version {version_timestamp}: {e}")

                # Generate latest.html from current working tree contents
                latest_date_str = versions[-1][1].split()[0]
                self.pandoc_convert(tex_file, output_dir / "latest.html",
                                   article_name, latest_date_str, nav_top_file, nav_bottom_file)
        finally:
            # Clean up nav files
            if nav_top_file and nav_top_file.exists():
                nav_top_file.unlink()
            if nav_bottom_file and nav_bottom_file.exists():
                nav_bottom_file.unlink()

        # Generate version index
        self.generate_version_index(output_dir, article_name, tex_file)

    def get_git_history(self, file_path: Path) -> List[Tuple[str, str]]:
        """Get git history for a file: [(commit_hash, commit_date), ...]"""
        try:
            # Check if file is in git
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(file_path)],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return []

            # Get commit history
            result = subprocess.run(
                ["git", "log", "--follow", "--format=%H %ci", "--", str(file_path)],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                check=True
            )

            versions = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        versions.append((parts[0], parts[1]))

            return list(reversed(versions))  # Oldest first

        except Exception as e:
            print(f"    Warning: git history error: {e}")
            return []

    def get_file_at_commit(self, file_path: Path, commit_hash: str) -> str:
        """Get file content at a specific commit"""
        # Git show needs relative path from repo root
        rel_path = file_path.relative_to(self.base_dir)
        result = subprocess.run(
            ["git", "show", f"{commit_hash}:{rel_path}"],
            cwd=self.base_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout

    def pandoc_convert(self, input_file: Path, output_file: Path,
                       title: str, date: str, nav_top_file: Path = None, nav_bottom_file: Path = None):
        """Convert tex file to HTML using pandoc"""
        with open(input_file, 'r') as f:
            content = f.read()
        self.pandoc_convert_content(content, output_file, title, date, nav_top_file, nav_bottom_file)

    def pandoc_convert_content(self, content: str, output_file: Path,
                               title: str, date: str, nav_top_file: Path = None, nav_bottom_file: Path = None):
        """Convert tex content to HTML using pandoc"""

        # Build pandoc command
        cmd = [
            "pandoc",
            "-f", "latex",
            "-o", str(output_file),
            "--standalone",
            "--katex=https://cdn.jsdelivr.net/npm/katex@latest/dist/",  # Explicit CDN URL
            "--metadata", f"title={title}",
            "--metadata", f"date={date}",
        ]

        # Add dark mode CSS
        dark_mode_file = self.output_dir / ".dark-mode.html"
        if dark_mode_file.exists():
            cmd.extend(["--include-in-header", str(dark_mode_file)])

        # Add Lua filter for custom processing
        lua_filter = self.base_dir / "filters" / "note-filter.lua"
        if lua_filter.exists():
            cmd.extend(["--lua-filter", str(lua_filter)])

        if nav_top_file and nav_top_file.exists():
            cmd.extend(["--include-before-body", str(nav_top_file)])  # Add navigation at top
        if nav_bottom_file and nav_bottom_file.exists():
            cmd.extend(["--include-after-body", str(nav_bottom_file)])   # Add navigation at bottom

        # Run pandoc
        try:
            subprocess.run(
                cmd,
                input=content,
                text=True,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            print(f"    Error running pandoc: {e.stderr}")
            raise

    def generate_simple_nav_html(self) -> str:
        """Generate simple navigation for regular posts (just back to home)"""
        nav_parts = []
        nav_parts.append('<hr style="margin: 2em 0; border: none; border-top: 1px solid #ddd;">')
        nav_parts.append('<nav style="margin-top: 1em;">')
        nav_parts.append('<p><a href="../../../index.html">← Back to all posts</a></p>')
        nav_parts.append('</nav>')
        return '\n'.join(nav_parts)

    def generate_nav_html(self, nav_info: dict, position: str = 'bottom') -> str:
        """Generate navigation HTML for collection articles

        Args:
            nav_info: Dictionary with collection_name, prev, next
            position: 'top' or 'bottom' - controls whether to show hr at top
        """
        collection_name = nav_info['collection_name']
        prev_file = nav_info['prev']
        next_file = nav_info['next']

        nav_parts = []

        # Add hr only for bottom navigation
        if position == 'bottom':
            nav_parts.append('<hr style="margin: 2em 0; border: none; border-top: 1px solid #ddd;">')

        nav_parts.append('<nav style="margin: 1em 0;">')
        nav_parts.append(f'<p style="color: #666; font-size: 0.9em; margin-bottom: 0.5em;">Collection: {collection_name}</p>')
        nav_parts.append('<p>')

        # Previous link
        if prev_file:
            prev_name = prev_file.stem
            nav_parts.append(f'<a href="../{prev_name}/latest.html">← Previous: {prev_name}</a>')
            nav_parts.append(' | ')

        # Collection index link
        nav_parts.append(f'<a href="../index.html">Collection Index</a>')

        # Next link
        if next_file:
            nav_parts.append(' | ')
            next_name = next_file.stem
            nav_parts.append(f'<a href="../{next_name}/latest.html">Next: {next_name} →</a>')

        nav_parts.append('</p>')
        nav_parts.append('</nav>')

        # Add hr only for top navigation (below the nav)
        if position == 'top':
            nav_parts.append('<hr style="margin: 2em 0; border: none; border-top: 1px solid #ddd;">')

        return '\n'.join(nav_parts)

    def generate_version_index(self, output_dir: Path, article_name: str, tex_file: Path):
        """Generate version history index for an article"""
        html_files = sorted([f for f in output_dir.glob("*.html")
                           if f.name != "index.html" and f.name != "latest.html"],
                          reverse=True)

        html = ['<!DOCTYPE html>']
        html.append('<html><head><meta charset="UTF-8">')
        html.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html.append(f'<title>{article_name} - Versions</title>')
        # Include dark mode CSS
        dark_mode_content = (self.output_dir / ".dark-mode.html").read_text()
        html.append(dark_mode_content)
        html.append('<style>')
        html.append('body{font-family:sans-serif;max-width:36em;margin:2em auto;padding:0 2em;line-height:1.6}')
        html.append('h1{border-bottom:1px solid #ddd;padding-bottom:0.5em}')
        html.append('h2{margin-top:1.5em}')
        html.append('a{color:#0066cc;text-decoration:none}a:hover{text-decoration:underline}')
        html.append('ul{padding-left:0;list-style:none}')
        html.append('li{margin:0.5em 0}')
        html.append('.nav{margin-top:2em;padding-top:1em;border-top:1px solid #ddd}')
        html.append('</style></head><body>')
        html.append(f'<h1>{article_name}</h1>')
        html.append('<p><strong><a href="latest.html">📄 Latest Version</a></strong></p>')

        if html_files:
            html.append('<h2>Version History</h2><ul>')
            for html_file in html_files:
                version = html_file.stem
                html.append(f'<li><a href="{html_file.name}">{version}</a></li>')
            html.append('</ul>')

        html.append('<div class="nav"><a href="../../../index.html">← Back to all posts</a></div>')
        html.append('</body></html>')

        with open(output_dir / "index.html", 'w') as f:
            f.write('\n'.join(html))

    def generate_collection_index(self, collection_name: str, tex_files: List[Path]):
        """Generate index page for a collection"""
        output_dir = self.output_dir / "collections" / collection_name
        output_dir.mkdir(parents=True, exist_ok=True)

        html = ['<!DOCTYPE html>']
        html.append('<html><head><meta charset="UTF-8">')
        html.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html.append(f'<title>{collection_name}</title>')
        html.append('<style>')
        html.append('body{font-family:sans-serif;max-width:36em;margin:2em auto;padding:0 2em;line-height:1.6;color:#1a1a1a}')
        html.append('h1{border-bottom:1px solid #ddd;padding-bottom:0.5em}')
        html.append('a{color:#0066cc;text-decoration:none}a:hover{text-decoration:underline}')
        html.append('ol{padding-left:2em}')
        html.append('li{margin:0.8em 0}')
        html.append('.meta{color:#666;font-size:0.9em;margin-left:0.5em}')
        html.append('.date{color:#666;font-size:0.9em}')
        html.append('.nav{margin-top:2em;padding-top:1em;border-top:1px solid #ddd}')
        html.append('@media (prefers-color-scheme: dark){')
        html.append('body{color:#e8e8e8;background-color:#1a1a1a}')
        html.append('a{color:#58a6ff}a:visited{color:#8e96f0}')
        html.append('h1{color:#e8e8e8;border-bottom-color:#4a4a4a}')
        html.append('.meta,.date{color:#a0a0a0}')
        html.append('.nav{border-top-color:#4a4a4a}')
        html.append('}')
        html.append('</style></head><body>')
        html.append(f'<h1>{collection_name}</h1>')
        html.append('<ol>')

        for tex_file in tex_files:
            article_name = tex_file.stem

            # Get last modification date from git
            versions = self.get_git_history(tex_file)
            if versions:
                last_date = versions[-1][1].split()[0]
            else:
                last_date = self.get_current_time().strftime("%Y-%m-%d")

            html.append(f'<li>')
            html.append(f'<a href="{article_name}/latest.html">{article_name}</a>')
            html.append(f' <span class="date">({last_date})</span>')
            html.append(f' <span class="meta">(<a href="{article_name}/index.html">history</a>)</span>')
            html.append('</li>')

        html.append('</ol>')
        html.append('<div class="nav"><a href="../../index.html">← Back to all posts</a></div>')
        html.append('</body></html>')

        with open(output_dir / "index.html", 'w') as f:
            f.write('\n'.join(html))

    def generate_main_index(self):
        """Generate main index.html"""
        # Get last commit time
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%cd', '--date=format:%Y-%m-%d %H:%M:%S'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                check=True
            )
            last_commit_time = result.stdout.strip()
        except:
            last_commit_time = self.get_current_time().strftime("%Y-%m-%d %H:%M:%S")

        html = ['<!DOCTYPE html>']
        html.append('<html lang="en"><head><meta charset="UTF-8">')
        html.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html.append('<title>Blog</title>')
        html.append('<style>')
        html.append('body{font-family:sans-serif;max-width:36em;margin:2em auto;padding:0 2em;line-height:1.6;color:#1a1a1a}')
        html.append('h1{border-bottom:1px solid #ddd;padding-bottom:0.5em}')
        html.append('h2{margin-top:1.5em;font-size:1.3em}')
        html.append('a{color:#0066cc;text-decoration:none}a:hover{text-decoration:underline}')
        html.append('ul{padding-left:0;list-style:none}')
        html.append('li{margin:0.6em 0}')
        html.append('.meta{color:#666;font-size:0.9em;margin-left:0.5em}')
        html.append('.date{color:#666;font-size:0.9em}')
        html.append('@media (prefers-color-scheme: dark){')
        html.append('body{color:#e8e8e8;background-color:#1a1a1a}')
        html.append('a{color:#58a6ff}a:visited{color:#8e96f0}')
        html.append('h1,h2{color:#e8e8e8;border-bottom-color:#4a4a4a}')
        html.append('.meta,.date{color:#a0a0a0}')
        html.append('}')
        html.append('</style></head><body>')
        html.append('<h1>Blog</h1>')
        html.append(f'<p class="date">Last updated: {last_commit_time} | <a href="https://github.com/odlove/odlove.github.io">Source Code</a></p>')

        # Collections section
        if self.collections_dir.exists():
            collections = sorted([d for d in self.collections_dir.iterdir() if d.is_dir()])
            if collections:
                html.append('<h2>Collections</h2>')
                html.append('<ul>')
                for collection_dir in collections:
                    collection_name = collection_dir.name
                    tex_files = list(collection_dir.rglob("*.tex"))
                    tex_count = len(tex_files)

                    # Get latest modification date from all files in collection
                    latest_date = None
                    for tex_file in tex_files:
                        versions = self.get_git_history(tex_file)
                        if versions:
                            file_date = versions[-1][1].split()[0]
                            if latest_date is None or file_date > latest_date:
                                latest_date = file_date

                    if latest_date is None:
                        latest_date = self.get_current_time().strftime("%Y-%m-%d")

                    html.append(f'<li>')
                    html.append(f'<a href="collections/{collection_name}/index.html">{collection_name}</a>')
                    html.append(f' <span class="date">({latest_date})</span>')
                    html.append(f' <span class="meta">({tex_count} articles)</span>')
                    html.append('</li>')
                html.append('</ul>')

        # Regular blogs section
        if self.blogs_dir.exists():
            tex_files = sorted(self.blogs_dir.rglob("*.tex"), reverse=True)
            if tex_files:
                html.append('<h2>Posts</h2>')
                html.append('<ul>')
                for tex_file in tex_files:
                    rel_path = tex_file.relative_to(self.blogs_dir)
                    article_name = tex_file.stem

                    # Get last modification date from git
                    versions = self.get_git_history(tex_file)
                    if versions:
                        last_date = versions[-1][1].split()[0]
                    else:
                        last_date = self.get_current_time().strftime("%Y-%m-%d")

                    # Generate URL based on folder structure
                    if tex_file.parent.name == article_name:
                        # blogs/2025/article-name/article-name.tex -> blogs/2025/article-name/
                        url = f"blogs/{rel_path.parent}/index.html"
                    else:
                        # blogs/2025/article-name.tex -> blogs/2025/article-name/
                        url = f"blogs/{rel_path.parent}/{article_name}/index.html"
                    html.append(f'<li>')
                    html.append(f'<a href="{url}">{article_name}</a>')
                    html.append(f' <span class="date">({last_date})</span>')
                    html.append('</li>')
                html.append('</ul>')

        html.append('</body></html>')

        with open(self.output_dir / "index.html", 'w') as f:
            f.write('\n'.join(html))


def main():
    base_dir = Path(__file__).parent
    builder = BlogBuilder(base_dir)
    builder.run()


if __name__ == "__main__":
    main()
