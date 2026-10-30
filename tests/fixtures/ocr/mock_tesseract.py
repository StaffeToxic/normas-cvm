"""Simulated Tesseract binary for deterministic OCR testing."""
import sys


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    # Arguments: <image_path> stdout -l <lang>
    if len(sys.argv) < 2:
        sys.exit(1)

    img_path = sys.argv[1]
    if "ruido" in img_path.lower():
        print("x")
        sys.exit(0)

    print(
        "PORTARIA CVM Nº 109, DE 15 DE JANEIRO DE 2020\n\n"
        "Art. 1º Fica delegada a competência ao Diretor Geral.\n\n"
        "Art. 2º Esta Portaria entra em vigor na data de sua publicação."
    )


if __name__ == "__main__":
    main()
