# -*- coding: utf-8 -*-
from typing import Tuple, Optional, Dict, Callable, Any, Union

# To avoid pyflakes check and still make use of forward declaration
from sarah.bot import values
assert values


PluginConfig = Tuple[str, Optional[Dict]]

CommandFunction = Callable[
    ...,
    Union[str, 'values.RichMessage', 'values.UserContext']]

ScheduledFunction = Callable[..., Union[str, 'values.RichMessage']]

CommandConfig = Dict[str, Any]
