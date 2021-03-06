#!/usr/bin/env python3

# This script replaces the Makefile to provide a convenient cross-platform build tool

import argparse
import glob
import os
from os import path
import shutil
import subprocess
import sys

def fatal_print(msg):
	print(msg)
	exit(1)

def fs_action(action, sourcefile, destfile = ""):
	isfile = path.isfile(sourcefile) or path.islink(sourcefile)
	isdir = path.isdir(sourcefile)
	if action == "copy":
		fs_action("delete", destfile)
		if isfile:
			shutil.copy(sourcefile, destfile)
		elif isdir:
			shutil.copytree(sourcefile, destfile)
	elif action == "move":
		fs_action("delete", destfile)
		shutil.move(sourcefile, destfile)
	elif action == "mkdir":
		if isfile:
			fs_action("delete", sourcefile)
		elif not isdir:
			os.makedirs(sourcefile)
	elif action == "delete":
		if isfile:
			os.remove(sourcefile)
		elif isdir:
			shutil.rmtree(sourcefile)
	else:
		raise Exception("Invalid action, must be 'copy', 'move', 'mkdir', or 'delete'")

def run_cmd(cmd, print_output = True, realtime = False, print_command = False):
	if print_command:
		print(cmd)

	proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr=subprocess.STDOUT, shell = True)
	output = ""
	status = 0
	if realtime: # print the command's output in real time, ignores print_output
		while True:
			realtime_output = proc.stdout.readline().decode("utf-8")
			if realtime_output == "" and status is not None:
				return ("", status)
			if realtime_output:
				print(realtime_output.strip())
				output += realtime_output
			status = proc.poll()
	else: # wait until the command is finished to print the output
		output = proc.communicate()[0]
		if output is not None:
			output = output.decode("utf-8").strip()
		else:
			output = ""
		status = proc.wait()
		if output != "" and print_output:
			print(output)
	if status is None:
		status = 0
	return (output, status)

def in_pathenv(file):
	paths = os.environ["PATH"].split(path.pathsep)
	for loc in paths:
		if path.isfile(path.join(loc, file)) or path.isfile(path.join(loc, file + ".exe")):
			return True
	return False


def out_file(platform, windows):
	oc8_out = "oc8"
	if windows and platform == "native":
		oc8_out += ".exe"
	elif platform == "c64" or platform == "apple2":
		oc8_out += "-" + platform + ".prg"
	elif platform == "gb":
		oc8_out += ".gb"
	elif platform == "emscripten":
		oc8_out += ".html"
	elif not "native":
		fatal_print("Unsupported platform " + platform)

	return oc8_out

def term_type():
	if "FrameworkVersion" in os.environ:
		return "msbuild"
	if "OS" in os.environ and "MINGW_PREFIX":
		return "mingw"
	if "TERM" in os.environ:
		return "unix"
	if "OS" in os.environ:
		return "cmd"
	return "other"

def build(platform = "native", library = "sdl", debugging = False):
	term = term_type()
	msbuild = term == "msbuild" and platform == "native"

	if platform == "native" and not msbuild and "TERM" not in os.environ:
		fatal_print(
			"You appear to be in Windows, but are not using the Visual Studio command prompt\n" +
			"or Cygwin. In order to build OmniChip-8 natively in Windows, you need to use\n" +
			"one of the two. Eventually, this build script may use something else as an\n" +
			"alternative"
		)

	oc8_out = out_file(platform, "OS" in os.environ and os.environ["OS"] == "Windows_NT")

	if platform != "native":
		debugging = False

	cmd = ""
	sources = ["src/chip8.c", "src/util.c", "src/main.c"]

	if msbuild:
		# Visual Studio development console is being used
		if not in_pathenv("msbuild"):
			fatal_print("Unable to find msbuild.exe. Check your Visual Studio installation and try again")
		cmd = "msbuild.exe OmniChip-8.sln"
		if debugging:
			cmd += " -p:Configuration=Debug"
		else:
			cmd += " -p:Configuration=Release"
	elif platform == "native":
		if not in_pathenv("cc"):
			fatal_print("Unable to find the cc compiler")

		includes_path = "/usr/include"
		if term == "mingw":
			includes_path = "/mingw64/include"

		lib = "-lSDL2"
		if library == "curses":
			lib = "-lcurses"
		elif library == "sdl":
			includes_path += "/SDL2"

		sources.append("src/io_{}.c".format(library))

		cmd = "cc -o {oc8_out} -D{io_const}_IO {includes_path} {cflags} {sources} {lib}".format(
			oc8_out = oc8_out,
			io_const = library.upper(),
			includes_path = "-I" + includes_path,
			cflags = "-g -pedantic -Wall -std=c89 -D_POSIX_SOURCE",
			sources = " ".join(sources),
			lib = lib
		)
	elif platform == "cc65":
		if not in_pathenv("cl65"):
			fatal_print("Unable to find the cc65 development kit, required to build for 65xx targets")
	elif platform == "gb":
		if not in_pathenv("zcc"):
			fatal_print("Unable to find the z88dk development kit, required to build for the GameBoy")

		sources.append("src/io_{}.c".format(platform))
		cmd = "zcc +gb -create-app -o oc8.gb -DGB_IO {sources}".format(
			sources = " ".join(sources)
		)
	elif platform == "emscripten":
		if not in_pathenv("emcc"):
			fatal_print("Unable to find the emscripten development kit, required to build browser-compatible JavaScript")
		sources.append("src/io_{}.c".format("sdl"))
		cmd = "emcc -o {oc8_out} -s --embed-file games USE_SDL=2 --shell-file shell.html -DSDL_IO -DEMSCRIPTEN_IO {sources}".format(
			oc8_out = oc8_out,
			sources = " ".join(sources)
		)
	else:
		fatal_print("Unsupported platform " + platform)

	status = run_cmd(cmd, print_output = True, realtime = True, print_command = True)
	if status[1] != 0:
		fatal_print("Failed building OmniChip-8, see command output for details")
	print("Built OmniChip-8 successfully")

def clean():
	print("Cleaning up")
	fs_action("delete", "build/")
	del_files = glob.glob("oc8*") + ["SDL2.dll"]
	for del_file in del_files:
		fs_action("delete", del_file)

if __name__ == "__main__":
	action = "build"
	try:
		action = sys.argv.pop(1)
	except Exception: # no argument was passed
		pass
	if(action.startswith("-") == False):
		sys.argv.insert(1, action)

	valid_actions = ("build", "clean")
	parser = argparse.ArgumentParser(description = "OmniChip-8 build script")
	parser.add_argument("action", nargs = 1, default = "build", choices = valid_actions)

	if action == "--help" or action == "-h":
		parser.print_help()
		exit(2)
	elif action == "build":
		default_library = "sdl"
		parser.add_argument("--platform", help = "the platform to build for, valid values are c64, gb, and native (default)", default = "native")
		parser.add_argument("--library", help = "the library to use when platform = native. Valid values are sdl and curses", default = default_library)
		parser.add_argument("--debug", help = "build OmniChip-8 with debugging symbols", default = True)
		args = parser.parse_args()
		build(args.platform, args.library, args.debug)
	elif action == "clean":
		clean()
		exit(0)
	else:
		parser.print_help()
		exit(0)

	args = parser.parse_args()
