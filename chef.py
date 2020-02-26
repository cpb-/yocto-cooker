#!/usr/bin/env python3
""" chef.py: meta build tool for Yocto Project based Linux embedded systems."""

__author__ = "Christophe BLAESS, Patrick BOETTCHER"
__license__ = "GPL"

import json
import os
import shutil
import sys
import argparse
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(prog='Chef')
    parser.add_argument('--debug', action='store_true', help='activate debug printing')

    # parsing subcommand's arguments
    subparsers = parser.add_subparsers(help='subcommands of Chef')

    # clear command
    clear_parser = subparsers.add_parser('clear', help='clear the current directory')
    clear_parser.add_argument('menu', help='JSON filename of the menu', type=argparse.FileType('r'), nargs=1)
    clear_parser.set_defaults(func=clear_directory)

    # prepare command
    prepare_parser = subparsers.add_parser('prepare', help='create the content of the menu')
    prepare_parser.add_argument('menu', help='JSON filename of the menu', type=argparse.FileType('r'), nargs=1)
    prepare_parser.set_defaults(func=prepare_directory)

    # build command
    build_parser = subparsers.add_parser('build', help='build the targets from the menu')
    build_parser.add_argument('menu', help='JSON filename of the menu', type=argparse.FileType('r'), nargs=1)
    build_parser.set_defaults(func=build_targets)

    args = parser.parse_args()
    try:
        args.func(args) # call function of selected command
    except:
        sys.exit(1)

    sys.exit(0)



def clear_directory(args):
    if args.debug: 
        print('Clearing directory using {}'.format(args.menu[0].name))

    try:
        menu = load_menu(args.menu[0], args.debug)

        for source in menu['sources']:
            remove_source(source, args.debug)

        for target in menu['targets']:
            directory = 'build-' + target
            remove_directory(directory, args.debug)
    except:
        raise
    return 0



def prepare_directory(args):
    if args.debug: 
        print('Preparing directory using {}'.format(args.menu[0].name))
    try:
        menu = load_menu(args.menu[0], args.debug)
        populate_directory(menu, args.debug)
    except:
        raise



def build_targets(args):

    if args.debug: 
         print('Building targets from {}'.format(args.menu[0].name))

    try:
        menu = load_menu(args.menu[0], args.debug)
        populate_directory(menu, args.debug)

        for target in menu['targets']:
            build_target(target, menu['targets'][target], args.debug)
    except:
        raise



def load_menu(menu, debug = False):
    if (debug):
        print('  Loading menu "{}"'.format(menu.name))
    try:
        return json.load(menu)
    except json.decoder.JSONDecodeError as e:
        print('menu load error at', e)
        raise



def remove_directory(directory, debug=False):
	if (debug):
		print('  Removing directory "{}"'.format(directory))

	if os.path.isdir(directory):
		shutil.rmtree(directory, ignore_errors=True)



def remove_source(source, debug=False):
    if 'url' in source:
        try:
            url = urlparse(source['url'])
            remove_directory(url.path[1:], debug)
        except:
            raise



def populate_directory(menu, debug=False):

    if debug:
        print('  Populating directory')

    for source in menu['sources']:
        download_source(source, debug)

    for target in menu['targets']:
        content = menu['targets'][target]
        layers = content['layers']
        local_conf = content['local.conf']
        directory = 'build-' + target
        prepare_build_directory(directory, menu['layers'], layers, local_conf, debug)



def build_target(target_name, target, debug=False):
    try:
        if debug:
            print('  Building target({})'.format(target_name))

        directory = "build-" + target_name
        if 'image' in target:
            image = target['image']
        else:
            image = 'core-image-base'

        if "init-script" in target:
            init_script = target['init-script']
        else:
            init_script = 'poky/oe-init-build-env'
        command_line = 'env bash -c "source {} {} && bitbake {}"'.format(init_script, directory, image)
        if debug:
            print('    Executing : "{}"'.format(command_line))
        os.system(command_line)
    except:
        raise



def download_source(source, debug=False):
    if 'url' in source:
        if debug:
            print('    Downloading source from {}'.format(source['url']))
        try:
            url = urlparse(source['url'])
        except:
            print('url-parse-error')
            raise

        # Use the same method names than Yocto Project.
        # See https://www.yoctoproject.org/docs/3.0/mega-manual/mega-manual.html#var-SRC_URI

        # Try to find the method from the URL prefix.
        if url.scheme == 'file':
             method = 'file'
        if url.scheme == 'git':
             method = 'git'

        # The 'method' field can override the URL prefix.
        if 'method' in source:
            method = source['method']

        if method == 'git':
            if not 'commit' in source:
                print('WARNING: source "{}" has no "commit" field, the build will not be reproducible!'.format(source['url']))
            if 'branch' in source:
                branch = '-b ' + source['branch']
            else:
                branch = ''
            dir = url.path[1:]
            if not os.path.isdir(dir):
                os.system('git clone {} {} {}'.format(branch, url.geturl(), dir))
                if 'commit' in source:
                    os.system('cd ' + dir + '; git checkout ' + source['commit'])
            else:
                if not 'commit' in source:
                    os.system('git pull')



def prepare_build_directory(dir, global_layers, layers, local_conf, debug=False):

    if debug:
        print('    Preparing directory "build-{}"'.format(dir))

    cwd = os.path.abspath(os.getcwd())
    if not os.path.isdir(dir):
        os.mkdir(dir)
    os.chdir(dir)
    if not os.path.isdir("conf"):
        os.mkdir("conf")

    with open('conf/local.conf', 'w') as file:
        for line in local_conf:
            file.write(line)
            file.write(' = "')
            file.write(local_conf[line])
            file.write('"\n')

        file.write('''DL_DIR ?= "${TOPDIR}/../downloads"
SSTATE_DIR ?= "${TOPDIR}/../sstate-cache"
DISTRO ?= "poky"
PACKAGE_CLASSES ?= "package_rpm"
BB_DISKMON_DIRS ??= "\\
\tSTOPTASKS,${TMPDIR},1G,100K \\
\tSTOPTASKS,${DL_DIR},1G,100K \\
\tSTOPTASKS,${SSTATE_DIR},1G,100K \\
\tSTOPTASKS,/tmp,100M,100K \\
\tABORT,${TMPDIR},100M,1K \\
\tABORT,${DL_DIR},100M,1K \\
\tABORT,${SSTATE_DIR},100M,1K \\
\tABORT,/tmp,10M,1K"
CONF_VERSION = "1"
''')

    with open('conf/bblayers.conf', 'w') as file:
        file.write('''POKY_BBLAYERS_CONF_VERSION = "2"
BBPATH = "${TOPDIR}"
BBFILES ?= ""
''')

        file.write('BBLAYERS ?= " \\\n')
        for layer in global_layers:
            file.write(cwd + '/' + layer + '  \\\n')
        for layer in layers:
            file.write(cwd + '/' + layer + '  \\\n')
        file.write('"\n')

    with open('conf/templateconf.cfg', 'w') as file:
        file.write("meta-poky/conf\n")

    os.chdir("..")



if __name__ == '__main__':
    main()
