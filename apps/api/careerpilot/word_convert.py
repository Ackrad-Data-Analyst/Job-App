import sys

from docx2pdf import convert

if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
