import os
import re
import chardet
import hashlib
from typing import Optional

from zipfile import ZipFile, BadZipfile

# REGEX
PATTERN = re.compile("\\b(text|real|integer|string)\\W", re.I)


def create_hash(*item):
    string_for_hash_bytes = "".join([str(item) for item in item]).encode()
    hash_object = hashlib.md5(string_for_hash_bytes)
    hash_key = hash_object.hexdigest()
    return hash_key


def get_file_encoding(file_path: str) -> tuple[str, float]:
    """
    Detects the encoding and confidence level of a file.

    :param file_path: The path to the file.
    :return: A tuple containing the encoding and confidence level.
    """
    with open(file_path, 'rb') as file:
        raw_data = file.read()

    result = chardet.detect(raw_data)
    encoding = result['encoding']
    confidence = result['confidence']

    return encoding, confidence


def split_string(input_string: str) -> list[str]:
    """
    Splits a string into substrings, using the space between quoted text as the delimiter.
    The space within the quoted text is not split.

    :param input_string: The input string to split.
    :return: A list of substrings extracted from the input string.
    """
    return re.findall(r'"([^"]*)"', input_string)


def remove_parenthesis(input_string: str) -> str:
    """
    Removes unnecessary whitespace to enable splitting into key-value pairs.

    :param input_string: The input string to process.
    :return: The string without parenthesis.

    """
    return input_string.replace("  ", " ").replace('"', "").strip()


def clean_text(text):
    """
        Cleans the text by removing comments and empty lines
        :param str text:
        :return: str
    """
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        line = remove_parenthesis(line).strip()
        line = PATTERN.sub("", line).strip()
        if not line \
                or line.startswith('//') \
                or line.startswith('null') \
                or line.startswith('model') \
                or 'project_directory' in line \
                or len(line) == 0:
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


class TextFrom12dConverter:
    """
    A class for converting 12d files (.12da or .12daz) to text format.

    :args file_path (str): The path to the 12d file.

    methods:
        get_12da_text(): Retrieves the raw text data from the 12d file.
        get_file_encoding(): Determines the encoding of the 12d file.
        convert_12da_to_text(): Converts a .12da file to text based on its encoding.
        convert_12daz_to_text(): Extracts and converts a .12daz file to text based on its encoding.
    """

    def __init__(self, file_path: str):
        file_path = file_path.replace(' ', '_')
        self.file_path = file_path

    def get_12da_text(self) -> Optional[str]:
        """
        Retrieves the raw text data from the 12d file (.12da or .12daz).

        :return Optional[str]: The raw text data from the file, or None if an error occurs.

        """

        _, ext = os.path.splitext(self.file_path)
        if ext == '.12da':
            return self.convert_12da_to_text()
        else:
            return self.convert_12daz_to_text()

    def get_file_encoding(self):
        """
        Determines the encoding of the 12d file.

        :return Tuple[str, float]: The encoding of the file and the confidence level.

        """

        with open(self.file_path, 'rb') as file:
            raw_data = file.read()

        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']

        return encoding, confidence

    def convert_12da_to_text(self) -> Optional[str]:
        """
        Converts a .12da file to text based on its encoding.

        :return Optional[str]: The raw text data from the file, or None if an error occurs.

        """

        encoding = self.get_file_encoding()[0]

        with open(self.file_path, 'r', encoding=encoding) as file:
            try:
                raw_data = file.read()
            except UnicodeDecodeError:
                print(f"UnicodeDecodeError: {self.file_path}")
                raw_data = self.convert_12daz_to_text()

        return raw_data

    def convert_12daz_to_text(self) -> Optional[str]:
        """
        Extracts and converts a .12daz file to text based on its encoding.

        :return Optional[str]: The raw text data from the file, or None if an error occurs.

        """
        try:

            with ZipFile(self.file_path, 'r') as zip_file:
                files_in_zip = zip_file.namelist()
                file_name = files_in_zip[0]

                with zip_file.open(file_name) as file:
                    raw_data = file.read().decode('utf-16')


        except BadZipfile:
            print(f"BadZipfile: {self.file_path}")
            raw_data = self.convert_12da_to_text()

        return raw_data
