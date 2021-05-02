from name_that_hash import runner


class Nth:
    def __init__(self):
        pass

    def get_hashes(self, text: str) -> dict:
        to_ret = runner.api_return_hashes_as_dict(text)
        return to_ret
