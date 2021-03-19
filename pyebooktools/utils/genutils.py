"""General utilities
"""
import codecs
import json
import logging.config
import os
import shlex
import shutil
import subprocess
import sys
from argparse import Namespace
from collections import OrderedDict
from logging import NullHandler
from runpy import run_path
from types import SimpleNamespace

import pyebooktools
from pyebooktools.configs import default_config as default_cfg
from pyebooktools.utils.logutils import (init_log, set_logging_field_width,
                                         set_logging_formatter, set_logging_level)

logger = init_log(__name__, __file__)
logger.addHandler(NullHandler())

CFG_TYPES = ['main', 'log']
CONFIGS_DIRNAME = 'configs'


def get_config_dict(cfg_type='main'):
    if cfg_type == 'main':
        cfg_filepath = get_main_config_filepath()
    elif cfg_type == 'log':
        cfg_filepath = get_logging_filepath()
    else:
        raise ValueError(f"Invalid cfg_type: {cfg_type}")
    return load_cfg_dict(cfg_filepath, cfg_type)


def get_settings(conf, cfg_type):
    if cfg_type == 'log':
        set_logging_field_width(conf['logging'])
        return conf['logging']
    elif cfg_type == 'main':
        _settings = {}
        for opt_name, opt_value in conf.items():
            if opt_name.startswith('__') and opt_name.endswith('__'):
                continue
            elif isinstance(opt_value, type(os)):
                # e.g. import config
                continue
            else:
                _settings.setdefault(opt_name, opt_value)
        return _settings
    else:
        raise ValueError(f"Invalid cfg_type: {cfg_type}")


def load_cfg_dict(cfg_filepath, cfg_type):

    def _load_cfg_dict(cfg_filepath, cfg_type):
        if file_ext == '.py':
            cfg_dict = run_path(cfg_filepath)
            cfg_dict = get_settings(cfg_dict, cfg_type)
        elif file_ext == '.json':
            cfg_dict = load_json(cfg_filepath)
        else:
            raise TypeError("Config file extension not supported: "
                            f"{cfg_filepath}")
        return cfg_dict

    assert cfg_type in CFG_TYPES, f"Invalid cfg_type: {cfg_type}"
    _, file_ext = os.path.splitext(cfg_filepath)
    try:
        cfg_dict = _load_cfg_dict(cfg_filepath, cfg_type)
    except FileNotFoundError as e:
        print(f"WARNING: Config file '{os.path.basename(cfg_filepath)}' will "
              "be created")
        # Copy it from the default one
        # TODO: IMPORTANT destination with default?
        if cfg_type == 'main':
            src = get_main_config_filepath(default_config=True)
        else:
            src = get_logging_filepath(default_config=True)
        shutil.copy(src, cfg_filepath)
        cfg_dict = _load_cfg_dict(cfg_filepath, cfg_type)
    return cfg_dict


def load_json(filepath, encoding='utf8'):
    """Load JSON data from a file on disk.

    If using Python version betwee 3.0 and 3.6 (inclusive), the data is
    returned as :obj:`collections.OrderedDict`. Otherwise, the data is
    returned as :obj:`dict`.

    Parameters
    ----------
    filepath : str
        Path to the JSON file which will be read.
    encoding : str, optional
        Encoding to be used for opening the JSON file in read mode (the default
        value is '*utf8*').

    Returns
    -------
    data : dict or collections.OrderedDict
        Data loaded from the JSON file.

    Raises
    ------
    OSError
        Raised if any I/O related error occurs while reading the file, e.g. the
        file doesn't exist.

    References
    ----------
    `Are dictionaries ordered in Python 3.6+? (stackoverflow)`_

    """
    try:
        with codecs.open(filepath, 'r', encoding) as f:
            if sys.version_info.major == 3 and sys.version_info.minor <= 6:
                data = json.load(f, object_pairs_hook=OrderedDict)
            else:
                data = json.load(f)
    except OSError:
        raise
    else:
        return data


def mkdir(path):
    # Since path can be relative to the cwd
    path = os.path.abspath(path)
    dirname = os.path.basename(path)
    if os.path.exists(path):
        logger.debug(f"Folder already exits: {path}")
        logger.debug(f"Skipping it!")
    else:
        logger.debug(f"Creating folder '{dirname}': {path}")
        os.mkdir(path)
        logger.debug("Folder created!")


def move(src, dest):
    # Since path can be relative to the cwd
    src = os.path.abspath(src)
    filename = os.path.basename(src)
    if os.path.exists(dest):
        logger.debug(f"File already exits: '{filename}'")
        logger.debug(f"Folder path: {os.path.dirname(dest)}")
        logger.debug(f"Skipping it!")
    else:
        logger.debug(f"Moving '{filename}'")
        logger.debug(f"Folder path: {os.path.dirname(dest)}")
        shutil.move(src, dest)
        logger.debug("File moved!")


def namespace_to_dict(ns):
    namspace_classes = [Namespace, SimpleNamespace]
    # TODO: check why not working anymore
    # if isinstance(ns, SimpleNamespace):
    if type(ns) in namspace_classes:
        adict = vars(ns)
    else:
        adict = ns
    for k, v in adict.items():
        # if isinstance(v, SimpleNamespace):
        if type(v) in namspace_classes:
            v = vars(v)
            adict[k] = v
        if isinstance(v, dict):
            namespace_to_dict(v)
    return adict


def override_config_with_args(config, parser):
    ignored_args = ['func', 'subparser_name']
    # If config is Namespace
    config = vars(config)
    args = parser.parse_args().__dict__
    args_not_found_in_config = []
    default_args_overriden = []
    config_opts_overridden = []
    for arg_name, arg_val in args.items():
        if arg_name in ignored_args:
            continue
        config_val = config.get(arg_name)
        # No value was specified, use default value
        default_val = getattr(default_cfg, arg_name, None)
        if arg_val is not None:
            # User specified a value in the command-line
            if arg_val != config_val:
                config[arg_name] = arg_val
                config_opts_overridden.append((arg_name, config_val, arg_val))
            # else: command-line arg and config option same value, nothing to do
        elif config_val is not None:
            # User provided a value from the config file
            if config_val != default_val:
                default_args_overriden.append((arg_name, default_val, config_val))
        else:
            if default_val:
                config[arg_name] = default_val
            else:
                raise AttributeError("No value could be found for the "
                                     f"argument {arg_name}")

    # ================================
    # Process previous returned values
    # ================================

    def log_opts_overriden(opts_overriden, msg, log_level='info'):
        nb_items = len(opts_overriden)
        for i, (cfg_name, old_v, new_v) in enumerate(opts_overriden):
            msg += "\t {}: {} --> {}".format(cfg_name, old_v, new_v)
            if i + 1 < nb_items:
                msg += "\n"
        getattr(logger, log_level)(msg)

    # Process 1st returned values: default args overriden by config options
    if default_args_overriden:
        msg = "Default arguments overridden by config options:\n"
        log_opts_overriden(default_args_overriden, msg)
    # Process 2nd returned values: config options overriden by args
    if config_opts_overridden:
        msg = "Config options overridden by command-line arguments:\n"
        log_opts_overriden(config_opts_overridden, msg, 'debug')
    # Process 3rd returned values: arguments not found in config file
    """
    if args_not_found_in_config:
        msg = "Command-line arguments not found in config file: " \
              "\n\t{}".format(args_not_found_in_config)
        logger.debug(msg)
    """


def run_cmd(cmd):
    """Run a shell command with arguments.

    The shell command is given as a string but the function will split it in
    order to get a list having the name of the command and its arguments as
    items.

    Parameters
    ----------
    cmd : str
        Command to be executed, e.g. ::

            open -a TextEdit text.txt

    Returns
    -------
    retcode: int
        Returns code which is 0 if the command was successfully completed.
        Otherwise, the return code is non-zero.

    Raises
    ------
    FileNotFoundError
        Raised if the command ``cmd`` is not recognized, e.g.
        ``$ TextEdit {filepath}`` since `TextEdit` is not an executable.

    """
    try:
        if sys.version_info.major == 3 and sys.version_info.minor <= 6:
            # TODO: PIPE not working as arguments and capture_output new in
            # Python 3.7
            # Ref.: https://stackoverflow.com/a/53209196
            #       https://bit.ly/3lvdGlG
            result = subprocess.run(shlex.split(cmd))
        else:
            result = subprocess.run(shlex.split(cmd), capture_output=True)
    except FileNotFoundError:
        raise
    else:
        return result


def setup_log(quiet=False, verbose=False, logging_level=None,
              logging_formatter=None):
    logging_level = logging_level.upper()
    package_path = os.getcwd()
    log_filepath = get_logging_filepath()
    main_cfg_msg = f"Main config path: {get_main_config_filepath()}"
    main_log_msg = f'Logging path: {log_filepath}'
    # Get logging cfg dict
    log_dict = load_cfg_dict(log_filepath, cfg_type='log')
    # NOTE: if quiet and verbose are both activated, only quiet will have an effect
    # TODO: get first cfg_dict to setup log (same in train_models.py)
    if not quiet:
        if verbose:
            set_logging_level(log_dict, level='DEBUG')
        if logging_level:
            # TODO: add console_for_users at the top
            set_logging_level(log_dict, level=logging_level)
        if logging_formatter:
            set_logging_formatter(log_dict, formatter=logging_formatter)
        # Load logging config dict
        logging.config.dictConfig(log_dict)
    # =============
    # Start logging
    # =============
    logger.info("Running {} v{}".format(pyebooktools.__name__,
                                        pyebooktools.__version__))
    logger.info("Verbose option {}".format(
        "enabled" if verbose else "disabled"))
    logger.debug("Working directory: {}".format(package_path))
    logger.debug(main_cfg_msg)
    logger.debug(main_log_msg)


# -------------------------------
# Configs: dirpaths and filepaths
# -------------------------------
def get_configs_dirpath():
    from pyebooktools.configs import __path__
    return __path__[0]


def get_logging_filepath(default_config=False):
    # TODO: add names of logging files as global
    if default_config:
        return os.path.join(get_configs_dirpath(), 'default_logging.py')
    else:
        return os.path.join(get_configs_dirpath(), 'logging.py')


def get_main_config_filepath(default_config=False):
    # TODO: add names of config files as global
    if default_config:
        return os.path.join(get_configs_dirpath(), 'default_config.py')
    else:
        return os.path.join(get_configs_dirpath(), 'config.py')
