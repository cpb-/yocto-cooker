#!/usr/bin/env python3

import json
import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(prog='Chef')
    parser.add_argument('--debug', action='store_true', help='activate debug printing')

    # parsing subcommand's arguments
    subparsers = parser.add_subparsers(help='subcommands of Chef')

    # clear command
    clear_parser = subparsers.add_parser('clear', help='clear the current directory')
    clear_parser.set_defaults(func=clear_directory)

    # prepare command
    prepare_parser = subparsers.add_parser('prepare', help='create the content of the menu')
    prepare_parser.add_argument('menu', help='JSON filename of the menu', type=argparse.FileType('r'), nargs=1)
    prepare_parser.set_defaults(func=prepare_menu)

    args = parser.parse_args()
    try:
        args.func(args) # call function of selected command
    except:
        sys.exit(1)

    sys.exit(0)


def clear_directory(args):
    print('clear dir')
    return 0


def prepare_menu(args):
    try:
        print('Loading menu...')
        menu = load_menu(args.menu[0])
        print('loaded')
        populate_directory(menu)
    except:
        raise


def load_menu(menu):
    try:
        return json.load(menu)
    except json.decoder.JSONDecodeError as e:
        print('menu load error at', e)
        raise


def populate_directory(menu):

    for source in menu["sources"]:
        download_source(source)

    for target in menu["targets"]:
        content = menu["targets"][target]
        layers = content["layers"]
        local_conf = content["local.conf"]

        if "image" in content:
            image = content["image"]
        else:
            image = "core-image-base"

        if "init-script" in content:
            init_script = content["init-script"]
        else:
            init_script = "poky/oe-init-build-env"

        directory = "build-" + target
        print("Preparing directory",directory,"...", end='')
        prepare_build_directory(directory, menu["layers"], layers, local_conf)
        print("ready")
        display_instructions_for_build(init_script, directory, image)



def download_source(source):
    if "url" in source:
        url = source["url"]
        dir = url[url.rfind("/") + 1:]
        if not os.path.isdir(dir):
            if url.startswith("git"):
                os.system("git clone " + url + " " + dir)
                if "refspec" in source:
                    os.system("cd " + dir + "; git checkout " + source["refspec"])



def prepare_build_directory(dir, global_layers, layers, local_conf):

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
        file.write('DL_DIR ?= "${TOPDIR}/../downloads"\n')
        file.write('SSTATE_DIR ?= "${TOPDIR}/../sstate-cache\n')

        file.write('DISTRO ?= "poky"\n')
        file.write('PACKAGE_CLASSES ?= "package_rpm"\n')
        file.write('BB_DISKMON_DIRS ??= "\\\n')
        file.write('\tSTOPTASKS,${TMPDIR},1G,100K \\\n')
        file.write('\tSTOPTASKS,${DL_DIR},1G,100K \\\n')
        file.write('\tSTOPTASKS,${SSTATE_DIR},1G,100K \\\n')
        file.write('\tSTOPTASKS,/tmp,100M,100K \\\n')
        file.write('\tABORT,${TMPDIR},100M,1K \\\n')
        file.write('\tABORT,${DL_DIR},100M,1K \\\n')
        file.write('\tABORT,${SSTATE_DIR},100M,1K \\\n')
        file.write('\tABORT,/tmp,10M,1K"\n')
        file.write('CONF_VERSION = "1"\n')

    with open('conf/bblayers.conf', 'w') as file:

        file.write('POKY_BBLAYERS_CONF_VERSION = "2"\n')
        file.write('BBPATH = "${TOPDIR}"\n')
        file.write('BBFILES ?= ""\n')

        file.write('BBLAYERS ?= " \\\n')
        for layer in global_layers:
            file.write(cwd + '/' + layer + '  \\\n')
        for layer in layers:
            file.write(cwd + '/' + layer + '  \\\n')
        file.write('"\n')

    with open('conf/templateconf.cfg', 'w') as file:
        file.write("meta-poky/conf\n")

    os.chdir("..")


def display_instructions_for_build(init_script, directory, image):

    print("\n")
    print("You can run:")
    print("   $ source " + init_script + "  " + directory)
    print("   $ bitbake " + image)


if __name__ == '__main__':
    main()
