#!/usr/bin/env python3
"""Convenience entry point for the Viva Engage report generator."""

import sys

from . import generate_reports


if __name__ == "__main__":
    # simply delegate to the main function; arguments are passed through
    generate_reports.main()
