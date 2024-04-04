#!/usr/bin/env python3
""" cooker.py: meta build tool for Yocto Project based Linux embedded systems."""

import argparse
import pyjson5
import json
import os
import re
import sys
from urllib.parse import urlparse
import jsonschema
import pkg_resources
import subprocess
import shlex
from abc import ABC, abstractmethod

from typing import List

__version__ = '1.4.0'


def debug(*args):
    if CookerCall.DEBUG:
        print(*args, file=sys.stderr)


def info(*args):
    print('# ', end='')
    print(*args)
    sys.stdout.flush()


def warn(*args):
    print('WARN:', *args, file=sys.stderr)


def fatal_error(*args):
    print('FATAL:', *args, file=sys.stderr)
    sys.exit(1)


class OsCalls:

    def create_directory(self, directory):
        os.makedirs(directory, exist_ok=True)

    def file_open(self, filename):
        return open(filename, 'w')

    def file_write(self, file, string):
        file.write('{}\n'.format(string))

    def file_close(self, file):
        file.close()

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def directory_exists(self, dirname):
        return os.path.isdir(dirname)

    def replace_process(self, shell: str, args: List[str]):
        return os.execv(shell, args)

    def subprocess_run(self, args, cwd, capture_output=True):
        return subprocess.run(args, capture_output=capture_output, cwd=cwd)


class DryRunOsCalls:

    def create_directory(self, directory):
        print('mkdir {}'.format(directory))
        sys.stdout.flush()

    def file_open(self, filename):
        print('cat > {} <<-EOF'.format(filename))
        sys.stdout.flush()
        return 0

    def file_write(self, file, string):
        print('\t{}'.format(string.replace('$', '\$')))
        sys.stdout.flush()

    def file_close(self, file):
        print('EOF')
        sys.stdout.flush()

    def file_exists(self, filename):
        return True

    def directory_exists(self, dirname):
        return True

    def replace_process(self, shell: str, args: List[str]):
        print('exec {} {}'.format(shell, ' '.join(args)))
        return True

    def subprocess_run(self, args, cwd,  capture_output=True):
        if cwd is not None:
            print("cd " + cwd)
        print(' '.join(args))
        sys.stdout.flush()
        return subprocess.CompletedProcess(args, 0, stderr="")


class Config:
    DEFAULT_CONFIG_FILENAME = '.cookerconfig'
    DEFAULT_CONFIG = {
        'menu': '',
        'layer-dir': 'layers',
        'build-dir': 'builds',
        'dl-dir': 'downloads',
        'sstate-dir': 'sstate-cache',
        'cooker-config-version': 1
    }
    CURRENT_CONFIG_VERSION = 1

    def __init__(self):
        debug('Looking for', Config.DEFAULT_CONFIG_FILENAME)

        self.filename = os.path.join(os.getcwd(), self.DEFAULT_CONFIG_FILENAME)

        path = os.getcwd().split(os.sep)
        while path:
            filename = '/' + os.path.join(*path, self.DEFAULT_CONFIG_FILENAME)

            debug(' Trying', filename)

            if os.path.isfile(filename):
                debug('  Found')

                self.filename = filename

                found = False
                try:
                    with open(self.filename) as json_file:
                        self.cfg = json.load(json_file)

                    found = True

                except Exception as e:
                    fatal_error('configuration load error', e)

                if found:
                    self.check_and_migrate_config()
                    self.path = "/".join(path)
                    return

                break

            path.pop()  # cd ..

        self.cfg = self.DEFAULT_CONFIG.copy()
        self.path = ""

        debug('No config-file found. Will be using', self.filename)

    def check_and_migrate_config(self):
        config_version = self.cfg.get('cooker-config-version', 0)
        if config_version == self.CURRENT_CONFIG_VERSION:
            return

        debug(f'migrating cookerconfig from {config_version} to {self.CURRENT_CONFIG_VERSION}')

        ## here we add changes incrementally from one version to another (do not elif)

        # from 0 to 1 we added the sstate-dir
        if config_version == 0:
            if 'sstate-dir' not in self.cfg:  # intermediate version where sstate-dir was added
                self.cfg['sstate-dir'] = self.DEFAULT_CONFIG['sstate-dir']
            config_version = 1

        # cooker-config-version is updated
        self.cfg['cooker-config-version'] = config_version

        self.save()

    def project_root(self):
        return os.path.dirname(self.filename)

    def set_menu(self, menu_file):
        if menu_file.startswith('/'):
            self.cfg['menu'] = os.path.realpath(menu_file)
        else:
            self.cfg['menu'] = os.path.relpath(menu_file, self.path)

    def set_layer_dir(self, path):
        # paths in the config-file are relative to the project-dir
        self.cfg['layer-dir'] = os.path.relpath(path, self.project_root())

    def layer_dir(self, name=''):
        return os.path.join(self.project_root(), self.cfg['layer-dir'], name)

    def set_build_dir(self, path):
        self.cfg['build-dir'] = os.path.relpath(path, self.project_root())

    def build_dir(self, name=''):
        return os.path.join(self.project_root(), self.cfg['build-dir'], name)

    def set_dl_dir(self, path):
        self.cfg['dl-dir'] = os.path.relpath(path, self.project_root())

    def dl_dir(self):
        return os.path.join(self.project_root(), self.cfg['dl-dir'])

    def set_sstate_dir(self, path):
        self.cfg['sstate-dir'] = os.path.relpath(path, self.project_root())

    def sstate_dir(self, name=''):
        return os.path.join(self.project_root(), self.cfg['sstate-dir'], name)

    def menu(self):
        menu_path = self.cfg['menu']
        if menu_path.startswith('/'):
            return menu_path
        else:
            return self.path + "/" + menu_path

    def save(self):
        debug('Saving configuration file')
        with open(self.filename, 'w') as json_file:
            json.dump(self.cfg, json_file, indent=4)

    def empty(self):
        return not self.cfg['menu']


class BuildConfiguration:
    ALL = {}

    def __init__(self, name, config, layers, local_conf, target, inherit):
        self.name_ = name
        self.config_ = config
        self.layers_ = layers
        self.local_conf_ = local_conf
        if type(target) == list:
            self.targets_ = target
        elif target:
            self.targets_ = [target]
        else:
            self.targets_ = []
        self.inherit_ = inherit

        self.parents_ = []  # first level parents
        self.ancestors_ = []  # all ancestors cleaned of duplicates

        BuildConfiguration.ALL[name] = self

    def targets(self):
        if not self.buildable():
            return None

        for build in [self] + self.ancestors_[::-1]:
            if build.targets_:
                return build.targets_

    def name(self):
        return self.name_

    def dir(self):
        return self.config_.build_dir('build-' + self.name_)

    def buildable(self):
        if self.name_.startswith('.'):  # template
            return False

        return any(build.targets_ for build in self.ancestors_ + [self])

    def layers(self):
        layers = []

        for build in self.ancestors_ + [self]:
            for layer in build.layers_:
                if layer not in layers:
                    layers.append(layer)
                else:
                    debug('ignored - duplicate layer for build "{}": "{}"'
                          .format(build.name(), layer))

        return layers

    def local_conf(self):
        lines = []

        for build in self.ancestors_ + [self]:
            for new_line in build.local_conf_:
                if new_line in lines:
                    debug('ignored - duplicate line in local.conf for build "{}": "{}"'
                          .format(build.name(), new_line))
                lines.append(new_line)

        return lines

    def set_parents(self):
        debug('setting first-level-parents of build "{}"'.format(self.name_))

        if self.inherit_:
            for parent_name in self.inherit_:

                if parent_name not in BuildConfiguration.ALL:
                    fatal_error('build "{}"\'s parent "{}" not found in builds-section'
                                .format(self.name_, parent_name))

                parent_instance = BuildConfiguration.ALL[parent_name]

                if parent_instance == self:
                    fatal_error('"{}" inherits from itself, that is impossible'.format(self.name_))

                debug('adding {} as parent to {}'.format(parent_instance.name(), self.name()))
                self.parents_.append(parent_instance)

    def get_ancestors(self, start, path=None):
        if path is None:
            path = list()
        path.append(self.name())

        parents = []

        if start in self.parents_:
            fatal_error('recursive inheritance detected for "{}" via "{}"'
                        .format(start.name(), ' -> '.join(path + [start.name()])))

        for parent in self.parents_:

            new_parents = parent.get_ancestors(start, path) + [parent]

            for new_parent in new_parents:
                if new_parent in parents:
                    debug('build "{}" parent "{}" inherited multiple times - ignoring'
                          .format(self.name(), new_parent.name()))
                else:
                    parents.append(new_parent)

        path.pop()

        return parents


def resolve_parents():
    for _, build in BuildConfiguration.ALL.items():
        build.set_parents()

    for _, build in BuildConfiguration.ALL.items():
        build.ancestors_ = build.get_ancestors(build)

        debug('ancestors of build "{}": "{}"'
              .format(build.name(), [n.name() for n in build.ancestors_]))


class PokyDistro:

    DISTRO_NAME = "poky"
    BASE_DIRECTORY = "poky"
    BUILD_SCRIPT = "oe-init-build-env"
    TEMPLATE_CONF = ("meta-poky/conf", "meta-poky/conf/templates/default")
    DEFAULT_CONF_VERSION = "1"
    LAYER_CONF_NAME = "POKY_BBLAYERS_CONF_VERSION"
    LAYER_CONF_VERSION = "2"
    PACKAGE_FORMAT = "package_rpm"
    DEFAULT_BITBAKE_MAJOR_VERSION = 2
    BITBAKE_INIT_FILE = "bitbake/lib/bb/__init__.py"

class AragoDistro:

    DISTRO_NAME = "arago"
    BASE_DIRECTORY = "openembedded-core"
    BUILD_SCRIPT = "oe-init-build-env"
    TEMPLATE_CONF = ("meta/conf",)
    DEFAULT_CONF_VERSION = "1"
    LAYER_CONF_NAME = "LCONF_VERSION"
    LAYER_CONF_VERSION = "7"
    PACKAGE_FORMAT = "package_ipk"
    DEFAULT_BITBAKE_MAJOR_VERSION = 2
    BITBAKE_INIT_FILE = "sources/bitbake/lib/__init__.py"


class LogFormat(ABC):

    def __init__(self, changes):
        self.changes = changes
        self.output = ""

    @abstractmethod
    def print_history_item(self, line):
        pass

    def print_history(self, data):
        for line in data['history']:
            line_str = self.format_rev_history(line, data['to']['url'])
            self.print_history_item(line_str)

    @abstractmethod
    def print_added_item(self, source, rev_str):
        pass

    @abstractmethod
    def print_modified_item(self, source, rev_str):
        pass

    @abstractmethod
    def print_deleted_item(self, source, rev_str):
        pass

    def format_rev_history(self, line, url):
        return line

    def format_rev_commit(self, data):
        return '{}'.format(data['rev'][0:7])

    @abstractmethod
    def format_rev_commits(self, data):
        pass

    def print_added(self, changes):
        for source, data in changes.items():
            rev_str = self.format_rev_commit(data)
            self.print_added_item(source, rev_str)

    def print_modified(self, changes):
        for source, data in changes.items():
            rev_str = self.format_rev_commits(data)
            self.print_modified_item(source, rev_str)
            if 'history' in data:
                self.print_history(data)

    def print_deleted(self, changes):
        for source, data in changes.items():
            rev_str = self.format_rev_commit(data)
            self.print_deleted_item(source, rev_str)

    def generate(self):
        if self.changes['added']:
            self.print_added(self.changes['added'])

        if self.changes['modified']:
            self.print_modified(self.changes['modified'])

        if self.changes['deleted']:
            self.print_deleted(self.changes['deleted'])

    def add_line(self, line=""):
        if self.output:
            self.output += "\n"
        self.output += line

    def display(self):
        print(self.output)


class LogLinkedFormat(LogFormat):

    GITHUB_URL = "https://github.com"
    GITLAB_URL = "https://gitlab.com"
    GIT_HL_URL = (GITHUB_URL, GITLAB_URL)

    def format_rev_history(self, line, url):
        if url.startswith(self.GIT_HL_URL):
            index = line.find(' ')
            rev = line[0:index]
            text = line[index+1:]
            return '[{0}]({1}/commit/{0}) {2}'.format(rev, url, text)
        return super().format_rev_history(line, url)

    def format_rev_commit(self, data):
        if data['url'].startswith(self.GIT_HL_URL):
            return '[{}]({}/commit/{})'.format(
                data['rev'][0:7],
                data['url'],
                data['rev']
            )
        return super().format_rev_commit(data)


class LogTextFormat(LogFormat):

    def print_history_item(self, line):
        self.add_line('  {}'.format(line))

    def format_rev_commits(self, data):
        return '{} .. {}'.format(data['from']['rev'][0:7], data['to']['rev'][0:7])

    def print_added_item(self, source, rev_str):
        self.add_line('A {}: {}'.format(source, rev_str))

    def print_modified_item(self, source, rev_str):
        self.add_line('M {}: {}'.format(source, rev_str))

    def print_deleted_item(self, source, rev_str):
        self.add_line('D {}: {}'.format(source, rev_str))


class LogLinkedTextFormat(LogTextFormat, LogLinkedFormat):

    def format_rev_commits(self, data):
        if data['to']['url'].startswith(self.GIT_HL_URL):
            return '[{} .. {}]({}/compare/{}..{})'.format(
                data['from']['rev'][0:7],
                data['to']['rev'][0:7],
                data['to']['url'],
                data['from']['rev'],
                data['to']['rev'],
            )
        return super().format_rev_commits(data)


class LogMarkdownFormat(LogFormat):

    def print_history_item(self, line):
        self.add_line('  - {}'.format(line))

    def format_rev_commits(self, data):
        return '{} to {}'.format(data['from']['rev'][0:7], data['to']['rev'][0:7])

    def print_added_item(self, source, rev_str):
        self.add_line('- {} at revision {}'.format(source, rev_str))

    def print_modified_item(self, source, rev_str):
        self.add_line('- {} changed from {}'.format(source, rev_str))

    def print_deleted_item(self, source, rev_str):
        self.add_line('- {} at revision {}'.format(source, rev_str))

    def print_added(self, changes):
        self.add_line('### Added projects')
        super().print_added(changes)
        self.add_line()

    def print_modified(self, changes):
        self.add_line('### Modified projects')
        super().print_modified(changes)
        self.add_line()

    def print_deleted(self, changes):
        self.add_line('### Deleted projects')
        super().print_deleted(changes)
        self.add_line()


class LogLinkedMarkdownFormat(LogMarkdownFormat, LogLinkedFormat):

    def format_rev_commits(self, data):
        if data['to']['url'].startswith(self.GIT_HL_URL):
            return '[{} to {}]({}/compare/{}..{})'.format(
                data['from']['rev'][0:7],
                data['to']['rev'][0:7],
                data['to']['url'],
                data['from']['rev'],
                data['to']['rev'],
            )
        return super().format_rev_commits(data)


class CookerCommands:
    """ The class aggregates all functions representing a low-level cooker-command """

    def __init__(self, config, menu):
        self.config = config
        self.menu = menu
        if menu is not None:
            distros = {
                'poky': PokyDistro,
                'arago': AragoDistro,
            }
            name = menu.setdefault('base-distribution', 'poky')
            try:
                self.distro = distros[name.lower()]
            except:
                fatal_error('base-distribution {} is unknown, please add a `base-distribution.py` file next your menu.'.format(name))

            # Update distro if custom distro is defined in menu
            self.update_override_distro()

    def init(self, menu_name, layer_dir=None, build_dir=None, dl_dir=None, sstate_dir=None):
        """ cooker-command 'init': (re)set the configuration file """
        self.config.set_menu(menu_name)

        if layer_dir:
            self.config.set_layer_dir(layer_dir)

        if build_dir:
            self.config.set_build_dir(build_dir)

        if dl_dir:
            self.config.set_dl_dir(dl_dir)

        if sstate_dir:
            self.config.set_sstate_dir(sstate_dir)

        self.config.save()

    def update(self):
        info('Update layers in project directory')

        for source in self.menu['sources']:
            self.update_source(source)

    def local_dir_from_source(self, source):
        if 'dir' in source:
            local_dir = source['dir']
        else:
            local_dir = None
            if 'url' in source:
                try:
                    if '://' in source['url']:
                        url = urlparse(source['url'])
                        local_dir = url.path[1:]
                    elif ':' in source['url']:  # must be short URL
                        _, local_dir = source['url'].split(':', 2)
                    else:
                        raise ValueError('invalid source URL given')
                except Exception as e:
                    fatal_error('url-parse-error', source['url'], e)

        return os.path.realpath(self.config.layer_dir(local_dir)), source['url']

    def update_source(self, source):
        method = 'git'

        if 'method' in source:
            method = source['method']

        if method == 'ignore':
            return

        local_dir, remote_dir = self.local_dir_from_source(source)

        branch = source.setdefault('branch', '')
        rev = source.setdefault('rev', '')

        if not os.path.isdir(local_dir):
            self.update_directory_initial(method, local_dir, remote_dir, branch, rev)

        if CookerCall.os.directory_exists(local_dir):
            self.update_directory(method, local_dir, remote_dir != '', branch, rev)

    def update_directory_initial(self, method, local_dir, remote_dir, branch, rev):
        info('Downloading source from ', remote_dir)

        if CookerCall.VERBOSE:
            redirect = ''
        else:
            redirect = ' >/dev/null 2>&1'

        if method == 'git':
            complete = CookerCall.os.subprocess_run(["git", "ls-remote", remote_dir ], None)
            if complete.stdout is not None:
                refs = complete.stdout.decode("utf-8")
            else:
                refs=""

            command = ["git", "clone", "--recurse-submodules", remote_dir, local_dir]
            if re.search("refs/tags/" + rev + "$", refs, re.MULTILINE):
                command.extend(["--branch", rev])
            elif branch != '':
                command.extend(["--branch", branch])

            complete = CookerCall.os.subprocess_run(command, None)
            if complete.returncode != 0:
                fatal_error('Unable to clone {}: {}'.format(remote_dir, complete.stderr.decode('ascii')))

    def update_directory(self, method, local_dir, has_remote, branch, rev):
        if CookerCall.VERBOSE:
            redirect = ''
        else:
            redirect = ' >/dev/null 2>&1'

        if method == 'git':

            if rev == '':

                if branch == '':
                    warn('WARNING! source "{}" has no "rev" nor "branch" field, '.format(local_dir) +
                         'the build will not be reproducible at all!')

                    info('Trying to update source {}... '.format(local_dir))
                    if has_remote:
                        complete = CookerCall.os.subprocess_run(["git", "pull"], local_dir)
                        if complete.returncode != 0:
                            fatal_error('Unable to pull updates for {}: {}'.format(local_dir, complete.stderr.decode('ascii')))

                else:
                    warn('source "{}" has no "rev" field, the build will not be reproducible!'.format(local_dir))
                    info('Updating source {}... '.format(local_dir))

                    complete = CookerCall.os.subprocess_run(["git", "checkout", branch], local_dir)
                    if complete.returncode != 0:
                        fatal_error('Unable to checkout branch {} for {}: {}'.format(branch, local_dir, complete.stderr.decode('ascii')))

                    if has_remote:
                        complete = CookerCall.os.subprocess_run(["git", "pull"], local_dir)
                        if complete.returncode != 0:
                            fatal_error('Unable to pull updates for {}: {}'.format(local_dir, complete.stderr.decode('ascii')))

            else:
                info('Updating source {}... '.format(local_dir))

                complete = CookerCall.os.subprocess_run(["git", "fetch"], local_dir)
                if complete.returncode != 0:
                    fatal_error('Unable to fetch {}: {}'.format(local_dir, complete.stderr.decode('ascii')))

                complete = CookerCall.os.subprocess_run(["git", "checkout", rev], local_dir)
                if complete.returncode != 0:
                    fatal_error('Unable to checkout rev {} for {}: {}'.format(rev, local_dir, complete.stderr.decode('ascii')))

            complete = CookerCall.os.subprocess_run(["git", "submodule", "update", "--recursive", "--init"], local_dir)
            if complete.returncode != 0:
                fatal_error('Unable to update submodules in {}: {}'.format(local_dir, complete.stderr.decode('ascii')))

    def diff(self):
        for source in self.menu['sources']:
            local_dir = self.local_dir_from_source(source)[0]
            source_name = os.path.basename(local_dir)
            debug('check the diff of the source {}'.format(source_name))

            if 'rev' not in source:
                debug('no revision field in the menu file for source {}'.format(source_name))
                continue

            menu_rev = source['rev']

            if not CookerCall.os.directory_exists(local_dir):
                warn('{} directory of source {} does not exist'.format(local_dir, source_name))
                continue

            complete = CookerCall.os.subprocess_run(["git", "describe", "--abbrev=7", "--tags", "--always", "--dirty"], local_dir)
            if complete.returncode != 0:
                warn('unable to get the current revision of the local source {}'.format(local_dir))
                debug(complete.stderr.decode('ascii'))
                continue

            local_rev = complete.stdout.strip().decode('ascii')
            debug('menu revision: {}, local revision: {}'.format(menu_rev, local_rev))
            if menu_rev != local_rev:
                print('{}: {} .. {}'.format(source_name, menu_rev, local_rev))

    def generate_build_config_from_menu(self, menu, build_name):
        """
        Generates the BuildConfiguration classes from the given menu version.
        Resolve the parents and returns the BuildConfiguration class of the build.

        Backup and restore the ALL BuildConfiguration class variable to avoid
        overwriting the existing content.
        """
        backup = BuildConfiguration.ALL
        BuildConfiguration.ALL = {}

        BuildConfiguration('root',
                           self.config,
                           menu.setdefault('layers', []),
                           menu.setdefault('local.conf', []),
                           None,
                           None)

        for name, build in menu['builds'].items():
            BuildConfiguration(name,
                               self.config,
                               build.setdefault('layers', []),
                               build.setdefault('local.conf', []),
                               build.setdefault('target', None),
                               build.setdefault('inherit', ['root']))

        resolve_parents()

        build_config = BuildConfiguration.ALL[build_name]

        BuildConfiguration.ALL = backup

        return build_config

    def get_sources_from_build_layers(self, menu, layers):
        """
        Returns a key/data entry of the sources from the layers used by the build.
        """
        layers_dir = list(dict.fromkeys(list(map(lambda p: p.split('/')[0], layers))))
        sources = {}

        for source in menu['sources']:
            local_dir, url = self.local_dir_from_source(source)
            key = os.path.basename(local_dir)
            data = {
                'rev': source['rev'],
                'url': url
            }

            if key in layers_dir:
                sources[key] = data

        return sources

    def load_and_validate_menu(self, menu_file, schema):
        with open(menu_file, "r") as file:
            try:
                menu = pyjson5.load(file)
            except Exception as e:
                fatal_error('menu load error:', e)

            try:
                jsonschema.validate(menu, schema)
            except Exception as e:
                fatal_error('menu file {} validation failed:'.format(menu_file), e)

        debug('menu file {} validation passed'.format(menu_file))
        return menu

    def log(self, build_name, menu_from_file, menu_to_file, history, log_format):
        """
        Generates a log of the build sources revision changes between two menu file version.
        """
        schema = pyjson5.loads(pkg_resources.resource_string(__name__, "cooker-menu-schema.json").decode('utf-8'))
        menu_from = self.load_and_validate_menu(menu_from_file, schema)
        menu_to = self.menu

        if build_name not in menu_from['builds'] or build_name not in menu_to['builds']:
            fatal_error('build `{}` does not exist in the menu file'.format(build_name))

        # Generates a BuildConfiguration class for the menu since the build layers
        # can change between menu version. If 'menu to' is ommitted, use the
        # current up-to-date BuildConfiguration class.

        build_config_from = self.generate_build_config_from_menu(menu_from, build_name)
        build_config_to = BuildConfiguration.ALL[build_name]

        if menu_to_file is not None:
            menu_to = self.load_and_validate_menu(menu_to_file, schema)
            build_config_to = self.generate_build_config_from_menu(menu_to, build_name)

        # Gets the sources used by the build from the list of layers.

        sources_from = self.get_sources_from_build_layers(menu_from, build_config_from.layers())
        sources_to = self.get_sources_from_build_layers(menu_to, build_config_to.layers())

        debug('sources `from` menu: {}'.format(sources_from))
        debug('sources `to` menu: {}'.format(sources_to))

        # Filters the changes from sources. Local directory basename of the source
        # as key

        changes = {}
        changes['added'] = {s: sources_to[s] for s in sources_to if s not in sources_from}
        changes['modified'] = {s: {'from': sources_from[s], 'to': sources_to[s]} for s in sources_to if s in sources_from and sources_to[s] != sources_from[s]}
        changes['deleted'] = {s: sources_from[s] for s in sources_from if s not in sources_to}

        # Append the git commit history for the filtered modified sources.

        if history is not None:
            for source, data in changes['modified'].items():
                if source in history and CookerCall.os.directory_exists(self.config.layer_dir(source)):
                    complete = CookerCall.os.subprocess_run([
                        "git",
                        "log",
                        "{}..{}".format(data['from']['rev'], data['to']['rev']),
                        "--oneline",
                        "--abbrev-commit"
                    ],self.config.layer_dir(source))
                    if complete.returncode != 0:
                        warn('unable to get the git history of the source {}'.format(source))
                        debug(complete.stderr.decode('ascii'))
                        continue
                    data['history'] = complete.stdout.decode('ascii').splitlines()

        # Prints the formatted log output from the changes dict.

        if log_format in ['md', 'markdown']:
            log = LogMarkdownFormat(changes)
        elif log_format in ['lmd', 'l-md', 'linked-md', 'linked-markdown']:
            log = LogLinkedMarkdownFormat(changes)
        elif log_format in ['ltxt', 'l-txt', 'linked-txt', 'l-text', 'linked-text']:
            log = LogLinkedTextFormat(changes)
        else:
            log = LogTextFormat(changes)

        log.generate()
        log.display()

    def generate(self):
        info('Generating dirs for all build-configurations')

        self.read_local_conf_version()

        for build in BuildConfiguration.ALL.values():
            if build.buildable():
                self.prepare_build_directory(build)

    def generate_distro_base_dir_path(self):
        """
        This method generates the full path to the distro base directory
        """
        return os.path.join(self.config.layer_dir(), self.distro.BASE_DIRECTORY)

    def get_template_conf_path(self):
        """
        This method returns the relative path to the directory containing the local.conf.sample file
        """
        for template_conf in self.distro.TEMPLATE_CONF:
            full_path = os.path.join(
                self.generate_distro_base_dir_path(),
                template_conf,
                "local.conf.sample"
            )
            if os.path.exists(full_path):
                return template_conf
        return

    def get_template_conf_full_path(self):
        """
        This method returns the full path to the directory containing the local.conf.sample file
        """
        template_conf_path = self.get_template_conf_path()
        if template_conf_path is None:
            # Raises an Error when we don't find the local.conf.sample in template conf dir
            raise FileNotFoundError(f"Can't find local.conf.sample file in any of the following folders: {' '.join(self.distro.TEMPLATE_CONF)}")
        else:
            full_path = os.path.join(
                self.generate_distro_base_dir_path(),
                template_conf_path,
                "local.conf.sample"
            )
            return full_path
        return

    def read_local_conf_version(self):
        self.local_conf_version = str(self.distro.DEFAULT_CONF_VERSION)
        try:
            file = open(self.get_template_conf_full_path())
            for line in file:
                if line.lstrip().startswith("CONF_VERSION"):
                    self.local_conf_version = re.search(r'\d+', line).group(0)
                    return
        except:
            return

    def read_bitbake_version(self):
        self.bitbake_major_version = int(self.distro.DEFAULT_BITBAKE_MAJOR_VERSION)
        try:
            file = open(self.config.layer_dir() + self.distro.BASE_DIRECTORY + "/" + self.distro.BITBAKE_INIT_FILE)
            for line in file:
                if '__version__' in line:
                    self.bitbake_major_version = int(line.split('=')[1].strip(' "').split('.')[0])
                    return
        except:
            return

    def prepare_build_directory(self, build):
        debug('Preparing directory:', build.dir())

        CookerCall.os.create_directory(build.dir())

        conf_path = os.path.join(build.dir(), 'conf')
        CookerCall.os.create_directory(conf_path)
        dl_dir = '${TOPDIR}/' + os.path.relpath(self.config.dl_dir(), build.dir())

        sstate_dir = '${TOPDIR}/' + os.path.relpath(self.config.sstate_dir(), build.dir())
        layer_dir = os.path.join('${TOPDIR}', os.path.relpath(self.config.layer_dir(), build.dir()))

        self.read_bitbake_version()
        halt_verb = "HALT"
        if self.bitbake_major_version < 2:
            halt_verb = "ABORT"

        file = CookerCall.os.file_open(os.path.join(conf_path, 'local.conf'))

        CookerCall.os.file_write(file, '# DO NOT EDIT! - This file is automatically created by cooker.\n\n')
        CookerCall.os.file_write(file, 'COOKER_LAYER_DIR = "{}"'.format(layer_dir))
        CookerCall.os.file_write(file, 'DL_DIR = "{}"'.format(dl_dir))
        CookerCall.os.file_write(file, 'SSTATE_DIR = "{}"'.format(sstate_dir))
        CookerCall.os.file_write(file, 'COOKER_BUILD_NAME = "{}"'.format(build.name()))
        for line in build.local_conf():
            CookerCall.os.file_write(file, line)
        CookerCall.os.file_write(file, 'DISTRO ?= "{}"'.format(self.distro.DISTRO_NAME))
        CookerCall.os.file_write(file, 'PACKAGE_CLASSES ?= "{}"'.format(self.distro.PACKAGE_FORMAT))
        CookerCall.os.file_write(file, 'BB_DISKMON_DIRS ??= "\\')
        CookerCall.os.file_write(file, '\tSTOPTASKS,${TMPDIR},1G,100K \\')
        CookerCall.os.file_write(file, '\tSTOPTASKS,${DL_DIR},1G,100K \\')
        CookerCall.os.file_write(file, '\tSTOPTASKS,${SSTATE_DIR},1G,100K \\')
        CookerCall.os.file_write(file, '\tSTOPTASKS,/tmp,100M,100K \\')
        CookerCall.os.file_write(file, '\t{},${{TMPDIR}},100M,1K \\'.format(halt_verb))
        CookerCall.os.file_write(file, '\t{},${{DL_DIR}},100M,1K \\'.format(halt_verb))
        CookerCall.os.file_write(file, '\t{},${{SSTATE_DIR}},100M,1K \\'.format(halt_verb))
        CookerCall.os.file_write(file, '\t{},/tmp,10M,1K"'.format(halt_verb))
        CookerCall.os.file_write(file, 'CONF_VERSION ?= "{}"'.format(self.local_conf_version))
        CookerCall.os.file_close(file)

        file = CookerCall.os.file_open(os.path.join(conf_path, 'bblayers.conf'))
        CookerCall.os.file_write(file, '# DO NOT EDIT! - This file is automatically created by cooker.\n\n')
        CookerCall.os.file_write(file, '{} = "{}"'.format(self.distro.LAYER_CONF_NAME, self.distro.LAYER_CONF_VERSION))
        CookerCall.os.file_write(file, 'BBPATH = "${TOPDIR}"')
        CookerCall.os.file_write(file, 'BBFILES ?= ""')
        CookerCall.os.file_write(file, 'BBLAYERS ?= " \\')
        for layer in sorted(build.layers()):
            layer_path = os.path.relpath(self.config.layer_dir(layer), build.dir())
            CookerCall.os.file_write(file, '\t${{TOPDIR}}/{} \\'.format(layer_path))
        CookerCall.os.file_write(file, '"\n')
        CookerCall.os.file_close(file)

        file = CookerCall.os.file_open(os.path.join(conf_path, 'templateconf.cfg'))
        CookerCall.os.file_write(file, '{}\n'.format(self.get_template_conf_path()))
        CookerCall.os.file_close(file)

    def show(self, builds, layers, conf, tree, build_arg, sources):

        # show source dirs
        if sources:
            for source in self.menu['sources']:
                l, r = self.local_dir_from_source(source)
                info('source URL:', r)
                info('  locally: ', l)

        # check if selected builds exist
        for build in builds:
            if build not in BuildConfiguration.ALL:
                fatal_error('cannot show infos about build "{}" as it does not exists.'.format(build))

        # empty given builds - use all existing ones
        if not builds:
            builds = BuildConfiguration.ALL.keys()

        # print information per build
        for build_name in sorted(builds):
            build = BuildConfiguration.ALL[build_name]

            if build.targets():
                build_info = ' (bakes {})'.format(', '.join(build.targets()))
            else:
                build_info = ''

            info('build: {}{}'.format(build.name(), build_info))

            if layers:
                info(' used layers')
                for layer in build.layers():
                    info('  - {} ({})'.format(layer, self.config.layer_dir(layer)))

            if conf:
                info(' local.conf entries')
                for entry in build.local_conf():
                    info('  - {}'.format(entry))

            if build_arg:
                if build.targets():
                    info('  .',
                         os.path.relpath(self.config.layer_dir(self.distro.BASE_DIRECTORY + "/" + self.distro.BUILD_SCRIPT), os.getcwd()),
                         os.path.relpath(build.dir(), os.getcwd()))
                else:
                    info('build', build.name(), 'has no target')

            if tree:
                if build.ancestors_:
                    info('builds ancestors:', [n.name() for n in build.ancestors_])

    def build(self, builds, sdk, keepgoing, download):
        debug('Building build-configurations')

        for build in self.get_buildable_builds(builds):
            self.build_targets(build, sdk, keepgoing, download)

    def build_targets(self, build, sdk, keepgoing, download):
        for target in build.targets():
            try:
                info('Building {} ({})'.format(build.name(), target))
                bb_task = ""

                if keepgoing:
                    bb_task = "-k"

                if download:
                    bb_task += " --runall=fetch"

                self.run_bitbake(build, bb_task, target)
                if sdk:
                    self.run_bitbake(build, "-c populate_sdk", target)

            except Exception as e:
                fatal_error('build for', build.name(), 'failed', e)

    def clean(self, recipe, builds):
        debug('cleaning {}'.format(recipe))

        for build in self.get_buildable_builds(builds):
            self.clean_build_config(recipe, build)

    def clean_build_config(self, recipe, build):
        try:
            info('Clean {} for {}'.format(recipe, build.name()))
            self.run_bitbake(build, "-c cleansstate", recipe)
        except Exception as e:
            fatal_error('clean for', build.name(), 'failed', e)

    def get_buildable_builds(self, builds: List[str]):
        """ gets buildable build-objects from a build-name-list or all of them if list is empty. """

        if builds:
            buildables = []
            for build in builds:
                if build not in BuildConfiguration.ALL:
                    fatal_error('undefined build:', build)

                if not BuildConfiguration.ALL[build].targets():
                    fatal_error('build', build, 'is not buildable')

                buildables += [BuildConfiguration.ALL[build]]
            return buildables
        else:  # use all builds which have targets
            return [x for x in BuildConfiguration.ALL.values() if x.buildable()]

    def run_bitbake(self, build_config, bb_task, bb_target):
        directory = build_config.dir()

        init_script = self.config.layer_dir(self.distro.BASE_DIRECTORY + "/" + self.distro.BUILD_SCRIPT)
        if not CookerCall.os.file_exists(init_script):
            fatal_error('init-script', init_script, 'not found')

        command_line = 'source {} {} && bitbake {} {}'.format(init_script, directory, bb_task, bb_target)

        complete = CookerCall.os.subprocess_run(["env", "bash", "-c", command_line], None, capture_output=False)
        if complete.returncode != 0:
            fatal_error('Execution of {} failed.'.format(command_line))

    def shell(self, build_names: List[str], cmd: List[str]):
        build_dir = self.get_buildable_builds(build_names)[0].dir()
        init_script = self.config.layer_dir(self.distro.BASE_DIRECTORY + "/" + self.distro.BUILD_SCRIPT)
        shell = os.environ.get('SHELL', '/bin/bash')

        if len(cmd) >= 1:
            str_cmd = shlex.join(cmd)
            debug('running "{}" in poky-initialized shell {} {} {}'.format(str_cmd, build_dir, init_script, shell))
            full_command_line = 'source {} {} > /dev/null || exit 1; {}'.format(init_script, build_dir, str_cmd)
            if not CookerCall.os.subprocess_run([shell, "-c", full_command_line], None, capture_output=False):
                fatal_error('Execution of {} failed.'.format(full_command_line))
        else:
            debug('running interactive, poky-initialized shell {} {} {}'.format(build_dir, init_script, shell))

            if not CookerCall.os.replace_process(shell, [shell, '-c', ". {} {}; {}".format(init_script, build_dir, shell)]):
                fatal_error('could not run interactive shell for {} with {}'.format(build_names[0], shell))

    def update_override_distro(self):
        """ update distro values from menu file if exists """
        override_distro = self.menu.get("override_distro", {})
        if override_distro:
            self.distro.BASE_DIRECTORY = override_distro.get("base_directory", self.distro.BASE_DIRECTORY)
            self.distro.BUILD_SCRIPT = override_distro.get("build_script", self.distro.BUILD_SCRIPT)
            # Template conf must be a tuple
            self.distro.TEMPLATE_CONF = (override_distro.get("template_conf", self.distro.TEMPLATE_CONF),)


class CookerCall:
    """
    CookerCall represents a call of the cooker-tool, handles all arguments, opens the config-file,
    loads the menu, checks the menu and calls the appropriate low-level commands
    """

    DEBUG = False
    WARNING = True
    VERBOSE = False

    os = OsCalls()

    def __init__(self):
        parser = argparse.ArgumentParser(prog='cooker')

        parser.add_argument('--debug', action='store_true', help='activate debug printing')
        parser.add_argument('--version', action='store_true', help='cooker version')
        parser.add_argument('-v', '--verbose', action='store_true',
                            help='activate verbose printing (of called subcommands)')
        parser.add_argument('-n', '--dry-run', action='store_true',
                            help='print what would have been done (without doing anything)')

        # parsing subcommand's arguments
        subparsers = parser.add_subparsers(help='subcommands of Cooker', dest='sub-command')

        # `cook` command (`init` + `update` + `generate`)
        cook_parser = subparsers.add_parser('cook', help='prepare the directories and cook the menu')
        cook_parser.add_argument('-d', '--download', action='store_true', help='download all sources needed for offline-build')
        cook_parser.add_argument('-k', '--keepgoing', action='store_true', help='Continue as much as possible after an error')
        cook_parser.add_argument('-s', '--sdk', action='store_true', help='build also the SDK')
        cook_parser.add_argument('menu', help='filename of the JSON menu', type=argparse.FileType('r'), nargs=1)
        cook_parser.add_argument('builds', help='build-configuration to build', nargs='*')
        cook_parser.set_defaults(func=self.cook)

        # `init` command
        init_parser = subparsers.add_parser('init', help='initialize the project-dir')
        init_parser.add_argument('-f', '--force', help='re-init an existing project',
                                 default=False, action='store_true')
        init_parser.add_argument('-l', '--layer-dir', help='path where layers will saved/cloned')
        init_parser.add_argument('-b', '--build-dir', help='path where the build-directories will be placed')
        init_parser.add_argument('-d', '--dl-dir', help='path where yocto-fetched-repositories will be saved')
        init_parser.add_argument('-s', '--sstate-dir', help='path where shared state cached will be saved')
        init_parser.add_argument('menu', help='filename of the JSON menu', type=argparse.FileType('r'), nargs=1)
        init_parser.set_defaults(func=self.init)

        # `update` command
        update_parser = subparsers.add_parser('update', help='update source layers')
        update_parser.set_defaults(func=self.update)

        # `diff` command
        diff_parser = subparsers.add_parser('diff', help='show current revision differences of all sources')
        diff_parser.set_defaults(func=self.diff)

        # `log` command
        log_parser = subparsers.add_parser('log', help='prints the changes of the build sources between two menu versions')
        log_parser.add_argument('build', help='build for the log', nargs=1)
        log_parser.add_argument('menu_from', help='previous menu file version', nargs=1, default=None)
        log_parser.add_argument('menu_to', help='menu file to compare (default: current menu file)', nargs='?', default=None)
        log_parser.add_argument('-H', '--history', help='list of layers to be detailed with the commit history', nargs='*')
        log_parser.add_argument('-o', '--format', help='ouput log format: text, markdown, md (default: text)')
        log_parser.set_defaults(func=self.log)

        # `generate` command
        generate_parser = subparsers.add_parser('generate', help='generate build-configuration')
        generate_parser.set_defaults(func=self.generate)

        # `show` command
        show = subparsers.add_parser('show', help='show builds and targets information')
        show.add_argument('-a', '--all', help='show all information about the build-configurations',
                          action='store_true', default=False)
        show.add_argument('-b', '--build',
                          help='show poky-command-line to enter the build-dir and initialize the environment',
                          action='store_true', default=False)
        show.add_argument('-c', '--conf', help='list local.conf-entries per build-configuration', action='store_true',
                          default=False)
        show.add_argument('-l', '--layers', help='list layers per build-configuration', action='store_true',
                          default=False)
        show.add_argument('-t', '--tree', help='list all build-configurations as a parent-child-tree',
                          action='store_true', default=False)
        show.add_argument('-s', '--sources', help='list all sources local and remote directories',
                          action='store_true', default=False)
        show.add_argument('builds', help='show information of the given builds', nargs='*')
        show.set_defaults(func=self.show)

        # `build` command
        build_parser = subparsers.add_parser('build', help='build one or more configurations')
        build_parser.add_argument('-d', '--download', action='store_true', help='download all sources needed for offline-build')
        build_parser.add_argument('-k', '--keepgoing', action='store_true', help='Continue as much as possible after an error')
        build_parser.add_argument('-s', '--sdk', action='store_true', help='build also the SDK')
        build_parser.add_argument('builds', help='build-configuration to build', nargs='*')
        build_parser.set_defaults(func=self.build)

        # `shell` command
        shell_parser = subparsers.add_parser('shell', help='run an interactive shell ($SHELL) for the given build')
        shell_parser.add_argument('build', help='build-configuration to use', nargs=1)
        shell_parser.add_argument('cmd', help='execute a command in a poky-initialized shell.' +
            ' Commands with arguments starting with "-" needs to be after "--".' +
            ' Example: cooker shell <cooker-build> -- bitbake -c cve_check <package-name>', nargs='*')
        shell_parser.set_defaults(func=self.shell)

        # `clean` command
        clean_parser = subparsers.add_parser('clean', help='clean a previously build recipe')
        clean_parser.add_argument('recipe', help='bitbake recipe to clean', nargs=1)
        clean_parser.add_argument('builds', help='build-configurations concerned', nargs='*')
        clean_parser.set_defaults(func=self.clean)

        self.clargs = parser.parse_args()

        CookerCall.DEBUG = self.clargs.debug
        CookerCall.VERBOSE = self.clargs.verbose

        if self.clargs.version:
            info(__version__)
            sys.exit(0)

        if self.clargs.dry_run:
            CookerCall.os = DryRunOsCalls()

        # find and initialize config
        self.config = Config()

        debug('Project root', self.config.project_root())

        if self.config.empty():
            debug('empty config')
        else:
            debug('config present')

        # figure out which menu-file to use
        menu_file = None
        if 'menu' in self.clargs and self.clargs.menu is not None:  # menu-file from the cmdline has priority
            menu_file = self.clargs.menu[0]
        elif not self.config.empty():  # or the one from the config-file
            try:
                menu_file = open(self.config.menu())
            except Exception as e:
                fatal_error('menu load error', e)

        self.menu = None
        if menu_file:
            try:
                self.menu = pyjson5.load(menu_file)
            except Exception as e:
                fatal_error('menu load error:', e)

            schema = pyjson5.loads(pkg_resources.resource_string(__name__, "cooker-menu-schema.json").decode('utf-8'))
            try:
                jsonschema.validate(self.menu, schema)
            except Exception as e:
                fatal_error('menu file validation failed:', e)

            debug('menu file validation passed')

            # create build-configurations and resolve parents

            # the main config is root containing the menu's layers and
            # local.conf-fields

            BuildConfiguration('root',
                               self.config,
                               self.menu.setdefault('layers', []),
                               self.menu.setdefault('local.conf', []),
                               None,
                               None)

            for name, build in self.menu['builds'].items():
                BuildConfiguration(name,
                                   self.config,
                                   build.setdefault('layers', []),
                                   build.setdefault('local.conf', []),
                                   build.setdefault('target', None),
                                   build.setdefault('inherit', ['root']))

            resolve_parents()

        self.commands = CookerCommands(self.config, self.menu)

        if 'func' in self.clargs:
            self.clargs.func()  # call function of selected command
        else:
            parser.print_usage(file=sys.stderr)
            sys.exit(1)

        sys.exit(0)

    def init(self):
        """ function use by command-line-arg-parser as entry point for the 'init' """
        if not self.clargs.force and not self.config.empty():
            fatal_error('Project in', self.config.project_root(), 'has already been initalized')

        self.commands.init(self.clargs.menu[0].name,
                           self.clargs.layer_dir,
                           self.clargs.build_dir,
                           self.clargs.dl_dir,
                           self.clargs.sstate_dir)

    def update(self):
        """ entry point for 'update' """
        if self.menu is None:
            fatal_error('update needs a menu')

        self.commands.update()

    def diff(self):
        if self.menu is None:
            fatal_error('diff needs a menu')

        self.commands.diff()

    def log(self):
        self.commands.log(self.clargs.build[0], self.clargs.menu_from[0], self.clargs.menu_to, self.clargs.history, self.clargs.format)

    def cook(self):
        self.commands.init(self.clargs.menu[0].name)
        self.commands.update()
        self.commands.generate()
        self.commands.build(self.clargs.builds, self.clargs.sdk, self.clargs.keepgoing, self.clargs.download)

    def generate(self):
        if self.menu is None:
            fatal_error('generate needs a menu')

        self.commands.generate()

    def show(self):
        if self.menu is None:
            fatal_error('show command needs a menu')

        self.commands.show(self.clargs.builds,
                           self.clargs.layers or self.clargs.all,
                           self.clargs.conf or self.clargs.all,
                           self.clargs.tree or self.clargs.all,
                           self.clargs.build or self.clargs.all,
                           self.clargs.sources or self.clargs.all)

    def build(self):
        if self.menu is None:
            fatal_error('build needs a menu')

        self.commands.build(self.clargs.builds, self.clargs.sdk, self.clargs.keepgoing, self.clargs.download)

    def shell(self):
        if self.menu is None:
            fatal_error('shell needs a menu')

        self.commands.shell(self.clargs.build, self.clargs.cmd)

    def clean(self):
        if self.menu is None:
            fatal_error('clean needs a menu')

        self.commands.clean(self.clargs.recipe[0], self.clargs.builds)


def main():
    CookerCall()
