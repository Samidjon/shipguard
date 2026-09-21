#!/usr/bin/env python3
"""
Run the ShipGuard verification pipeline over the whole inbox.

Writes results.json (full output including diagnostics) and
submission.json (the official hackathon shape) to the repository root,
regardless of the working directory this is invoked from.

    python run_pipeline.py
"""

from shipguard.pipeline import main


if __name__ == "__main__":
    main()
