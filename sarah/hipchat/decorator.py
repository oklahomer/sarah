# -*- coding: utf-8 -*-


def command(command_string):
    def wrapper(func):
        def wrapped_function(*args, **kwargs):
            func(*args, **kwargs)
        wrapped_function.hipchat_plugin_meta = {
            'command': command_string,
        }
        return wrapped_function
    return wrapper
