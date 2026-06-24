import os
import subprocess
import sys
from abc import ABC, abstractmethod


class OsCallsBase(ABC):
    @staticmethod
    @abstractmethod
    def create_directory(directory):
        pass

    @staticmethod
    @abstractmethod
    def file_open(filename):
        pass

    @staticmethod
    @abstractmethod
    def file_write(file, string):
        pass

    @staticmethod
    @abstractmethod
    def file_close(file):
        pass

    @staticmethod
    @abstractmethod
    def file_exists(filename):
        pass

    @staticmethod
    @abstractmethod
    def directory_exists(dirname):
        pass

    @staticmethod
    @abstractmethod
    def replace_process(shell: str, args: list[str]):
        pass

    @staticmethod
    @abstractmethod
    def subprocess_run(args, cwd, capture_output=True):
        pass


class OsCalls(OsCallsBase):
    @staticmethod
    def create_directory(directory):
        os.makedirs(directory, exist_ok=True)

    @staticmethod
    def file_open(filename):
        return open(filename, "w", encoding="utf-8")

    @staticmethod
    def file_write(file, string):
        file.write(f"{string}\n")

    @staticmethod
    def file_close(file):
        file.close()

    @staticmethod
    def file_exists(filename):
        return os.path.isfile(filename)

    @staticmethod
    def directory_exists(dirname):
        return os.path.isdir(dirname)

    @staticmethod
    def replace_process(shell: str, args: list[str]):
        return os.execv(shell, args)

    @staticmethod
    def subprocess_run(args, cwd, capture_output=True):
        return subprocess.run(args, capture_output=capture_output, cwd=cwd, check=False)


class DryRunOsCalls(OsCallsBase):
    @staticmethod
    def create_directory(directory):
        print(f"mkdir {directory}")
        sys.stdout.flush()

    @staticmethod
    def file_open(filename):
        print(f"cat > {filename} <<-EOF")
        sys.stdout.flush()
        return 0

    @staticmethod
    def file_write(file, string):
        escaped = string.replace("$", "\$")
        print(f"\t{escaped}")
        sys.stdout.flush()

    @staticmethod
    def file_close(file):
        print("EOF")
        sys.stdout.flush()

    @staticmethod
    def file_exists(filename):
        return True

    @staticmethod
    def directory_exists(dirname):
        return True

    @staticmethod
    def replace_process(shell: str, args: list[str]):
        print("exec {} {}".format(shell, " ".join(args)))
        return True

    @staticmethod
    def subprocess_run(args, cwd, capture_output=True):
        if cwd is not None:
            print("cd " + cwd)
        print(" ".join(args))
        sys.stdout.flush()
        return subprocess.CompletedProcess(args, 0, stderr="")
