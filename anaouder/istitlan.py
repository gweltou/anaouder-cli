#!/usr/bin/env python3

import sys
from anaouder.adskrivan import main_adskrivan


def main_istitlan():
	args = sys.argv[1:] + ["-t", "srt"]
	return main_adskrivan(*args)


if __name__ == "__main__":
	main_istitlan()