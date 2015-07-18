# -*- coding: utf-8 -*-
from typing import Tuple, Optional, Dict, Callable, AnyStr, Any, Iterable

PluginConfig = Tuple[str, Optional[Dict]]

CommandFunction = Callable[[Iterable[Any]], str]

CommandConfig = Dict[str, Any]

Path = AnyStr

AnyFunction = Callable[[Iterable[Any]], Any]
