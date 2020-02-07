#! /usr/bin/python

from __future__ import print_function

import getopt
import json
import sys



def main(argv):

	if len(argv) < 1:
		display_usage()
		sys.exit(0)

	try:
		if argv[0] == 'clear':
			clear_directory()

		elif argv[0] == 'prepare':
			prepare_menu(argv[1:])

		else:
			print("Error: bad command name")
			raise
	except:
		sys.exit(1)

	sys.exit(0)



def display_usage():
	print("usage:", sys.argv[0], "[options...] command [argument]")
	print("  commands:")
	print("    clear                   clear the current directory.")
	print("    prepare <menu-file>     create the content of the menu.")



def clear_directory():
	return 0



def prepare_menu(argv):

	if len(argv) < 1:
		print("Error: missing menu name")
		raise
	try:
		menu = load_menu(argv[0])
		populate_directory(menu)
		
	except:
		raise



def load_menu(filename):
	try:
		with open(filename) as file:
			data = json.load(file)
	except:
		print("Error reading", filename)

	return data



def populate_directory(menu):
	return 0



main(sys.argv[1:])
