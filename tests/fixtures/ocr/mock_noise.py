"""Simulated Tesseract binary returning insufficient/noisy output."""
import sys


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("...")


if __name__ == "__main__":
    main()
