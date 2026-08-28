import os
from collections import defaultdict as dd


class Base:
    pass


@staticmethod
class Service(Base):
    def run(
        self,
        value: int,
    ) -> int:
        helper(value)
        return value

    class Nested:
        async def execute(self):
            return os.getcwd()


def helper(value: int) -> int:
    def inner() -> int:
        return dd(list)

    return inner()
