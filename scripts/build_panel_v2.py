#!/usr/bin/env python3
"""Construye el panel taxonómico v2 (output/panel_v2.csv).

Uso:
    python -m scripts.build_panel_v2
"""

from src.core.panel_v2 import build_panel_v2


def main():
    build_panel_v2()


if __name__ == "__main__":
    main()
