import os
import sys
import regex as re
from oboe.utils import slug_case, md_link, render_markdown, write, find_subdirs_recursively
from oboe.Note import Note
from oboe import LOG
from oboe import GLOBAL


class Vault:
    def __init__(self, extra_folders=[], html_template=None, filter_list=[]):
        self.extra_folders = extra_folders

        # If all folders are to be added
        if "all" in extra_folders:
            LOG.debug("Adding notes from all subdirectories recursively.")
            self.extra_folders = find_subdirs_recursively(GLOBAL.VAULT_ROOT)

        self.notes = self._find_files()

        include_filter = []; exclude_filter = []
        for elem in filter_list:
            if elem[0] == ".":
                exclude_filter.append(elem[1:])
            else:
                include_filter.append(elem)

        # Filters out all notes that contain a tag in the exclude filter
        self.notes = list(filter(lambda x: not set(exclude_filter).intersection(set(x.tags)), self.notes))
        LOG.info(f"Filtered out notes containing tags: {exclude_filter}")
        # If include filter is present, filters out any notes NOT containing a tag in include filter
        if include_filter:
            self.notes = list(filter(lambda x: set(include_filter).intersection(set(x.tags)), self.notes))
            LOG.info(f"Filtered out notes NOT containing tags: {include_filter}")

        self._add_backlinks()

        if html_template:
            self.html_template_path = os.path.abspath(html_template)
            try:
                with open(html_template, "r", encoding="utf8") as f:
                    self.html_template = f.read()
                LOG.debug(f"Using template: \"{os.path.abspath(self.html_template_path)}\"")
            except FileNotFoundError:
                LOG.error(f"Cannot find a template at path \"{self.html_template_path}\", aborting.")
                sys.exit()

        LOG.info(f"Created Vault object with root \"{os.path.abspath(GLOBAL.VAULT_ROOT)}\"")


    def _add_backlinks(self):
        for i, note in enumerate(self.notes):
            # Make temporary list of all notes except current note in loop
            others = [other for other in self.notes if other != note]
            backlinks = note.find_backlinks(others)
            if backlinks:
                self.notes[i].backlink_html += "\n<div class=\"backlinks\" markdown=\"1\">\n"
                for backlink in backlinks:
                    if GLOBAL.BACKLINK_DASH == True: #If user disabled backlinkdash, then save it without the dash!
                        self.notes[i].backlink_html += f"- {backlink.md_link()}\n"
                    else:
                        self.notes[i].backlink_html += f"{backlink.md_link()}\n"

                self.notes[i].backlink_html += "</div>"

                self.notes[i].backlink_html = render_markdown(self.notes[i].backlink_html)


    def export_html(self):
        # Ensure the output directory exists, as well as all extra folders.
        if not os.path.exists(GLOBAL.OUTPUT_DIR):
            os.makedirs(GLOBAL.OUTPUT_DIR)
        for folder in self.extra_folders:
            out_folder = os.path.join(GLOBAL.OUTPUT_DIR, os.path.relpath(folder, GLOBAL.VAULT_ROOT))
            if not os.path.exists(out_folder):
                os.makedirs(out_folder)

        if hasattr(self, "html_template"):
            stylesheets = re.findall('<link+.*rel="stylesheet"+.*href="(.+?)"', self.html_template)
            for stylesheet in stylesheets:
                # Check if template contains reference to a stylesheet
                stylesheet_abspath = os.path.join(os.path.dirname(self.html_template_path), stylesheet)
                # Check if the referenced stylesheet is local, and copy it to the output directory if it is
                if os.path.isfile(stylesheet_abspath):
                    GLOBAL.STYLESHEETS.append(stylesheet)
                    LOG.info("Copying stylesheet to the output directory...")

                    with open(stylesheet_abspath, encoding="utf-8") as f:
                        stylesheet_content = f.read()
                    write(stylesheet_content, os.path.join(GLOBAL.OUTPUT_DIR, stylesheet))

                    LOG.info("Copied local stylesheet into the output directory.")

            # Use the supplied template on all notes
            for note in self.notes:
                LOG.debug(f"Formatting {note.title} according to the supplied HTML template...")

                html = self.html_template.format(title=note.title, content=note.html(), backlinks=note.backlink_html)
                # If we have copied stylesheet, make sure the paths are correct for each subdirectory
                for stylesheet in GLOBAL.STYLESHEETS:
                    relative_path = os.path.join(os.path.relpath(GLOBAL.OUTPUT_DIR, os.path.dirname(note.out_path)), stylesheet)
                    html = html.replace(f"href=\"{stylesheet}\"", f"href=\"{relative_path}\"")

                write(html, note.out_path)

                LOG.debug(f"{note.title} written.")
        else:
            # Do not use a template, just output the content and a list of backlinks
            for note in self.notes:
                LOG.debug(f"Exporting {note.title} without using a template.")

                html = "{content}\n{backlinks}".format(content=note.html(), backlinks=note.backlink_html)
                write(html, note.out_path)

                LOG.debug(f"{note.title} written.")


    def _find_files(self):
        # Find all markdown-files in vault root.
        md_files = self._find_files_in_dir(GLOBAL.VAULT_ROOT)
        # Find all markdown-files.
        for folder in self.extra_folders:
            md_files += self._find_files_in_dir(folder, is_extra_dir=True)

        LOG.info(f"Found {len(md_files)} notes!")
        return md_files


    def _find_files_in_dir(self, folder, is_extra_dir=False):
        md_files = []
        for md_file in os.listdir(folder):
            # Check if the element in 'folder' has the extension .md and is indeed a file
            if not (md_file.endswith(".md") and os.path.isfile(os.path.join(folder, md_file))):
                continue

            note = Note(os.path.join(folder, md_file))

            md_files.append(note)
            # Filter tags
            # if self.filter:
            #     if set(self.filter).intersection(set(note.tags)):
            #         md_files.append(note)
            #         break
            #     continue
            # else:
            #     md_files.append(note)

        return md_files
