# -*- coding: utf-8 -*-


def hipchat_command(command_string):
    def wrapper(func):
        def wrapped_function(*args, **kwargs):
            func(*args, **kwargs)
        wrapped_function.hipchat_plugin_meta = {
            'command': command_string,
        }
        return wrapped_function
    return wrapper
