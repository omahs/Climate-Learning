# '''
# Created on 2022-01-13

# @author: Alessandro Lovo
# '''
'''
Set of general purpose functions
'''

# import libraries
from curses import wrapper
import enum
from inspect import indentsize
from os import terminal_size
import numpy as np
import sys
from functools import wraps
import time
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)
logger.level = logging.INFO

######## time formatting ##########
def now():
    '''
    Returns the current time as string formatted as year-month-day hour:minute:second
    '''
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def pretty_time(t):
    '''
    Takes a time in seconds and returns it in a string with the format <hours> h <minutes> min <seconds> s

    Examples
    --------
    >>> pretty_time(124)
    '2 min 4.0 s'
    >>> pretty_time(3601.4)
    '1 h 1.4 s'
    '''
    h = t//3600
    t = t - h*3600
    m = t//60
    s = t - m*60
    pt = ''
    if h > 0:
        pt += f'{h:.0f} h '
    if m > 0:
        pt += f'{m:.0f} min '
    pt += f'{s:.1f} s'
    return pt

default_formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

###### function decorators for logging ###

## indenting ####

def indent_write(write):
    '''
    decorator for a function that writes to a stream, e.g. sys.stdout or a file. Indents the message.

    Examples
    --------
    >>> def test():
    ...     print('before')
    ...     old_write = sys.stdout.write
    ...     sys.stdout.write = indent_write(sys.stdout.write)
    ...     print('Hello!')
    ...     sys.stdout.write = old_write
    ...     print('after')

    Will give output
    before
        Hello!
    after
    '''
    @wraps(write)
    def wrapper(message):
        message = ('\t'+'\n\t'.join(message[:-1].split('\n')) + message[-1])
        return write(message)
    return wrapper

def indent(*streams):
    '''
    Returns a decorator that indents the output produced by the decorated function on the streams provided

    Examples
    --------
    >>> @indent(sys.stdout)
    ... def show(a=0):
    ...     print(f'{a = }')
    >>> def test(a=0):
    ...     print('before')
    ...     show(a)
    ...     print('after')
    
    When running `test(24)` you will get
    before
        a = 24
    after

    Indentation can be chained

    >>> @indent(sys.stdout)
    ... def test_innner(a=0):
    ...     print('before inner')
    ...     show(a)
    ...     print('after inner')
    >>> def test_outer(a=0):
    ...     print('before outer')
    ...     test_inner(a)
    ...     print('after outer')

    test_outer(24) will give
    before outer
        before inner
            a = 24
        after inner
    after outer

    You can also indent a handler `h` of the logging module by creating a decorator @indent(h.stream)
    '''
    def wrapper_outer(func):
        @wraps(func)
        def wrapper_inner(*args, **kwargs):
            # save old write and emit functions
            old_write = [stream.write if hasattr(stream, 'write') else None for stream in streams]
            # indent write and emit functions
            for i,stream in enumerate(streams):
                if old_write[i] is not None:
                    stream.write = indent_write(stream.write)
            try:
                r = func(*args, **kwargs)
            finally:
                # restore original functions
                for i,stream in enumerate(streams):
                    if old_write[i] is not None:
                        stream.write = old_write[i]
            return r
        return wrapper_inner
    return wrapper_outer

def indent_logger(logger=None):
    '''
    Indents all handlers of a given logger when the decorated function is running

    Parameters
    ----------
    logger : logging.loggers.Logger, optional
        logger, if None the root logger is used. The default is None
    '''
    if logger is None:
        logger = logging.getLogger()
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    return indent(*[h.stream for h in logger.handlers])

def indent_stdout(func):
    '''
    Indents the stdout output produced by a function
    '''
    return indent(sys.stdout)(func)

## execution time    

def execution_time(func):
    '''
    Prints the execution time of a function

    Examples
    --------
    >>> @execution_time
    ... def test(a):
    ...     time.sleep(1)
    ...     print(a)
    >>> test('Hi')
    test:
    Hi
    test: completed in 1.0 s
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.info(f'{func.__name__}:')
        r = func(*args, **kwargs)
        logger.info(f'{func.__name__}: completed in {pretty_time(time.time() - start_time)}')
        return r
    return wrapper

#### TELEGRAM LOGGER ####

def new_telegram_handler(chat_ID=None, token=None, level=logging.WARNING, formatter=default_formatter, **kwargs):
    '''
    Creates a telegram handler object

    Parameters
    ----------
    chat_ID : int or None, optional
        chat ID of the telegram user or group to whom send the logs. If None it is the last used.
        To find your chat ID go to telegram and search for 'userinfobot' and type '/start'. The bot will provide you with your chat ID.
        You can do the same with a telegram group, and, in this case, you will need to invite 'autoJASCObot' to the group.
        The default is None.
    token: str
        token for the telegram bot or path to a text file where the first line is the token
    level : int or logging.(NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL), optional
        The default is logging.WARNING.
    formatter : logging.Formatter, str or None, optional
        The formatter used to log the messages. The default is default_formatter.
        If string it can be for example '%(levelname)s: %(message)s'
    **kwargs :
        additional arguments for telegram_handler.handlers.TelegramHandler

    Returns
    -------
    th: telegram_handler.handlers.TelegramHandler
        handler that logs to telegram
    '''
    import telegram_handler # NOTE: to install this package run pip install python-telegram-handler
    try:
        with open(token, 'r') as token_file:
            token = token_file.readline().rstrip('\n')
    except FileNotFoundError:
        pass
    th = telegram_handler.handlers.TelegramHandler(token=token, chat_id=chat_ID, **kwargs)
    if isinstance(formatter, str):
        if formatter == 'default':
            formatter = default_formatter
        else:
            formatter = logging.Formatter(formatter)
    if formatter is not None:
        th.setFormatter(formatter)
    th.setLevel(level)
    return th


########## ARGUMENT PARSING ####################

def run_smart(func, default_kwargs, **kwargs): # this is not as powerful as it looks like
    '''
    Runs a function in a vectorized manner:

    Parameters
    ----------
    func : function with signature func(**kwargs) -> None
    default_kwargs : dict
        default values for the keyword arguments of func
    **kwargs : 
        non default values of the keyword arguments. If a list is provided, the function is run iterating over the list

    Examples
    --------
    >>> def add(x, y=0):
    ...     print(x + y)
    >>> run_smart(add, {'x': 0, 'y': 0}, x=1)
    1
    >>> run_smart(add, {'x': 0, 'y': 0}, x=1, y=[1,2,3]) # iterates over y
    2
    3
    4
    >>> run_smart(add, {'x': 0, 'y': 0}, x=[0, 10], y=[1,2]) # iterates over x and y
    1
    2
    11
    12
    >>> run_smart(add, {'x': [0], 'y': [0]}, x=[1,2], y=[1]) # correctly interprets lists when not supposed to iterate over them
    [1, 2, 1]
    >>> run_smart(add, {'x': [0], 'y': [0]}, x=[1,2], y=[[1], [0]]) # to iterate over list arguments, nest the lists
    [1, 2, 1]
    [1, 2, 0]
    '''
    evaluate = True
    for k,v in kwargs.items():
        if k not in default_kwargs:
            raise KeyError(f'Unknown argument {k}')
        iterate = False
        if isinstance(v, list): # possible need to iterate over the argument
            if isinstance(default_kwargs[k], list):
                if isinstance(v[0], list):
                    iterate = True
            else:
                iterate = True
        if iterate:
            evaluate = False
            for _v in v:
                kwargs[k] = _v
                run_smart(func, default_kwargs, **kwargs)
            break
    if evaluate:
        f_kwargs = default_kwargs
        for k,v in kwargs.items():
            f_kwargs[k] = v
        func(**f_kwargs)

#### JSON IO #########

def json2dict(filename):
    '''
    Reads a json file `filename` as a dictionary

    Returns
    -------
    d : dict
    '''
    with open(filename, 'r') as j:
        d = json.load(j)
    return d

def dict2json(d, filename):
    '''
    Saves a dictionary `d` to a json file `filename`
    '''
    with open(filename, 'w') as j:
        json.dump(d, j, indent=4)

#### MANAGE NESTED DICTIONARIES #####

def collapse_dict(d_nested, d_flat=None):
    '''
    Flattens a nested dictionary `d_nested` into a flat one `d_flat`.

    Parameters
    ----------
    d_nested : dict, can contain dictionaries and other types.
        If a key is present more times the associated values must be the same, otherwise an error will be raised
    d_flat : dict, optional
        flat dictionary into which to store the items of `d_nested`. If None an empty one is created.
        WARNING: If provided the variable passed as d_flat is modified inplace.
        The default is None
    
    Returns
    -------
    d_flat: dict

    Raises
    ------
    ValueError
        if a key appears more than once with different values

    Examples
    --------
    >>> collapse_dict({'a': 10, 'b': {'a': 10, 'c': 4}})
    {'a': 10, 'c': 4}
    >>> collapse_dict({'a': 10, 'b': {'a': 10, 'c': 4}}, d_flat={'a': 10, 'z': 7})
    {'a': 10, 'z': 7, 'c': 4}
    '''
    if d_flat is None:
        d_flat = {}

    for k,v in d_nested.items():
        if isinstance(v, dict):
            d_flat = collapse_dict(v,d_flat)
        else:
            if k in d_flat and v != d_flat[k]:
                raise ValueError(f'Multiple definitions for argument {k}')
            d_flat[k] = v
    return d_flat

def extract_nested(d_nested, key):
    '''
    Method to access items in a nested dictionary

    Parameters
    ----------
    d_nested : dict
        nested dictionary
    key : str
    
    Returns
    -------
    v : Any
        The value corresponding to `key` at the highest hierarchical level

    Raises
    ------
    KeyError
        if `key` is not a key of `d_nested` or the dictionaries inside it at every nested level

    Examples
    --------
    >>> d = {'a': 10, 'b': {'z': 1, 'w': {'q': 20}}}
    >>> extract_nested(d, 'a')
    10
    >>> extract_nested(d, 'b')
    {'z': 1, 'w': {'q': 20}}
    >>> extract_nested(d, 'q')
    20
    '''
    try: 
        return d_nested[key]
    except KeyError:
        for v in d_nested.values():
            if isinstance(v, dict):
                try:
                    return extract_nested(v, key)
                except KeyError:
                    continue
        raise KeyError(f'{key} is not a valid key')


def set_values_recursive(d_nested, d_flat, inplace=False):
    '''
    Given a nested dictionary `d_nested` replaces its values at any level of indentation according to the ones in `d_flat`.
    keys in `d_flat` that do not appear in `d_nested` are ignored.
    If `inplace`, `d_nested` is modified and returned, otherwise a copy is returned (i.e. the variable `d_nested` keeps its original value)

    Examples
    --------
    >>> d = {'a': 10, 'b': {'a': 10, 'c': 8}}
    >>> set_values_recursive(d, {'a': 'hello', 'z': 42}, inplace=True)
    {'a': 'hello', 'b': {'a': 'hello', 'c': 8}}
    >>> d
    {'a': 'hello', 'b': {'a': 'hello', 'c': 8}}
    >>> d = {'a': 10, 'b': {'a': 10, 'c': 8}}
    >>> set_values_recursive(d, {'a': 'hello', 'z': 42}, inplace=False)
    {'a': 'hello', 'b': {'a': 'hello', 'c': 8}}
    >>> d
    {'a': 10, 'b': {'a': 10, 'c': 8}}
    '''
    if len(d_flat) == 0:
        return d_nested
    
    if inplace:
        d_n = d_nested
    else:
        d_n = d_nested.copy()

    for k,v in d_n.items():
        if isinstance(v, dict):
            d_n[k] = set_values_recursive(v, d_flat, inplace=inplace)
        elif k in d_flat:
            d_n[k] = d_flat[k]
    return d_n

#### PERMUTATIONS ####

def invert_permutation(permutation):
    '''
    Inverts a permutation.

    Parameters
    ----------
    permutation : 1D array-like
        permutation of an array of the kind `np.arange(n)` with `n` integer

    Returns
    -------
    np.ndarray
        inverted permutation

    Examples
    --------
    >>> a = np.array([3,4,2,5])
    >>> p = np.random.permutation(np.arange(4))
    >>> a_permuted = a[p]
    >>> p_inverse = invert_permutation(p)
    >>> all(a == a_permuted[p_inverse])
    True
    '''
    return np.argsort(permutation)

def compose_permutations(permutations):
    '''
    Composes a series of permutations

    Parameters
    ----------
    permutations : list
        list of 1D array-like that must be a permutation of an array of the kind `np.arange(n)` with `n` integer and the same for every permutation
    
    Examples
    --------
    >>> a = np.array([3,4,2,5])
    >>> p1 = np.random.permutation(np.arange(4))
    >>> p2 = np.random.permutation(np.arange(4))
    >>> p_composed = compose_permutations([p1,p2])
    >>> a_permuted1 = a[p1]
    >>> a_permuted2 = a_permuted1[p2]
    >>> a_permuted_c = a[p_composed]
    >>> all(a_permuted_c == a_permuted2)
    True
    '''
    l = len(permutations[0])
    for p in permutations[1:]:
        if len(p) != l:
            raise ValueError('All permutations must have the same length')
    ps = permutations[::-1]
    p = ps[0]
    for _p in ps[1:]:
        p = _p[p]
    return p