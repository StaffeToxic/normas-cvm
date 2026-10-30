"""Conversion of official documents into publication candidates."""

from cvm_archive.convert.html import convert_html
from cvm_archive.convert.pdf import convert_pdf
from cvm_archive.convert.word import convert_word_tables, extract_docx_tables

__all__ = ["convert_html", "convert_pdf", "convert_word_tables", "extract_docx_tables"]
