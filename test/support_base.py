from mock import Mock


def mock_cache():
    mock_cache = Mock()
    setattr(mock_cache, '__enter__', Mock())
    setattr(mock_cache, '__exit__', Mock())
    return mock_cache


class Compare(object):
    """
    Value that compares equal for anything as long as it's always the same.

    The first time you compare it, it always returns True. But it remembers
    what you compared it to that first time. Every subsequent time you compare
    it, it performs a standard comparison between that first value and the new
    comparison. So...

    i = Compare()
    i == 2  # True
    i == 6  # False
    i == 2  # True
    """
    def __init__(self):
        self._compared = False
        self._compare_value = None

    def __eq__(self, other):
        if self._compared:
            return self._compare_value == other
        else:
            self._compared = True
            self._compare_value = other
            return True
