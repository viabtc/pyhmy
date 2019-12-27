import subprocess
import pexpect
import os
import shutil
import re

from .util import get_bls_build_variables, get_gopath

_addresses = {}  # Internal address keystore, not guaranteed to be up-to-date unless needed.
_binary_path = "hmy"  # Internal binary path.
_environment = os.environ.copy()  # Internal environment dict for Subprocess & Pexpect.


def _get_default_hmy_binary_path(file_name="hmy"):
    """
    Internal function to get the binary path by looking for the first file with
    the same name as the param in the current working directory.

    :param file_name: The file name to look for.
    """
    assert '/' not in file_name, "file name must not be a path."
    for root, dirs, files in os.walk(os.getcwd()):
        if file_name in files:
            return os.path.join(root, file_name)
    return ""


def _sync_addresses():
    """
    Internal function to sync address with the binary's keystore addresses.
    """
    global _addresses
    curr_addresses = {}
    response = single_call("hmy keys list")
    lines = response.split("\n")
    if "NAME" not in lines[0] or "ADDRESS" not in lines[0]:
        raise ValueError("Name or Address not found on first line of key list")
    if lines[1] != "":
        raise ValueError("Unknown format: No blank line between label and data")
    for line in lines[2:]:
        columns = line.split("\t")
        if len(columns) != 2:
            break  # Done iterating through all of the addresses.
        name, address = columns
        curr_addresses[name.strip()] = address
    _addresses = curr_addresses


def set_binary_path(path):
    """
    :param path: The path of the CLI binary to use.
    """
    global _binary_path
    assert os.path.isfile(path), f"`{path}` is not a file"
    _binary_path = path
    _sync_addresses()


def get_version():
    """
    :return: The version string of the CLI binary.
    """
    proc = subprocess.Popen([_binary_path, "version"], env=_environment,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if not err:
        raise RuntimeError(f"Could not get version.\n"
                           f"\tGot exit code {proc.returncode}. Expected non-empty error message.")
    return err.decode().strip()


def get_account_keystore_path():
    """
    :return: The account keystore path of the CLI binary.
    """
    response = single_call("hmy keys location").strip()
    if not os.path.exists(response):
        os.mkdir(response)
    return response


def check_address(address):
    """
    :param address: A 'one1...' address.
    :return: Boolean of if the address is in the CLI's keystore.
    """
    if address in _addresses.values():
        return True
    else:
        _sync_addresses()
        return address in _addresses.values()


def get_address(name):
    """
    :param name: The alias of a key used in the CLI's keystore.
    :return: The associated 'one1...' address.
    """
    if name in _addresses:
        return _addresses[name]
    else:
        _sync_addresses()
        return _addresses.get(name, None)


def get_accounts(address):
    """
    :param address: The 'one1...' address
    :return: A list of account names associated with the param
    """
    _sync_addresses()
    return [acc for acc, addr in _addresses.items() if address == addr]


def remove_account(name):
    """
    Note that this edits the keystore directly since there is currently no
    way to remove an address using the CLI.

    :param name: The alias of a key used in the CLI's keystore.
    :raises RuntimeError: If it failed to remove an account.
    """
    if not get_address(name):
        return
    keystore_path = f"{get_account_keystore_path()}/{name}"
    try:
        shutil.rmtree(keystore_path)
    except (shutil.Error, FileNotFoundError) as err:
        raise RuntimeError(f"Failed to delete dir: {keystore_path}\n"
                           f"\tException: {err}") from err
    del _addresses[name]


def remove_address(address):
    """
    :param address: The 'one1...' address to be removed.
    """
    for name in get_accounts(address):
        remove_account(name)


def single_call(command, timeout=60):
    """
    :param command: String of command to execute on CLI
    :param timeout: Optional timeout in seconds
    :returns: Decoded string of response from hmy CLI call
    :raises: RuntimeError if bad command
    """
    command_toks = command.split(" ")
    if re.match(".*hmy", command_toks[0]):
        command_toks = command_toks[1:]
    command_toks = [_binary_path] + command_toks
    try:
        response = subprocess.check_output(command_toks, env=_environment, timeout=timeout).decode()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        raise RuntimeError(f"Bad arguments for CLI.\n "
                           f"\tException: {err}") from err
    return response


def expect_call(command, timeout=60):
    """
    :param command: String fo command to execute on CLI
    :param timeout: Optional timeout in seconds
    :return: A pexpect child program
    :raises: RuntimeError if bad command
    """
    command_toks = command.split(" ")
    if re.match(".*hmy", command_toks[0]):
        command_toks = command_toks[1:]
    try:
        proc = pexpect.spawn(f"{_binary_path}", command_toks, env=_environment, timeout=timeout)
    except (pexpect.ExceptionPexpect, pexpect.TIMEOUT) as err:
        raise RuntimeError(f"Bad arguments for CLI.\n "
                           f"\tException: {err}") from err
    return proc


_binary_path = _get_default_hmy_binary_path()
if os.path.exists(f"{get_gopath()}/src/github.com/harmony-one/bls") \
        and os.path.exists(f"{get_gopath()}/src/github.com/harmony-one/mcl"):  # Check prevents needless import fail.
    _environment.update(get_bls_build_variables())  # Needed if using dynamically linked CLI binary.
