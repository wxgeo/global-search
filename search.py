#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# +---------------------------------------+
# |                                       |
# |       Global search utility           |
# |                                       |
# +---------------------------------------+

#    Copyright (C) 2005-2023  Nicolas Pourcelot
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


import os
import sys
import re
import subprocess
import argparse

IGNORE = (
    ".*",
    "dist/",
    "doc/",
    ".tox/*",
)
DEFAULT_EDITOR = "nano"
SUPPORTED_EDITORS = ("geany", "gedit", "nano", "vim", "emacs", "kate", "kile")

# TODO: Support user config file.
# TODO: update IGNORE by autodetecting .gitignore content, if any.


def global_search(
    string: str = "",
    case=True,
    include_comments=False,
    comment_marker: str = "#",
    extensions: Iterable[str] = (".py", ".pyw"),
    maximum: int = 100,
    codec="utf8",
    stats=False,
    replace_with: str = None,
    color: str = None,
    edit_with: str = None,
    edit_result: Iterable[int] = None,
    skip_paths: Iterable[str | Path] = (),
) -> bool:
    """Search recursively for `string` in the current directory.

    Read the content of the files of the current directory and its subdirectories
    which meets the following conditions:
    - extension is included in `extensions`,
    - name do not start with a prefix of `exclude_prefix`, nor end with a suffix of `exclude_suffix`.

    For each file found, returns all lines where `string` is found.
    The maximum number of lines returned is set by 'maximum', to avoid saturating the system.
    If this number is exceeded (i.e. all occurrences of 'string' are not displayed)
    displayed), the function returns False, otherwise, True.

    By default, the search is case-sensitive (set `case` to `False` for case-insensitive search).
    """

    if skip_paths:
        IGNORE_RE = re.compile(
            "|".join("(%s)" % pattern.replace("*", ".*").strip() for pattern in skip_paths if pattern)
        )
    else:
        IGNORE_RE = None

    if color is None:
        color = sys.platform.startswith("linux")
    if color:

        def blue(s):
            return "\033[0;36m" + s + "\033[0m"

        def blue2(s):
            return "\033[1;36m" + s + "\033[0m"

        def red(s):
            return "\033[0;31m" + s + "\033[0m"

        def green(s):
            return "\033[0;32m" + s + "\033[0m"

        def green2(s):
            return "\033[1;32m" + s + "\033[0m"

        def yellow(s):
            return "\033[0;33m" + s + "\033[0m"

        def white(s):
            return "\033[1;37m" + s + "\033[0m"

    else:
        green = blue = white = blue2 = red = green2 = yellow = lambda s: s

    if not string:
        stats = True
    if not case:
        string = string.lower()
    if replace_with is not None:
        assert case
    cwd = os.getcwd()
    repertoires = os.walk(cwd)
    print("Searching in " + green(cwd) + "...")
    end_root_pos = len(cwd) + 1
    print("")
    fichiers = []
    for root, dirs, files in repertoires:
        files = [f for f in files if f[f.rfind(".") :] in extensions]
        fichiers += [root + os.sep + f for f in files]
    # nombre de lignes de code au total
    code_lines_count = 0
    # nombre de lignes de commentaires au total
    comments_lines_count = 0
    # nombre de fichiers
    files_count = 0
    # nombre de lignes vides
    empty_lines_count = 0
    # nombre de lignes contenant l'expression recherchée
    matching_lines = 0
    # Nombre d'occurrences trouvées.
    occurrences = 0
    for filename in fichiers:
        if IGNORE_RE is not None and re.search(IGNORE_RE, filename):
            continue
        files_count += 1
        correct_encoding = True
        with open(filename) as fichier:
            lines = []
            results = []
            try:
                for n, line in enumerate(fichier):
                    if replace_with is not None:
                        lines.append(line)
                    if stats:
                        line = line.strip()
                        if line:
                            if line[0] != comment_marker:
                                code_lines_count += 1
                            elif line.strip(comment_marker):
                                comments_lines_count += 1
                            else:
                                empty_lines_count += 1
                        else:
                            empty_lines_count += 1
                        continue
                    if not include_comments and line.lstrip().startswith(comment_marker):
                        # comment line
                        continue
                    if not case:
                        line = line.lower()
                    pos = line.find(string)
                    if pos != -1:
                        if not include_comments:
                            substr = line[:pos]
                            if comment_marker in substr:
                                # test if the substring found was inside a comment
                                # at the end of the line.
                                # You have to be careful, because `comment_marker` may be
                                # inside a string...
                                # TODO: handle triple quotes.
                                mode = None
                                for c in substr:
                                    if c in ("'", '"', comment_marker):
                                        if mode is None:
                                            mode = c
                                            if c == comment_marker:
                                                continue
                                        elif mode == c:
                                            mode = None
                                if mode == comment_marker:
                                    # substring found inside a comment
                                    continue

                        occurrences += 1
                        if replace_with is not None:
                            lines[-1] = line.replace(string, replace_with)
                        line = line[:pos] + blue2(line[pos : pos + len(string)]) + line[pos + len(string) :]
                        results.append(
                            "   "
                            + blue("(" + str(matching_lines + 1) + ")")
                            + "  line "
                            + white(str(n + 1))
                            + ":   "
                            + line
                        )

                        if (
                            edit_with is not None
                            and edit_result is not None
                            and (len(edit_result) == 0 or ((matching_lines + 1) in edit_result))
                        ):
                            if edit_with not in SUPPORTED_EDITORS:
                                print(edit_with + " is currently not supported.")
                                print("Supported editors : " + ",".join(SUPPORTED_EDITORS))
                            elif edit_with in ("geany", "kate"):
                                command = "%s -l %s %s" % (edit_with, n + 1, filename)
                            elif edit_with in ("kile",):
                                command = "%s --line %s %s" % (edit_with, n + 1, filename)
                            else:
                                command = "%s +%s %s" % (edit_with, n + 1, filename)
                            # ~ print('%s executed...' % command)
                            subprocess.call(command, shell=True)

                        matching_lines += 1
                        if matching_lines > maximum:
                            return red("Maximum output exceeded...!")
            except UnicodeDecodeError:
                correct_encoding = False
                print(
                    red("ERROR:")
                    + " Can't read %s, encoding isn't %s." % (filename, sys.getdefaultencoding())
                )

        if correct_encoding and results:
            print(" \u2022 in " + green(filename[:end_root_pos]) + green2(filename[end_root_pos:]))
            for result in results:
                print(result.rstrip())

            if replace_with is not None:
                with open(filename, "w") as fichier:
                    for line in lines:
                        fichier.write(line)

    if stats:
        return (
            blue(str(code_lines_count) + " lignes de code\n")
            + str(comments_lines_count)
            + " lignes de commentaires ("
            + str(comments_lines_count)
            + " hors licence)\n"
            + str(empty_lines_count)
            + " lignes vides\n"
            + str(files_count)
            + " fichiers"
        )
    if replace_with is None:
        return blue("\n-> %s occurence(s) trouvée(s)." % occurrences)
    else:
        return blue(
            "%s occurence(s) de %s remplacée(s) par %s." % (occurrences, repr(string), repr(replace_with))
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        argument_default=argparse.SUPPRESS,
        description="Search recursively for specified string in all the files of a directory.",
    )
    parser.add_argument("string", metavar="STRING", help="string to search")
    parser.add_argument(
        "-r",
        "--replace-with",
        metavar="REPLACEMENT_STRING",
        help="Replace all occurrences of STRING with REPLACEMENT_STRING.",
    )
    parser.add_argument(
        "-e",
        "--edit-result",
        metavar="N",
        type=int,
        nargs="*",
        help="""Open editor and display result number N
                         (use --edit with no argument to
                        open all files where searched string was found).""",
    )
    parser.add_argument(
        "-w", "--edit-with", metavar="EDITOR", choices=SUPPORTED_EDITORS, default=DEFAULT_EDITOR
    )
    parser.add_argument("-s", "--stats", help="Display statistics concerning scanned files.")
    parser.add_argument(
        "-m", "--maximum", type=int, metavar="N", default=100, help="Display only the first N results."
    )
    parser.add_argument("-i", "--include-comments", action="store_true", help="Search in comments too.")
    parser.add_argument(
        "-x",
        "--extensions",
        metavar="EXTENSION",
        nargs="+",
        default=(".py", ".pyw"),
        help="Search only files whose name ends with any specified extension.",
    )
    parser.add_argument("-n", "--no-color", dest="color", action="store_false", help="Disable colors.")
    parser.add_argument(
        "-k", "--skip-paths", metavar="PATH_TO_SKIP", nargs="*", default=IGNORE, help="Paths to skip."
    )
    parser.add_argument(
        "-c", "--discard-case", dest="case", action="store_false", help="Make search case insensitive."
    )
    args = parser.parse_args()

    title = "\n=== Recherche de %s ===\n" % repr(args.string)
    if sys.platform.startswith("linux"):
        title = "\033[1;37m" + title + "\033[0m"
    print(title)
    # ~ print(vars(args))
    print(gs(**vars(args)))
