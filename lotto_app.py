"""Entry point for the standalone executable.

With arguments it behaves like `python -m lotto`; double-clicked (no arguments)
it runs `sim` and keeps the window open so the numbers can be read and re-drawn.
"""

import sys

from lotto.__main__ import main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        while True:
            main(["sim"])
            try:
                again = input("\n엔터: 다시 뽑기 / q: 종료 > ")
            except EOFError:
                break
            if again.strip().lower() == "q":
                break
            print()
